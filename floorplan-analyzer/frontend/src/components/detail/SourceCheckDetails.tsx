import { useState } from "react";
import type { RoomResult } from "../../types";
import { fmt, fmtPt } from "../../format";

interface Props {
  room: RoomResult;
  originalRoomName: string | null;
}

export default function SourceCheckDetails({ room, originalRoomName }: Props) {
  const [sourceOpen, setSourceOpen] = useState(false);
  const srcAreaDiff = room.source_area_px2 !== null ? room.floor_area_px2 - room.source_area_px2 : null;

  return (
    <details className="source-check" onToggle={(event) => setSourceOpen(event.currentTarget.open)}>
      <summary>元データとの照合（座標・線分 id・JSON 記載値）</summary>
      {sourceOpen && <>
      <div className="muted small">
        輪郭 id={room.id} ／ 頂点 {room.vertices.length} 点 ／ JSON の room_name: {originalRoomName === null ? "null" : `"${originalRoomName}"`}
        {srcAreaDiff !== null && <> ／ JSON 記載の面積 {fmt(room.source_area_px2!, 1)} px² との差 {fmt(srcAreaDiff, 2)} px²</>}
        {room.source_perimeter_px !== null && <> ／ 記載の周長 {fmt(room.source_perimeter_px, 1)} px（再計算 {fmt(room.perimeter_px, 1)} px）</>}
      </div>
      <div className="edge-table-wrap">
      <table className="edges compact">
        <thead><tr><th>辺</th><th>始点 → 終点 [px]</th><th>壁 (線分 id)</th><th>ドア (線分 id)</th></tr></thead>
        <tbody>
          {room.edges.map((e) => (
            <tr key={e.index}>
              <td><span className="badge">{e.index + 1}</span>{e.boundary_kind === "hole" && <span className="tag">内周</span>}</td>
              <td className="mono">{fmtPt(e.start)} → {fmtPt(e.end)}</td>
              <td className="mono small">{e.wall_intervals.map((iv) => `${fmt(iv.start_px, 0)}–${fmt(iv.end_px, 0)}px (id ${iv.ids.join(",")})`).join(" / ") || "—"}</td>
              <td className="mono small">{e.door_intervals.map((iv) => `${fmt(iv.start_px, 0)}–${fmt(iv.end_px, 0)}px (id ${iv.ids.join(",")})`).join(" / ") || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
      </>}
    </details>
  );
}
