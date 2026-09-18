"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import type { AnalyzeResponse, Layers, Warning, WarningCode } from "./types";
import { isWallWarning } from "./warnings";
import { fmt } from "./format";
import { useAnalysis } from "./hooks/useAnalysis";
import UploadPanel from "./components/UploadPanel";
import FloorPlanView from "./components/FloorPlanView";
import RoomTable from "./components/RoomTable";
import RoomDetail from "./components/RoomDetail";

const WARNING_LABELS: Record<WarningCode, { title: string; severity: "info" | "warn" }> = {
  room_overlap: { title: "部屋領域の重複", severity: "warn" },
  inferred_door_wall: { title: "扉部分の壁を補完", severity: "warn" },
  missing_wall_data: { title: "壁データなし", severity: "warn" },
  no_room_walls: { title: "壁が未検出の部屋", severity: "warn" },
  low_wall_coverage: { title: "壁の対応率が低い部屋", severity: "warn" },
  unnamed_room: { title: "部屋名が未設定", severity: "info" },
  unmatched_door: { title: "壁に対応付かないドア (控除されていません)", severity: "warn" },
  invalid_shape: { title: "形状に問題のある輪郭", severity: "warn" },
  ignored_contour: { title: "無視した輪郭", severity: "warn" },
  data_mismatch: { title: "JSON 記載値と再計算値の不一致", severity: "warn" },
  duplicate_id: { title: "id の重複", severity: "warn" },
  geometry_regularized: { title: "図面幾何を補正", severity: "info" },
  regularization_skipped: { title: "幾何補正を見送り", severity: "info" },
};

const EMPTY_OVERRIDES: Record<number, string> = {};

/** 解析状態と画面の選択状態をつなぎ、図面・結果表・算出根拠・警告を統合する。 */
export default function App() {
  const { file, isSample, imageUrl, appliedSettings, result, status, updatedAt, loadFile, loadSample } = useAnalysis();
  // 画面の見た目に関する状態
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [hoverId, setHoverId] = useState<number | null>(null);
  const [hoverEdge, setHoverEdge] = useState<number | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<number | null>(null);
  const [hoverSegments, setHoverSegments] = useState<number[]>([]);   // 一時的な強調 (ホバー/フォーカス)
  const [pinnedSegments, setPinnedSegments] = useState<number[]>([]); // 確定選択 (クリック。図面に戻っても保持)
  const [layers, setLayers] = useState<Layers>({ image: true, rooms: true, walls: true, doors: true, labels: true });
  // UI 上での表示名の上書き (JSON は変更しない)。読み込んだファイルに紐づけ、別ファイルには適用しない
  const [nameOverrides, setNameOverrides] = useState<{ fileKey: string; map: Record<number, string> }>({ fileKey: "", map: {} });
  const fileKey = file ? `${file.name}:${file.size}:${file.lastModified}` : "";
  const overrides = nameOverrides.fileKey === fileKey ? nameOverrides.map : EMPTY_OVERRIDES;
  const [flashDone, setFlashDone] = useState(false);
  const planRef = useRef<HTMLElement>(null);
  const detailRef = useRef<HTMLElement>(null);

  // 表示用の結果: 部屋名の上書きを反映。名前を付けた部屋は「未設定」扱いから外す (警告・タグも消す)
  const view: AnalyzeResponse | null = useMemo(() => {
    if (!result) return null;
    if (!Object.keys(overrides).length) return result;
    return {
      ...result,
      rooms: result.rooms.map((r) => (overrides[r.id] ? { ...r, name: overrides[r.id], room_name: overrides[r.id] } : r)),
      warnings: result.warnings.filter((w) => !(w.code === "unnamed_room" && w.contour_id !== null && overrides[w.contour_id])),
    };
  }, [result, overrides]);

  // 解析完了の通知を数秒だけ表示
  useEffect(() => {
    if (!updatedAt) return;
    setFlashDone(true);
    const t = setTimeout(() => setFlashDone(false), 4000);
    return () => clearTimeout(t);
  }, [updatedAt]);

  const selectRoom = useCallback((id: number | null) => {
    setSelectedId(id);
    setSelectedEdge(null);
    setHoverEdge(null);
    setHoverSegments([]);
    setPinnedSegments([]);
  }, []);

  const handleFile = useCallback(
    async (f: File) => {
      selectRoom(null);
      await loadFile(f); // 表示名はファイルに紐づくので、失敗しても現在のファイルの表示名は残る
    },
    [loadFile, selectRoom],
  );

  // サンプルは人が選んだときだけ読み込む。URL の ?sample=1 は、使い方ページの「サンプルで試す」から来た場合。
  // それ以外（パラメータ無し・?start=upload）は選択枠だけを表示する。URL の room はサンプル表示時の事前選択。
  const loadSampleRef = useRef(loadSample);
  loadSampleRef.current = loadSample;
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    if (q.get("sample") !== "1") return;
    const room = Number(q.get("room"));
    void Promise.resolve(loadSampleRef.current()).then(() => { if (q.has("room") && Number.isFinite(room)) setSelectedId(room); });
  }, []);

  useEffect(() => {
    if (result && selectedId !== null && !result.rooms.some((r) => r.id === selectedId)) selectRoom(null);
  }, [result, selectedId, selectRoom]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") selectRoom(null); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectRoom]);

  const scrollTo = useCallback((ref: React.RefObject<HTMLElement | null>) => {
    // 動きを減らす設定 (prefers-reduced-motion) ではスムーズスクロールを使わない
    const reduce = typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
    ref.current?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  }, []);
  const showDetail = useCallback(() => {
    scrollTo(detailRef);
    // スクロール後に見出しへフォーカス (スクリーンリーダー・キーボード利用者のため)
    setTimeout(() => detailRef.current?.querySelector<HTMLElement>("#room-detail-heading")?.focus({ preventScroll: true }), 400);
  }, [scrollTo]);
  const showOnPlan = useCallback(() => scrollTo(planRef), [scrollTo]);
  const closeDetail = useCallback(() => selectRoom(null), [selectRoom]);
  const renameRoom = useCallback((id: number, name: string | null) => {
    setNameOverrides((o) => {
      const map = { ...(o.fileKey === fileKey ? o.map : {}) };
      if (name) map[id] = name; else delete map[id];
      return { fileKey, map };
    });
  }, [fileKey]);

  // 注意事項: 種類ごとにまとめ、対象の部屋/線分へ誘導する
  const warningGroups = useMemo(() => {
    if (!view) return [];
    const map = new Map<WarningCode, Warning[]>();
    // 専用ブロックで見せるもの (壁の要確認、重複箇所) は診断一覧から外し、同じ内容を二重に並べない
    const hasOverlapBlock = !!view.overlaps?.length;
    view.warnings
      .filter((w) => !isWallWarning(w) && !(w.code === "room_overlap" && hasOverlapBlock))
      .forEach((w) => map.set(w.code, [...(map.get(w.code) ?? []), w]));
    const order: WarningCode[] = ["room_overlap", "inferred_door_wall", "geometry_regularized", "regularization_skipped", "missing_wall_data", "no_room_walls", "low_wall_coverage", "unmatched_door", "data_mismatch", "ignored_contour", "invalid_shape", "duplicate_id", "unnamed_room"];
    return order.filter((c) => map.has(c)).map((c) => ({ code: c, items: map.get(c)! }));
  }, [view]);
  const roomIds = useMemo(() => new Set(view?.rooms.map((r) => r.id) ?? []), [view]);
  const lineIds = useMemo(() => new Set([...(view?.walls ?? []), ...(view?.doors ?? [])].map((s) => s.id)), [view]);
  const locateWarning = (w: Warning) => {
    if (w.contour_id === null) return;
    if (roomIds.has(w.contour_id)) { selectRoom(w.contour_id); scrollTo(planRef); }
    else if (lineIds.has(w.contour_id)) { setPinnedSegments([w.contour_id]); scrollTo(planRef); }
  };
  const hasWarnOnly = warningGroups.some((g) => WARNING_LABELS[g.code].severity === "warn");

  const wallWarnings = view?.warnings.filter(isWallWarning) ?? [];
  const hasChecks = warningGroups.length > 0 || wallWarnings.length > 0 || !!view?.overlaps?.length;
  const selectedRoom = view?.rooms.find((r) => r.id === selectedId) ?? null;
  const loading = status.state === "loading";

  return (
    <main className="app">
      <header className="header">
        <div>
          <h1>平面図 面積・壁面積 解析</h1>
          <p className="muted">部屋・壁・ドアのセグメンテーション結果 (JSON) から、部屋ごとの床面積・周長・壁面積を算出します。</p>
          <nav className="guide-entry" aria-label="操作ガイド"><Link href="/guide">はじめての方へ：使い方を見る</Link></nav>
        </div>
        {view && (
          <div className="summary-cards">
            {/* 課題の主役である壁面積を先頭に置く。重複除外は床面積カードの副行にまとめる */}
            <div className="card card-primary"><span className="card-label">壁面積 合計（内壁・両面計上）{wallWarnings.length > 0 && <b className="wall-review" title="壁が未検出または対応率が低い部屋を含みます。図面下の「解析結果の確認事項」に理由があります">要確認</b>}</span><span className="card-value">{fmt(view.summary.total_wall_area_m2)} <small>m²</small></span></div>
            <div className="card">
              <span className="card-label">床面積 合計（部屋別の合算）</span>
              <span className="card-value">{fmt(view.summary.total_floor_area_m2)} <small>m²</small></span>
              {(view.summary.overlap_floor_area_m2 ?? 0) > 0 && <span className="card-sub" title="部屋領域が重なっている分を除いた床面積">重複を除くと {fmt(view.summary.union_floor_area_m2!)} m²</span>}
            </div>
            <div className="card"><span className="card-label">部屋数</span><span className="card-value">{view.summary.room_count}</span></div>
          </div>
        )}
      </header>

      <section className="panel">
        <UploadPanel fileName={file?.name ?? null} isSample={isSample} loading={loading} onFile={handleFile} onLoadSample={() => { selectRoom(null); void loadSample(); }} compact={!!file || loading} />
        <section className="workspace-section" aria-labelledby="conditions-heading">
        <h2 id="conditions-heading" className="section-heading">課題指定の計算条件（固定）</h2>
        <div className="conditions">
          <span className="cond-chip">天井高 <b>{fmt(appliedSettings.ceiling_height_m, 1)} m</b></span>
          <span className="cond-chip">ドア高 <b>{fmt(appliedSettings.door_height_m, 1)} m</b></span>
          <span className="cond-chip" title={`図面上の ${appliedSettings.scale_px} px を ${appliedSettings.scale_m} m として換算します。縮尺の異なる図面では実寸と一致しません`}>スケール <b>{appliedSettings.scale_px} px ＝ {appliedSettings.scale_m} m</b></span>
        </div>
        {/* 課題の中心となる式を、条件チップの直下で常時読めるようにする（使い方ページと同じ文言） */}
        <p className="section-description conditions-note">課題の指定値で固定しています（入力・変更は不要。JSON を選ぶとこの条件で即時解析）。壁面積 ＝ 壁長 × 天井高 {fmt(appliedSettings.ceiling_height_m, 1)} m − 控除ドア幅 × ドア高 {fmt(appliedSettings.door_height_m, 1)} m（壁が検出されない区間は含めない）／ 床面積 ＝ 頂点座標の面積 × (m/px)²</p>
        </section>
        {loading && <div className="status loading" role="status" aria-live="polite">解析中…{view ? "（前回の結果を表示中）" : ""}</div>}
        {!loading && flashDone && <div className="status done" role="status" aria-live="polite">結果を更新しました</div>}
        {status.state === "error" && <div className="status error" role="alert">エラー: {status.message}</div>}

      </section>

      {view && (
        <>
          <section className="main-grid" aria-busy={loading}>
            <section className="panel" ref={planRef} aria-labelledby="plan-heading">
              <h2 id="plan-heading" className="section-heading">図面（可視化結果）</h2>
              <FloorPlanView
                result={view}
                imageUrl={imageUrl}
                layers={layers}
                onLayersChange={setLayers}
                selectedId={selectedId}
                hoverId={hoverId}
                hoverEdge={hoverEdge}
                selectedEdge={selectedEdge}
                highlightSegmentIds={hoverSegments.length ? hoverSegments : pinnedSegments}
                onSelect={selectRoom}
                onHover={setHoverId}
                onHoverEdge={setHoverEdge}
                onSelectEdge={setSelectedEdge}
              />
              {selectedRoom && (
                <div className="selection-bar" role="status">
                  <span className="swatch" style={{ background: selectedRoom.color }} />
                  <b>{selectedRoom.name}</b>
                  <span>床面積 {fmt(selectedRoom.floor_area_m2)} m²</span>
                  <span>壁面積 <b>{fmt(selectedRoom.wall_area_m2)} m²</b></span>
                  {selectedEdge !== null && <span className="plan-hint">辺 {selectedEdge + 1} を選択中</span>}
                  <span className="spacer" />
                  <button type="button" className="btn btn-primary btn-sm" onClick={showDetail}>算出根拠を見る ↓</button>
                  <button type="button" className="btn btn-secondary btn-sm" onClick={() => selectRoom(null)}>選択解除</button>
                </div>
              )}
              {view && hasChecks && <section className="workspace-section result-checks" aria-labelledby="checks-heading">
              <h2 id="checks-heading" className="section-heading">解析結果の確認事項</h2>
              <p className="section-description">表示中の図面に対する検出結果です。対象箇所と入力データを確認してください。</p>
              <div className="result-checks-scroll" role="region" aria-label="確認事項のスクロール領域" tabIndex={0}>
              {!!view?.overlaps?.length && <details className="status warn overlap-check">
                <summary><span className="check-title">重複箇所を図面で確認</span><span className="check-description">部屋の組み合わせ・重複面積・対象への移動</span></summary>
                <p>紫の斜線が重複部分です。部屋別の面積は変更せず、合計から重複計上分 {fmt(view.summary.overlap_floor_area_m2 ?? 0)} m² を除いた値を併記しています。どの部屋に属するか確認してください。</p>
                <ul>{view.overlaps.map((overlap, i) => <li key={i}>{overlap.room_ids.map(id => view.rooms.find(r => r.id === id)?.name ?? `#${id}`).join(" / ")}：{fmt(overlap.area_m2)} m²
                  {overlap.room_ids.map(id => <button type="button" className="btn btn-link" key={id} onClick={() => { selectRoom(id); scrollTo(planRef); }}>部屋 #{id} を確認</button>)}
                </li>)}</ul>
              </details>}
              {wallWarnings.length > 0 && (
                <div className="status warn" role="alert">
                  <strong>壁面積は要確認です</strong>
                  <p>壁が未検出、または対応率が低い結果を含みます。0 m² を「壁なし」と確定せず、壁レイヤーと計算条件を確認してください。</p>
                  <ul>{wallWarnings.map((w, i) => <li key={i}>{w.message}{w.contour_id !== null && <button type="button" className="btn btn-link" onClick={() => locateWarning(w)}>対象を確認</button>}</li>)}</ul>
                </div>
              )}
              {view && warningGroups.length > 0 && (
                <details className={`status diagnostics-check ${hasWarnOnly ? "warn" : "info"}`}>
                  <summary>
                    <span className="check-title">診断メッセージ一覧</span>
                    <span className="check-description">{warningGroups.map((g) => `${WARNING_LABELS[g.code].title} ${g.items.length} 件`).join("、")}</span>
                  </summary>
                  {warningGroups.map((g) => (
                    <div key={g.code} className="warn-group">
                      <div className="warn-title">{WARNING_LABELS[g.code].title}</div>
                      <ul>
                        {g.items.map((w, i) => (
                          <li key={i}>
                            {w.message}
                            {w.contour_id !== null && (roomIds.has(w.contour_id) || lineIds.has(w.contour_id)) && (
                              <button type="button" className="btn btn-link btn-sm" onClick={() => locateWarning(w)}>対象を確認</button>
                            )}
                          </li>
                        ))}
                      </ul>
                      {g.code === "unnamed_room" && <div className="muted small">部屋を選択して「名前を付ける」から表示名を設定できます（JSON は変更しません）。</div>}
                    </div>
                  ))}
                </details>
              )}
              </div>
              </section>}
            </section>
            <section className="panel" aria-labelledby="table-heading">
              <RoomTable result={view} selectedId={selectedId} hoverId={hoverId} onSelect={selectRoom} onHover={setHoverId} onShowDetail={showDetail} />
            </section>
          </section>
          {selectedRoom && (
            <section className="panel" ref={detailRef} aria-label="算出根拠">
              <RoomDetail
                key={`${fileKey}:${selectedRoom.id}`} // 部屋やファイルを切り替えたら編集状態を初期化する
                result={view}
                room={selectedRoom}
                originalRoomName={result?.rooms.find((r) => r.id === selectedRoom.id)?.room_name ?? null}
                hoverEdge={hoverEdge}
                selectedEdge={selectedEdge}
                onHoverEdge={setHoverEdge}
                onSelectEdge={setSelectedEdge}
                onHoverSegments={setHoverSegments}
                pinnedSegments={pinnedSegments}
                onPinSegments={setPinnedSegments}
                onRename={renameRoom}
                onShowOnPlan={showOnPlan}
                onClose={closeDetail}
              />
            </section>
          )}
        </>
      )}

      <footer className="footer muted">
        床面積: 頂点座標のシューレース公式 × スケール² ／ 壁面積: 辺上に検出された壁区間の長さ × 天井高 − ドア幅 × ドア高（壁のない区間は除外）
      </footer>
    </main>
  );
}
