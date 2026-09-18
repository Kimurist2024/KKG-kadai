import { wallWarningsForRoom } from "../warnings";
import { memo, useState } from "react";
import type { AnalyzeResponse, RoomResult } from "../types";
import { floorAreaFormula, fmt, perimeterFormula } from "../format";

import EdgeBreakdownTable from "./detail/EdgeBreakdownTable";
import SourceCheckDetails from "./detail/SourceCheckDetails";

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

/** 選択部屋の計算式と辺ごとの内訳を表示し、図面上の強調表示や表示名の編集と連動する。 */
function RoomDetail({ result, room, originalRoomName, hoverEdge, selectedEdge, onHoverEdge, onSelectEdge, onHoverSegments, pinnedSegments, onPinSegments, onRename, onShowOnPlan, onClose }: Props) {
  const s = result.settings;
  const mpp = s.meters_per_px;
  const [editing, setEditing] = useState(false);
  const [nameDraft, setNameDraft] = useState(room.name);

  const commitName = () => {
    const v = nameDraft.trim();
    // 元の名前と同じなら上書きを解除。それ以外 (再編集で変更なしを含む) は入力値をそのまま保持
    onRename(room.id, v && v !== (originalRoomName ?? "") ? v : null);
    setEditing(false);
  };

  return (
    <div className="detail">
      {/* 「算出根拠を見る」の着地先であることを名指しする (h2 は部屋名のまま) */}
      <p className="section-kicker">算出根拠（計算式・辺ごとの内訳）</p>
      <div className="detail-head">
        <span className="swatch lg" style={{ background: room.color }} />
        {editing ? (
          <form className="rename" onSubmit={(e) => { e.preventDefault(); commitName(); }}>
            <input
              autoFocus
              value={nameDraft}
              onChange={(e) => setNameDraft(e.target.value)}
              // 入力中の Esc はフォームの取消にし、画面全体の「選択解除」(window の Esc) には伝えない
              onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); setEditing(false); setNameDraft(room.name); } }}
              aria-label="部屋の表示名"
              maxLength={40}
            />
            <button type="submit" className="btn btn-primary btn-sm">決定</button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => { setEditing(false); setNameDraft(room.name); }}>取消</button>
          </form>
        ) : (
          <>
            <h2 tabIndex={-1} id="room-detail-heading">{room.name}</h2>
            <button type="button" className="btn btn-link btn-sm" onClick={() => { setNameDraft(originalRoomName === null && room.room_name === null ? "" : room.name); setEditing(true); }} title="表示名を変更 (JSON は変更しません)">
              {room.room_name === null ? "名前を付ける" : "表示名を変更"}
            </button>
            {room.name !== (originalRoomName ?? "") && room.room_name !== null && (
              <>
                <span className="tag">表示名を上書き中</span>
                <button type="button" className="btn btn-link btn-sm" onClick={() => onRename(room.id, null)} title="JSON に記載の名前 (無ければ自動命名) に戻します">元に戻す</button>
              </>
            )}
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
          壁部分 <b>{fmt(room.wall_area_gross_m2)} m²</b> − ドア控除 <b>{fmt(room.door_area_m2)} m²</b> ＝ <b>{fmt(room.wall_area_m2)} m²</b>
          <div className="muted small">
            壁部分 ＝ 壁長 {fmt(room.wall_length_m)} m × 天井高 {fmt(s.ceiling_height_m, 1)} m ／
            ドア控除 ＝ 控除ドア幅 {fmt(room.door_length_m)} m × ドア高 {fmt(s.door_height_m, 1)} m（{room.door_count} 箇所）
            {room.opening_length_m > 0.005 && <> ／ 壁なし長 {fmt(room.opening_length_m)} m は含めない</>}
          </div>
        </div>
      </div>

      <div className="metrics">
        <div className="metric">
          <div className="metric-label">床面積</div>
          <div className="metric-value">{fmt(room.floor_area_m2)} <small>m²</small></div>
          <div className="metric-formula" title="頂点座標からシューレース公式で算出">{floorAreaFormula(room, mpp)}</div>
          <div className="muted small">1 px ＝ {s.scale_m} m ÷ {s.scale_px} px ＝ {mpp.toFixed(5)} m（課題指定の縮尺）</div>
        </div>
        <div className="metric">
          <div className="metric-label">周長</div>
          <div className="metric-value">{fmt(room.perimeter_m)} <small>m</small></div>
          <div className="metric-formula">{perimeterFormula(room, mpp)}</div>
          <div className="muted small">うち壁あり {fmt(room.wall_length_m)} m ／ 壁なし {fmt(room.opening_length_m)} m</div>
        </div>
      </div>

      <EdgeBreakdownTable room={room} settings={s} hoverEdge={hoverEdge} selectedEdge={selectedEdge} onHoverEdge={onHoverEdge} onSelectEdge={onSelectEdge} onHoverSegments={onHoverSegments} pinnedSegments={pinnedSegments} onPinSegments={onPinSegments} />

      <SourceCheckDetails room={room} originalRoomName={originalRoomName} />
    </div>
  );
}

export default memo(RoomDetail);
