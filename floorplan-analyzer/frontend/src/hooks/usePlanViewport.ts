import { useEffect, useMemo, useState } from "react";
import type { RefObject } from "react";
import type { RoomResult } from "../types";
import { fitRoomViewport } from "../viewport";

interface Props {
  canvasRef: RefObject<HTMLDivElement | null>;
  selected: RoomResult | null;
  selectedId: number | null;
  imageWidth: number;
  imageHeight: number;
}

const ZOOM_STEPS = [100, 125, 150, 200, 250, 300, 400];

export function usePlanViewport({ canvasRef, selected, selectedId, imageWidth: W, imageHeight: H }: Props) {
  const [zoom, setZoom] = useState(100);
  const [awaitingFit, setAwaitingFit] = useState(false);
  const [fitRoom, setFitRoom] = useState(false); // 選択部屋に合わせて表示
  const fitModeActive = fitRoom || awaitingFit; // 部屋を選ぶ待機中もボタンを選択色にする
  const [containerW, setContainerW] = useState(800);
  const [fitHeight, setFitHeight] = useState(480);
  const fitting = fitRoom && selectedId !== null;

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

  const zoomIdx = ZOOM_STEPS.indexOf(zoom);
  const zoomBy = (d: number) => setZoom(ZOOM_STEPS[Math.max(0, Math.min(ZOOM_STEPS.length - 1, zoomIdx + d))]);
  const zoomIn = () => zoomBy(1);
  const zoomOut = () => zoomBy(-1);
  const showWhole = () => { setFitRoom(false); setAwaitingFit(false); setZoom(100); };
  const fitToSelected = () => {
    if (selected) { setFitRoom(true); setZoom(100); if (canvasRef.current) { canvasRef.current.scrollTop = 0; canvasRef.current.scrollLeft = 0; } }
  };
  const requestFit = () => setAwaitingFit(true);

  return {
    zoom, awaitingFit, viewBox, fitting, fitModeActive, fitHeight,
    unitsPerPx, labelSize, badgeR, badgeFont, hitWidth,
    canZoomIn: zoomIdx < ZOOM_STEPS.length - 1, canZoomOut: zoomIdx > 0,
    zoomIn, zoomOut, showWhole, fitToSelected, requestFit,
  };
}
