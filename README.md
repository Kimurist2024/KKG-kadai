# 平面図 面積・壁面積 解析アプリ

> この `main` ブランチには説明資料を掲載しています。アプリ本体は [feature/kimura](https://github.com/Kimurist2024/KKG-kadai/tree/feature/kimura) を参照してください。以下の起動手順は同ブランチをチェックアウトし、`floorplan-analyzer/` を作業ディレクトリとして実行します（`.claude/scripts/` のコマンドはリポジトリ直下で実行）。

公開サイト: https://floorplan-analyzer-taupe.vercel.app （JSON 解析を確認済み、画像 AI は未設定）

**部屋・壁・ドアマスク JSON** から、部屋ごとの **床面積・周長・壁面積** を算出する Web アプリです。
提出用の画面は JSON アップロードと固定条件での解析に絞っています。画像 AI の入力欄は表示しません。

- フロントエンド: TypeScript / React / Next.js App Router（`frontend/`）
- バックエンド: Python / FastAPI（`backend/`）
- AI: FastAPI → OpenAI Responses API（画像入力・Structured Outputs）。キー未設定でも JSON 解析は利用できます。
- 配置: Docker Compose、AWS ECS Fargate 用 Terraform、GitHub Actions（テスト・ビルド・手動デプロイ）。
- ブラウザ → Next.js の API プロキシ → FastAPI と HTTP で連携します。

部屋選択時の表示処理の改善と計測結果は [性能検証](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/selection-performance.md) を参照してください。
面積・壁・扉の計算高速化と変更前後の全項目比較は [アルゴリズム性能検証](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/validation/algorithm-performance/report.md) を参照してください。
直前の実装を基準にした最新の高速化・浮動小数点の完全一致検証・論文調査は [計算結果を変えない高速化](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/validation/exact-speed/README.md) にあります。100倍の目標は未達です。
追加の5倍高速化に向けた [端点イベント走査の実測](floorplan-analyzer/docs/validation/interval-sweep/README.md) では、人工的な1,024頂点の輪郭で初回解析が7.9〜11.1倍になりました。同梱図面はほぼ同速で、全入力で5倍の目標は未達です。

応募要件との対応と動作確認の範囲は [技術構成と検証状況](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/architecture.md)、AWS の手順は [インフラ手順](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/infra/README.md) を参照してください。

![概要画面](floorplan-analyzer/docs/images/screenshot_overview.png)
![部屋を選択した画面](floorplan-analyzer/docs/images/screenshot_room_detail.png)

---

## 目次

1. [ディレクトリ構成](#1-ディレクトリ構成)
2. [実行確認方法（環境構築・起動手順）](#2-実行確認方法環境構築起動手順)
3. [使い方](#3-使い方)
4. [API 仕様](#4-api-仕様)
5. [アルゴリズムの考え方・設計背景](#5-アルゴリズムの考え方設計背景)
6. [UI 設計において工夫した点](#6-ui-設計において工夫した点)
7. [フロントエンド / バックエンドの責務分担・API 設計の判断と理由](#7-フロントエンド--バックエンドの責務分担api-設計の判断と理由)
8. [前提・制限事項と今後の拡張](#8-前提制限事項と今後の拡張)
9. [AI の活用方法と開発ハーネス](#9-ai-の活用方法と開発ハーネス)

---

## 1. ディレクトリ構成

アプリ本体は `floorplan-analyzer/`、GitHub Actionsと開発用の `.claude/` はリポジトリ直下にあります。

```text
floorplan-analyzer/
├── frontend/          # Next.js・React・TypeScript、表示とCSV出力
├── backend/app/       # FastAPI、入力検証・幾何計算・キャッシュ
├── backend/benchmarks/ # 性能計測・比較用の固定実装
├── test/gpt-6/        # frontend / backend のテスト
├── sample/           # 同梱の図面データ
├── scripts/          # 起動・停止・検証ツール
├── docs/             # 設計・画像・検証記録
├── infra/terraform/  # AWS構成
└── compose.yaml      # コンテナ起動
```

ファイルの責務は [ARCHITECTURE](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/ARCHITECTURE.md)、開発手順は [CONTRIBUTING](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/CONTRIBUTING.md)、その他の資料は [docs/README.md](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/README.md) を参照してください。

## 2. 実行確認方法（環境構築・起動手順）

Python 3.9以上、Node.js 20.9以上が必要です。以下は `floorplan-analyzer/` で実行します。

### かんたん起動（macOS / Linux）

```bash
./scripts/start.sh
# 「起動完了」後、http://localhost:5173 を開く
./scripts/stop.sh
```

起動スクリプトは8000/5173番を使用中のプロセスを停止してからセットアップ・起動します。初回セットアップ、両サーバーの起動、疎通確認は依存しない範囲で並列実行します。`BACK_RELOAD=0 ./scripts/start.sh` でバックエンドの自動リロードを省けます。計測条件は [起動性能](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/startup-performance.md) にあります。

### 手動起動

バックエンドとフロントエンドを別ターミナルで起動します。各ターミナルの開始位置はアプリ直下です。

```bash
# バックエンド
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

```bash
# フロントエンド
cd frontend
npm install
npm run dev
```

画面は **http://localhost:5173**、APIの疎通確認は `http://127.0.0.1:8000/api/health`、API仕様は `http://127.0.0.1:8000/docs` です。8000番ではアプリ画面は表示されません。

### テスト・コンテナ

```bash
# アプリ直下から、それぞれ別に実行
(cd backend && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest -q)
(cd frontend && npm test && npm run build)
docker compose up --build  # http://localhost:3000
```

Next.jsがAPIをFastAPIへ中継します。`API_PROXY_TARGET` で接続先を指定でき、ローカル既定は `http://127.0.0.1:8000` です。JSON解析にAIキーは不要です。環境変数・画像AI・AWSの詳細は [技術構成](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/architecture.md) と [インフラ手順](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/infra/README.md) を参照してください。

## 3. 使い方

1. 初回は同梱サンプルを自動解析します。操作説明は画面上部の「はじめての方へ」から `/guide` を開きます。
2. 自分のJSONはドラッグ＆ドロップ、または「別のJSONを選択」から読み込みます。
3. 天井高 **2.4m**、ドア高 **2.0m**、縮尺 **96.7px = 1.365m** で即座に解析します。通常画面では入力輪郭の幾何補正は無効です。
4. 部屋を図面・表から選ぶと、床面積・周長・壁面積と、辺ごとの計算根拠を確認できます。図面の辺番号と内訳表は対応しています。
5. 「CSVダウンロード」で結果を保存できます。表示の拡大・縮小は計算値に影響しません。

壁データがない、対応する壁がない、壁の対応率が周長の20%未満の場合は「要確認」を表示し、CSVにも理由を残します。20%は確認の目安であり、開放空間にも該当します。壁面積0は「壁がないと確認できた」という意味ではありません。

画像AIの入力欄は非表示です。内部コンポーネントと認識APIは残していますが、提出用画面では使いません。

## 4. API 仕様

| メソッド・パス | 内容 |
|---|---|
| GET `/api/health` | 疎通確認 |
| GET `/api/defaults` | 計算条件の既定値 |
| POST `/api/analyze` | multipartの `file` にJSONをアップロード |
| POST `/api/analyze/json` | JSONボディで同じ解析を実行 |
| GET `/api/ai/status` | AI設定の有無（秘密値は返さない） |
| POST `/api/recognize` | 画像認識。画像と `X-AI-Token` が必要 |

解析APIは `ceiling_height_m`（2.4）、`door_height_m`（2.0）、`scale_px`（96.7）、`scale_m`（1.365）、`tolerance_px`（10）を任意のクエリとして受け付けます。通常画面は課題の固定値を使用します。

レスポンスは `summary`（全体集計）、`rooms`（部屋別結果）、`walls`・`doors`（描画用線分）、`warnings` を含みます。各部屋の `edges` に壁・開口・ドア区間と根拠IDを保持します。完全な型は `backend/app/schemas.py` と `frontend/src/types.ts`、リクエスト例はAPIの `/docs` を参照してください。

エラーは400（JSON不正）、413（容量超過）、422（入力形式・計算条件不正）で返し、画面に理由を表示します。

## 5. アルゴリズムの考え方・設計背景

提出用の画面では部屋輪郭の補正を無効にしています。研究用の幾何補正実装と API の任意パラメータは保持していますが、画面からは変更できません。詳細は [docs/geometry-regularization.md](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/geometry-regularization.md) を参照してください。

### 5-1. 入力の分類

`contours` を次のように分類します。

| 種別 | 条件 | 例 |
|---|---|---|
| 部屋 | `isLine` が真でない多角形 | LD, K, 浴室 … |
| 壁 | `isLine == true` かつ `label_id == 2` | 赤い線分 (2 頂点) |
| ドア | `isLine == true` かつ `label_id == 3` | 緑の線分 (2 頂点) |

`room_name` が `null` の部屋（サンプルでは id=3, 10。図面上のパントリー・シューズクロークに相当）も
面積計算の対象とし、`未命名 #<id>` という表示名を与えたうえで `warnings` で通知します。

### 5-2. 床面積・周長

- **床面積** = 頂点座標にシューレース（Gauss）の公式を適用した面積 [px²] × (m/px)²
- **周長** = 隣接頂点間距離の総和 [px] × (m/px)
- **スケール** m/px = 1.365 / 96.7 ≒ 0.014116

JSON に含まれる `area` / `perimeter` は信用せず、頂点から再計算しています（両者が食い違う場合は
`warnings` に出し、UI でも「JSON 記載値との差」を表示します）。サンプルでは全部屋で一致しました。

#### 部屋の輪郭と壁の位置関係

![部屋の輪郭が壁の内法を通る場合、壁芯を通る場合、認識ずれがある場合を比較した概念図](floorplan-analyzer/docs/images/room-boundary-wall-reference.png)

この図は考察用の概念図であり、同梱データの輪郭位置を断定するものではありません。
灰色は壁、青破線は入力輪郭、緑実線は壁の室内側の面（内法）の基準です。

- **内法を通る場合**：室内側の床面積を求めるなら、壁厚による補正は原則不要です。
- **壁芯を通る場合**：内法面積へ変換するには実際の壁厚が必要です。各壁の中心から室内側へ壁厚の半分だけ境界を移し、角の接続を再構成して面積を計算します。壁のない境界は同じようには移動しません。
- **認識ずれがある場合**：まず壁との対応と輪郭の基準を確認します。一律に内側へ移動すると、誤差を増やす可能性があります。

**壁芯から内法への変換と、認識誤差の修正は別の処理です。** 現在の通常画面は入力輪郭の面積を計算し、壁厚による面積補正は行いません。
同梱データの輪郭基準・実際の壁厚は未確定です。`tolerance_px` は線分の対応付けに使う許容距離であり、実際の壁厚を表す値ではありません。

### 5-3. 壁面積（本課題の中心）

要件は「壁面積 = 辺の長さ × 天井高、ドア部分は控除、**壁が存在しない輪郭区間がある**」です。
部屋の輪郭の辺と壁線分は別々の輪郭として与えられ、座標も数 px ずれているため、
**「各辺のうち、どの範囲に壁があるか」を 1 次元の区間として求める** 方針を採りました。

部屋の各辺について、次の順に計算します。

1. **射影**：角度差10°以内で、壁線の両端が辺の延長線から `tolerance_px`（既定10px）以内なら、辺上の区間へ変換します。辺の外側は切り落とすため、長い壁も部屋ごとに配分できます。
2. **ノイズ除去**：重複を併合し、`min(tolerance_px, 辺長/2)` 未満の区間を除きます。後から補完で短い断片が膨らむのを防ぎます。
3. **隙間・端点の補完**：許容幅以下の隙間を併合し、辺端に近い区間を端まで延ばします。このため、小さな実開口を埋める可能性があります。
4. **開口の特定**：辺全体から壁あり区間を除き、壁なし区間とします。
5. **ドアの対応付け**：ドアも射影し、ドアごとに壁との共通部分を取ってから併合します。壁のない場所のドアは控除しません。両側の壁の隙間とドアが対応する場合だけ壁を補完し、警告を付けます。
6. **面積計算**：壁あり長[m]×2.4m − 控除ドア幅[m]×2.0mを求め、部屋ごとに集計します。ドア上部の0.4m分は壁として残ります。「×2」はドアの枚数ではなく高さです。

すべての中間結果（区間の位置・長さ・寄与した壁/ドアの id）を API レスポンスに含め、UI で根拠として提示します。

### 5-4. サンプルデータでの結果と妥当性確認

同梱11部屋の合計は、床面積 **48.75m²**、ドア控除後の壁面積 **155.54m²** です。LDは床面積21.27m²・壁面積41.46m²、Kは床面積6.25m²・壁面積15.57m²でした。

LD＋Kの床面積27.52m²に対し、図面記載のLDKは27.22m²で約1%の差があります。壁芯・内法などの境界基準や認識ずれが原因の候補ですが、原因は未確定です。この近さだけで実面積の精度を保証するものではありません。

LDとKの開放部分、階段とホール、ホールと玄関の境界には壁なし区間があります。再計算した面積・周長とJSON記載値の照合は `test/gpt-6/backend/analyzer/test_analyze.py::test_sample_file_results` で確認しています。

### 5-5. 許容誤差 `tolerance_px` について

サンプルでは壁線分と部屋輪郭のずれは最大でも 2〜3 px（壁の `lineWidth` 5 px の半分程度）でした。
既定値 10 px（≒ 14 cm）はこれを十分吸収しつつ、隣接する平行な壁（最短でも数十 px 離れる）を誤って
拾わない値として選びました。提出用の画面ではこの値も固定です。

### 5-6. R-treeによる候補検索と高速化

各部屋の辺と、すべての壁・ドアを毎回比較すると、辺がE本、線分がN本なら比較数はE×Nになります。そこで、位置の近い線分をまとめて探せる空間インデックスを使います。現在の実装はShapelyの **STRtree（R-tree系の構造）** です。

R-treeは、各線分を囲むx軸・y軸に平行な長方形を作り、近い長方形をさらに大きな長方形でまとめ、その集まりを階層化します。部屋の辺の近くを探すとき、上位の長方形が検索範囲と重ならなければ、その中の線分を一本ずつ確認する必要がありません。「遠い線分をまとめて除外する」のが高速化の理由です。

検索範囲の基準は部屋の中心ではなく、計算対象の1本の辺です。辺を囲む長方形を既定10pxと微小な丸め誤差対策分だけ上下左右へ広げ、x方向・y方向の両方で重なる候補を残します。斜めの辺では余分な候補も入るため、検索後に角度・垂直距離・射影区間で最終判定します。長方形が重なっただけでは、壁として採用しません。

壁・ドアそれぞれ64本未満なら木を作らず全件を調べます。木を使う場合も候補を元の入力順へ戻し、計算順序を維持します。検索時間は通常O(log N + k)（kは候補数）が目安ですが、領域が密集すると全件に近い候補が残ります。木の構築や候補の並べ替えにも時間がかかるため、最悪時の高速化を保証するものではありません。

同じ輪郭・許容条件の幾何結果はプロセス内で最大8件・合計16MiB・5分間キャッシュし、実寸へ換算して再利用します。画像本体はキャッシュしません。追加の端点イベント走査は、重複区間や多頂点輪郭で不要な比較を減らしますが、候補を上位だけに打ち切るビームサーチは使っていません。

高速化は変更前後の数値・ID・警告・配列順を比較して評価します。人工的な1,024頂点の図面で得た倍率を、同梱図面や画面表示全体の倍率とはみなしません。比較元・測定範囲・未達の目標は冒頭の検証資料に記録しています。

## 6. UI 設計において工夫した点

- **結果と根拠を連動**：表・図面から部屋を選び、辺番号や区間チップを使って計算に採用した線分まで追えます。壁・開口・ドアは色と線種で区別します。
- **式の意味を表示**：壁面積は「壁部分 − ドア控除」と示します。共有壁は両面計上、窓は控除対象外という前提も表示します。
- **確認すべきデータへ誘導**：未命名、壁不足、未対応ドア、JSON記載面積との差を警告します。表示名の変更は元JSONを変更せず、画面とCSVに反映します。
- **図面を見やすく操作**：全体・選択部屋へのフィット、追加ズーム、ドラッグ移動、レイヤー切替に対応します。表示倍率と実寸縮尺は別です。
- **狭い画面とキーボード操作**：スマホでは主要列を優先し、全項目表示へ切り替えられます。部屋・辺の選択はTabとEnterにも対応します。

起動直後のサンプルと使い方ページで操作を確認でき、ファイル切替後は固定条件で再計算します。UI改善時の検討は `docs/reviews/ui_dialogue.md` に記録しています。

## 7. フロントエンド / バックエンドの責務分担・API 設計の判断と理由

数値の計算・入力検証はFastAPIに集約し、Next.js / Reactは図面、表、計算式、CSVを担当します。別クライアントからも同じ計算を利用でき、表示変更で計算ロジックが分岐しない構成です。型はバックエンドのスキーマとフロントエンドのTypeScript定義を対応させます。

面積・射影・区間演算はPython、多角形の穴・重複・和集合はShapely/GEOSを使います。床面積はメッシュ近似ではなく頂点から求めます。描画はSVGで、専用の描画ライブラリは使いません。

APIはアップロードファイルを保存せず、結果と算出根拠を返します。元画像はクライアントにあるため解析レスポンスには含めません。丸めは表示時のみ行い、計算値は保持します。領域の扱いは [穴・重複・扉補完の仕様](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/geometry-upgrade.md) にまとめています。

## 8. 前提・制限事項と今後の拡張

- **共有壁は両面計上**：部屋ごとの内装面積を求めるため、隣接部屋のそれぞれに計上します。建物全体で壁を一度だけ数える定義とは異なります。
- **壁厚・柱型・窓・高さ差**：壁厚による床面積補正は未実装です。窓は控除せず、天井高とドア高は課題の固定値を使います。
- **小さな開口と近接辺**：許容幅以内の隙間を補完するため、小さな実開口を埋める可能性があります。同じ部屋の向かい合う辺が許容幅以内だと、同じ線分が両方に対応する場合があります。
- **不正輪郭・重複**：面積0、自己交差、不正な穴は警告付きで除外します。部屋間の重複は通知しますが、部屋別面積を自動で削減せず、和集合の面積を併記します。
- **入力・形状の前提**：NaN・無限大、不正な高さは拒否します。曲線は頂点列で近似された直線多角形として扱います。警告がないことは実図面に対する精度保証ではありません。

今後の候補は、境界基準と壁厚を確認したうえでの壁芯／内法変換、部屋別天井高、複数ファイル処理です。過去のコードレビューは `docs/reviews/` に保存しています。

## 9. AI の活用方法と開発ハーネス

AIは仕様整理・実装・検証に利用し、使用したプロンプトと判断を記録しています。課題要件を最終基準とし、提案をそのまま採用せず、計算根拠・テスト・差分レビューで確認する方針です。

Claude側は要件・テスト観点を整理し、Codexが実装、別セッションがレビューを担当する開発手順を用意しました。作業の役割と範囲は `.claude/agents/`、共通指示は `AGENTS.md`・`CLAUDE.md`、課題補足は `kadai.md` にあります。各担当を毎回すべて起動せず、独立した作業だけを分担します。

検証ゲートは終了コードで合否を判定します。リポジトリ直下で実行してください。

```bash
.claude/scripts/verify.sh quick  # pytest・型検査・Vitest
.claude/scripts/verify.sh all    # 上記と本番ビルド
```

通常の開発は `work/*` で進め、検証成功後に `feature/kimura` 宛てのPRと別セッションのレビューを経て統合します。mainへの反映は通常自動化せず、ユーザーの明示的な指示で行います。変更ファイル、実行コマンドと結果、未確認事項を報告し、実施していない検証を成功扱いしません。

再利用するプロンプトは `.claude/scripts/`、個別ログはGit管理外の `.claude/logs/`、公開する検討・レビュー記録は `docs/reviews/` に保存します。手順の詳細は [開発オーケストレーション](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/orchestration.md) を参照してください。自動テストは確認した条件での動作を検証するもので、壁芯・内法の定義や実ブラウザの見た目まで保証しません。

参考にした開発記事には [Anthropicのコンテキスト設計](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)、[Claude Codeの実践指針](https://code.claude.com/docs/en/best-practices)、[Mitchell HashimotoのAI活用記](https://mitchellh.com/writing/my-ai-adoption-journey) があります。幾何計算・高速化の参考文献と採用範囲は、本文からリンクした各検証資料を参照してください。

## 配置・運用

ローカルはNext.jsからFastAPIへ中継し、Composeでは両サービスをまとめて起動します。VercelはRoot Directoryを `floorplan-analyzer` とし、`vercel.json` のServicesでAPIをFastAPI、それ以外をNext.jsへ振り分けます。AWS用TerraformとCI/CDも同梱しています。環境ごとの確認範囲は [Vercelデプロイ記録](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/vercel-deployment.md) と [インフラ手順](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/infra/README.md) を参照してください。
