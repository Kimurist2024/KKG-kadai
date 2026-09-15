貼付コードを対象にした静的レビューです。ファイルの参照・変更、テスト実行は行っていません。優先して修正すべき点は、**tolerance による壁の過剰補完、ドア ID の誤った引き継ぎ、ファイル読み込みの競合**です。ドアと壁の入力表現に依存する点は、確定的なバグと分けて記載します。

1. **[High] 同じ tolerance が壁の検出・補完・削除を兼ねており、壁なし区間を消してしまう**

   **対象ファイル:関数名**  
   `backend/app/analyzer.py:wall_intervals_on_edge`  
   `backend/app/geometry.py:merge_intervals, snap_to_edge_ends, drop_short`

   **問題**  
   `tolerance_px=10` は、直線との距離だけでなく、隙間の充填、端点の延長、短区間の削除にも使われます。UI の説明からは、面積を増減させる処理まで含むことが分かりません。

   例えば、100 px の辺に壁 `[0,40]` と `[48,100]` があると、実在する 8 px の開口を壁として埋めます。また、壁 `[9,10]` は先に `[0,10]` へスナップされるため、1 px のノイズが短区間除去を通過します。一方、辺の途中にある正当な 9 px の壁は削除されます。

   **提案（コード例）**  
   許容距離と形状補完の設定を分け、まず補完なしの測定を基本にします。短区間を除くなら、補完前に判定してください。

   ```python
   class GeometryPolicy:
       distance_tolerance_px: float = 10.0
       gap_fill_px: float = 0.0
       endpoint_snap_px: float = 0.0
       min_support_px: float = 0.0

   raw = g.project_segments_onto_edge(a, b, segments, policy.distance_tolerance_px)
   observed = g.merge_intervals(raw)
   observed = g.drop_short(observed, policy.min_support_px)

   inferred = g.merge_intervals(observed, policy.gap_fill_px)
   inferred = g.snap_to_edge_ends(inferred, length, policy.endpoint_snap_px)
   ```

   補完を有効にする場合は、観測区間と補完区間を区別して返し、補完による面積差を表示すると検証しやすくなります。

2. **[High] 両端の距離だけでは、辺に沿う線分か判定できない**

   **対象ファイル:関数名**  
   `backend/app/geometry.py:project_segments_onto_edge`

   **問題**  
   両端が許容帯内にあることは、平行であることを保証しません。水平辺に対して `(40,-9)→(60,9)` は tolerance 10 で採用され、約42度傾いた線分が20 pxの壁になります。

   完全に垂直な線分は射影長がゼロになるため除外されますが、短い斜めの接合線は残ります。逆に、非常に長い線分では、辺の近傍部分が沿っていても遠方の端点が許容帯を外れるだけで全体が除外されます。

   **提案（コード例）**  
   距離・角度・有効な射影長を独立して評価します。角度閾値は入力の誤差特性に合わせて決めてください。

   ```python
   vx, vy = q[0] - p[0], q[1] - p[1]
   segment_length = math.hypot(vx, vy)
   if segment_length <= eps_px:
       continue

   sin_angle = abs(ux * vy - uy * vx) / segment_length
   if sin_angle > math.sin(math.radians(angle_tolerance_deg)):
       continue

   # この後で距離判定と [0, edge_length] へのクリップを行う
   ```

   長い線分を扱う場合は、「入力線分全体の一致」を要求するのか、「辺と重なる部分の一致」を要求するのかも仕様にしてください。

3. **[High] 区間併合によって、実際には重ならないドア ID が控除対象へ混入する**

   **対象ファイル:関数名**  
   `backend/app/analyzer.py:door_intervals_on_edge, analyze_room, analyze`  
   `backend/app/geometry.py:merge_intervals, clip_intervals`

   **問題**  
   `merge_intervals` は ID の集合を区間全体に付けます。その後クリップすると、切り落とされた位置にしか存在しなかった ID まで残ります。

   例として、ドア A=`[0,20]`、B=`[20,40]`、壁=`[0,10]` の場合、先に併合されたドア `[0,40] {A,B}` が `[0,10] {A,B}` になります。B は壁と重ならないのに、`door_count=2` となり、未対応ドアの警告も出ません。

   **提案（コード例）**  
   **各入力ドアをクリップしてから**控除長の和集合を作ります。

   ```python
   raw = g.project_segments_onto_edge(a, b, door_segments, tolerance_px)

   contributions = []
   for door in raw:
       contributions.extend(g.clip_intervals([door], walls))

   used_ids = {sid for iv in contributions for sid in iv.ids}
   deduction_intervals = g.merge_intervals(contributions)
   ```

   面積計算用の和集合と、位置ごとの寄与 ID は別のデータにするのが安全です。詳細な対応関係が必要なら、境界点で区間を分割し、各部分区間に正確な ID 集合を持たせてください。

4. **[High] ドア位置で壁線分が途切れる入力では、ドア上部の壁面積を計上できない**

   **対象ファイル:関数名**  
   `backend/app/analyzer.py:door_intervals_on_edge, analyze_edge`  
   `backend/tests/test_analyzer.py:test_door_on_open_section_is_not_deducted_and_warned`

   **問題**  
   これは**入力仕様に依存する問題**です。

   現実装は、ドア幅にも壁線分が存在することを前提にしています。例えば壁 `[0,40]` と `[60,100]`、ドア `[40,60]` の表現では、ドア部分を高さ全体の開口とみなします。ドア上に壁があるなら、本来必要な `20 px × mpp × (2.4−2.0)` が計上されません。

   既存テストは現実装の方針を固定していますが、その方針が入力データの意味と一致するかはコードから確認できません。

   **提案（コード例）**  
   入力契約として、壁がドア幅を含むのかを明文化します。含まない場合は、境界に対応付けられたドアを使って壁の総延長を復元します。

   ```python
   if policy.wall_encoding == "continuous_through_doors":
       gross_intervals = walls
       deductible = g.clip_intervals(assigned_doors, walls)
   else:
       gross_intervals = g.merge_intervals([*walls, *assigned_doors])
       deductible = g.merge_intervals(assigned_doors)

   gross = g.total_length(gross_intervals) * mpp * ceiling_height
   net = gross - g.total_length(deductible) * mpp * door_height
   ```

   `assigned_doors` は距離・角度・部屋境界との対応を確認したものに限定します。壁線分が未検出であることと、実際に壁が存在しないことも区別して表示すべきです。

5. **[High] 非有限値、不正な高さ関係、退化多角形を受け入れてしまう**

   **対象ファイル:関数名**  
   `backend/app/schemas.py:Vertex, AnalysisSettings, Contour`  
   `backend/app/analyzer.py:analyze, analyze_room`  
   `backend/app/geometry.py:polygon_area, polygon_perimeter`

   **問題**  
   以下が未検証です。

   - `door_height_m > ceiling_height_m` により壁面積が負になる。
   - 座標などの `NaN`・無限大が計算やレスポンス生成を壊す。
   - 3頂点以上でも、全点一致・一直線・自己交差した部屋が通る。
   - 非空の `holes` が無視され、穴のある部屋の床面積を過大評価する。
   - 幾何関数のゼロ長基準と部屋の辺スキップ基準が異なり、周長と辺長合計が微小にずれる。

   自己交差図形ではシューレース公式の絶対値を取っても、意図した床領域の面積にはなりません。

   **提案（コード例）**  
   スカラー検証と形状検証を分けます。

   ```python
   from pydantic import FiniteFloat, model_validator

   class Vertex(BaseModel):
       x: FiniteFloat
       y: FiniteFloat

   # AnalysisSettings 内。数値フィールドも FiniteFloat に変更する。
   @model_validator(mode="after")
   def validate_heights(self):
       if self.door_height_m > self.ceiling_height_m:
           raise ValueError("ドア高さは天井高以下にしてください")
       return self
   ```

   多角形は連続重複点・末尾の閉じ点を正規化したうえで、有効頂点数、自己交差、面積を検証し、面積・周長・辺解析すべてで同じ点列を使ってください。穴を実装しない場合は、非空の `holes` を明示的に拒否します。

   追加したモデル検証の例外は、`settings_from_query` でも明示的に422へ変換する必要があります。

6. **[High] ファイル読み込みの競合により、ファイル名・画像・結果が別の入力になる**

   **対象ファイル:関数名**  
   `frontend/src/hooks/useAnalysis.ts:loadFile, runAnalysis, loadSample`

   **問題**  
   キャンセルは `runAnalysis` に入ってから行われます。A の画像抽出中に B を選び、B の抽出が先に終わると、遅れて完了した A が B の解析を中断して結果を上書きできます。

   また、新ファイル選択時に旧 `result` が残るため、新画像と旧解析結果を重ねて表示します。新解析が失敗すると、その不整合が残ります。サンプル取得も同じ競合管理の外にあります。

   **提案（コード例）**  
   ユーザー操作開始時に世代を更新し、ファイル・画像・結果を一つの成功スナップショットとして確定させます。以下はフック内への組み込み例です。

   ```tsx
   const generation = useRef(0);

   async function loadFile(f: File) {
     const id = ++generation.current;
     abortRef.current?.abort();
     const ctrl = new AbortController();
     abortRef.current = ctrl;
     setStatus({ state: "loading" });

     try {
       const [imageUrl, result] = await Promise.all([
         extractImageUrl(f),
         analyzeFile(f, settings, ctrl.signal),
       ]);
       if (id !== generation.current || ctrl.signal.aborted) return;

       setSnapshot({ file: f, imageUrl, result });
       setStatus({ state: "idle" });
     } catch (e) {
       if (id !== generation.current || ctrl.signal.aborted) return;
       setStatus({ state: "error", message: (e as Error).message });
     }
   }
   ```

   サンプル取得・再計算にも同じ世代管理を適用します。旧結果を残す場合は「前回の結果」と明示し、アンマウント時にも中断してください。

7. **[Medium] 未知ラベルを壁として計算し、不正な線分・重複 ID も受け入れる**

   **対象ファイル:関数名**  
   `backend/app/analyzer.py:classify, _segment_of, _extract_segments`  
   `backend/app/schemas.py:MaskFile, Contour`

   **問題**  
   `classify` は `isLine=True` かつドア以外のすべてを壁に分類します。要件の `label_id=2` より広く、未知ラベルで面積が増えます。

   また、3頂点以上の線は先頭・末尾だけを結んでしまい、ゼロ長線も本数に含まれます。ID 重複はドア数の過少計上、React の key 衝突、複数部屋の同時選択につながります。

   **提案（コード例）**

   ```python
   if c.isLine:
       if c.label_id == LABEL_WALL:
           walls.append(c)
       elif c.label_id == LABEL_DOOR:
           doors.append(c)
       else:
           warnings.append(f"未知の線分ラベル: id={c.id}, label={c.label_id}")
   else:
       rooms.append(c)
   ```

   入力境界で「線分はちょうど2頂点」「長さが正」「ID が一意」を検証します。ID が種類ごとにしか一意でない仕様なら、API とフロントエンド双方で `(kind, id)` を識別子にしてください。

8. **[Medium] 1 px 未満のドア控除を落とすため、頂点の分割方法で計算結果が変わる**

   **対象ファイル:関数名**  
   `backend/app/analyzer.py:door_intervals_on_edge, analyze_room`

   **問題**  
   `drop_short(..., min_length_px=1.0)` は、壁との交差後に適用されます。正当な部分重なりも削除します。

   例えば幅1.5 pxのドアは、一直線の辺上なら残りますが、途中に部屋頂点を追加して0.75 pxずつに分かれると両方削除されます。物理的に同じ形でも頂点表現で面積が変わります。壁の短区間除去にも同種の問題があります。

   **提案（コード例）**  
   元の検出線分に対するノイズ判定と、交差演算の微小量除去を分けます。

   ```python
   clipped = g.clip_intervals(raw_doors, walls)
   return [iv for iv in clipped if iv.length > EPS_PX]
   ```

   最小ドア幅を設けるなら、辺ごとの断片ではなく、元ドアまたは部屋単位の対応長で判定してください。

9. **[Medium] 近接した複数の辺へ同じ線分が対応付けられる**

   **対象ファイル:関数名**  
   `backend/app/analyzer.py:analyze_room, analyze_edge`  
   `backend/app/geometry.py:project_segments_onto_edge`

   **問題**  
   各辺が全線分を独立して採用します。幅が tolerance より小さい細い部屋などでは、一方の壁が反対側の辺にも採用され得ます。ドアも同様です。

   共有壁を隣接する2部屋の内壁面として数えることは正当ですが、同じ部屋の近接した別境界への重複対応とは別の問題です。

   **提案（コード例）**  
   部屋単位で候補を作り、曖昧な対応を解決する段階を設けます。

   ```python
   candidates = collect_candidates(room_edges, segments, policy)
   assignments, warnings = resolve_candidates(
       candidates,
       allow_shared_between_rooms=True,
   )
   ```

   比較には距離・角度・重なり長を使います。一つの長い壁が連続する複数辺を覆う場合もあるため、単純な「線分ごとに1辺」制約ではなく、重なる部分ごとに解決してください。

10. **[Medium] 区間関数の入力契約が曖昧で、補集合が辺の外へはみ出す**

    **対象ファイル:関数名**  
    `backend/app/geometry.py:Interval, complement_intervals, total_length`

    **問題**  
    `complement_intervals([Interval(20,30)], 10)` は `[0,20]` を返します。現在の主要経路では射影時にクリップされますが、汎用関数としては前提が隠れています。

    `Interval` は逆転・非有限値を保持でき、`length` が逆転をゼロとして隠します。`total_length` も、重なる区間を渡すと重複計上します。

    **提案（コード例）**  
    区間の整合性は生成時に検証し、補集合の前には必ず対象領域へクリップします。

    ```python
    def complement_intervals(intervals, edge_length):
        if not math.isfinite(edge_length) or edge_length < 0:
            raise ValueError("辺長が不正です")

        covered = clip_intervals(intervals, [Interval(0.0, edge_length)])
        out, cursor = [], 0.0
        for iv in covered:
            if iv.start > cursor + EPS_PX:
                out.append(Interval(cursor, iv.start))
            cursor = iv.end
        if cursor < edge_length - EPS_PX:
            out.append(Interval(cursor, edge_length))
        return out
    ```

    `total_length` は「正規化済み区間の合計」と明示するか、`union_length` を別に用意します。浮動小数点用の EPS とセグメンテーション許容誤差は分離してください。

11. **[Medium] アップロード制限が全読み込み後にしか働かず、JSON API では制限がない**

    **対象ファイル:関数名**  
    `backend/app/main.py:analyze_upload, analyze_body, _parse_mask`  
    `backend/app/analyzer.py:analyze`

    **問題**  
    `await file.read()` は上限確認前に全データをメモリへ読みます。JSON ボディ版には同じサイズ制限がありません。

    また、アップロードの `async` ハンドラ内で同期の JSON 解析・幾何計算を実行し、イベントループを占有します。計算量は概ね全辺数×全線分数で増え、入力バイト数だけでは処理負荷を制限できません。

    **提案（コード例）**

    ```python
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "ファイルサイズが上限を超えています")
    ```

    これに加えて、両ルート共通の受信サイズ制限をプロキシまたは ASGI 層で設け、輪郭数・総頂点数にも上限を設けます。上の修正だけでは multipart 受信処理自体のサイズは制限できません。

    同期処理はワーカーへ移します。

    ```python
    def parse_and_analyze(raw, settings):
        return analyze(_parse_mask(raw), settings)

    return await run_in_threadpool(parse_and_analyze, raw, settings)
    ```

    CPU 負荷が大きい運用ではプロセス分離も検討します。幾何計算側では、許容距離分広げた辺の bounding box で候補線分を絞ると改善できます。

12. **[Medium] CSV の部屋名が表計算ソフトで数式として評価され得る**

    **対象ファイル:関数名**  
    `frontend/src/format.ts:roomsToCsv`

    **問題**  
    ユーザー入力の `room_name` をそのまま CSV に出力しています。`=1+1` などは、Excel で開くと文字列ではなく数式として扱われる可能性があります。CSV の引用符だけでは防げません。また、現行エスケープは `\r` 単独を考慮していません。

    **提案（コード例）**  
    外部由来の文字列列に数式対策を適用してから CSV エスケープします。

    ```ts
    const safeText = (s: string) =>
      /^[\s\u0000-\u001f]*[=+\-@]/.test(s) || /^[\t\r\n]/.test(s)
        ? "'" + s
        : s;

    const esc = (s: string) =>
      /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;

    // 部屋名列
    const name = safeText(r.name);
    ```

    対象ソフトで挙動を検証してください。文字列を確実に保持する必要があれば、文字列セル型を指定した XLSX 出力が適しています。

13. **[Medium] マウス専用操作とイベント伝播により、キーボード操作や選択が不安定になる**

    **対象ファイル:関数名**  
    `frontend/src/components/UploadPanel.tsx:UploadPanel`  
    `frontend/src/components/RoomTable.tsx:RoomTable`  
    `frontend/src/components/RoomDetail.tsx:Chips, RoomDetail`  
    `frontend/src/components/FloorPlanView.tsx:FloorPlanView`  
    `frontend/src/App.tsx:App`

    **問題**  
    - アップロード領域の `role="button"` 内にサンプルボタンがあり、子の Enter/Space が親へ伝播してファイル選択まで起動し得る。
    - 表の並べ替えが `th` のクリックのみ。
    - 辺・区間の強調表示がホバーのみで、キーボードやタッチから利用しにくい。
    - 選択中の辺をクリックすると SVG まで伝播し、選択が解除される。
    - 解析中・エラーの読み上げ通知がない。

    **提案（コード例）**  
    アップロード用とサンプル用の native button を兄弟要素にし、表見出しにも button を置きます。

    ```tsx
    <th
      scope="col"
      aria-sort={sort.key === c.key
        ? sort.dir === 1 ? "ascending" : "descending"
        : "none"}
    >
      <button type="button" onClick={() => clickHeader(c.key)}>
        {c.label}
      </button>
    </th>
    ```

    ```tsx
    {loading && <div role="status">解析中…</div>}
    {status.state === "error" && (
      <div role="alert">エラー: {status.message}</div>
    )}
    ```

    辺やチップの操作はフォーカス・クリックでも実行可能にし、表の選択は名前セルのボタンで明示すると扱いやすくなります。SVG の選択解除は背景矩形のみに付ける方法が簡潔です。選択変更時には `hoverEdge`・`highlightSegments` もまとめて初期化してください。

14. **[Medium] 計算条件の入力が未完成値を扱えず、ブラウザの min 制約も適用されない**

    **対象ファイル:関数名**  
    `frontend/src/components/SettingsPanel.tsx:SettingsPanel`  
    `frontend/src/hooks/useAnalysis.ts:runAnalysis`

    **問題**  
    数値化できない入力を前の値へ戻すため、全削除して入力し直す操作がしにくくなっています。また、`min` があっても `type="button"` のクリックではフォーム検証が実行されず、0や負値を送信できます。

    `appliedSettings` も、サーバーが返した実際の適用値ではなく送信値を保存しています。

    **提案（コード例）**  
    編集中は文字列で保持し、フォーム送信時に検証・数値化します。

    ```tsx
    <form onSubmit={(e) => {
      e.preventDefault();
      if (!e.currentTarget.reportValidity()) return;
      const parsed = parseAndValidateSettings(draft);
      if (parsed.ok) onApply(parsed.value);
    }}>
      {/* value は文字列。required / min / step を設定 */}
      <button type="submit" disabled={disabled}>この条件で再計算</button>
    </form>
    ```

    高さの相関エラーを各入力へ `aria-describedby` で関連付けます。適用済み条件はレスポンスの `settings` から必要なキーを取り出して確定してください。

15. **[Low] 計算モデル・API モデル・表示用データが密結合で、仕様変更を追いにくい**

    **対象ファイル:関数名**  
    `backend/app/analyzer.py:analyze_edge, analyze_room, analyze`  
    `backend/app/schemas.py:AnalyzeResponse`  
    `frontend/src/types.ts`  
    `frontend/src/hooks/useAnalysis.ts:extractImageUrl`

    **問題**  
    コア解析が Pydantic のレスポンス型を直接生成し、表示名の調整や警告文作成も担っています。観測区間・補完区間・寄与 ID を拡張すると API まで同時に変わります。

    型と既定値もバックエンド・フロントエンドで重複しています。また、画像抽出関数の「サーバへは送らない」というコメントは、元ファイル全体をアップロードする実装と一致しません。

    **提案（コード例）**  
    純粋計算の結果を内部モデルで返し、API 変換を分離します。

    ```python
    @dataclass(frozen=True)
    class EdgeMeasure:
        wall_length_px: float
        door_length_px: float
        wall_area_m2: float
        warnings: tuple["AnalysisWarning", ...]

    def measure_edge(...) -> EdgeMeasure:
        ...

    def to_edge_response(measure: EdgeMeasure, ...) -> EdgeResult:
        ...
    ```

    警告には `code, contour_id, edge_index, message` を持たせ、UI から該当部位を選択できるようにします。既定値は `/api/defaults`、型は API スキーマからの生成を検討してください。

    画像を実際に送らない設計にするなら、クライアントで解析用 JSON を分離する必要があります。コメントだけでなく送信契約も合わせて変更します。

16. **[Low] ホバーごとに静的な SVG データを再計算し、凹多角形のラベルが部屋外へ出る**

    **対象ファイル:関数名**  
    `frontend/src/components/FloorPlanView.tsx:FloorPlanView`  
    `frontend/src/format.ts:centroid`  
    `frontend/src/hooks/useAnalysis.ts:extractImageUrl`

    **問題**  
    ホバー状態の変更でも全室の points 文字列・重心・幅を再計算します。`Math.max(...xs)` は大量の頂点で引数数の上限に達する可能性もあります。

    重心計算式自体は妥当ですが、凹多角形の重心は領域外に出ることがあり、ラベル配置点には常に適しません。また、大容量 JSON の `JSON.parse` はメインスレッドを止めます。

    **提案（コード例）**

    ```tsx
    const roomShapes = useMemo(
      () => result.rooms.map((room) => ({
        room,
        points: pointsAttr(room.vertices),
        label: findInteriorLabelPoint(room.vertices),
        bounds: boundsByReduction(room.vertices),
      })),
      [result.rooms],
    );
    ```

    `findInteriorLabelPoint` は内部点を保証する関数として実装し、静的レイヤーと選択レイヤーを分けて必要に応じてメモ化します。大容量入力では画像抽出を Worker へ移し、まず計測してから Canvas 化などを判断してください。

17. **[Medium] テストが代表例中心で、幾何計算の不変条件・競合・不正入力を検証していない**

    **対象ファイル:関数名**  
    `backend/tests/test_geometry.py`  
    `backend/tests/test_analyzer.py`  
    `backend/tests/test_api.py`  
    フロントエンド各コンポーネント・フックのテスト

    **問題**  
    現行テストは基本的な長方形とサンプル確認には有効ですが、上記の誤計算を捕捉できません。特に壁面積は、広い許容範囲のサンプル検証だけでなく、手計算可能な小さい入力が必要です。

    **提案（コード例）**  
    この項目は重要度順では上記 Medium 項目と同じ優先度です。まず次の回帰テストを追加してください。

    ```python
    def test_door_ids_are_clipped_before_merge():
        doors = [
            (1, ((0, 0), (20, 0))),
            (2, ((20, 0), (40, 0))),
        ]
        result = door_intervals_on_edge(
            (0, 0), (100, 0), doors,
            [g.Interval(0, 10)],
            tolerance_px=0,
        )
        assert {sid for iv in result for sid in iv.ids} == {1}
        assert g.total_length(result) == pytest.approx(10)
    ```

    不足している主なケースは以下です。

    | 分類 | 追加するケース |
    |---|---|
    | tolerance | 閾値の直前・一致・直後、0、辺長より大きい値、端点ノイズの膨張、短い正当な壁 |
    | 射影 | 斜め線分、反転線分、ゼロ長線分、短辺、遠方にはみ出す線分、近接した平行辺 |
    | 区間演算 | 包含・接触・重複・範囲外・逆転、入力の非変更、寄与 ID の局所性 |
    | ドア | 部分重なり、重複検出、辺をまたぐドア、1 px未満の断片、ドア位置で途切れる壁 |
    | 多角形 | 凹形、閉じ点の重複、全点一致、一直線、自己交差、穴、重複 ID |
    | API | 両ルートの413、未知ラベル、非有限値、高さ相関、過剰な頂点数、両ルートの結果一致 |
    | フロント | A→B選択で完了順が逆、失敗時の旧結果、サンプル取得との競合、キーボード操作、CSV特殊文字 |

    さらに、許容誤差込みで次の不変条件を確認します。

    ```python
    assert edge.wall_length_m + edge.opening_length_m == pytest.approx(edge.length_m)
    assert 0 <= edge.door_length_m <= edge.wall_length_m + eps
    assert edge.wall_area_m2 == pytest.approx(
        edge.wall_area_gross_m2 - edge.door_area_m2
    )
    ```

    頂点順の反転、線分順の入れ替え、線分端点の反転、一直線上への頂点追加で結果が変わらないことも重要です。共有壁を両室へ計上する既存テストは、そのまま維持してください。