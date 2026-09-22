import type { AnalyzeResponse, EdgeResult, IntervalOut, RoomResult } from "../../types";
import { edgeWallFormula, fmt } from "../../format";

interface Props {
  room: RoomResult;
  settings: AnalyzeResponse["settings"];
  hoverEdge: number | null;
  selectedEdge: number | null;
  onHoverEdge: (i: number | null) => void;
  onSelectEdge: (i: number | null) => void;
  onHoverSegments: (ids: number[]) => void;
  pinnedSegments: number[];
  onPinSegments: (ids: number[]) => void;
}

interface ChipsProps {
  label: string;
  items: IntervalOut[];
  cls: string;
  pinned: number[];
  onHoverSegments: (ids: number[]) => void;
  onPinSegments: (ids: number[]) => void;
}

/** 区間チップ。ホバー/フォーカスは一時的な強調、クリックは確定選択 (図面に戻っても保持) */
function Chips({ label, items, cls, pinned, onHoverSegments, onPinSegments }: ChipsProps) {
  if (!items.length) return null;
  const isPinned = (ids: number[]) => ids.length > 0 && ids.every((id) => pinned.includes(id)) && pinned.length === ids.length;
  return (
    <span className="chips">
      {items.map((iv, i) => (
        <button
          type="button"
          key={i}
          className={`chip ${cls} ${isPinned(iv.ids) ? "pinned" : ""}`}
          disabled={!iv.ids.length}
          aria-pressed={isPinned(iv.ids)}
          title={`辺の始点から ${fmt(iv.start_px, 1)}〜${fmt(iv.end_px, 1)} px${iv.ids.length ? `\n対応する線分 id: ${iv.ids.join(", ")}\nクリックで図面上の線分を選択` : ""}`}
          onMouseEnter={() => onHoverSegments(iv.ids)}
          onMouseLeave={() => onHoverSegments([])}
          onFocus={() => onHoverSegments(iv.ids)}
          onBlur={() => onHoverSegments([])}
          onClick={(e) => { e.stopPropagation(); onPinSegments(isPinned(iv.ids) ? [] : iv.ids); }}
        >
          {isPinned(iv.ids) ? "✓ " : ""}{label} {fmt(iv.length_m)} m
        </button>
      ))}
    </span>
  );
}

export default function EdgeBreakdownTable({ room, settings: s, hoverEdge, selectedEdge, onHoverEdge, onSelectEdge, onHoverSegments, pinnedSegments, onPinSegments }: Props) {
  return (
    <>
      <h3>
        辺ごとの内訳
        <span className="muted small">（行をクリックすると図面上の辺を選択。{selectedEdge !== null ? `辺 ${selectedEdge + 1} を選択中` : "未選択"}）</span>
      </h3>
      <div className="edge-table-wrap">
        <table className="edges">
          <thead>
            <tr>
              <th scope="col">辺</th>
              <th scope="col" className="num">辺長 [m]</th>
              <th scope="col" className="num">壁長 [m]</th>
              <th scope="col" className="num">壁なし [m]</th>
              <th scope="col" className="num">ドア [m]</th>
              <th scope="col" className="num">壁面積 [m²]</th>
              <th scope="col">計算式</th>
              <th scope="col">区間の内訳</th>
            </tr>
          </thead>
          <tbody>
            {room.edges.map((e: EdgeResult) => {
              const active = selectedEdge === e.index || hoverEdge === e.index;
              return (
                <tr
                  key={e.index}
                  className={`${active ? "hover" : ""} ${selectedEdge === e.index ? "selected" : ""} ${e.wall_length_m <= 1e-9 ? "no-wall" : ""}`}
                  tabIndex={0}
                  aria-selected={selectedEdge === e.index}
                  onClick={() => onSelectEdge(selectedEdge === e.index ? null : e.index)}
                  onKeyDown={(ev) => { if (ev.target === ev.currentTarget && (ev.key === "Enter" || ev.key === " ")) { ev.preventDefault(); onSelectEdge(selectedEdge === e.index ? null : e.index); } }}
                  onMouseEnter={() => onHoverEdge(e.index)}
                  onMouseLeave={() => onHoverEdge(null)}
                >
                  <td><span className={`badge ${active ? "active" : ""}`}>{e.index + 1}</span>{e.boundary_kind === "hole" && <span className="tag">内周</span>}</td>
                  <td className="num">{fmt(e.length_m)}</td>
                  <td className="num">{fmt(e.wall_length_m)}</td>
                  <td className="num">{fmt(e.opening_length_m)}</td>
                  <td className="num">{fmt(e.door_length_m)}</td>
                  <td className="num strong">{fmt(e.wall_area_m2)}</td>
                  <td className="mono small">{edgeWallFormula(e, s.ceiling_height_m, s.door_height_m)}</td>
                  <td>
                    <Chips label="壁" items={e.wall_intervals} cls="chip-wall" pinned={pinnedSegments} onHoverSegments={onHoverSegments} onPinSegments={onPinSegments} />
                    <Chips label="壁なし" items={e.opening_intervals} cls="chip-open" pinned={pinnedSegments} onHoverSegments={onHoverSegments} onPinSegments={onPinSegments} />
                    <Chips label="ドア" items={e.door_intervals} cls="chip-door" pinned={pinnedSegments} onHoverSegments={onHoverSegments} onPinSegments={onPinSegments} />
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr>
              <td>合計</td>
              <td className="num">{fmt(room.perimeter_m)}</td>
              <td className="num">{fmt(room.wall_length_m)}</td>
              <td className="num">{fmt(room.opening_length_m)}</td>
              <td className="num">{fmt(room.door_length_m)}</td>
              <td className="num strong">{fmt(room.wall_area_m2)}</td>
              <td colSpan={2} className="mono small">{fmt(room.wall_area_gross_m2)} − {fmt(room.door_area_m2)} = {fmt(room.wall_area_m2)} m²</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </>
  );
}
