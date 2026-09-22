import { wallWarningsForRoom } from "../warnings";
import { memo, useMemo, useState } from "react";
import type { AnalyzeResponse, RoomResult } from "../types";
import { downloadText, fmt, roomsToCsv } from "../format";

interface Props {
  result: AnalyzeResponse;
  selectedId: number | null;
  hoverId: number | null;
  onSelect: (id: number | null) => void;
  onHover: (id: number | null) => void;
  onShowDetail: () => void;
}

type SortKey = "id" | "name" | "floor_area_m2" | "perimeter_m" | "wall_length_m" | "opening_length_m" | "door_length_m" | "wall_area_m2";

const COLUMNS: { key: SortKey; label: string; unit: string; numeric: boolean; optional: boolean; title?: string }[] = [
  { key: "name", label: "部屋", unit: "", numeric: false, optional: false },
  { key: "floor_area_m2", label: "床面積", unit: "m²", numeric: true, optional: false, title: "頂点座標から算出した床面積" },
  { key: "perimeter_m", label: "周長", unit: "m", numeric: true, optional: true },
  { key: "wall_length_m", label: "壁長", unit: "m", numeric: true, optional: true, title: "周長のうち壁が存在する長さ" },
  { key: "opening_length_m", label: "壁なし長", unit: "m", numeric: true, optional: true, title: "周長のうち壁線分が検出されなかった長さ (壁面積に含めない)" },
  { key: "door_length_m", label: "控除ドア幅", unit: "m (箇所)", numeric: true, optional: true, title: "壁上にあるドアの合計幅 (箇所数)。ドア高 × 幅 を壁面積から控除" },
  { key: "wall_area_m2", label: "壁面積", unit: "m² (ドア控除後)", numeric: true, optional: false, title: "壁長 × 天井高 − ドア幅 × ドア高" },
];


interface RowProps {
  r: RoomResult;
  selected: boolean;
  hovered: boolean;
  /** 壁面積に付ける「要確認」の理由 (改行区切り)。空文字なら警告なし。memo 比較のため文字列で渡す */
  wallWarningText: string;
  onSelect: Props["onSelect"];
  onHover: Props["onHover"];
  onShowDetail: Props["onShowDetail"];
}

const OPENING_TITLE = "壁線分が検出されなかった区間があります（壁面積に含めません）";

// 選択・ホバーが変わった行だけ更新し、他の部屋の数値セルを作り直さない。
const RoomRow = memo(function RoomRow({ r, selected, hovered, wallWarningText, onSelect, onHover, onShowDetail }: RowProps) {
  const hasOpening = r.opening_length_m > 0.005; // 課題 2-2「壁が存在しない輪郭区間」を表の段階で拾えるようにする
  return (
              <tr
                className={`${selected ? "selected" : ""} ${hovered ? "hover" : ""}`}
                tabIndex={0}
                aria-selected={selected}
                onClick={() => onSelect(selected ? null : r.id)}
                onKeyDown={(e) => { if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onSelect(selected ? null : r.id); } }}
                onFocus={() => onHover(r.id)}
                onBlur={() => onHover(null)}
                onMouseEnter={() => onHover(r.id)}
                onMouseLeave={() => onHover(null)}
              >
                <td className="color-col"><span className="swatch" style={{ background: r.color }} /></td>
                <td className="name-col">
                  {r.name}
                  {r.room_name === null && <span className="tag" title="JSON に room_name がありません。詳細で名前を付けられます">名称未設定</span>}
                  {/* 狭い画面で「壁なし長」列が隠れても分かるように、部屋名の隣にも印を出す */}
                  {hasOpening && <span className="tag tag-opening only-narrow" title={OPENING_TITLE}>壁なし区間あり</span>}
                  {selected && (
                    <button type="button" className="btn btn-link btn-sm row-action" onClick={(e) => { e.stopPropagation(); onShowDetail(); }}>
                      算出根拠を見る ↓
                    </button>
                  )}
                </td>
                <td className="num">{fmt(r.floor_area_m2)}</td>
                <td className="num col-optional">{fmt(r.perimeter_m)}</td>
                <td className="num col-optional">{fmt(r.wall_length_m)}</td>
                <td className={`num col-optional ${hasOpening ? "has-opening" : ""}`} title={hasOpening ? OPENING_TITLE : undefined}>{fmt(r.opening_length_m)}</td>
                <td className="num col-optional">{fmt(r.door_length_m)}{r.door_count > 0 && <span className="muted"> ({r.door_count})</span>}</td>
                <td className="num strong"><span>{fmt(r.wall_area_m2)}</span>{wallWarningText && <span className="wall-review" title={wallWarningText} aria-label={`要確認: ${wallWarningText}`}>要確認</span>}</td>
              </tr>
  );
});

/** 部屋別の結果を並べ替えて表示し、部屋選択・算出根拠への移動・CSV 保存を提供する。 */
export default function RoomTable({ result, selectedId, hoverId, onSelect, onHover, onShowDetail }: Props) {
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "id", dir: 1 });
  const [showAll, setShowAll] = useState(false); // 狭い画面で全列を表示

  const rows = useMemo(() => {
    const copy = [...result.rooms];
    copy.sort((a, b) => {
      const va = a[sort.key], vb = b[sort.key];
      if (typeof va === "string" && typeof vb === "string") return va.localeCompare(vb, "ja") * sort.dir;
      return ((va as number) - (vb as number)) * sort.dir;
    });
    return copy;
  }, [result.rooms, sort]);

  const totals = useMemo(
    () =>
      result.rooms.reduce(
        (t, r) => ({
          perimeter_m: t.perimeter_m + r.perimeter_m,
          wall_length_m: t.wall_length_m + r.wall_length_m,
          opening_length_m: t.opening_length_m + r.opening_length_m,
          door_length_m: t.door_length_m + r.door_length_m,
          door_count: t.door_count + r.door_count,
        }),
        { perimeter_m: 0, wall_length_m: 0, opening_length_m: 0, door_length_m: 0, door_count: 0 },
      ),
    [result.rooms],
  );

  // 見出しのクリックで 降順 → 昇順 → 元の順 (id 順) の 3 状態を巡回する (部屋名は昇順から)
  const clickHeader = (key: SortKey) =>
    setSort((s) => {
      const first: 1 | -1 = key === "name" ? 1 : -1;
      if (s.key !== key) return { key, dir: first };
      if (s.dir === first) return { key, dir: first === 1 ? -1 : 1 };
      return { key: "id", dir: 1 };
    });
  const arrow = (key: SortKey) => (sort.key === key ? (sort.dir === 1 ? " ▲" : " ▼") : "");
  const cls = (c: { optional: boolean; numeric: boolean }) => `${c.numeric ? "num" : ""} ${c.optional ? "col-optional" : ""}`;

  return (
    <div className={`table-wrap ${showAll ? "show-all" : ""}`}>
      <h2 id="table-heading" className="section-heading">部屋別の床面積・壁面積</h2>
      <div className="table-toolbar">
        <span className="muted">{result.summary.room_count} 部屋 / 壁 {result.summary.wall_count} 本 / ドア {result.summary.door_count} 本</span>
        <span className="spacer" />
        <label className="chk only-narrow">
          <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} /> 全項目を表示
        </label>
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => downloadText("room_wall_areas.csv", roomsToCsv(result))}>
          CSV ダウンロード
        </button>
      </div>
      <p className="muted small table-hint">行をクリックすると図面でハイライトし、画面下部に算出根拠パネルが開きます（行の「算出根拠を見る ↓」で移動）。見出しをクリックすると 降順 → 昇順 → 元の順 に並べ替えます。</p>
      <div className="table-scroll">
        <table className="rooms">
          <thead>
            <tr>
              <th className="color-col" />
              {COLUMNS.map((c) => (
                <th key={c.key} scope="col" className={cls(c)} title={c.title} aria-sort={sort.key === c.key ? (sort.dir === 1 ? "ascending" : "descending") : "none"}>
                  <button type="button" className="th-btn" onClick={() => clickHeader(c.key)}>
                    {c.label}{arrow(c.key)}
                    {c.unit && <small className="unit-sub">{c.unit}</small>}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r: RoomResult) => (
              <RoomRow key={r.id} r={r} selected={r.id === selectedId} hovered={r.id === hoverId}
                wallWarningText={wallWarningsForRoom(result, r.id).map((w) => w.message).join("\n")}
                onSelect={onSelect} onHover={onHover} onShowDetail={onShowDetail} />
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td />
              <td>合計</td>
              <td className="num">{fmt(result.summary.total_floor_area_m2)}</td>
              <td className="num col-optional">{fmt(totals.perimeter_m)}</td>
              <td className="num col-optional">{fmt(totals.wall_length_m)}</td>
              <td className={`num col-optional ${totals.opening_length_m > 0.005 ? "has-opening" : ""}`}>{fmt(totals.opening_length_m)}</td>
              <td className="num col-optional">{fmt(totals.door_length_m)}{totals.door_count > 0 && <span className="muted"> ({totals.door_count})</span>}</td>
              <td className="num strong">{fmt(result.summary.total_wall_area_m2)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      <p className="totals-note">合計は各部屋の内壁面積の合計です。共有壁は両方の部屋に計上し、窓は控除しません。</p>
      <details className="definition">
        <summary>壁面積の定義（詳細）</summary>
        <ul>
          <li>各部屋の<b>内壁面積</b>です。2 部屋に挟まれた壁は両方の部屋に計上します（両面計上）。</li>
          <li>壁面積 ＝ 壁長 × 天井高 − 控除ドア幅 × ドア高。ドアの上部（垂れ壁）は壁として残ります。</li>
          <li>「壁なし長」は輪郭上に壁線分が検出されなかった区間で、壁面積に含めません（オープンな境界など）。</li>
          <li>窓など、ドア以外の開口は入力に含まれないため控除しません。</li>
        </ul>
      </details>
    </div>
  );
}
