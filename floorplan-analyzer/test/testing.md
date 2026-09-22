# テストの入口

アプリの回帰テストはこのディレクトリで管理します。

```text
test/
└── gpt-6/
    ├── frontend/   # 表示・操作・API中継・固定データ
    └── backend/    # 幾何計算・解析API・結果一致
```

`floorplan-analyzer/` から実行します。

```sh
# フロントエンド（依存は frontend/ で npm ci）
(cd frontend && npm run typecheck && npm test && npm run build)

# バックエンド（依存は backend/requirements-dev.txt）
(cd backend && .venv/bin/python -m pytest -q)
```

CI の `npm test` と `python -m pytest -q` も、それぞれ Vitest・pytest の設定を通してこの場所を参照します。実装側へのテストの複製は不要です。

## まとめて検証するときとログの場所

リポジトリ直下で `.claude/scripts/verify.sh quick`（pytest・型検査・Vitest）または `verify.sh all`（さらに本番ビルド）を実行します。コンソールには各ステップの結果・所要時間・要約が 1 行ずつ出て、失敗したステップだけログの末尾 40 行とパスが表示されます。

各ステップの全出力は `.claude/logs/verify/<実行時刻>/` に `01-backend-pytest.log` のような名前で保存され、`pytest.junit.xml` と `vitest.junit.xml`、各ステップの結果をまとめた `summary.tsv` も同じ場所に出ます。直近の実行は `.claude/logs/verify/latest` から開けます（保存は最新 10 回分。保存先は環境変数 `VERIFY_LOG_DIR` で変えられます）。

pytest は `backend/pytest.ini` で、失敗時に短いトレースバックと要約（`-ra`）を出し、キャプチャしたログを `時刻 レベル ロガー名: メッセージ` の書式で表示するように設定しています。ログを流しながら実行したいときは `pytest --log-cli-level=INFO` を使います。

テスト用の依存関係は引き続き frontend/・backend/ に置きます。性能計測ツールと変更前の比較実装は `backend/benchmarks/`、計測レポートは `docs/validation/` に残しています。
