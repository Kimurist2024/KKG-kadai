import type { RoomResult } from "../../types";
import { DOOR_COLOR, OPENING_COLOR, SELECT_COLOR } from "./colors";

interface Props {
  selected: RoomResult;
  selectedEdge: number | null;
  hoverEdge: number | null;
  onSelectEdge: (index: number | null) => void;
  onHoverEdge: (index: number | null) => void;
  unitsPerPx: number;
  hitWidth: number;
  badgeR: number;
  badgeFont: number;
}

/** 選択中の部屋: 辺ごとの 壁あり / 開口 / ドア 区間と辺番号 */
export default function SelectedRoomEdges({ selected, selectedEdge, hoverEdge, onSelectEdge, onHoverEdge, unitsPerPx, hitWidth, badgeR, badgeFont }: Props) {
  return (
    <>
      {selected.edges.map((e) => {
        const active = selectedEdge === e.index || hoverEdge === e.index;
        const mid = { x: (e.start.x + e.end.x) / 2, y: (e.start.y + e.end.y) / 2 };
        return (
          <g
            key={e.index}
            onClick={() => onSelectEdge(selectedEdge === e.index ? null : e.index)}
            onMouseEnter={() => onHoverEdge(e.index)}
            onMouseLeave={() => onHoverEdge(null)}
            style={{ cursor: "pointer" }}
            role="button"
            tabIndex={0}
            aria-label={`辺 ${e.index + 1} を選択`}
            aria-pressed={selectedEdge === e.index}
            onKeyDown={(ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); onSelectEdge(selectedEdge === e.index ? null : e.index); } }}
          >
            {active && <line x1={e.start.x} y1={e.start.y} x2={e.end.x} y2={e.end.y} stroke={SELECT_COLOR} strokeWidth={hitWidth * 0.6} strokeLinecap="round" opacity={0.35} />}
            <line x1={e.start.x} y1={e.start.y} x2={e.end.x} y2={e.end.y} stroke="transparent" strokeWidth={hitWidth} />
            {e.wall_intervals.map((iv, i) => <line key={`w${i}`} x1={iv.start.x} y1={iv.start.y} x2={iv.end.x} y2={iv.end.y} stroke="#9f1239" strokeWidth={6 * unitsPerPx} />)}
            {e.inferred_wall_intervals?.map((iv, i) => <line key={`inferred${i}`} x1={iv.start.x} y1={iv.start.y} x2={iv.end.x} y2={iv.end.y} stroke="#a21caf" strokeWidth={10 * unitsPerPx} strokeDasharray={`${3 * unitsPerPx} ${3 * unitsPerPx}`} pointerEvents="none" />)}
            {e.opening_intervals.map((iv, i) => <line key={`o${i}`} x1={iv.start.x} y1={iv.start.y} x2={iv.end.x} y2={iv.end.y} stroke={OPENING_COLOR} strokeWidth={5 * unitsPerPx} strokeDasharray={`${7 * unitsPerPx} ${5 * unitsPerPx}`} />)}
            {e.door_intervals.map((iv, i) => <line key={`d${i}`} x1={iv.start.x} y1={iv.start.y} x2={iv.end.x} y2={iv.end.y} stroke={DOOR_COLOR} strokeWidth={8 * unitsPerPx} />)}
            <circle cx={mid.x} cy={mid.y} r={badgeR} fill={active ? SELECT_COLOR : "#fff"} stroke={SELECT_COLOR} strokeWidth={1.5 * unitsPerPx} />
            <text x={mid.x} y={mid.y} textAnchor="middle" dominantBaseline="central" fontSize={badgeFont} fontWeight={700} fill={active ? "#fff" : SELECT_COLOR} pointerEvents="none">
              {e.index + 1}
            </text>
          </g>
        );
      })}
    </>
  );
}
