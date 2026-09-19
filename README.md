# 平面図 面積・壁面積 解析アプリ

> `main` ブランチには説明資料だけを置いています。アプリ本体は [feature/kimura](https://github.com/Kimurist2024/KKG-kadai/tree/feature/kimura) にあります。以下の起動手順は同ブランチをチェックアウトし、`floorplan-analyzer/` で実行してください（`.claude/scripts/` のコマンドだけはリポジトリ直下で実行します）。

公開サイト: https://floorplan-analyzer-taupe.vercel.app （2026-09-19 にデプロイし、同梱サンプルの解析結果がローカルと表示桁で一致することを HTTP で確認しました）

**部屋・壁・ドアのマスク JSON** を読み込み、部屋ごとの **床面積・周長・壁面積** を算出して、図面と表で確かめられる Web アプリです。

- フロントエンド: Next.js 16.3.5 / React 19.3.0 / TypeScript 5.9.3。図面は SVG で描画しています。
- バックエンド: Python / FastAPI / Pydantic 2 / Shapely 2.0 系。座標から面積を計算します。
- 配置: Vercel で公開し、Docker Compose と AWS ECS Fargate 用の Terraform も同梱しました。

README に収めなかった詳細は [設計の補足](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/design-notes.md) と [資料一覧](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/documents.md) にあります。

![概要画面](floorplan-analyzer/docs/images/screenshot_overview.png)
![部屋を選択した画面](floorplan-analyzer/docs/images/screenshot_room_detail.png)

## 1. 起動・操作

Python 3.12 と Node.js 22 を推奨します（Node.js は20.9以上）。`floorplan-analyzer/` で実行してください。初回は依存関係のセットアップも自動で行います。

```bash
./scripts/start.sh   # 起動後、http://localhost:5173 を開く
./scripts/stop.sh    # 停止
```

1. 「JSON ファイルを選択」を押すか、画面に JSON をドロップすると解析します。「サンプルで試す」で同梱のサンプルも開けます。
2. 図面か表から部屋を選ぶと、面積・周長と辺ごとの内訳を確認できます。
3. 拡大・ドラッグ・レイヤー切替で図面を確かめ、結果はCSVで保存できます。

計算条件は **天井高2.4m、ドア高2.0m、96.7px＝1.365m** に固定しています。Docker で動かす場合は `docker compose up --build`（画面は `http://localhost:3000`）です。

### UI設計で工夫した点

画面は「出てきた数値が正しいかを、利用者が自分で確かめられること」を軸に設計しました。

- **表と図面の連動**：表の行か図面の部屋を選ぶと、もう一方でも同じ部屋が強調されます。Escキーか「選択解除」で元に戻せます。
- **計算式と根拠の表示**：計算条件と式は常に表示し、部屋を選ぶと辺ごとに「壁あり・壁なし・ドア」の区間と、対応する線分のidを確認できます。
- **壁がない区間を見落とさない**：壁なしの長さを表で強調し、壁が見つからない部屋には「要確認」を付けて、確認事項の一覧から対象へ移動できます。
- **図面で確かめやすく**：元画像の上に部屋・壁・ドアを重ね、レイヤー切替・拡大・ドラッグと、選んだ部屋への表示合わせができます。
- **最初の画面は最小限に**：初期画面はドロップ領域と「サンプルで試す」だけに絞り、操作の流れは使い方ページ（`/guide`）にまとめました。
- **操作のしやすさ**：列の並べ替え、CSV保存、キーボードでの選択、狭い画面向けのレイアウトに対応しています。

## 2. 構成と役割

- `frontend/`：Next.js・React・TypeScript。図面、結果表、計算式、CSVを担当します。
- `backend/app/`：FastAPI。入力検証と幾何計算をここに集めています。
- `test/gpt-6/`：フロント・バックのテスト。`sample/`：同梱の図面。`docs/`：設計と検証の記録。
- `infra/terraform/`：AWS構成。`scripts/`：起動・停止・提出用zipのツール。`.claude/`：AI開発のスクリプトと役割の定義。

主要なAPIは `POST /api/analyze`（multipartの `file`）と `POST /api/analyze/json`（JSONボディ）の2つで、部屋別・全体の集計、各辺の区間と根拠になる線分のID、警告を返します。不正なJSONは400、容量超過は413、検証エラーは422です。仕様は起動後に `http://127.0.0.1:8000/docs` で確認できます。

環境ごとのAPIの経路とCIは [設計の補足](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/design-notes.md)、責務の詳細は [ARCHITECTURE](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/ARCHITECTURE.md)、課題要件との対応は [技術構成と検証状況](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/architecture.md)、AWSは [インフラ手順](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/infra/deployment.md) にあります。

### 構成上の判断と理由

- **フレームワーク**：課題の指定（フロントエンドはTypeScript、バックエンドはPython）に合わせ、応募要件にあるNext.jsとFastAPIを選びました。Pydanticの入力検証で、形式の合わないJSONを計算の前で止められます。
- **計算はすべてバックエンドに集める**：同じ式を画面側にも持つと二重に確かめることになるので、数値はすべてPythonで計算し、画面を動かさなくてもpytestだけで検証できるようにしました。
- **丸めるのは表示するときだけ**：途中で丸めると、部屋ごとの値を足した結果と全体の合計が合わなくなるためです。
- **APIは根拠まで返す**：画面は計算をやり直さず、受け取った区間と線分のIDをそのまま表示します。ファイル版は画面用、JSON版はテストや他のプログラム用です。
- **ブラウザは同一オリジンの `/api/*` だけを見る**：接続先はサーバー側の設定（`API_PROXY_TARGET`）で切り替えるので、環境が変わっても画面のコードは変わりません。
- **レスポンスに画像を含めない**：元画像はアップロードしたJSONの中にあり、ブラウザ側で取り出せます。送り返すと応答が大きくなるだけなので、幅と高さだけを返します。

## 3. 面積計算の考え方

### 床面積・周長

入力はまず、部屋（`isLine` が真でない輪郭）、壁（線分・`label_id=2`）、ドア（線分・`label_id=3`）に分けます。名前のない部屋も対象にしています。

床面積は、頂点の外積を順に足していく **シューレースの公式** で求めます。穴の面積は差し引き、周長は外周と穴それぞれの辺の長さを合計します。実寸への換算は、長さに `1.365/96.7` を、面積にはその二乗を掛けます。JSONに書かれている面積はそのまま使わず、頂点から計算し直しています。

### 壁面積・ドア控除

輪郭と壁線は完全には重ならないので、部屋の各辺に線分を投影して「辺のどの範囲に壁があるか」を区間として求めることにしました。

1. **対応付け**：角度差が10°以内で、壁線の両端が辺の延長線から10px以内なら射影し、辺からはみ出した部分を切り落とします。
2. **壁区間の整理**：重なりを併合し、極端に短いノイズを除いてから、小さな隙間と端点のずれを補います。
3. **開口の特定**：辺全体から壁のある区間を除いた残りを「壁なし」とします。
4. **ドア控除**：ドアごとに射影し、壁と重なる区間だけを控除します。両側の壁の隙間とドアが対応する場合は壁区間を補い、警告を出します。
5. **集計**：各辺の結果を部屋ごとに合計します。

`壁面積 = 壁あり長[m] × 2.4m − 控除ドア幅[m] × 2.0m`

ドア幅に掛けている2.0mは、枚数ではなく高さです。ドアの上部0.4m分は壁として残ります。採用した線分のIDと区間を保持しているので、図面・表・計算式のどこからでも根拠をたどれます。ドアを先にまとめず、壁との交差を1本ずつ取っているのは、対応しないドアのIDが混ざるのを防ぐためです。

## 4. R-treeによる高速化

![同じ線分a1・a2・a3を、配置図からR-treeの候補検索、最終判定まで追う流れ](floorplan-analyzer/docs/images/rtree-candidate-search-v2.png)

部屋の辺がE本、壁とドアの線分がN本あると、総当たりではE×N組の比較になります。これを減らすために、Shapelyの **STRtree（R-tree系の空間インデックス）** を使いました。

- 各線分を長方形で囲み、近いものどうしを大きな長方形にまとめた木です。検索範囲と重ならない長方形は、配下の線分ごと調べずに済みます。
- 検索の起点はいま計算している1本の辺で、その外接長方形を許容距離の10px分だけ広げて候補を取ります。壁として採用するかは、その後に角度・垂直距離・射影区間で判定します。
- 木を作る時間もかかるので、壁とドアがそれぞれ64本未満のときは全件を確認します。候補は元の入力順に並べ直し、計算の順序を変えていません。
- 同じ入力の幾何計算の結果は、最大8件・16MiB・5分間を上限に保持して使い回します。重なった区間の処理には端点イベント走査を入れました。候補を上位だけに絞る近似は入れていないので、結果は高速化の前と変わりません。

課題で配布されたJSONそのもので、変更前と現行を交互に101回測りました。初回解析は2.89ms→2.30ms（1.25倍）、設定を変えた再解析は2.90ms→0.88ms（3.3倍）で、結果はbit単位で一致します（[同梱JSONでの速度確認](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/validation/sample-speed/sample-speed.md)）。

図の読み方は [設計の補足](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/design-notes.md)、ほかの計測は [アルゴリズム性能検証](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/validation/algorithm-performance/report.md)、[計算結果を変えない高速化](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/validation/exact-speed/exact-speed.md)、[表示処理の性能検証](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/selection-performance.md) にあります。

## 5. 輪郭の基準と注意点

![部屋の輪郭が内法・壁芯を通る場合と認識ずれの比較](floorplan-analyzer/docs/images/room-boundary-wall-reference-v2.png)

今回は、入力された輪郭が囲む範囲をそのまま部屋の床とみなし、輪郭を内法（室内側の境界）として計算しています。同梱データの輪郭がどの基準で引かれているのか、壁厚がどれくらいなのかが、JSONからは分からないためです。

- **内法の場合**：今回の扱いと一致します。
- **壁芯の場合**：内法に直すには壁厚が必要で、今回の扱いでは床面積が内法より大きめに出ます。
- **認識ずれの場合**：輪郭と壁の対応関係と基準を確かめるところからになります。

壁厚が分からないまま推測で輪郭を動かすと誤差の原因が増えるだけなので、輪郭には手を加えていません。研究用に用意した補正（方向の正則化）は [幾何補正の説明](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/geometry-regularization.md) にあります。

- 壁は、向きがほぼ平行で辺から10px以内にある線分を対応付けます。共有壁は隣り合う部屋それぞれの内壁として両面を数え、窓は控除していません。
- 自己交差・面積0・不正な穴の輪郭は、警告を出して計算から外します。部屋どうしの重なりは、部屋別の面積をそのままにして和集合の面積を併記します。
- 「壁が足りない」という警告や対応率20%未満の表示は、目で確かめてほしい箇所の目印です。最後は図面と照らして確認する使い方を想定しています。

## 6. 検証・AIの活用

同梱の11部屋を合計すると **床面積48.75m²、壁面積155.54m²** になります。LD＋Kは27.52m²で、図面に書かれている27.22m²より約1%大きい値です。

この差は計算の誤りではなく、輪郭の引かれ方によるものだと考えています。頂点座標から求めた面積と周長はJSONに記載された値と表示桁まで一致し、高速化の前後で結果が完全に一致することもテストで確認しているからです。

同梱データには、隣り合う部屋の輪郭どうしが重なっている箇所が9か所あります（合計0.18m²で、床面積合計の約0.4%）。部屋別の床面積は入力どおりに表示し、合計には重複を除いた床面積（48.58m²）を併記して、図面には紫の斜線で示しました。

検証は、同梱サンプル・境界条件・変更前後の比較をpytestとVitestで行いました。公開図面を使った精度の確認は [外部図面での検証](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/validation/REPORT.md) にまとめています。

### 自分で判断・改善した点

コードの多くはAIに書かせましたが、どの案を採るか、出てきた結果が正しいかは自分で確かめて決めました。

- **入力欄をなくした**：天井高・ドア高・縮尺は課題文で決まっているので、入力させずに固定条件ですぐ解析する画面に作り直しました。使わなくなった画像AIの機能もコードごと外しています。
- **補正すべき対象を考え直した**：最初はドアの厚みの補正が要ると考えましたが、面積に効くのは壁のほうだと気づき、輪郭が壁のどこを通るかを図に整理しました（5章の図）。
- **高速化の順番と条件を決めた**：まず計測し、扉投影の重複をなくす→区間処理の改善→STRtree→結果の使い回し、の順を指定しました。区間の走査にいもす法の発想を使う案も出しています。条件は「計算結果が一切ずれないこと」で、これに合わないビームサーチは採用していません。
- **測り方を疑った**：複製で作った人工データは正しさを確かめようがないと考え、配布されたJSONで測り直しました。初回解析が3.02ms→3.88msと逆に遅くなっていたのが分かり、2.30msまで直しました。
- **同梱データ以外でも確かめた**：公開されている寸法つきの図面で検証しました（床面積の平均誤差はURの8区画で0.59%、小規模住宅の3区画で5.95%）。壁が見つからない部屋に警告を出すようにしたのは、この検証がきっかけです。
- **警告を座標で確かめた**：「部屋が重なっている」という警告が本当かをJSONの座標で確認し、実在したので、合計にだけ重複を除いた値を併記しました。強調表示も外接円から形に沿った縁取りに変えています。
- **AIの提案を見直した**：「初期表示でサンプルの結果を見せる」案は一度採用しましたが、実際の画面で見ると見栄えが悪かったので、人が選んだときだけ表示する形に戻しました。

### 使用したプロンプト

開発の初期に数回に分けて出した指示を、1つにまとめたものです。

> 添付の課題文（PDFとkadai.md）を要件定義として読み、これを満たすWebアプリを作ってほしい。応募要件にあるNext.js・FastAPI・Docker・Terraformなどは、このタスクで使えるところに使う。動くものができたら、より良くするためにオーケストレーションを組みたい。UI作成・アルゴリズム・Webリサーチを担当するサブエージェントを作るべきだと考えている。文章と計画の作成にはFable 5.1を使う。課題文は毎回最優先で読むこと。まず単体テストを作る。GitHubではブランチを分けて`feature/kimura`を作り、1サイクルごとにプルリクエストを出してCodexにレビューさせ、正しいと確認できたものだけを統合する。mainへの統合は、自分で動かして確かめてから行う。

ゴールは数値を出すことだけでなく、**採用した線分IDと区間を保持し、図面・表・計算式から根拠を追えること**に置きました。根拠をたどれない数値は、検証も修正もできないからです。

共通プロンプトは `.claude/scripts/`、役割は `.claude/agents/`、文章とmainへの反映の判断基準は `.claude/skills/`、レビューの記録は `floorplan-analyzer/docs/reviews/` に残しています。

### AIの使い方

AIの活用が認められている課題なので、コードを生成させること自体よりも**AIの出力を人が保証できる状態を先に作ること**を目標にしました。

- 画面・API・幾何計算で責務を分け、数値計算はPythonに集約して、計算の正しさを画面と切り離して確認できるようにしました。
- 守らせたい規約は文章で指示せず、`verify.sh`の終了コードで判定するゲートにしました。
- 実装は担当ごとに分け（UIはFable 5.1、バックエンドはCodex）、レビューは実装とは別のセッションのCodexに任せて、書き手と評価者を分けました。最後は課題要件と照らして人が採否を判断します。

### サブエージェントの体制と1サイクルの流れ

```mermaid
flowchart TD
    P["依頼：課題文を要件定義として実装"] --> M["司令塔：要件の分解・担当の割当・統合"]
    M --> R["Webリサーチ担当：調査のみ"] -.->|"調査結果"| M
    M --> UI["UI担当：Fable 5.1"] --> U["画面：入力・図面・結果表示"]
    M --> AL["アルゴリズム担当：実装はCodex"] --> G["API・Pythonの幾何計算"]
    U -->|"JSONを送信"| G -->|"数値・根拠・警告"| U
    G --> V["verify.sh：pytest・型検査・Vitest・ビルド"] --> RV["プルリクエスト・Codexレビュー"]
    RV -->|"OK"| F["feature/kimuraに統合"] --> H["課題要件と照らして人が確認し、mainに統合"]
```

### 検証の実行方法

初回は `floorplan-analyzer/` で `backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt` を実行してテスト用の依存を入れ、リポジトリ直下で検証します（仮想環境は起動スクリプトが作ります）。

```bash
.claude/scripts/verify.sh quick  # pytest・型検査・Vitest
.claude/scripts/verify.sh all    # 上記と本番ビルド
```

コードの変更は作業ブランチで検証し、レビューを経て `feature/kimura` に統合しています。mainへの反映は私が手動で行います（[開発手順](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/orchestration.md)）。

## 7. 参考文献

各資料の詳しい使い方は、引用している各文書（[資料一覧](https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/floorplan-analyzer/docs/documents.md) からたどれます）に書いています。

### 論文・解説記事

- Leutenegger ほか [STR: A Simple and Efficient Algorithm for R-Tree Packing](https://www.cs.odu.edu/~mln/ltrs-pdfs/icase-1997-14.pdf)（1997）：空間データを矩形でまとめて木にし、検索候補を絞るアルゴリズムの論文。Shapely の STRtree の基礎で、4章の候補検索の根拠にしました。
- Boncz ほか [MonetDB/X100: Hyper-Pipelining Query Execution](https://www.cidrdb.org/cidr2005/papers/P19.pdf)（CIDR 2005）：データベースの処理をベクトル単位にまとめて速くする論文。辺ごとの検索呼び出しを部屋の輪郭単位にまとめる発想に使いました。
- Amdahl [Validity of the Single Processor Approach to Achieving Large Scale Computing Capabilities](https://www.cs.cmu.edu/~18742/papers/Amdahl1967.pdf)（1967）：一部だけを速くしても全体の高速化には限りがあることを示した論文。速度は解析全体で測るという評価方針の根拠です。
- Liu ほか [Raster-to-Vector: Revisiting Floorplan Transformation](https://openaccess.thecvf.com/content_ICCV_2017/html/Liu_Raster-to-Vector_Revisiting_Floorplan_ICCV_2017_paper.html)（ICCV 2017）：ラスタ画像の平面図から部屋や壁のベクトル表現を復元する研究。研究用の幾何補正で「局所ではなく全体の接続関係で整える」考え方の参考にしました。
- Chen ほか [Floor-SP: Inverse CAD for Floorplans by Sequential Room-wise Shortest Path](https://openaccess.thecvf.com/content_ICCV_2019/html/Chen_Floor-SP_Inverse_CAD_for_Floorplans_by_Sequential_Room-Wise_Shortest_Path_ICCV_2019_paper.html)（ICCV 2019）：部屋ごとの最短経路探索で平面図の輪郭を求める研究。上と同じ考え方の参考にしました。
- Chen ほか [HEAT: Holistic Edge Attention Transformer for Structured Reconstruction](https://openaccess.thecvf.com/content/CVPR2022/html/Chen_HEAT_Holistic_Edge_Attention_Transformer_for_Structured_Reconstruction_CVPR_2022_paper.html)（CVPR 2022）：辺どうしの関係を全体で捉えて構造を復元する研究。上と同じ考え方の参考にしました。
- [いもす法の原著者による解説](https://imoz.jp/algorithms/imos_method.html)（2012）：区間の出入り口だけを記録して重なりを数える手法の解説。重複区間の走査で「開始・終了のイベントだけを見る」発想に使いました（被覆数ではなく区間 ID を保持する形に変えています）。

### 公式ドキュメント

- [pydantic_core.to_json](https://docs.pydantic.dev/latest/api/pydantic_core/#pydantic_core.to_json)：Pydantic の JSON 書き出し関数の仕様。キャッシュの書き出しに使いました。
- [OpenAI 公式 AGENTS.md ガイド](https://learn.chatgpt.com/docs/agent-configuration/agents-md)：Codex 向けの指示ファイルの書き方の仕様。開発ハーネスの設定に使いました。

### 検証に使った外部図面

- [UR 都市機構 S2 建築図 ver1.1](https://www.ur-net.go.jp/rd_portal/UR-BIM/jni4dd0000001wmv-att/03_kenchikuzu_S2_ver1.1.pdf)：1階の用途別色分図。L字を含む 8 区画を、同梱データ以外の図面での計算精度の検証に使いました。
- [Countryside Kenora / Candlewood Homes Mini Homes](https://b9f0a121-a2f4-4be4-a8a0-ebf384c417bf.filesusr.com/ugd/0dcb7e_6ad37e587a4b47f7baebde4c7abafb32.pdf)：寸法つきの小規模住宅（2寝室）の平面図。同じ検証に使いました。
