"""Generate the report and trace overlays from saved evaluation outputs."""
import base64
import hashlib
import html
import json
import statistics
from pathlib import Path

P=Path(__file__).resolve().parents[2] / 'docs' / 'validation'
r=json.loads((P/'results.json').read_text())
rows=r['area_rows']
for ds in ['ur','mini']:
    d=json.loads((P/(ds+'_mask.json')).read_text())
    w,h=d['image_width'],d['image_height']
    items=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
           f'<image width="{w}" height="{h}" href="data:image/png;base64,{d["image_data"]["base64"]}"/>']
    for c in d['contours']:
        xy=c['vertices']; pts=' '.join(f'{v["x"]},{v["y"]}' for v in xy)
        items.append(f'<polygon points="{pts}" fill="#2563eb" fill-opacity="0.13" stroke="#2563eb" stroke-width="2"/>')
        for v in xy:
            items.append(f'<circle cx="{v["x"]}" cy="{v["y"]}" r="3" fill="#1d4ed8"/>')
    items.append('</svg>')
    (P/(ds+'_trace.svg')).write_text('\n'.join(items))

table='\n'.join(f'| {x["dataset"]} | {x["room"]} | {x["reference_m2"]:.3f} | {x["actual_m2"]:.3f} | {x["error_pct"]:+.2f}% | {x["reference_perimeter_m"]:.3f} | {x["perimeter_m"]:.3f} | {x["perimeter_error_pct"]:+.2f}% |' for x in rows)
summary='\n'.join(f'| {n.upper()} | {r["datasets"][n]["n"]} | {r["datasets"][n]["mape_pct"]:.2f}% | {r["datasets"][n]["max_absolute_pct"]:.2f}% | {statistics.mean(abs(x["perimeter_error_pct"]) for x in rows if x["dataset"]==n):.2f}% |' for n in ['ur','mini'])
scale_table='\n'.join(f'| {x["scale_error_pct"]:+.0f}% | {x["floor_error_pct"]:+.2f}% | {x["wall_error_pct"]:+.2f}% |' for x in r['scale_sensitivity'])
offset_table='\n'.join(f'| {x["offset_x_y_px"]} | {x["wall_area_m2"]:.4f} | {x["wall_error_pct"]:+.2f}% |' for x in r['offset_sensitivity'])
report=f'''# 公開図面を用いた精度検証

検証日: 2026-09-14 / 対象: ローカルの floorplan-analyzer。実装の変更は行わず、検証資料を追加した。

## 判定

**正しく座標化・縮尺設定された JSON の計算は良好。ただし、任意の図面画像から自動的に正しい面積を出せると評価することはできない。**

公開された 2 図面の 11 区画を手作業でトレースし、実装の `/api/analyze` に multipart で渡した。
UR の寸法付き図面では床面積の平均絶対百分率誤差が 0.59%、最大 1.78%。
住宅カタログの部屋では平均 5.95%、浴室は +15.94% だった。
これは「図面読み取り + 縮尺校正 + 計算」の一致度であり、画像認識の正解率でも、建物の実測精度でもない。

壁面積は現地の正解値がない。外部図面の寝室形状に高さを仮定した条件付き検算では、床面積・周長・壁面積が独立した四則演算と 1e-9 未満の差で一致した。

## 1. 入力と検証対象

アプリの入力は部屋多角形・壁線分・ドア線分の JSON。PDF/PNG から輪郭を抽出するモデルや OCR は実装されていない。
本検証では人が作った JSON を使用したため、「未知の図面からの自動抽出精度」は測定していない。

| 資料 | 対象と採用理由 | 校正 |
|---|---|---|
| [UR 都市機構 S2 建築図 ver1.1]({rows[0]['source_url']}) PDF 3ページ、図番 A-S2-002 | 1階用途別色分図。L字を含む連続した住戸 8 区画。全区画を採用し、良い結果だけを選別していない | X0-X7 の 44,650 mm を 949 px として校正 |
| [Countryside Kenora / Candlewood Homes Mini Homes]({rows[-1]['source_url']}) PDF 5ページ | 14×40 ft、2寝室。寸法があり境界を明示できる Bedroom 2、Bath、Master の 3 区画。Living/Kitchen は開放境界が不明確なため除外 | 建物外形 40 ft = 12.192 m を 1,142 px として校正 |

採用前に資料の図面画像を確認。UR は PDF を 1.5 px/point、Mini Homes は 2 px/point で PNG 化した。
座標は画像上の線を手作業で読み取り、記載面積に一致するよう補正していない。
参照面積と校正寸法を分けており、部屋の面積から縮尺を逆算していない。
トレースをやり直すと 1 px 程度の差が生じ得る。UR の細い 1K 区画では幅 1 px が面積約 0.414 m²、約 1.44% に相当する。

UR は壁芯付近の住戸専有区画であり、個々の居室の内法面積ではない。柱型・MB/EPS等を精密に別計測していない。
Mini Homes は内側の描画線を採用。Bedroom 2 は左の収納を除外、Master は寸法表記に対応する収納込みの矩形を採用した。
これらの境界定義を変えると結果も変わる。第三者の独立した二重アノテーションは行っていない。

図面上の面積表記は必ずしも一意でない。UR は区画内ラベルを参照した。
同ページのタイプ表には 1K が 28.60 m²、1LDK-42-EV が 42.48 m² とあり、区画内ラベルの 28.66 / 42.59 m² と異なる。
1階合計欄は 326.51 m²、採用した区画ラベルの合計は 326.48 m²。この不整合も参照値の限界である。

## 2. 床面積と周長

誤差 [%] = (アプリ値 / 参照値 - 1) × 100。
平均絶対誤差 [%] (MAPE) は各区画の誤差の絶対値の単純平均。小さな浴室も大きな住戸と同じ重みとなる。

| 図面 | 区画数 | 床面積 MAPE | 床面積 最大絶対誤差 | 周長 MAPE |
|---|---:|---:|---:|---:|
{summary}

| 図面 | 区画 | 参照面積 m² | アプリ m² | 面積誤差 | 参照周長 m | アプリ m | 周長誤差 |
|---|---|---:|---:|---:|---:|---:|---:|
{table}

UR の周長参照は各区画の寸法線の幅と高さ 8.8 m から算出。L字区画は角の矩形欠き取りのため、外接矩形の周長と同じ 2×(6.05+8.8) m。
Mini Homes の参照面積・周長は、部屋表記の 8×11 ft、4×8 ft、9×13 ft から算出し、1 ft = 0.3048 m で換算した。
UR 区画合計は 325.842 m²、参照ラベル合計 326.480 m² に対して -0.20%。合計では個々の誤差が打ち消し合うため、MAPE と併記した。

浴室は外形で校正すると描画上約 4.41×8.41 ft、表記は 4×8 ft。片辺ずつの差が積になって +15.94% となる。
寸法の丸め・図の縮尺や線の読み取り・境界定義が原因候補だが、本資料だけではどれが原因か断定できない。
この浴室の結果を「アプリ計算ロジックが16%間違っている」と解釈するのは不適切。

## 3. 壁面積の条件付き検算

Mini Homes の Bedroom 2 のトレースを使い、天井高 2.4 m、ドア高 2.0 m、図面上のドア幅 73 px を仮定。
窓は現行仕様どおり控除せず、ドアを含む壁区間を連続線として入力した。
天井高・ドア高はこの外部住宅の実測値や仕様から取得していないため、実物の壁面積の正解値ではない。

| 項目 | 独立計算の式 | 期待値 | API |
|---|---|---:|---:|
| 床面積 | 幅×奥行 | 8.021710 m² | 8.021710 m² |
| 周長 | 2×(幅+奥行) | 11.444680 m | 11.444680 m |
| 壁面積 | 周長×2.4 - ドア幅×2.0 | 25.908534 m² | 25.908534 m² |

計算に使った幅・奥行はそれぞれ 306 px、230 px。換算は 12.192 / 1,142 m/px。
独立計算は矩形の四則演算で、アプリの geometry/analyzer 関数を期待値生成に流用していない。

**壁線をドア開口で切る場合**: 同じ形状で下辺の 73 px を欠いた壁線を入力すると 25.596794 m² (-1.20%)。
`unmatched_door` 警告が発生し、ドア上部の垂れ壁 0.311739 m² が計上されなかった。
これは現在の入力契約と一致する挙動だが、一般的な図面の線をそのまま採用する場合の実用上の制限。
床面積だけを検証した `ur_mask.json` / `mini_mask.json` には壁・ドア線を入れていないため、壁面積 0 は未検証項目であり精度評価の対象外。

## 4. 縮尺・座標ずれへの感度

以下は寝室データから作った人工的な変形テストで、独立した外部図面のサンプル数には数えない。

### 縮尺

| m/px の設定誤差 | 床面積誤差 | 壁面積誤差 |
|---:|---:|---:|
{scale_table}

床面積は縮尺の二乗、壁面積は高さ固定なら縮尺に比例する。
既定の 96.7 px = 1.365 m を変更せず使うと、この UR データは床面積 -91.00%、Mini Homes は +74.82% になる（換算式による算出）。
ファイルごとの縮尺設定は必須で、別図面へ既定値をそのまま適用してはいけない。

### 壁・ドア線だけの位置ずれ

部屋輪郭を固定し、全壁線・ドア線の x と y をそれぞれ同じ px 数だけ平行移動。
許容誤差は 10 px 固定。壁形状が軸平行である今回の条件では次の結果だった。

| x,y 各方向のずれ px | 壁面積 m² | 基準比 |
|---:|---:|---:|
{offset_table}

10 px と 11 px の間で判定が切り替わり、全ての壁が対応しなくなる。
これは「常に11 pxで全壁が消える」という一般則ではなく、この軸平行の全線一括移動ケースの結果。
許容誤差を単純に大きくすると近接壁の誤採用もあり得るため、画像解像度と線の位置ずれに合わせる必要がある。

## 5. Web アプリの動作確認範囲

| 確認 | 結果 |
|---|---|
| Chrome で初期画面を開く | 成功。JSON 選択・計算条件・サンプルボタンを確認 |
| ブラウザ操作による JSON 選択と結果描画 | 未完了。拡張機能によるファイル指定が `Not allowed`。続くネイティブブラウザ操作も URL アクセス制限で終了 |
| Vite 5173 → `/api/analyze` → FastAPI 8000 | 成功。実際の multipart HTTP リクエストで 4 データセット全て HTTP 200 |
| 実 HTTP と TestClient の照合 | UR、Mini、連続壁の寝室、ドア開口で壁を切った寝室のレスポンス全体がそれぞれ完全一致 |
| 本番 Vercel 上の検証 | 未実施。デプロイ前のローカル検証 |

画面の計算結果表示・CSV操作・モバイル表示・コンソールエラーの確認を完了したとは扱わない。
ブラウザ自動操作の失敗をアプリ自体のアップロード不具合と断定していない。
既存の 39 件のテストと本番ビルドは同セッションの先行確認で成功済み。今回の精度数値は新しい外部データによるもの。

## 6. 改善優先度

1. **図面ごとの縮尺確認を必須にする**。基準線を選択し、寸法を入力してから計算する導線が最も効果的。
2. **壁の対応率を検査する**。壁線なし・対応する壁長が極端に少ない場合、結果の 0 を通常の確定値として見せず確認を促す。
3. **ドア開口の入力契約を明示する**。一般図面から切れた壁線を入力する用途を支援するなら、ドア上部の扱いを別モードで設計する。
4. **別系統の図面と第三者アノテーションで拡大検証**。今回の 2 図面 / 11 区画は小規模で、斜め壁・曲線・穴・窓の控除・全室の壁面積を網羅していない。

今回は検証依頼のため、上記の仕様変更・ロジック変更は実施していない。

## 7. 再実行・手動確認

プロジェクトルートから:

```sh
backend/.venv/bin/python scripts/validation/run_validation.py
backend/.venv/bin/python scripts/validation/build_report.py
```

既存の backend 開発依存（FastAPI / httpx 等）を利用。外部サービスや認証情報は不要。
元 PDF の描画を再生成するときだけ PyMuPDF が必要。PNG は `sources/` に保存済み。

画面での確認用ファイル:

- `ur_mask.json`: 画像上 **949 px = 44.65 m**。床面積合計 325.84 m²、8区画。
- `mini_mask.json`: 画像上 **1142 px = 12.192 m**。床面積合計 22.34 m²、3区画。
- `bedroom_wall_mask.json`: **1142 px = 12.192 m**、天井 2.4 m、ドア 2.0 m、許容誤差 10 px。壁面積 25.91 m²。
- `bedroom_door_gap_mask.json`: 同条件。壁面積 25.60 m²、ドア警告あり。

元図面は外部の著作物。ローカルの検証用に保存し、今回公開・デプロイはしていない。
`docs/` は既存 `.vercelignore` でデプロイ対象外。

## 添付

- [全区画の数値 CSV](area_results.csv)
- [集計・感度テスト JSON](results.json)
- [実 HTTP 照合結果](http_results.json)
- [UR トレース重ね合わせ](ur_trace.svg)
- [Mini Homes トレース重ね合わせ](mini_trace.svg)
- [検証スクリプト](../../scripts/validation/run_validation.py)

青線と青点が採用した輪郭・頂点。元画像を含む SVG なので拡大して照合できる。
'''
(P/'REPORT.md').write_text(report)
manifest={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in P.rglob('*') if f.is_file() and f.suffix in ['.pdf','.png','.json','.py'] and f.name!='sha256.json'}
for script in Path(__file__).parent.glob('*.py'):
    manifest['../../scripts/validation/' + script.name] = hashlib.sha256(script.read_bytes()).hexdigest()
(P/'sha256.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('REPORT.md and trace overlays generated')
