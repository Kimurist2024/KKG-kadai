# テストの入口

アプリの回帰テストはこのディレクトリで管理します。

```text
test/
└── gpt-6/
    ├── frontend/   # 表示・操作・API中継・固定データ
    └── backend/    # 幾何計算・解析API・AI応答・結果一致
```

`floorplan-analyzer/` から実行します。

```sh
# フロントエンド（依存は frontend/ で npm ci）
(cd frontend && npm run typecheck && npm test && npm run build)

# バックエンド（依存は backend/requirements-dev.txt）
(cd backend && .venv/bin/python -m pytest -q)
```

CI の `npm test` と `python -m pytest -q` も、それぞれ Vitest・pytest の設定を通してこの場所を参照します。実装側へのテストの複製は不要です。

テスト用の依存関係は引き続き frontend/・backend/ に置きます。性能計測ツールと変更前の比較実装は `backend/benchmarks/`、計測レポートは `docs/validation/` に残しています。
