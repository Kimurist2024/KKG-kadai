# フォルダ整理（2026-09-15）

実装、設定、スクリプト、テスト、設計資料を用途ごとに分けました。Next.jsとFastAPIのビルド単位は維持します。別プロジェクト固有のコード・設定・機能は取り込んでいません。

| 以前の場所 | 現在の場所 |
|---|---|
| `start.sh` / `stop.sh` の実処理 | `scripts/start.sh` / `scripts/stop.sh`（旧入口も利用可能） |
| `.env.example` | `config/env.example`（コピー先の `.env` はアプリ直下） |
| `frontend/src/*.test.ts(x)` | `frontend/tests/` |
| `frontend/src/test-data/` | `frontend/tests/fixtures/` |
| `docs/validation/run_validation.py` | `scripts/validation/run_validation.py` |
| `docs/validation/build_report.py` | `scripts/validation/build_report.py` |
| `docs/review_gpt6_codex*.md` / `docs/ui_dialogue.md` | `docs/reviews/` |
| `docs/screenshot_*.png` | `docs/images/` |

新しく `ARCHITECTURE.md`、`CONTRIBUTING.md`、各フォルダのREADMEを追加しました。変更前の性能計測データと固定実装は保存し、レポートへの既存パスも維持しています。

`vercel.json` とComposeは引き続き `frontend/`・`backend/` を参照します。GitHub Actionsはワークスペース直下に置きます。認証済みの `.vercel/`、ローカルの `.env.local`、依存インストール先、仮想環境は移動していません。

`docs/validation/sha256.json` は当時の検証ファイルのハッシュ記録です。そこにある `run_validation.py` / `build_report.py` のパスとハッシュは移動前の状態を示します。過去の記録は書き換えず、今後レポートを生成した際には移動先スクリプトのハッシュを記録します。

## 整理後の確認

- バックエンド: 126テスト成功。
- フロントエンド: 8ファイル・22テスト、型検査、本番ビルド成功。
- 起動・停止スクリプト4本: `bash -n` 成功。既存プロセスを止めるため、実際の起動・停止操作は未実施。
- 移動した検証スクリプト: 一時ディレクトリで実行成功。11区画の結果、四則演算との比較、Markdown・SVG生成を確認。過去の検証出力は上書きしていません。
- 新しい案内資料とREADMEのローカルリンク45件、Vercelのサービス参照先を確認。
- サービスの場所は同じため、CI・Docker・Vercelのビルド対象パスは変更不要。GitHub ActionsやDockerの実行、本番への再デプロイは今回行っていません。
