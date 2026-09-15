# アーキテクチャ

このアプリは図面の部屋・壁・扉の座標から面積を計算します。画像AIは座標候補の作成を担当し、面積の算出はPythonの幾何計算が担当します。

## 配置と責務

| 場所 | 内容・読み始めるファイル |
|---|---|
| `frontend/src/app/` | Next.jsのページ・レイアウト・API中継 |
| `frontend/src/App.tsx` | 解析画面の組み立て |
| `frontend/src/components/` | 図面、設定、結果表、算出根拠の表示 |
| `frontend/src/hooks/` | 解析要求、選択、ドラッグ操作の状態管理 |
| `frontend/src/api.ts` / `types.ts` | APIクライアントとレスポンス型 |
| `test/gpt-6/frontend/` | UI・表示計算・API中継のテストと固定データ |
| `backend/app/main.py` | FastAPIのエンドポイントと入力検証 |
| `backend/app/schemas.py` | 座標、設定、解析結果の契約 |
| `backend/app/analyzer.py` | 部屋ごとの計算と結果の集計 |
| `backend/app/geometry.py` | 射影、距離、面積、区間演算 |
| `backend/app/topology.py` | 穴を含む多角形の検証・構築 |
| `backend/app/spatial.py` | STRtreeによる候補の絞り込み |
| `backend/app/analysis_cache.py` | 幾何結果の保存と縮尺・高さの再計算 |
| `backend/app/ai.py` / `ai_schemas.py` | 画像AIとの通信と出力検証 |
| `test/gpt-6/backend/` | 計算・API・キャッシュ・AI応答の回帰テスト |
| `backend/benchmarks/` | 性能計測コードと変更前・段階別の固定実装 |
| `scripts/` | 起動・停止、検証レポートの生成 |
| `config/` | 利用者がコピーして設定する環境変数の例 |
| `sample/` | 同梱サンプルと期待結果の画像 |
| `docs/` | 設計説明、検証結果、過去のレビュー、画像 |
| `infra/` | AWS構成とTerraform・運用手順 |
| `../.github/workflows/` | ワークスペース単位のCIとAWSデプロイ |

`frontend/` と `backend/` は独立したビルド・配置単位です。Next.jsの `src/app/` とPythonの `app/` は、それぞれのフレームワークに合わせたソースの置き場です。依存定義、Dockerfile、Next.js/Vitest/Pytestの設定はサービス直下に置きます。

## JSON解析の流れ

1. フロントエンドがJSONと縮尺・高さ・許容誤差を送信する。
2. FastAPIが入力を検証し、解析処理へ渡す。
3. 多角形と穴を検証し、壁・扉の候補を絞って辺へ投影する。
4. 区間の重複を統合し、床面積・壁長・扉控除・部屋重複を算出する。
5. 設定値で単位変換・壁面積を計算し、警告とともに返す。
6. フロントエンドが図面、結果表、算出根拠、CSVを表示する。

幾何キャッシュは各プロセスで最大8件・16MiB・5分。図形や許容誤差が変われば再計算します。高さと縮尺だけの変更では、保存済みの幾何結果を使って再集計します。キャッシュがなくても解析できます。

## 配置先とエントリポイント

- ローカル: `scripts/start.sh` → FastAPI `app.main:app` とNext.js。
- Docker: `compose.yaml` → 各サービスのDockerfile。Next.jsからFastAPIへ中継。
- Vercel: `vercel.json` のServices設定。`/api/*` は直接バックエンドへ、それ以外はフロントエンドへ。
- AWS: `infra/terraform/` と `../.github/workflows/`。手順は [infra/README.md](infra/README.md)。

`api/index.py` とルートの `requirements.txt` は以前の単一Function方式の互換用です。現在のVercel Services設定では使用しません。ルートの `start.sh` / `stop.sh` も従来コマンド用の委譲先で、実処理は `scripts/` にあります。

詳細は [技術構成と検証履歴](docs/architecture.md)、[幾何計算の拡張](docs/geometry-upgrade.md)、[性能測定](docs/validation/algorithm-performance/report.md) を参照してください。


## コードを読む順番

画面の流れは `frontend/src/App.tsx` から辿ります。`hooks/useAnalysis.ts` が
ファイル読込・縮尺確認待ち・API 通信を管理し、`components/SettingsPanel.tsx` が
条件入力を検証します。表示は `FloorPlanView`（図面）、`RoomTable`（一覧）、
`RoomDetail`（算出根拠）に分かれています。各コンポーネントの宣言前に役割を記載しています。

計算は `backend/app/main.py` → `analyzer.analyze` の順です。
`_analyze_core` は分類・部屋解析・警告・重複判定・集計の流れをまとめ、
`analyze_room` が外周と穴、`analyze_edge` が壁・扉の対応付けを担当します。
`_wall_and_door_warnings` は壁不足・未対応扉の通知、`_room_overlaps` は交差と和集合の計算です。
入力・出力の意味は `schemas.py`、AI 候補の制約は `ai_schemas.py` の各クラスに説明しています。

`analysis_cache.py` は幾何結果を px 単位で再利用し、今回の縮尺・高さに換算します。
数値の再現性を保つため、通常計算と同じ順で加算・乗算します。
`spatial.py` は候補を絞るだけで、壁・扉の採用条件は `geometry.py` が判定します。
この役割分担と計算順序は、短く書くためだけに省略しないでください。

### 2026-09-15 可読性整理の検証

警告・重複判定の関数化、設定フォーム初期化の共通化、操作名・役割コメントを整理しました。
変更直前のバックエンド実装を一時ディレクトリに保存して、同梱サンプル・穴と扉補完の例・
110 部屋・550 部屋の 4 入力 × 5 条件 × キャッシュなし/初回/再利用の 60 レスポンスを比較しました。
数値 1,522,938 項目の差は 0。警告文・ID・配列順も一致しました。
既存の 126 バックエンドテスト、22 フロントエンドテスト、型検査、本番ビルドが成功しています。
ブラウザの UI 操作検証はユーザー指定により実施していません。今回の変更は再デプロイしていません。
