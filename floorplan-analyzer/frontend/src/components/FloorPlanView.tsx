import { useId, useMemo, useRef } from "react";
import type { AnalyzeResponse, Layers } from "../types";
import { bounds, fmt, labelPoint, regionPath } from "../format";
import { usePlanViewport } from "../hooks/usePlanViewport";
import DetectedSegmentLayer from "./plan/DetectedSegmentLayer";
import SelectedRoomEdges from "./plan/SelectedRoomEdges";
import { WALL_COLOR, DOOR_COLOR, OPENING_COLOR, SELECT_COLOR } from "./plan/colors";
import { usePlanPan } from "../hooks/usePlanPan";

interface Props {
  result: AnalyzeResponse;
  imageUrl: string | null;
  layers: Layers;
  onLayersChange: (l: Layers) => void;
  selectedId: number | null;
  hoverId: number | null;
  hoverEdge: number | null;
  selectedEdge: number | null;
  highlightSegmentIds: number[];
  onSelect: (id: number | null) => void;
  onHover: (id: number | null) => void;
  onHoverEdge: (index: number | null) => void;
  onSelectEdge: (index: number | null) => void;
}

const pointsAttr = (vs: { x: number; y: number }[]) => vs.map((v) => `${v.x},${v.y}`).join(" ");

/** 解析結果を元画像に重ね、部屋・辺の選択、レイヤー、拡大・パンを扱う図面ビュー。 */
export default function FloorPlanView(props: Props) {
  const {
    result, imageUrl, layers, onLayersChange, selectedId, hoverId, hoverEdge, selectedEdge,
    highlightSegmentIds, onSelect, onHover, onHoverEdge, onSelectEdge,
  } = props;
  const overlapPattern = useId();
  const { width: W, height: H } = result.image;
  const canvasRef = useRef<HTMLDivElement>(null);
  const pan = usePlanPan(canvasRef);
  const selected = result.rooms.find((r) => r.id === selectedId) ?? null;
  const {
    zoom, awaitingFit, viewBox, fitting, fitModeActive, fitHeight,
    unitsPerPx, labelSize, badgeR, badgeFont, hitWidth,
    canZoomIn, canZoomOut, zoomIn, zoomOut, showWhole, fitToSelected, requestFit,
  } = usePlanViewport({ canvasRef, selected, selectedId, imageWidth: W, imageHeight: H });
  const highlight = useMemo(() => new Set(highlightSegmentIds), [highlightSegmentIds]);

  // ホバーのたびに再計算しないよう、部屋ごとの静的な描画データはメモ化
  const shapes = useMemo(
    () =>
      result.rooms.map((r) => {
        const b = bounds(r.vertices);
        return {
          room: r,
          points: pointsAttr(r.vertices),
          label: r.label_point ?? labelPoint(r.vertices),
          path: regionPath(r.vertices, r.holes),
          // 部屋幅に収まる大きさまで縮めるが、画面上 10px を下限にして読めなくならないようにする
          fontSize: Math.max(10 * unitsPerPx, Math.min(labelSize, (b.maxX - b.minX) / (r.name.length * 1.05 + 0.5))),
        };
      }),
    [result.rooms, labelSize, unitsPerPx],
  );

  const toggle = (k: keyof Layers) => onLayersChange({ ...layers, [k]: !layers[k] });

  return (
    <div className="plan">
      <div className="plan-toolbar">
        <span className="toolbar-group" role="group" aria-label="表示レイヤー">
          {([["image", "元画像"], ["rooms", "部屋"], ["walls", "壁"], ["doors", "ドア"], ["labels", "部屋名"]] as [keyof Layers, string][]).map(([k, label]) => (
            <label key={k} className="chk">
              <input type="checkbox" checked={layers[k]} onChange={() => toggle(k)} /> {label}
            </label>
          ))}
        </span>
        <span className="spacer" />
        <span className="toolbar-group" role="group" aria-label="表示範囲">
          <button type="button" className={`btn btn-sm ${!fitModeActive ? "active" : ""}`} aria-pressed={!fitModeActive} onClick={showWhole}>全体</button>
          <button type="button" className={`btn btn-sm ${fitModeActive ? "active" : ""}`} aria-pressed={fitModeActive} onClick={() => {
            if (selected) { fitToSelected(); }
            else { requestFit(); onLayersChange({ ...layers, rooms: true }); }
          }} title={selected ? "選択中の部屋の周囲を表示" : "押した後、図面または表から拡大する部屋を選択"}>
            選択部屋に合わせる
          </button>
          <button type="button" className="btn btn-sm" onClick={zoomOut} disabled={!canZoomOut} aria-label="縮小">−</button>
          <span className="zoom-label" title="表示範囲に収めた状態を100%とする表示倍率。面積計算の縮尺は変わりません。">{fitting ? "フィット " : ""}{zoom}%</span>
          <button type="button" className="btn btn-sm" onClick={zoomIn} disabled={!canZoomIn} aria-label="拡大">＋</button>
        </span>
      </div>

      {awaitingFit && <p className="status info" role="status">拡大する部屋を図面または表でクリックしてください。全体ボタンで取り消せます。</p>}
      <div className="plan-canvas" role="region" aria-label="平面図のスクロール領域" tabIndex={0} ref={canvasRef} style={{ height: fitting ? fitHeight + 2 : undefined }}>
        <svg
          {...pan}
          onDragStart={(event) => event.preventDefault()}
          viewBox={`${viewBox.x} ${viewBox.y} ${viewBox.w} ${viewBox.h}`}
          style={{ width: `${zoom}%`, height: fitting ? fitHeight * zoom / 100 : undefined }}
          preserveAspectRatio="xMidYMid meet"
          role="img"
          aria-label="平面図の解析結果"
        >
          <defs><pattern id={overlapPattern} width={8 * unitsPerPx} height={8 * unitsPerPx} patternUnits="userSpaceOnUse"><path d={`M 0,0 L ${8 * unitsPerPx},${8 * unitsPerPx}`} stroke="#a21caf" strokeWidth={2 * unitsPerPx} /></pattern></defs>
          {/* 背景クリックで選択解除 (背景矩形にだけ付ける) */}
          <rect x={0} y={0} width={W} height={H} fill="#fff" onClick={() => onSelect(null)} />
          {layers.image && imageUrl && <image href={imageUrl} x={0} y={0} width={W} height={H} pointerEvents="none" />}

          {/* 部屋領域 */}
          {layers.rooms &&
            shapes.map(({ room: r, points, path }) => {
              const Shape = r.holes?.length ? "path" : "polygon";
              const isSel = r.id === selectedId;
              const isHover = r.id === hoverId;
              // ホバーを優先し、選択済みの部屋でもカーソル位置がはっきり分かる濃さにする。
              const fillOpacity = isHover ? 0.8 : isSel ? 0.55 : selectedId !== null ? 0.12 : 0.32;
              return (
                <Shape
                  key={r.id}
                  points={points}
                  d={path}
                  fillRule="evenodd"
                  fill={r.color}
                  fillOpacity={fillOpacity}
                  stroke={isSel ? SELECT_COLOR : r.color}
                  strokeWidth={(isSel || isHover ? 3 : 1.5) * unitsPerPx}
                  strokeLinejoin="round"
                  style={{ cursor: "pointer", transition: "fill-opacity .15s" }}
                  onClick={() => onSelect(isSel ? null : r.id)}
                  onMouseEnter={() => onHover(r.id)}
                  onMouseLeave={() => onHover(null)}
                >
                  <title>{`${r.name}\n床面積 ${fmt(r.floor_area_m2)} m²\n周長 ${fmt(r.perimeter_m)} m\n壁面積 ${fmt(r.wall_area_m2)} m²`}</title>
                </Shape>
              );
            })}

          {layers.rooms && result.overlaps?.flatMap((overlap, i) => overlap.regions.map((region, j) => <path key={`overlap-${i}-${j}`} data-overlap="true" d={regionPath(region.vertices, region.holes)} fillRule="evenodd" fill={`url(#${overlapPattern})`} stroke="#a21caf" strokeWidth={unitsPerPx} pointerEvents="none" />))}

          {/* 壁・ドア (検出線分) */}
          {layers.walls && <DetectedSegmentLayer segments={result.walls} highlight={highlight} unitsPerPx={unitsPerPx} color={WALL_COLOR} strokeWidth={3} highlightedStrokeWidth={7} haloWidth={12} opacity={0.9} keyPrefix="w" titleKind="壁" />}
          {layers.doors && <DetectedSegmentLayer segments={result.doors} highlight={highlight} unitsPerPx={unitsPerPx} color={DOOR_COLOR} strokeWidth={4} highlightedStrokeWidth={9} haloWidth={14} opacity={0.95} keyPrefix="d" titleKind="ドア" />}

          {selected && <SelectedRoomEdges selected={selected} selectedEdge={selectedEdge} hoverEdge={hoverEdge} onSelectEdge={onSelectEdge} onHoverEdge={onHoverEdge} unitsPerPx={unitsPerPx} hitWidth={hitWidth} badgeR={badgeR} badgeFont={badgeFont} />}

          {/* 部屋名ラベル */}
          {layers.labels &&
            shapes.map(({ room: r, label: c, fontSize: size }) => (
              <text key={`t${r.id}`} x={c.x} y={c.y} textAnchor="middle" dominantBaseline="central" fontSize={size} fontWeight={700} fill="#111" stroke="#fff" strokeWidth={3 * unitsPerPx} paintOrder="stroke" opacity={selectedId !== null && selectedId !== r.id ? 0.45 : 1} pointerEvents="none">
                {r.name}
              </text>
            ))}
        </svg>
      </div>

      {/* 補助文は状態に合わせる: 拡大中だけ移動方法を、それ以外は拡大方法を案内する */}
      <p className="muted small">
        {zoom > 100 || fitting
          ? "拡大した図面はマウスでドラッグして移動できます。スクロールバー・ホイールでも移動できます。"
          : "「＋」で拡大、「選択部屋に合わせる」で選んだ部屋を大きく表示できます。表示倍率を変えても計算結果は変わりません。"}
      </p>
      <div className="legend">
        {!!result.overlaps?.length && layers.rooms && <span><i style={{ background: "#a21caf" }} /> 紫斜線：部屋の重複</span>}
        {selected?.edges.some(e => e.inferred_wall_intervals?.length) && <span>紫点線：扉から補完した壁</span>}
        {layers.walls && <span><i style={{ background: WALL_COLOR }} /> 壁 (検出線分)</span>}
        {layers.doors && <span><i style={{ background: DOOR_COLOR }} /> ドア (検出線分)</span>}
        {selected ? (
          <>
            <span><i style={{ background: "#9f1239" }} /> 壁あり区間</span>
            <span><i className="dashed" style={{ borderColor: OPENING_COLOR }} /> 壁なし区間</span>
            <span><i className="badge-legend">1</i> 辺番号 (クリックで選択・内訳表と対応)</span>
            <span className="plan-hint">{selectedEdge !== null ? `辺 ${selectedEdge + 1} を選択中` : "辺は未選択"}</span>
          </>
        ) : (
          <span className="muted">部屋をクリックすると辺ごとの壁区間を表示します</span>
        )}
      </div>
    </div>
  );
}
