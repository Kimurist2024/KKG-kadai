# 平面図解析アプリの作業指示

ユーザー指定（2026-09-14）: computer use は禁止。ブラウザ・ネイティブアプリの UI 自動操作を行わず、サブエージェントにも委譲しない。検証はコード、CLI、HTTP API、コンポーネントテストで進める。以下や個別担当のブラウザ検証指示よりこの指定を優先する。ユーザーが明示的に解除するまで継続する。

実装は `floorplan-analyzer/`。作業前に `floorplan-analyzer/README.md` と `floorplan-analyzer/docs/orchestration.md` を読む。

ユーザーは UI・アルゴリズム・Web リサーチの 3 担当によるオーケストレーションを希望している。独立した具体的な作業がある場合、利用可能なサブエージェントへ委譲する。小さな単独作業に全担当を起動しない。

各担当へ `.claude/agents/ui-designer.md`、`.claude/agents/algorithm-engineer.md`、`.claude/agents/web-researcher.md` の対応する本文を渡す。これらの YAML にある Claude 固有のツール名・モデル名は Codex の設定として適用しない。実際の利用可能ツールと権限に従う。このファイルは作業指示であり、名前付きエージェントを自動登録・常駐させる設定ではない。

メイン担当は要件分解、変更ファイルの排他的割当、API 契約の調整、frontend/src/types.ts と api.ts の同期、統合レビュー、最終報告を担当する。利用できない検証を成功扱いしない。

Codex はこのプロジェクトのコード作成・変更の実行主体である（Claude 側の担当は仕様化と検証を行い、`.claude/scripts/codex-task.sh` からプロンプトを渡す）。プロンプトに書かれた編集可能ファイル・対象外・検証コマンドを守り、最終メッセージに変更ファイル・実行したコマンドと結果・未実施事項をまとめる。
