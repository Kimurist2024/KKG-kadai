import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { AnalyzeResponse, Layers } from "../types";
import { bounds, fmt, labelPoint, regionPath } from "../format";
import { fitRoomViewport } from "../viewport";
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

const WALL_COLOR = "#e5484d";
const DOOR_COLOR = "#12a594";
const OPENING_COLOR = "#f59e0b";
const SELECT_COLOR = "#2563eb";
const ZOOM_STEPS = [100, 125, 150, 200, 250, 300, 400];

const pointsAttr = (vs: { x: number; y: number }[]) => vs.map((v) => `${v.x},${v.y}`).join(" ");

/** 解析結果を元画像に重ね、部屋・辺の選択、レイヤー、拡大・パンを扱う図面ビュー。 */
export default function FloorPlanView(props: Props) {
  const {
    result, imageUrl, layers, onLayersChange, selectedId, hoverId, hoverEdge, selectedEdge,
    highlightSegmentIds, onSelect, onHover, onHoverEdge, onSelectEdge,
  } = props;
  const overlapPattern = useId();
  const { width: W, height: H } = result.image;
  const [zoom, setZoom] = useState(100);
  const [awaitingFit, setAwaitingFit] = useState(false);
  const [fitRoom, setFitRoom] = useState(false); // 選択部屋に合わせて表示
  const fitModeActive = fitRoom || awaitingFit; // 部屋を選ぶ待機中もボタンを選択色にする
  const canvasRef = useRef<HTMLDivElement>(null);
  const pan = usePlanPan(canvasRef);
  const [containerW, setContainerW] = useState(800);
  const [fitHeight, setFitHeight] = useState(480);
  const fitting = fitRoom && selectedId !== null;
  const selected = result.rooms.find((r) => r.id === selectedId) ?? null;

  // 表示領域の幅を監視し、辺番号などを「画面上のピクセル」基準で決める (スマホでも押せる大きさに)
  useEffect(() => {
    const el = canvasRef.current;
    if (!el) return;
    const resizeHeight = () => setFitHeight(Math.max(1, Math.min(480, window.innerHeight * 0.5) - 2));
    resizeHeight();
    window.addEventListener("resize", resizeHeight);
    const ro = new ResizeObserver((entries) => setContainerW(entries[0].contentRect.width || 800));
    ro.observe(el);
    return () => { ro.disconnect(); window.removeEventListener("resize", resizeHeight); };
  }, []);
  const highlight = useMemo(() => new Set(highlightSegmentIds), [highlightSegmentIds]);

  useEffect(() => { if (!selected) setFitRoom(false); }, [selected]);

  useEffect(() => {
    if (awaitingFit && selected) {
      setFitRoom(true);
      setZoom(100);
      setAwaitingFit(false);
    }
  }, [awaitingFit, selected]);

  useEffect(() => {
    if (canvasRef.current) {
      canvasRef.current.scrollTop = 0;
      canvasRef.current.scrollLeft = 0;
    }
    if (fitRoom) setZoom(100);
  // スクロールバーの出入りによる幅変化では移動位置・倍率をリセットしない。
  }, [fitRoom, selected?.id]);

  // 表示範囲 (viewBox): 全体 or 選択部屋の周囲
  const viewBox = useMemo(() => {
    if (fitRoom && selected) {
      return fitRoomViewport(selected.vertices, containerW, fitHeight);
    }
    return { x: 0, y: 0, w: W, h: H };
  }, [fitRoom, selected, W, H, containerW, fitHeight]);
  // 1 画面ピクセルあたりの図面座標 (ユーザー単位)
  const unitsPerPx = viewBox.w / Math.max(1, (containerW * zoom) / 100);
  const labelSize = (fitting ? 16 : 12) * unitsPerPx; // 部屋名: 図面に比例、ただし画面上 10px 以上
  const badgeR = 12 * unitsPerPx; // 辺番号: 画面上 半径 12px
  const badgeFont = 13 * unitsPerPx;
  const hitWidth = 28 * unitsPerPx; // 辺の当たり判定: 画面上 28px

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
          fontSize: Math.max(Math.min(labelSize * 0.55, 9 * unitsPerPx), Math.min(labelSize, (b.maxX - b.minX) / (r.name.length * 1.05 + 0.5))),
        };
      }),
    [result.rooms, labelSize, unitsPerPx],
  );

  const toggle = (k: keyof Layers) => onLayersChange({ ...layers, [k]: !layers[k] });
  const zoomIdx = ZOOM_STEPS.indexOf(zoom);
  const zoomBy = (d: number) => setZoom(ZOOM_STEPS[Math.max(0, Math.min(ZOOM_STEPS.length - 1, zoomIdx + d))]);

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
          <button type="button" className={`btn btn-sm ${!fitModeActive ? "active" : ""}`} aria-pressed={!fitModeActive} onClick={() => { setFitRoom(false); setAwaitingFit(false); setZoom(100); }}>全体</button>
          <button type="button" className={`btn btn-sm ${fitModeActive ? "active" : ""}`} aria-pressed={fitModeActive} onClick={() => {
            if (selected) { setFitRoom(true); setZoom(100); if (canvasRef.current) { canvasRef.current.scrollTop = 0; canvasRef.current.scrollLeft = 0; } }
            else { setAwaitingFit(true); onLayersChange({ ...layers, rooms: true }); }
          }} title={selected ? "選択中の部屋の周囲を表示" : "押した後、図面または表から拡大する部屋を選択"}>
            選択部屋に合わせる
          </button>
          <button type="button" className="btn btn-sm" onClick={() => zoomBy(-1)} disabled={zoomIdx <= 0} aria-label="縮小">−</button>
          <span className="zoom-label" title="表示範囲に収めた状態を100%とする表示倍率。面積計算の縮尺は変わりません。">{fitting ? "フィット " : ""}{zoom}%</span>
          <button type="button" className="btn btn-sm" onClick={() => zoomBy(1)} disabled={zoomIdx >= ZOOM_STEPS.length - 1} aria-label="拡大">＋</button>
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
          {layers.walls &&
            result.walls.map((w) => (
              <g key={`w${w.id}`} pointerEvents="none">
                {highlight.has(w.id) && <line x1={w.start.x} y1={w.start.y} x2={w.end.x} y2={w.end.y} stroke="#fff" strokeWidth={12 * unitsPerPx} strokeLinecap="round" />}
                <line x1={w.start.x} y1={w.start.y} x2={w.end.x} y2={w.end.y} stroke={WALL_COLOR} strokeWidth={(highlight.has(w.id) ? 7 : 3) * unitsPerPx} strokeLinecap="round" opacity={highlight.size && !highlight.has(w.id) ? 0.45 : 0.9}>
                  <title>{`壁 id=${w.id}  ${fmt(w.length_m)} m (${fmt(w.length_px, 1)} px)`}</title>
                </line>
              </g>
            ))}
          {layers.doors &&
            result.doors.map((d) => (
              <g key={`d${d.id}`} pointerEvents="none">
                {highlight.has(d.id) && <line x1={d.start.x} y1={d.start.y} x2={d.end.x} y2={d.end.y} stroke="#fff" strokeWidth={14 * unitsPerPx} strokeLinecap="round" />}
                <line x1={d.start.x} y1={d.start.y} x2={d.end.x} y2={d.end.y} stroke={DOOR_COLOR} strokeWidth={(highlight.has(d.id) ? 9 : 4) * unitsPerPx} strokeLinecap="round" opacity={highlight.size && !highlight.has(d.id) ? 0.45 : 0.95}>
                  <title>{`ドア id=${d.id}  ${fmt(d.length_m)} m (${fmt(d.length_px, 1)} px)`}</title>
                </line>
              </g>
            ))}

          {/* 選択中の部屋: 辺ごとの 壁あり / 開口 / ドア 区間と辺番号 */}
          {selected &&
            selected.edges.map((e) => {
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

          {/* 部屋名ラベル */}
          {layers.labels &&
            shapes.map(({ room: r, label: c, fontSize: size }) => (
              <text key={`t${r.id}`} x={c.x} y={c.y} textAnchor="middle" dominantBaseline="central" fontSize={size} fontWeight={700} fill="#111" stroke="#fff" strokeWidth={3 * unitsPerPx} paintOrder="stroke" opacity={selectedId !== null && selectedId !== r.id ? 0.45 : 1} pointerEvents="none">
                {r.name}
              </text>
            ))}
        </svg>
      </div>

      <p className="muted small">拡大した図面はマウスでドラッグして移動できます。スクロールバー・ホイールでも移動できます。</p>
      <div className="legend">
        {!!result.overlaps?.length && <span><i style={{ background: "#a21caf" }} /> 紫斜線：部屋の重複</span>}
        {selected?.edges.some(e => e.inferred_wall_intervals?.length) && <span>紫点線：扉から補完した壁</span>}
        <span><i style={{ background: WALL_COLOR }} /> 壁 (検出線分)</span>
        <span><i style={{ background: DOOR_COLOR }} /> ドア (検出線分)</span>
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
