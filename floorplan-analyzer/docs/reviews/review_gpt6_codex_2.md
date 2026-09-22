**主要な修正は有効ですが、提出前に壁の補完処理、サンプル取得の競合、設定フォームのリセットを直すことを勧めます。** バックエンドの既存テスト35件とフロントエンドの型検査は成功しました。ファイルは変更していません。

**A. 前回の指摘1〜17の判定**

パスはリポジトリ相対です。「部分的に解消」は、元の指摘に含まれる問題が一部残っていることを示します。

| # | 判定 | 根拠となるファイル:関数と評価 |
|---|---|---|
| 1 | **部分的に解消** | `backend/app/analyzer.py:wall_intervals_on_edge` — ノイズ除去がスナップより前になった。ただし隙間併合は除去より前で、同じ tolerance が距離・併合・除去・延長を兼ねる問題は残る。 |
| 2 | **解消** | `backend/app/geometry.py:project_segments_onto_edge` — 線分長で正規化した外積による10度の角度判定を追加。逆向き線分も正しく採用する。両端点の距離を要求する仕様もdocstringに明記されている。 |
| 3 | **解消** | `backend/app/analyzer.py:door_intervals_on_edge` — 各ドアを壁へクリップしてから併合する。壁と重ならないドアIDの混入を防ぎ、回帰テストもある。 |
| 4 | **未対応** | `backend/app/analyzer.py:analyze_edge, door_intervals_on_edge` — ドア位置で壁線分が途切れる入力への対応はない。READMEには「壁上のドアのみ控除」とあるが、「入力壁はドア幅を含む」という契約は明確でない。仕様依存の懸念であり、無条件の誤計算とは判定しない。 |
| 5 | **部分的に解消** | `backend/app/schemas.py:Vertex, AnalysisSettings._check_heights`、`backend/app/analyzer.py:analyze_room, analyze` — 座標・設定の有限値、高さ相関、辺スキップのEPSを改善。自己交差・退化形状は受理し、穴は警告だけで計算を続ける。`Contour.area/perimeter`も有限値未検証。 |
| 6 | **部分的に解消** | `frontend/src/hooks/useAnalysis.ts:run, loadFile, loadSample` — 通常のファイル選択は世代管理され、ファイル・画像・結果も同時確定。ただしサンプルのfetchとそのcatchは管理外。旧結果を保持していることの表示もない。 |
| 7 | **部分的に解消** | `backend/app/analyzer.py:classify, _extract_segments, analyze` — 未知ラベルとゼロ長線分は除外。3頂点以上の線分は警告付きで先頭・末尾を結び、重複IDも警告だけなので、誤計算・選択衝突は残る。 |
| 8 | **解消** | `backend/app/analyzer.py:door_intervals_on_edge` — ドア断片の1px閾値をEPSへ変更。壁区間が同じなら、1px未満の正当な控除を保持する。壁側の頂点分割依存は#1として残る。 |
| 9 | **未対応** | `backend/app/analyzer.py:analyze_room, analyze_edge` — 各辺が全線分を独立採用し、同一室の近接平行辺への二重対応を解決していない。 |
| 10 | **部分的に解消** | `backend/app/geometry.py:complement_intervals, total_length, Interval` — 補集合の範囲外問題を修正し、合計の入力前提も明記。区間の逆転・非有限値は未検証。 |
| 11 | **部分的に解消** | `backend/app/main.py:analyze_upload, analyze_body` — 読み込み上限と同期処理のスレッド移行を実装。JSONルートのサイズ制限、受信段階・形状数の制限はない。提出物では残りの運用対策はLowでよい。 |
| 12 | **未対応** | `frontend/src/format.ts:roomsToCsv` — 部屋名の数式対策と単独CRのエスケープがない。 |
| 13 | **部分的に解消** | `UploadPanel.tsx:UploadPanel`、`RoomTable.tsx:RoomTable`、`FloorPlanView.tsx:FloorPlanView`、`App.tsx:App` — サンプルボタンのキー伝播、ソート、辺クリック、状態通知を改善。`RoomDetail.tsx:Chips, RoomDetail`は依然ホバー専用。 |
| 14 | **部分的に解消** | `SettingsPanel.tsx:parseDraft, update, submit`、`useAnalysis.ts:run` — 空欄・有限値・最小値・高さ相関を検証。ただしリセット不具合と下書きの再数値化があり、適用済み設定もレスポンスではなく送信値を保存。 |
| 15 | **部分的に解消** | `useAnalysis.ts:extractImageUrl` — 画像送信についてのコメントは正しくなった。`analyzer.py:analyze_edge, analyze_room, analyze`のレスポンス型との結合、型・既定値の重複は残る。課題では大規模な分離は不要。 |
| 16 | **部分的に解消** | `FloorPlanView.tsx:FloorPlanView`、`format.ts:bounds, labelPoint` — 静的描画データをメモ化し、spreadによる最大値計算も解消。ただし固定格子が内部点を一つも拾えない形状ではラベルが部屋外に残る。 |
| 17 | **部分的に解消** | `backend/tests/test_geometry.py, test_analyzer.py, test_api.py` — 角度・逆向き・ドアID・不変条件・入力検証などを追加。サンプル競合、フォーム、CSVのフロントテストと、頂点分割・近接辺・JSONルートの異常系が不足。 |

**B. 今回の修正箇所の重点確認**

**角度判定：現在の利用範囲では退行を確認しませんでした。**

`|u×v| / |v|` と `sin(10°)` の比較は、向きのない線分の平行性判定として妥当です。180度反転した線分を許容するのも正しい挙動です。既存の「約42度の斜線を除外」「反転線分を保持」のテストは成功しています。

長い線分の遠方端点が許容帯を外れると全体を除外しますが、これは現在明記されている採用条件です。辺との重なり部分だけで評価する仕様へ変える場合は、別の変更として扱うべきです。

**ドアのクリップ順序：修正は正しいです。**

実行確認した結果、ドアA=`[0,20]`、B=`[20,40]`、壁=`[0,10]`から、`[0,10] {A}`だけが返りました。`clip_intervals`自体は内部で併合しますが、今回は1ドアずつ呼び出すためID混入を再発させません。

なお、最終的な併合区間のID集合は「その区間のどこかに寄与したID」であり、「全位置で寄与するID」ではありません。現在のドア数・控除長の計算には問題ありません。

**世代管理：通常ファイル選択は改善、サンプル競合は未解消です。**

`loadSample`はfetch開始時に世代を進めません。次の順序で新しい入力が上書きされます。

1. サンプル取得Aを開始する。
2. ユーザーがファイルBを選択し、解析が完了する。
3. Aの取得が完了し、`loadFile(sample)`が新しい世代を取得してBを置き換える。

Aの取得失敗がBの成功後に届くと、Bの画面へAのエラーを表示する経路もあります。これは前回からの残存問題です。

**フォーム：新しい下書き管理にリセット不具合があります。**

初期の`settings`は`DEFAULT_SETTINGS`と同じオブジェクトです。入力を空欄にすると、無効値なので親の`settings`は変わりません。その状態で「既定値に戻す」を押しても同じオブジェクトを渡すだけで、`[settings]`のeffectは動かず、**空欄が残ったままエラー表示だけ消えます**。

また、有効な入力のたびに`onChange → 親更新 → toDraft`が走るため、`2.40`などの入力表記は数値化されて失われます。文字列の下書きを保持する修正としては不完全です。これらはコード上の状態遷移による確認で、ブラウザ操作テストは未実施です。

**追加した有限値検証にも、ルート間の不整合があります。**

同じNaN座標を送った実行結果は以下でした。

| 入力経路 | 結果 |
|---|---|
| multipart `/api/analyze` | **422** |
| JSON `/api/analyze/json` | **500** |

JSONルートでは検証エラーに含まれるNaNのシリアライズが失敗します。NaNはJSON仕様外ですが、この実装のパーサーは受理するため、400または422へ揃える必要があります。検証追加に伴うエラー経路の漏れであり、以前からHTTP結果が悪化したかまでは断定できません。

**C. 残っている改善点：重要度順**

以下のコードは変更案です。補助関数名のみの部分は実装方針を示しています。

**1. High — 壁の補完と測定を分ける**

**対象ファイル:関数名**  
[backend/app/analyzer.py:wall_intervals_on_edge](/Users/kimuraryuu/Downloads/課題（共有用）/floorplan-analyzer/backend/app/analyzer.py:83)

**問題**  
`tolerance=10`で、実行確認した結果は次のとおりでした。

- 壁`[0,40]`と`[48,100]` → `[0,100]`となり、8pxの開口を消す。
- ノイズ`[9,10]`と`[19,20]` → 先に併合され、スナップ後は`[0,20]`になる。

ノイズ除去をスナップより前へ移しただけでは、補完による膨張を防げません。短い辺への分割でも結果が変わります。

**提案（コード例）**  
まず観測された区間の和集合を基本にし、補完は独立した設定にします。

```python
raw = g.project_segments_onto_edge(a, b, wall_segments, distance_tolerance_px)
walls = g.merge_intervals(raw)  # 初期方針：隙間充填・端点延長なし
```

ノイズ判定を残すなら、辺へのクリップ後の長さではなく元線分の品質で判定してください。

**2. High — サンプル取得を含めて操作開始時に世代を確保する**

**対象ファイル:関数名**  
[frontend/src/hooks/useAnalysis.ts:loadSample, run](/Users/kimuraryuu/Downloads/課題（共有用）/floorplan-analyzer/frontend/src/hooks/useAnalysis.ts:47)

**問題**  
サンプル取得の成功・失敗が新しい操作を上書きします。取得中のloading表示もありません。

**提案（コード例）**  
`run`を、世代を増やさず受け取った操作を完了させる関数に変更します。

```tsx
const op = beginOperation(); // 世代更新・abort・loading設定
try {
  const res = await fetch(sampleUrl, { signal: op.ctrl.signal });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const blob = await res.blob();
  if (!isCurrent(op)) return;
  await runWithin(op, new File([blob], "sample_mask.json"), settings);
} catch (e) {
  if (isCurrent(op)) setStatus({ state: "error", message: String(e) });
}
```

`isCurrent`は世代一致と`!signal.aborted`を確認し、アンマウントでも世代を無効化します。旧結果を残す場合は「前回成功した解析結果」と表示してください。

**3. High — 不正形状を正常な面積として返さない**

**対象ファイル:関数名**  
`backend/app/schemas.py:Contour, MaskFile`  
`backend/app/analyzer.py:analyze`

**問題**  
自己交差する蝶ネクタイ形状を送ると、**HTTP 200・床面積0**になりました。穴付き形状も警告だけで外周面積を返します。重複IDはドア数や部屋選択を壊し、3頂点以上の線分は存在しない直線へ置き換えられます。

**提案（コード例）**  
未対応形状を広く実装するより、入力契約を狭くして拒否する方が課題に適しています。

```python
@model_validator(mode="after")
def validate_shape(self):
    if self.holes:
        raise ValueError("holes は未対応です")
    if self.isLine:
        if len(self.vertices) != 2:
            raise ValueError("線分は2頂点で指定してください")
    else:
        validate_simple_polygon(self.vertices)
    return self
```

`validate_simple_polygon`で重複点の正規化、有効頂点数、面積、非隣接辺の交差を確認します。IDの一意性は`MaskFile`で検証します。

**4. Medium — フォームの下書きとリセットを明示的に管理する**

**対象ファイル:関数名**  
[frontend/src/components/SettingsPanel.tsx:SettingsPanel, update](/Users/kimuraryuu/Downloads/課題（共有用）/floorplan-analyzer/frontend/src/components/SettingsPanel.tsx:37)

**問題**  
Bで示したリセット失敗と、有効な入力のたびに文字列表記が失われる問題があります。

**提案（コード例）**

```tsx
const reset = () => {
  setDraft(toDraft(DEFAULT_SETTINGS));
  setError(null);
  onChange({ ...DEFAULT_SETTINGS });
};
```

通常編集中はdraftを維持し、親への有効値通知によってdraftを上書きしない設計にしてください。単純化するなら、draftをローカルで保持して送信時だけ親へ反映し、再計算可否もdraftの解析値と適用済み値から判断します。

`noValidate`自体は欠陥ではありません。現在は独自検証で空欄・下限をチェックしています。ただし`step`は検証していないため、刻み幅を制約にするか単なる操作補助にするかは統一してください。

**5. Medium — JSONルートでも安全な422を返す**

**対象ファイル:関数名**  
`backend/app/main.py:analyze_body, _parse_mask`  
`backend/app/schemas.py:Contour`

**問題**  
JSONルートの検証エラーがNaNを含むと500になります。入力メタデータの`area/perimeter`も通常のfloatのままです。

**提案（コード例）**

```python
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc):
    return JSONResponse(status_code=422, content={
        "detail": [
            {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]}
            for e in exc.errors()
        ]
    })
```

```python
area: Optional[FiniteFloat] = None
perimeter: Optional[FiniteFloat] = None
```

エラー情報から非有限値を含み得る`input`・`ctx`を除き、両ルートに同じ異常系テストを追加します。

**6. Medium — 同一室の近接辺への二重対応を検出する**

**対象ファイル:関数名**  
`backend/app/analyzer.py:analyze_room, analyze_edge`

**問題**  
`tolerance=10`、平行辺が`y=0`と`y=5`にある場合、`y=0`の壁1本が両辺で100pxずつ採用されることを確認しました。

**提案（コード例）**

```python
candidates = collect_candidates(room_edges, segments)
assignments = resolve_overlapping_candidates(
    candidates,
    prefer_smallest_distance=True,
)
```

同一線分の同じ部分が複数辺へ対応する場合に限定して解決します。課題規模では、曖昧な対応を警告する実装から始めてもよく、単純な「1線分＝1辺」制約は避けてください。

**7. Medium — CSVの文字列列を安全に出力する**

**対象ファイル:関数名**  
`frontend/src/format.ts:roomsToCsv`

**問題**  
部屋名の`=1+1`などが数式として解釈され得ます。単独CRも未エスケープです。

**提案（コード例）**

```ts
const safeName = (s: string) =>
  /^[\s\u0000-\u001f]*[=+\-@]/.test(s) || /^[\t\r\n]/.test(s)
    ? "'" + s : s;

const esc = (s: string) =>
  /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;

// 部屋名だけ safeName(r.name) を適用してからCSVエスケープ
```

**8. Medium — 詳細操作のキーボード・タッチ対応を完成させる**

**対象ファイル:関数名**  
`frontend/src/components/RoomDetail.tsx:Chips, RoomDetail`  
`frontend/src/components/UploadPanel.tsx:UploadPanel`

**問題**  
辺・区間の強調がホバー専用です。アップロード領域も、ボタン相当要素の中に別ボタンを置く構造が残っています。

**提案（コード例）**

```tsx
<button
  type="button"
  onFocus={() => onHoverSegments(iv.ids)}
  onBlur={() => onHoverSegments([])}
  onClick={() => onHoverSegments(iv.ids)}
>
  {label}
</button>
```

辺にも操作ボタンを設け、アップロードとサンプルは兄弟のnative buttonへ分けます。

**9. Medium — 今回の修正を守る小さな回帰テストを追加する**

**対象ファイル:関数名**  
`backend/tests/test_analyzer.py, test_api.py`  
`frontend/src/hooks/useAnalysis.ts:useAnalysis`  
`frontend/src/components/SettingsPanel.tsx:SettingsPanel`

**問題**  
35件は成功しましたが、今回確認した不具合を検出できません。

**提案（コード例）**

```python
@pytest.mark.parametrize("route", ["/api/analyze", "/api/analyze/json"])
def test_non_finite_input_returns_client_error(route):
    response = post_raw_invalid_mask(route)
    assert response.status_code in (400, 422)
```

フロントでは少なくとも「サンプルA→ファイルB→A完了／失敗」「空欄→既定値に戻す」を追加します。幾何では短辺への頂点追加、近接平行辺、併合される複数ノイズを手計算可能な入力で検証してください。

**10. Low — ドア位置の壁表現を入力契約として明文化する**

**対象ファイル:関数名**  
`backend/app/analyzer.py:door_intervals_on_edge`  
`README.md:5-3, 8`

**問題**  
ドア位置に壁線分がない場合、垂れ壁も計上されません。入力の意味が確定しないまま壁を復元するのも危険です。

**提案（コード例）**

```python
# 入力契約：壁線分はドア幅を含む総壁長を表す。
# ドア線分は、その壁から控除する開口幅を表す。
```

課題データがこの契約を満たすことを確認し、READMEとテストへ明記すれば十分です。複数エンコーディング対応は必須ではありません。

**11. Low — ラベルの内部点フォールバックを保証する**

**対象ファイル:関数名**  
`frontend/src/format.ts:labelPoint`

**問題**  
幅1pxのU字形状では、格子が内部点を拾えず、返された`(50, 33.72…)`は部屋外でした。実行確認済みです。

**提案（コード例）**

```ts
if (bestD < 0) {
  return interiorPointByScanline(pts);
}
return best;
```

水平走査線の内部区間の中点など、細い領域でも内部点を得られる方法をフォールバックにします。全面的な描画方式変更は不要です。

**12. Low — 設定・区間契約・運用上限を必要な範囲で揃える**

**対象ファイル:関数名**  
`useAnalysis.ts:run`、`geometry.py:Interval`、`main.py:analyze_upload, analyze_body`

**問題と提案（コード例）**

- 適用条件は送信値ではなくレスポンスから取得します。

  ```tsx
  const {
    ceiling_height_m, door_height_m, scale_px, scale_m, tolerance_px,
  } = result.settings;
  const applied = {
    ceiling_height_m, door_height_m, scale_px, scale_m, tolerance_px,
  };
  ```

- 区間の入力契約を生成時に検証します。

  ```python
  def __post_init__(self):
      if not all(map(math.isfinite, (self.start, self.end))):
          raise ValueError("区間端点は有限値である必要があります")
      if self.end < self.start:
          raise ValueError("区間が逆転しています")
  ```

- 外部公開する場合に、両ルートの受信サイズと形状数の上限を揃えます。

  ```python
  if total_vertices > MAX_TOTAL_VERTICES:
      raise HTTPException(413, "頂点数が上限を超えています")
  ```

プロキシ制限、プロセス分離、空間インデックス、Worker化、API型生成、内部モデルの全面分離は、採用課題の提出前には優先しなくてよいです。READMEのテスト件数「22件」と、旧スナップ・除去順序の説明は現状へ更新してください。

**検証結果**

| 検証 | 結果 |
|---|---|
| 指定のpytestコマンド | 標準出力キャプチャ用の一時ファイルを作れず、起動時に失敗 |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -s -p no:cacheprovider` | **35 passed in 0.22s** |
| `node node_modules/typescript/bin/tsc --noEmit` | **成功** |
| 追加のメモリ上での実行確認 | 壁の過剰補完、近接辺の二重対応、自己交差の受理、JSONルートの500、ラベルの部屋外配置を確認 |
| ブラウザ操作・フロントの振る舞いテスト | 未実施。競合とフォームは静的レビューによる判定 |

変更前のソース履歴は参照できなかったため、退行の判定は前回レビュー文書と現在のコードの比較に基づいています。