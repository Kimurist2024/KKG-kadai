# 設定例

`env.example` は環境変数のテンプレートです。アプリ直下から次を実行し、コピー先で値を設定します。

```bash
cp config/env.example .env
```

`.env` の置き場所はアプリ直下です。Composeが読み取ります。`config/` に実際の秘密値を保存しません。

ツールが所定の位置から読む設定は移動していません。Next.js・Vitestは `frontend/`、Pytestは `backend/`、Vercel・Composeはアプリ直下、Terraformは `infra/terraform/`、GitHub Actionsはワークスペース直下の `.github/workflows/` にあります。
