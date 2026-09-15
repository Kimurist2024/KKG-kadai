import { wallWarningsForRoom } from "../warnings";
import { memo, useState } from "react";
import type { AnalyzeResponse, EdgeResult, IntervalOut, RoomResult } from "../types";
import { edgeWallFormula, floorAreaFormula, fmt, fmtPt, perimeterFormula } from "../format";

interface Props {
  result: AnalyzeResponse;
  room: RoomResult;
  /** JSON に記載されていた元の room_name (表示名の上書き前) */
  originalRoomName: string | null;
  hoverEdge: number | null;
  selectedEdge: number | null;
  onHoverEdge: (i: number | null) => void;
  onSelectEdge: (i: number | null) => void;
  onHoverSegments: (ids: number[]) => void;
  pinnedSegments: number[];
  onPinSegments: (ids: number[]) => void;
  onRename: (id: number, name: string | null) => void;
  onShowOnPlan: () => void;
  onClose: () => void;
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
          {label} {fmt(iv.length_m)} m
        </button>
      ))}
    </span>
  );
}

/** 選択部屋の計算式と辺ごとの内訳を表示し、図面上の強調表示や表示名の編集と連動する。 */
function RoomDetail({ result, room, originalRoomName, hoverEdge, selectedEdge, onHoverEdge, onSelectEdge, onHoverSegments, pinnedSegments, onPinSegments, onRename, onShowOnPlan, onClose }: Props) {
  const s = result.settings;
  const mpp = s.meters_per_px;
  const [editing, setEditing] = useState(false);
  const [nameDraft, setNameDraft] = useState(room.name);
  const [sourceOpen, setSourceOpen] = useState(false);
  const srcAreaDiff = room.source_area_px2 !== null ? room.floor_area_px2 - room.source_area_px2 : null;

  const commitName = () => {
    const v = nameDraft.trim();
    // 元の名前と同じなら上書きを解除。それ以外 (再編集で変更なしを含む) は入力値をそのまま保持
    onRename(room.id, v && v !== (originalRoomName ?? "") ? v : null);
    setEditing(false);
  };

  return (
    <div className="detail">
      <div className="detail-head">
        <span className="swatch lg" style={{ background: room.color }} />
        {editing ? (
          <form className="rename" onSubmit={(e) => { e.preventDefault(); commitName(); }}>
            <input autoFocus value={nameDraft} onChange={(e) => setNameDraft(e.target.value)} aria-label="部屋の表示名" maxLength={40} />
            <button type="submit" className="btn btn-primary btn-sm">決定</button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => { setEditing(false); setNameDraft(room.name); }}>取消</button>
          </form>
        ) : (
          <>
            <h2 tabIndex={-1} id="room-detail-heading">{room.name}</h2>
            <button type="button" className="btn btn-link btn-sm" onClick={() => { setNameDraft(originalRoomName === null && room.room_name === null ? "" : room.name); setEditing(true); }} title="表示名を変更 (JSON は変更しません)">
              {room.room_name === null ? "名前を付ける" : "表示名を変更"}
            </button>
            {room.name !== (originalRoomName ?? "") && room.room_name !== null && <span className="tag">表示名を上書き中</span>}
          </>
        )}
        <span className="spacer" />
        <button type="button" className="btn btn-secondary btn-sm" onClick={onShowOnPlan}>図面で確認</button>
        <button type="button" className="btn btn-secondary btn-sm" onClick={onClose}>選択解除</button>
      </div>

      {!!room.holes?.length && <p className="status info">内側の穴 {room.holes.length} 個を床面積から除外しています。周長は穴の境界を含み、内側の壁は壁線が対応する区間だけ計上します。</p>}
      {result.warnings.filter(w => w.code === "inferred_door_wall" && w.contour_id === room.id).map((w,i) => <p className="status warn" key={i}>{w.message}</p>)}
      {/* 結論を先に: 壁面積とその分解 */}
      {wallWarningsForRoom(result, room.id).map((w, i) => <p key={i} className="status warn">壁面積は要確認: {w.message}</p>)}
      <div className="headline">
        <div className="headline-main">
          <span className="headline-label">壁面積（ドア控除後）</span>
          <span className="headline-value">{fmt(room.wall_area_m2)} <small>m²</small></span>
        </div>
        <div className="headline-breakdown">
          壁部分 <b>{fmt(room.wall_area_gross_m2)}</b> − ドア控除 <b>{fmt(room.door_area_m2)}</b> ＝ <b>{fmt(room.wall_area_m2)} m²</b>
          <div className="muted small">
            壁部分 ＝ 壁長 {fmt(room.wall_length_m)} m × 天井高 {s.ceiling_height_m} m ／
            ドア控除 ＝ 控除ドア幅 {fmt(room.door_length_m)} m × ドア高 {s.door_height_m} m（{room.door_count} 箇所）
            {room.opening_length_m > 0.005 && <> ／ 壁なし長 {fmt(room.opening_length_m)} m は含めない</>}
          </div>
        </div>
      </div>

      <div className="metrics">
        <div className="metric">
          <div className="metric-label">床面積</div>
          <div className="metric-value">{fmt(room.floor_area_m2)} <small>m²</small></div>
          <div className="metric-formula" title="頂点座標からシューレース公式で算出">{floorAreaFormula(room, mpp)}</div>
        </div>
        <div className="metric">
          <div className="metric-label">周長</div>
          <div className="metric-value">{fmt(room.perimeter_m)} <small>m</small></div>
          <div className="metric-formula">{perimeterFormula(room, mpp)}</div>
          <div className="muted small">うち壁あり {fmt(room.wall_length_m)} m ／ 壁なし {fmt(room.opening_length_m)} m</div>
        </div>
      </div>

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
    </div>
  );
}

export default memo(RoomDetail);
