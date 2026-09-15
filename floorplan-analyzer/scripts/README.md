# 開発・検証スクリプト

アプリ直下から実行します。

| スクリプト | 用途 |
|---|---|
| `./scripts/start.sh` | 開発サーバーを起動。指定ポートの既存プロセスを停止する |
| `./scripts/stop.sh` | 開発用ポートのプロセスを停止する |
| `validation/run_validation.py` | 保存した外部図面・手動輪郭をAPIで検算する |
| `validation/build_report.py` | 検証結果からMarkdownとSVGを生成する |

```bash
backend/.venv/bin/python scripts/validation/run_validation.py
backend/.venv/bin/python scripts/validation/build_report.py
```

検証スクリプトは `docs/validation/sources/` の画像を読み、`docs/validation/` の結果を上書きします。過去の結果を保管してから再実行してください。性能ベンチマークはPythonパッケージとして `backend/benchmarks/` に置き、実行方法はそのREADMEを参照します。

アプリ直下の `start.sh` / `stop.sh` は既存コマンドとの互換用です。処理を変更するときは、このフォルダの実体を編集します。
