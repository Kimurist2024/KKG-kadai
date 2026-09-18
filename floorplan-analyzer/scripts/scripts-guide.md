# 開発・検証スクリプト

アプリ直下から実行します。

| スクリプト | 用途 |
|---|---|
| `./scripts/start.sh` | 開発サーバーを起動。前回の `start.sh` が残っていれば子孫ごと停止し、指定ポートの既存プロセスも停止してから起動する |
| `./scripts/stop.sh` | このアプリの開発用プロセスをすべて停止する（残っている `start.sh` とその子孫、開発用ポートのプロセス、親を失った next / uvicorn） |
| `./scripts/check-start-stop.sh` | `start.sh` / `stop.sh` が古いプロセスを残さないことを、スタブのアプリ（ポート 8010 / 5183）で確かめる回帰チェック |
| `validation/run_validation.py` | 保存した外部図面・手動輪郭をAPIで検算する |
| `validation/build_report.py` | 検証結果からMarkdownとSVGを生成する |
| `measure_sample_speed.py` | 同梱 JSON だけを対象に、変更前の凍結実装と現行の解析時間を交互に計測する |

```bash
backend/.venv/bin/python scripts/validation/run_validation.py
backend/.venv/bin/python scripts/validation/build_report.py
backend/.venv/bin/python scripts/measure_sample_speed.py 101 docs/validation/sample-speed/results.json
```

検証スクリプトは `docs/validation/sources/` の画像を読み、`docs/validation/` の結果を上書きします。過去の結果を保管してから再実行してください。性能ベンチマークはPythonパッケージとして `backend/benchmarks/` に置き、実行方法は[ベンチマーク手順](../backend/benchmarks/benchmarks.md)を参照します。

開発サーバーは `http://localhost:5173` のほか、同じ LAN の別の端末から `http://<このPCのIP>:5173` でも開けます。Next.js は開発用リソース（`/_next/*`）へのクロスオリジン要求を既定で遮断するため、`frontend/next.config.ts` でこの PC の IPv4 アドレスを起動時に自動で許可しています。別名のホストやプロキシ経由で開く場合は、環境変数 `DEV_ALLOWED_ORIGINS` にカンマ区切りでホスト名を指定してから起動してください（例: `DEV_ALLOWED_ORIGINS=my-mac.local ./scripts/start.sh`）。

`next dev` の親プロセスは SIGTERM では終わらないことがあり、以前は起動し直すたびに古い `start.sh` と `next dev` が残っていました。現在は共通関数 `scripts/_proc.sh` で、TERM を送ってから `STOP_GRACE` 秒（既定 5 秒）で KILL に切り替えます。対象は作業ディレクトリがこのアプリ配下のプロセスだけです。

アプリ直下の `start.sh` / `stop.sh` は既存コマンドとの互換用です。処理を変更するときは、このフォルダの実体を編集します。
