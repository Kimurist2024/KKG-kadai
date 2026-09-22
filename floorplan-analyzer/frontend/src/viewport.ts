import { bounds } from "./format";
import type { Vertex } from "./types";

/** 部屋全体と画面上24pxの余白を、縦横両方に収める表示範囲。 */
export function fitRoomViewport(vertices: Vertex[], width: number, height: number) {
  const b = bounds(vertices);
  const w = Math.max(1, b.maxX - b.minX);
  const h = Math.max(1, b.maxY - b.minY);
  const padding = Math.min(24, width / 8, height / 8);
  const scale = Math.min((width - 2 * padding) / w, (height - 2 * padding) / h);
  const viewW = width / scale, viewH = height / scale;
  // 画像端の部屋も中央に配置するため、画像外への余白を許す。
  return { x: (b.minX + b.maxX - viewW) / 2, y: (b.minY + b.maxY - viewH) / 2, w: viewW, h: viewH };
}

/**
 * 重複の強調に輪を添えるかどうか。重複は壁沿いの細い帯になることが多く、外接円で囲むと巨大になって
 * 位置が分からなくなる。形そのものを縁取りで示すのを基本にし、画面上で縦横とも 24px 以下の
 * 見つけにくい重複にだけ、小さな輪（大きい方の辺の半分 + 8px）を返す。
 */
export function overlapRing(points: { x: number; y: number }[], unitsPerPx: number): { cx: number; cy: number; r: number } | null {
  if (!points.length) return null;
  const xs = points.map((p) => p.x), ys = points.map((p) => p.y);
  const left = Math.min(...xs), right = Math.max(...xs), top = Math.min(...ys), bottom = Math.max(...ys);
  const size = Math.max(right - left, bottom - top);
  if (size > 24 * unitsPerPx) return null;
  return { cx: (left + right) / 2, cy: (top + bottom) / 2, r: size / 2 + 8 * unitsPerPx };
}
