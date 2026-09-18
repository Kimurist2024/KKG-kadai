# 開発ガイド

まず [README](../README.md) で起動し、[ARCHITECTURE](ARCHITECTURE.md) で変更対象の責務を確認します。以下は `floorplan-analyzer/` から実行します。

## 開発環境

Python 3.9以上、Node.js 20.9以上が必要です。CIはPython 3.12・Node.js 22です。

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
npm --prefix frontend ci
./scripts/start.sh
```

起動スクリプトは使用する8000/5173ポートの既存プロセスを停止します。他のアプリが使用中ならREADMEの手動起動を使ってください。停止は `./scripts/stop.sh` です。

環境変数を上書きする場合は `config/env.example` を `.env` にコピーして設定します（現在、必須の環境変数はありません）。

## 変更場所

- 画面・操作: `frontend/src/`。対応する回帰テストは `test/gpt-6/frontend/`。
- 計算・入力検証: `backend/app/`。対応する回帰テストは `test/gpt-6/backend/`。
- API契約: `backend/app/schemas.py` と `frontend/src/types.ts` / `api.ts` を同期。
- 起動・検証ツール: `scripts/`。結果と資料は `docs/validation/`。
- クラウド構成: `infra/`、`vercel.json`、ワークスペースの `.github/workflows/`。

## 検証

```bash
(cd backend && .venv/bin/python -m pytest -q)
npm --prefix frontend run typecheck
npm --prefix frontend test
npm --prefix frontend run build
```

計算速度を変更するときは、同じ入力・設定で結果と時間の両方を比較します。

```bash
(cd backend && .venv/bin/python -m benchmarks.performance --phase final)
```

このコマンドは `docs/validation/algorithm-performance/final.json` とプロファイルを更新します。既存の測定記録を残してから実行し、日付・実行環境・入力・結果差を報告してください。`backend/benchmarks/baseline/` と `stages/` は比較用の固定実装で、通常の機能変更では編集しません。

## 記録とレビュー

変更の目的、利用者から見た動作、実行した検証と未確認事項を記録します。過去のレビューは `docs/reviews/`、計測の生データは `docs/validation/` に置きます。新しい結果を過去の検証済み事項として混在させません。

このワークスペースではcomputer useは禁止されています。コード・CLI・HTTP・コンポーネントテストを利用し、実ブラウザで確認していないことを明記します。エージェントの役割は [開発オーケストレーション](docs/orchestration.md) を参照してください。
