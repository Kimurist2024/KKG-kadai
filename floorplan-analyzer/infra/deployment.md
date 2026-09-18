# AWS へのデプロイ

Terraform で、Next.js フロントエンドと FastAPI バックエンド向けの小規模な ECS Fargate 環境を構築します。`.github/workflows/` は、`floorplan-analyzer/` と同じ階層の**リポジトリ直下**に配置します。この構成による AWS リソースの作成やイメージの公開はまだ行っていません。

```text
ブラウザ → HTTPS ALB → frontend:3000 → localhost:8000 backend → OpenAI
                       └── 一つの Fargate タスク、二つのコンテナ ──┘
```

VPC には、異なるアベイラビリティゾーンにある二つのパブリックサブネットと、インターネットゲートウェイを配置します。タスクには、ECR、Secrets Manager、ログ、外向きの HTTPS 通信に使うパブリック IPv4 アドレスを割り当て、NAT ゲートウェイを不要にしています。タスクのセキュリティグループは、**ALB のセキュリティグループからのみ**ポート3000への受信を許可します。ポート8000は外部に公開しません。ALB は HTTP を HTTPS にリダイレクトするため、検証済みの既存 ACM 証明書が必要です。通常時のサービスは一つのタスク（0.5 vCPU / 1 GiB）で、ローリングデプロイ中は最大二つのタスクとなるため、複数タスクによる高可用性構成ではありません。ALB、Fargate、パブリック IPv4、ログ、シークレットには料金が発生します。

## 前提条件

- Terraform 1.10+、AWS CLI v2、buildx を備えた Docker が必要です。ローカル検証には Node.js 22 / Python 3.12 を使用します。
- リソースの作成権限を持つ AWS 認証情報が必要です（GitHub のデプロイ用ロールには、意図的にインフラの作成権限を付与していません）。
- 選択したリージョンの検証済み ACM 証明書と、ALB を参照するよう設定できるドメインが必要です。
- 同じリージョン・アカウントに、OpenAI API キーとアプリケーションの AI アクセストークンを格納した、既存の Secrets Manager シークレットが二つ必要です。値は JSON ではなく**プレーンな文字列**にし、Terraform の外部で作成してください。Terraform が受け取るのは ARN のみで、シークレットの値を状態ファイルに読み込むことはありません。カスタマー管理の KMS キーを使う場合は、`secrets_kms_key_arn` を設定し、キーポリシーで実行ロールを許可してください。
- 既存の ECS サービスリンクロール、または AWS にその作成を許可するプロビジョニング用認証情報が必要です。必要に応じて、管理者がアカウントごとに一度 `aws iam create-service-linked-role --aws-service-name ecs.amazonaws.com` を実行します。
- このワークスペース構成の GitHub リポジトリが必要です。必須の `openai_model` には、アプリケーションが対応し、利用する OpenAI アカウントで有効になっている画像対応モデルを設定してください。モデルは自動では選択されません。

## 初回デプロイ：ECR → イメージ → アプリケーション

以下のコマンドはすべて `floorplan-analyzer/` から実行します。独立した二つの Terraform 状態により、依存関係の循環を解消しています。`bootstrap` はイメージリポジトリのみを作成し、`app` はイメージが存在する状態でそれらを参照します。`-target` は不要です。

1. 自分の AWS 認証情報で初期化し、レジストリを作成します。

   ```bash
   terraform -chdir=infra/terraform/bootstrap init
   terraform -chdir=infra/terraform/bootstrap plan -out=bootstrap.tfplan
   terraform -chdir=infra/terraform/bootstrap apply bootstrap.tfplan
   ```

   両方のルート構成の既定値は `ap-northeast-1` と `floorplan-analyzer` です。`aws_region` または `project_name` を変更する場合は、それぞれの `terraform.tfvars` ファイルを使い、両方に同じ値を指定してください。

2. 完全なコミット SHA を使い、**コミット済みのリビジョン**をビルドしてプッシュします。未コミットの変更がないチェックアウトから実行し、ソースを変更した後に同じタグを再利用しないでください。ECR のタグは変更不可です。

   ```bash
   export AWS_REGION=ap-northeast-1
   export FRONTEND_REPOSITORY=$(terraform -chdir=infra/terraform/bootstrap output -raw frontend_repository_url)
   export BACKEND_REPOSITORY=$(terraform -chdir=infra/terraform/bootstrap output -raw backend_repository_url)
   export IMAGE_TAG=$(git rev-parse HEAD)
   aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "${FRONTEND_REPOSITORY%%/*}"
   docker buildx build --platform linux/amd64 --push -t "$FRONTEND_REPOSITORY:$IMAGE_TAG" frontend
   docker buildx build --platform linux/amd64 --push -t "$BACKEND_REPOSITORY:$IMAGE_TAG" backend
   ```

3. `infra/terraform/app/terraform.tfvars.example` を同じディレクトリの `terraform.tfvars` にコピーし、プレースホルダーの ARN、リポジトリ名、イメージ URI を**すべて**置き換えてください。`frontend_image` / `backend_image` には、完全なコミット SHA のタグまたはイメージダイジェストが必要です。`github_repository` には、大文字・小文字も含めて正確な `owner/repository` を設定してください。

   AWS アカウント内の `token.actions.githubusercontent.com` 用 OIDC プロバイダーは最大一つです。既存のものがある場合は、`github_oidc_provider_arn` を設定して再利用します。ない場合は Terraform が作成します。ロールは、指定したリポジトリと設定済みの GitHub 環境が完全に一致し、対象者が `sts.amazonaws.com` である場合のみ信頼します。

   ```bash
   terraform -chdir=infra/terraform/app init
   terraform -chdir=infra/terraform/app plan -out=app.tfplan
   terraform -chdir=infra/terraform/app apply app.tfplan
   ```

4. ACM 証明書の対象ドメインを、出力値 `alb_dns_name` に向けてください（`alb_zone_id` を使う Route 53 のエイリアス、またはサブドメインの CNAME）。DNS の設定と証明書の発行は、意図的に構成外の前提条件としています。`https://YOUR_DOMAIN/api/health` が `{"status":"ok"}` を返し、UI が開くことを確認してください。ALB 自体の DNS ホスト名は利用する証明書の対象外です。TLS 検証を無効にしないでください。

## GitHub の設定とデプロイ

GitHub 環境 `production`（または任意の `github_environment`）を作成します。デプロイ可能なブランチを `main` に制限し、リポジトリのプランが対応していれば必須レビュアーを設定してください。ワークフローでも他のブランチからのデプロイを拒否します。異なる環境名を使う場合は、**リポジトリレベル**の変数 `DEPLOY_ENVIRONMENT` に、その名前を正確に設定してください。

次の GitHub リポジトリまたは環境の**変数**を設定してください（長期有効な AWS キーは使用しません）。

| 変数 | 値 |
|---|---|
| `AWS_REGION` | 両方の Terraform ルート構成で使用するリージョン |
| `AWS_DEPLOY_ROLE_ARN` | app の出力値 `github_deploy_role_arn` |
| `ECS_CLUSTER` | app の出力値 `ecs_cluster` |
| `ECS_SERVICE` | app の出力値 `ecs_service` |
| `ECR_FRONTEND` | bootstrap の出力値 `frontend_repository_url`（タグなし） |
| `ECR_BACKEND` | bootstrap の出力値 `backend_repository_url`（タグなし） |
| `APP_URL` | 末尾のスラッシュを除いた `https://YOUR_DOMAIN` |

`CI` は、プルリクエストとプッシュ時に、pytest、フロントエンドの型検査・テスト・ビルド、Linux AMD64 向け Docker Compose のビルド・起動とヘルスチェック・サンプルアップロードのスモークテスト、Terraform のフォーマット検査・検証を実行します。AWS 認証情報にはアクセスしません。`Deploy to AWS` は手動実行（`workflow_dispatch`）で、`main` を選択します。最初に同じ CI を実行し、OIDC 経由で短期有効な AWS 認証情報を取得して、SHA タグ付きイメージをビルド・プッシュします。その後、現在のタスク定義をイメージ URI を更新してコピーし、サービスをローリング更新して安定するまで待機します。有効なリビジョンを検証して自動ロールバックを検出し、最後にフロントエンドのプロキシ経由で HTTPS のヘルスエンドポイントを確認します。同じコミットを再実行した場合、既存の変更不可な ECR イメージがあれば再利用します。シークレットの値は GitHub に渡さず、Docker のビルド引数にも含めません。

デプロイ用ロールは、プロジェクトの二つのリポジトリへのプッシュ、この ECS サービスの更新、その実行ロール・タスクロールの ECS への引き渡しのみを許可します。`RegisterTaskDefinition` の対象は、このプロジェクトのタスクファミリーに限定します。`GetAuthorizationToken` と `DescribeTaskDefinition` では、リソースの範囲にワイルドカードが必要です。アプリケーションのタスクロールには AWS 権限を付与しません。実行ロールは、これらのイメージの取得、自身のログの書き込み、指定した二つのシークレットの取得が可能です。

## インフラの変更、ローテーション、ロールバック

Terraform はインフラと基準となるタスク定義を管理します。サービス作成後の有効なタスクリビジョンは GitHub が管理します（`ignore_changes = [task_definition]` により、Terraform がデプロイ済みのイメージを巻き戻すことを防ぎます）。そのため、Terraform で環境変数、シークレットの ARN、CPU・メモリ、コンテナ設定を変更した場合は、適用後に**明示的なローリング更新**が必要です。まず Terraform のイメージ変数を、その時点で使用したい SHA・ダイジェストに設定して適用し、運用者の認証情報で次を実行してください。

```bash
export ECS_CLUSTER=$(terraform -chdir=infra/terraform/app output -raw ecs_cluster)
export ECS_SERVICE=$(terraform -chdir=infra/terraform/app output -raw ecs_service)
export TASK_REVISION=$(terraform -chdir=infra/terraform/app output -raw terraform_task_definition_arn)
aws ecs update-service --cluster "$ECS_CLUSTER" --service "$ECS_SERVICE" --task-definition "$TASK_REVISION"
aws ecs wait services-stable --cluster "$ECS_CLUSTER" --services "$ECS_SERVICE"
```

既存のシークレットの値を更新した場合は、新しいタスクが必要です（`aws ecs update-service ... --force-new-deployment`）。稼働中のコンテナには、変更後の値は自動で反映されません。トークンを出力したりコミットしたりしないでください。ロールバックでは、以前正常に稼働していたタスク定義の ARN を `update-service` で選び、待機してから公開ヘルスエンドポイントを確認します。ECS のサーキットブレーカーは、過去に成功したデプロイがある場合、失敗したデプロイを自動でロールバックします。ロールバック用に正常動作が確認できた ECR イメージを保持してください。イメージの自動削除ポリシーは設定していません。

ローリング更新時のヘルスチェックは API への到達性を検証するもので、モデルの品質や認証付きの有料 OpenAI リクエストを検証するものではありません。デプロイ後に、有効なトークンと代表的な入力を使って AI 機能を別途確認してください。

## 状態管理と検証

この例では既定でローカルの状態ファイルを使い、状態ファイル、`.terraform/`、変数の値、プランファイルはコミットしません。独立した両方の状態ファイルを安全に保管してください。チームで使う場合は、非公開で暗号化とバージョニングを有効にした既存の S3 バケットを使い、別々のキーと状態ロックを設定してください。`init` の前に、各ルート構成にローカルの `backend.tf` を追加します（`app` には異なるキーを使ってください）。

```hcl
terraform {
  backend "s3" {
    bucket       = "YOUR_PRIVATE_STATE_BUCKET"
    key          = "floorplan/bootstrap.tfstate"
    region       = "ap-northeast-1"
    encrypt      = true
    use_lockfile = true
  }
}
```

初期化済みのルート構成は、`terraform init -migrate-state` で移行します。シークレットを読み込まなくても、状態ファイルとプランファイルにはインフラの識別子が含まれるため、保護が必要です。CI は `init -backend=false` を使い、構文とプロバイダー設定のみを検証します。実環境に対するプランの実行や、AWS 権限、クォータ、証明書の状態、リソースの利用可否のテストは行いません。両方の `.terraform.lock.hcl` ファイルをコミットしてください。検証には Terraform とプロバイダーのダウンロードが必要です。

デプロイ環境を削除する場合は、まず `app` の `terraform destroy` を確認してください。ECR リポジトリは、空でない場合に意図的に削除を拒否します（`force_delete = false`）。`bootstrap` を削除する前に、イメージの保持方針を別途決めてください。既存のシークレット、ACM 証明書、外部の状態保存用バケットは、これらのルート構成では管理も削除もしません。

## このワークスペースで実施した検証

- Terraform 1.10.5：`fmt -check -recursive` に合格しました。署名済みの AWS プロバイダー 6.64.0 を使い、両方のルート構成で `init -backend=false` と `validate` に合格しました。両方のロックファイルを同梱しています。
- actionlint 1.7.12：両方のワークフローの検査に合格しました（`-shellcheck=`。ShellCheck は未インストールでした）。ワークフロー内のシェルブロック14個も、すべて `bash -n` に合格しました。
- この環境には Docker がインストールされていないため、Compose のビルド・起動とスモークテストは CI に実装していますが、ローカルでは実行していません。リポジトリへのプッシュ、GitHub Actions の実行、AWS のプラン・適用、実環境へのデプロイはいずれも行っていません。

## 公式の参考資料

確認日：2026-09-14

- [AWS Fargate のネットワーク](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-task-networking.html)：タスクのパブリック IP、localhost 通信、イメージ取得時の接続についてです。
- [AWS ECS の Secrets Manager を使った環境変数](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/secrets-envvar-secrets-manager.html)：実行ロールの権限と再起動の要件についてです。
- [GitHub の AWS 向け OIDC](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws)：対象者と、リポジトリ・環境が完全に一致するサブジェクトの制限についてです。
- [Terraform の S3 バックエンド](https://developer.hashicorp.com/terraform/language/backend/s3)：状態ファイルの暗号化と S3 ロックファイルの設定についてです。

- [AWS ECS のサービス認可リファレンス](https://docs.aws.amazon.com/pt_br/service-authorization/latest/reference/list_amazonelasticcontainerservice.html)：登録時のタスクファミリーへの範囲制限と、リソースの範囲を限定しない参照権限についてです（英語版のポリシー例のページには、登録範囲がより広い古い例が掲載されています）。
