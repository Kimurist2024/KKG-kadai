# 平面図 面積・壁面積 解析アプリ

> `main` ブランチには説明資料を掲載しています。アプリ本体は [feature/kimura](https://github.com/Kimurist2024/KKG-kadai/tree/feature/kimura) を参照してください。以下の起動手順は同ブランチをチェックアウトし、`floorplan-analyzer/` を作業ディレクトリとして実行します（`.claude/scripts/` のコマンドはリポジトリ直下で実行）。

公開サイト: https://floorplan-analyzer-taupe.vercel.app （2026-09-18 に API 疎通を確認。画像 AI は無効。今回の確認では公開環境の解析処理・画面操作は再検証していません）

**部屋・壁・ドアマスク JSON** から、部屋ごとの **床面積・周長・壁面積** を算出する Web アプリです。
提出用の画面は JSON アップロードと固定条件での解析に絞っています。画像 AI の入力欄は表示しません。

- フロントエンド: Next.js 16.3.5 App Router / React 19.3.0 / TypeScript 5.9.3（`frontend/package-lock.json` の固定値）。図面は SVG で描画します。
- バックエンド: Python / FastAPI / Pydantic 2 / Shapely 2.0 系。Uvicorn で起動し、座標から面積を計算します。
- 公開用設定: Vercel Services で Next.js と FastAPI を分離。`/api/*` は FastAPI、それ以外は Next.js に振り分けます。
- 別の配置方法: Docker Compose と AWS ECS Fargate 用 Terraform を同梱。ローカル・Compose・AWS では Next.js の API プロキシを使います。
- 画像 AI: HTTPX 経由の OpenAI Responses API 呼び出しを任意機能として保持。通常画面には入力欄がなく、JSON 解析には AI 設定は不要です。

部屋選択時の表示処理の改善と計測結果は [性能検証](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/selection-performance.md) を参照してください。
面積・壁・扉の計算高速化と変更前後の全項目比較は [アルゴリズム性能検証](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/validation/algorithm-performance/report.md) を参照してください。
直前の実装を基準にした最新の高速化・浮動小数点の完全一致検証・論文調査は [計算結果を変えない高速化](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/validation/exact-speed/exact-speed.md) にあります。100倍の目標は未達です。
追加の5倍高速化に向けた [端点イベント走査の実測](floorplan-analyzer/docs/validation/interval-sweep/interval-sweep.md) では、人工的な1,024頂点の輪郭で初回解析が7.9〜11.1倍になりました。同梱図面はほぼ同速で、全入力で5倍の目標は未達です。

応募要件との対応と動作確認の範囲は [技術構成と検証状況](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/architecture.md)、AWS の手順は [インフラ手順](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/infra/deployment.md) を参照してください。

![概要画面](floorplan-analyzer/docs/images/screenshot_overview.png)
![部屋を選択した画面](floorplan-analyzer/docs/images/screenshot_room_detail.png)

---

## 1. 起動・操作

Python 3.12・Node.js 22 を推奨します（CI・Docker と同じ構成。Node.js の指定下限は20.9）。以下は `floorplan-analyzer/` で実行してください。

```bash
./scripts/start.sh   # 起動完了後、http://localhost:5173 を開く
./scripts/stop.sh    # 停止
```

起動時は8000/5173番を使用中のプロセスを停止し、依存関係のセットアップとサーバー起動を行います。独立した処理は並列化しています。JSON解析にAIキーは不要です。

1. 初回は同梱サンプルを表示します。操作説明は画面上部の「はじめての方へ」から確認できます。
2. 自分のJSONを選択またはドロップすると、固定条件で解析します。
3. 部屋を図面・表から選ぶと、面積・周長と辺ごとの内訳を確認できます。
4. 拡大・ドラッグ・レイヤー切替で図面を確認し、CSVで結果を保存できます。

計算条件は **天井高2.4m、ドア高2.0m、96.7px＝1.365m** です。表示倍率は計算値に影響しません。通常画面では画像AI入力と幾何補正を無効にしています。

ローカルのAPI疎通確認は `http://127.0.0.1:8000/api/health`、仕様は `http://127.0.0.1:8000/docs` です。8000番にはアプリ画面はありません。コンテナ起動は `docker compose up --build`（画面は `http://localhost:3000`）。Compose はホストへバックエンドの8000番を公開しません。

## 2. 構成と役割

- `frontend/`：Next.js・React・TypeScript。図面、結果表、計算式、CSVを担当。
- `backend/app/`：FastAPI。入力検証と幾何計算を一元化。
- `test/gpt-6/`：フロント・バックのテスト。`backend/benchmarks/`：性能比較。
- `sample/`：同梱図面。`docs/`：設計・参考文献・検証記録。
- `infra/terraform/`：AWS構成。`scripts/`：起動・停止ツール。

ブラウザは同一オリジンの `/api/*` に通信します。環境による経路の違いは次のとおりです。

| 環境 | API の経路 | 設定の根拠 |
|---|---|---|
| ローカル | Next.js :5173 → FastAPI :8000 | `scripts/start.sh`、`frontend/src/app/api/[...path]/route.ts` |
| Vercel | Services のルーティング → FastAPI（Next.js のプロキシを通さない） | `vercel.json` |
| Compose | Next.js :3000 → backend:8000 | `compose.yaml` |
| AWS（構成を同梱） | HTTPS ALB → Next.js :3000 → 同じタスクの FastAPI :8000 | `infra/terraform/app/main.tf` |

プロキシの接続先はサーバー側の `API_PROXY_TARGET` で指定します。旧単一Function用の `api/index.py` は互換用に残っていますが、現在の Vercel Services 設定では使用しません。アプリ直下の `requirements.txt` は `backend/requirements.txt` を参照します。

数値はバックエンドで計算し、表示時だけ丸めます。元画像はブラウザでも取り出して表示しますが、アップロードするJSON自体は画像データを含めてバックエンドに送信します。解析レスポンスには画像を含めません。座標・区間計算はPython、多角形の穴・重複・和集合はShapely/GEOSが担当します。

主要APIは `POST /api/analyze`（multipartの `file`）と `POST /api/analyze/json`（JSONボディ）です。部屋別・全体の集計に加え、各辺の区間と根拠ID、警告を返します。ファイル版は不正JSONを400、容量超過を413で通知し、形式・設定の検証エラーは422です。通常画面の条件は固定ですが、APIには条件指定・研究用幾何補正の設定が残っています。

GitHub Actions は Python/フロントエンドのテスト・本番ビルド・Compose疎通・Terraform検証を定義しています。AWS更新は main 対象の手動実行で、CI成功と環境設定が必要です。現在の説明資料だけの main では実行できず、コード・workflow の統合が前提です。構成ファイルの存在は AWS での稼働確認を意味しません。

詳しい責務は [ARCHITECTURE](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/ARCHITECTURE.md)、開発手順は [CONTRIBUTING](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/CONTRIBUTING.md)、環境変数・配置は [技術構成](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/architecture.md) と [インフラ手順](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/infra/deployment.md) を参照してください。

## 3. 面積計算の考え方

### 床面積・周長

入力を部屋（`isLine` が真でない輪郭）、壁（線分・`label_id=2`）、ドア（線分・`label_id=3`）へ分類します。未命名の部屋も対象です。

床面積は、頂点の外積を順番に足す **シューレースの公式** で求めます。穴の面積は差し引き、周長は外周と穴の各辺の長さを合計します。長さには `1.365/96.7`、面積にはその二乗を掛けて実寸へ換算します。JSON記載の面積をそのまま採用せず、頂点から再計算します。

### 壁面積・ドア控除

輪郭と壁線は完全には一致しないため、部屋の各辺へ線分を投影し、「辺のどの範囲に壁があるか」を区間として求めます。

1. **対応付け**：角度差10°以内、壁線の両端が辺の延長線から10px以内なら射影し、辺の外側を切り落とします。
2. **壁区間の整理**：重複を併合し、極短ノイズを除去してから、小さな隙間と端点のずれを補完します。
3. **開口の特定**：辺全体から壁あり区間を除いた部分を「壁なし」とします。
4. **ドア控除**：ドアごとに射影し、壁と重なる区間だけを控除します。両側の壁の隙間とドアが対応する場合は壁区間を補完し、警告します。
5. **集計**：各辺の結果を部屋ごとに合計します。

`壁面積 = 壁あり長[m] × 2.4m − 控除ドア幅[m] × 2.0m`

「×2」はドアの枚数ではなく高さです。ドア上部0.4m分は壁として残ります。採用した線分IDと区間を保持し、図面・表・計算式から根拠を追える設計です。ドアを先にまとめず、壁との交差を個別に取ることで、対応しないドアのIDが混ざるのを防ぎます。

## 4. R-treeによる高速化


![同じ線分a1・a2・a3を、配置図からR-treeの候補検索、最終判定まで追う流れ](floorplan-analyzer/docs/images/rtree-candidate-search-v2.png)

図の読み方：① 橙の輪郭の下辺が計算対象で、破線はその周囲の検索範囲です。A・B は壁そのものではなく、線分をまとめた領域です。② B は領域ごと、a3 は個別の外接長方形が重ならないため除外し、a1・a2 が候補に残ります。③ 同じ候補を精密に判定し、平行で近い a1 を採用、垂直な a2 を角度で除外します。配置・縮尺・木の分岐は説明用の模式図です。

辺がE本、壁・ドア線分がN本なら、全件比較はE×N組になります。これを減らすため、Shapelyの **STRtree（R-tree系の空間インデックス）** を使います。

各線分をx軸・y軸に平行な長方形で囲み、近い長方形を大きな長方形にまとめて階層化します。検索範囲と上位の長方形が重ならなければ、その中の線分を一本ずつ調べる必要がありません。遠い線分の集団をまとめて除外する仕組みです。

検索の基準は部屋の中心ではなく、計算対象の1本の辺です。その外接長方形を上下左右に10pxと微小な誤差対策分だけ広げ、x・y両方向で重なる候補を探します。これは候補の絞り込みにすぎず、最終的には角度・垂直距離・射影区間で対応を判定します。斜めの辺にも同じ手順を使います。

検索にかかる時間は通常O(log N＋k)（kは候補数）が目安ですが、線分が密集した配置ではほぼ全件が候補として残ります。木の構築や候補の並べ替えにも時間がかかるため、最悪の場合まで速くなるとは限りません。壁・ドアがそれぞれ64本未満のときは、木を作らずに全件を確認します。候補は元の入力順に並べ直してから処理し、計算の順序を変えないようにしています。

同じ入力の幾何結果は最大8件・16MiB・5分間、プロセス内で再利用します。追加の端点イベント走査では重複区間や多頂点輪郭の不要な比較を減らします。ビームサーチのように候補を上位だけに打ち切る近似は使いません。速度は比較元・入力・キャッシュ条件で変わるため、実測の範囲は冒頭の検証資料に分けて記録しています。

## 5. 輪郭の基準と限界

[図が表示されない場合はこちら](floorplan-analyzer/docs/images/room-boundary-wall-reference-v2.png)

![部屋の輪郭が内法・壁芯を通る場合と認識ずれの比較](floorplan-analyzer/docs/images/room-boundary-wall-reference-v2.png)

上の図はあくまで概念図です。同梱データの輪郭がどの基準で引かれているのか、実際の壁厚がどれくらいなのかは、今のところ分かっていません。輪郭が室内側（内法）を通っているのか、壁の中心（壁芯）を通っているのかで、必要になる処理は変わります。

- **内法の場合**：輪郭がそのまま室内の床面積を表しているので、壁厚による補正は原則として要りません。
- **壁芯の場合**：内法に直すには壁厚が必要です。壁のある辺を室内側へ寄せ、ずれた分だけ角を作り直すことになります。
- **認識ずれの場合**：そもそも輪郭が壁とうまく対応していない可能性があるので、まず対応関係と基準を確かめるところからです。原因を確かめないまま一律に動かすと、かえって誤差が大きくなることがあります。

紛らわしいのですが、壁芯から内法への変換と、認識誤差の修正はまったく別の話です。現在の通常画面では入力された輪郭をそのまま使って計算していて、壁厚による床面積の補正は行っていません。壁の対応付けに使う10pxという許容距離も、壁厚を表す値ではないので注意してください。研究用に用意した補正の実装については、[幾何補正の説明](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/geometry-regularization.md) にあります。

このほかにも、次のような制約があります。

- 共有壁は、隣り合う部屋それぞれの内壁として両面を数えます。窓は控除の対象にしていません。
- 小さな隙間を埋める処理を入れているため、実際にある開口まで塞いでしまうことがあります。また、平行な辺が近くに並んでいると、同じ線分が両方の辺に対応してしまう場合があります。
- 自己交差している輪郭、面積が0の輪郭、不正な穴は、警告を出したうえで計算から外します。部屋どうしが重なっている場合も警告しますが、部屋ごとの面積はそのままにして、重複を除いた和集合の面積を併記します。
- 「壁が足りない」という警告や、対応率が20%未満という表示は、あくまで目で確かめてほしい箇所の目印です。壁面積が0であることや、警告が出ないことが、実際の図面に対して正しいという保証にはなりません。

## 6. 検証・AIの活用

同梱11部屋の合計は **床面積48.75m²、壁面積155.54m²** です。LD＋Kは27.52m²で、図面記載27.22m²と約1%異なります。境界基準や認識ずれが原因の候補ですが未確定で、近い数値だけでは精度を保証できません。

UIは図面・表・辺番号を連動させ、警告から対象を確認できる構成です。ズーム、ドラッグ、CSV、狭い画面とキーボード操作に対応します。計算はサンプル、境界条件、変更前後の比較で検証し、高速化時も数値・ID・警告・配列順を確認します。

初期プロンプトの要旨と設計上の工夫（原文未確認のため、課題文・設計記録から再構成）：

出発点の依頼は「平面図の解析結果JSONから、部屋ごとの床面積・周長・壁面積を計算して画面で確認できるようにする」ことでした。ただし数値を出すだけでは足りず、**採用した線分IDと区間を保持し、図面・表・計算式から根拠を追えること**をゴールに置いています。JSON記載の面積をそのまま採用せず頂点から再計算する以上、根拠をたどれない数値は検証も修正もできないからです。

AIの活用が認められている課題なので、コードを生成させること自体よりも**AIの出力を人が保証できる状態を先に作ること**を目標にしました。そのために画面・API・幾何計算で責務を分け、数値計算はPythonに集約して、計算の正しさを画面の実装から切り離して確認できるようにしています。

守らせたい規約は文章で指示するのではなく、`verify.sh`の終了コードで判定するゲートに落としました。実装（Codex）とレビュー（別セッション）で書き手と評価者を分け、最後は課題要件と照らして人が採否を判断します。

```mermaid
flowchart TD
    P["依頼の要旨：JSONから面積を計算・可視化"] --> D["設計：表示と計算の責務を分離"]
    subgraph APP["アプリの構造"]
        U["画面：入力・図面・結果表示"] -->|"JSONを送信"| A["API：入力検証・計算の呼び出し"]
        A --> G["Python：幾何計算"]
        G -->|"数値・根拠・警告"| A
        A -->|"解析結果"| U
    end
    D -.-> U
    D -.-> A
    D -.-> G
    APP --> V["テスト・レビューで検証"]
    V --> H["課題要件と照合し、人が採否を判断"]
```

共通プロンプトは `.claude/scripts/`、役割は `.claude/agents/`、検討・レビュー記録は `floorplan-analyzer/docs/reviews/` に保存しています。未実施の検証を成功扱いにはしません。

初回は `floorplan-analyzer/` で `backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt` を実行し、テスト用依存も導入してください（仮想環境は起動スクリプトで作成）。その後、リポジトリ直下で検証します。

```bash
.claude/scripts/verify.sh quick  # pytest・型検査・Vitest
.claude/scripts/verify.sh all    # 上記と本番ビルド
```

通常のコード変更は作業ブランチで検証し、レビュー後に `feature/kimura` へ統合します。mainへの反映はユーザーの明示的な指示で行います。詳細は [開発手順](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/orchestration.md)、参考文献・追加検証は [資料一覧](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/documents.md) を参照してください。
