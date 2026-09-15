# プロジェクト: 平面図 面積・壁面積 解析アプリ

## 最優先: 課題要件（毎回読む）

以下は課題の原文（`kadai.md`）。**判断に迷ったら常にこれを基準にする。** 取り込みが効かない環境では直接 `kadai.md` を読むこと。

@kadai.md

ユーザー指定（2026-09-14）: computer use 禁止。ブラウザ・ネイティブアプリの UI 自動操作はサブエージェントも含めて実行しない。コード・CLI・HTTP API・コンポーネントテストで検証する。ユーザーの明示的な解除まで、個別担当のブラウザ検証指示より優先する。

実装本体は `floorplan-analyzer/`（frontend: Next.js/React/TS、backend: Python/FastAPI）。詳細は `floorplan-analyzer/README.md`。

## モデルと実行主体の方針（2026-09-15 ユーザー指定、同日更新）

- **すべて Opus 5 で動かす**（`.claude/settings.json` の `opus[1m]`）。司令塔・全サブエージェント・案出し（設計の選択肢出し、改善点の洗い出し）も Opus。
- **Fable 5.1 は使わない**（使用制限のため）。ユーザーが明示的に解除するまで `/model fable` へ切り替えない。
- **コーディング作業はすべて Codex (gpt-6-astra) に委譲する**: ラッパー `.claude/scripts/codex-task.sh <dir> <medium|high> "<プロンプト>"`。`ui-designer` / `algorithm-engineer` は Edit/Write を持たず、仕様化 → Codex 実行 → 検証 → 報告を担う。
  - `high`: アルゴリズム変更、複数ファイルにまたがる設計判断、状態管理の競合が絡む UI 変更
  - `medium`: テスト追加、単一コンポーネントの表示調整、小さな修正
- 司令塔自身も原則コードを直接編集せず Codex に任せる。例外は `types.ts` / `api.ts` の同期など数行の統合作業と設定ファイル。
- 検証（pytest / npm test / typecheck / build）は Codex の自己申告に頼らず、担当エージェントまたは司令塔が再実行する。

## 1 サイクルの完了条件

1. 受入条件を決める → 担当エージェントが Codex に実装させる
2. `.claude/scripts/verify.sh` が **exit 0**（これが唯一の合格判定。自己申告は認めない）
3. 作業ブランチを push し、`feature/kimura` 宛に PR
4. `.claude/scripts/review.sh feature/kimura "<受入条件>"` が **VERDICT: OK**
5. `feature/kimura` にマージ。**`main` への反映はユーザーが行う（AI は触らない）**

詳細と差し戻しの扱いは `floorplan-analyzer/docs/orchestration.md`。

## オーケストレーション方針

着手前に `floorplan-analyzer/docs/orchestration.md` を読む。以下は役割の概要で、API 同期・割当・完了条件の詳細は同ドキュメントに従う。

メインセッションは司令塔として要件を分解し、実作業は以下のサブエージェントに委譲する。

| サブエージェント | 担当 | 触ってよい範囲 |
|---|---|---|
| `ui-designer` | 画面・コンポーネント・スタイル・アクセシビリティ | `frontend/src/` のみ |
| `algorithm-engineer` | 幾何計算・解析ロジック・API スキーマ・pytest | `backend/` のみ |
| `web-researcher` | 仕様・慣習・ライブラリ・事例の調査（出典付き） | 読み取り専用 |

### 典型的な流れ
1. 不明点があれば `web-researcher` に調査させ、結論を受け取る。
2. API 契約に変更が必要なら司令塔が仕様を確定し、`algorithm-engineer` が backend を実装する。司令塔が `frontend/src/types.ts` と `api.ts` を同期してから `ui-designer` に引き継ぐ。
3. 独立した作業は同時に起動する（例: UI 改善と backend のテスト追加）。
4. 各エージェントの最終報告にある検証結果（typecheck / test / build / pytest）を確認してから統合する。

### 共通ルール
- 依存追加は目的を明確にする。現在は Next.js/React と FastAPI/httpx/Pillow を使用し、幾何計算のコアは純 Python を維持する。
- `frontend/src/types.ts` は `backend/app/schemas.py` と常に一致させる。
- サンプル (`sample/sample_mask.json`) の結果は README 5-4 の表と一致していること。
- 統合・共通ファイル・依存設定・検証結果の確認は司令塔が担当する。同じファイルを複数の担当に同時に編集させない。
