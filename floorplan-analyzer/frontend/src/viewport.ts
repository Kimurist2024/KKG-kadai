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
