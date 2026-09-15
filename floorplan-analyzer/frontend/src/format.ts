import { wallWarningsForRoom, isWallWarning } from "./warnings";
import type { AnalyzeResponse, EdgeResult, RoomResult, Vertex } from "./types";

// 桁数ごとに整形器を再利用する。図面の値そのものは保持せず、表示の丸め方も変えない。
const numberFormats = new Map<number, Intl.NumberFormat>();
export function fmt(n: number, digits = 2): string {
  let formatter = numberFormats.get(digits);
  if (!formatter) {
    formatter = new Intl.NumberFormat("ja-JP", { minimumFractionDigits: digits, maximumFractionDigits: digits });
    numberFormats.set(digits, formatter);
  }
  return formatter.format(n);
}

export const fmtPt = (v: Vertex): string => `(${v.x.toFixed(0)}, ${v.y.toFixed(0)})`;

/** 床面積の算出根拠 (シューレース公式 → スケール換算) */
export function floorAreaFormula(r: RoomResult, mpp: number): string {
  return `${r.holes?.length ? "穴を除いた面積 " : ""}${fmt(r.floor_area_px2, 1)} px² × (${mpp.toFixed(5)} m/px)² = ${fmt(r.floor_area_m2)} m²`;
}

export function perimeterFormula(r: RoomResult, mpp: number): string {
  return `${fmt(r.perimeter_px, 1)} px × ${mpp.toFixed(5)} m/px = ${fmt(r.perimeter_m)} m`;
}

/** 辺ごとの壁面積の計算式 */
export function edgeWallFormula(e: EdgeResult, ceiling: number, door: number): string {
  if (e.wall_length_m <= 1e-9) return "壁なし (開口) → 0 m²";
  const base = `${fmt(e.wall_length_m)} m × ${ceiling} m`;
  if (e.door_length_m <= 1e-9) return `${base} = ${fmt(e.wall_area_m2)} m²`;
  return `${base} − ${fmt(e.door_length_m)} m × ${door} m = ${fmt(e.wall_area_m2)} m²`;
}

/** 部屋全体の壁面積の計算式 */
export function roomWallFormula(r: RoomResult, ceiling: number, door: number): string {
  const gross = `${fmt(r.wall_length_m)} m × ${ceiling} m`;
  if (r.door_length_m <= 1e-9) return `${gross} = ${fmt(r.wall_area_m2)} m²`;
  return `${gross} − ${fmt(r.door_length_m)} m × ${door} m = ${fmt(r.wall_area_gross_m2)} − ${fmt(r.door_area_m2)} = ${fmt(r.wall_area_m2)} m²`;
}

/** 表を CSV (UTF-8 BOM 付き, Excel で開ける) にする */
export function roomsToCsv(res: AnalyzeResponse): string {
  const header = ["部屋名", "床面積[m2]", "周長[m]", "壁長[m]", "開口長[m]", "ドア長[m]", "ドア数", "壁面積(控除前)[m2]", "ドア控除[m2]", "壁面積[m2]", "壁面積の注意事項", "解析の注意事項"];
  const rows = res.rooms.map((r) => [
    r.name,
    r.floor_area_m2.toFixed(3),
    r.perimeter_m.toFixed(3),
    r.wall_length_m.toFixed(3),
    r.opening_length_m.toFixed(3),
    r.door_length_m.toFixed(3),
    String(r.door_count),
    r.wall_area_gross_m2.toFixed(3),
    r.door_area_m2.toFixed(3),
    r.wall_area_m2.toFixed(3),
    wallWarningsForRoom(res, r.id).map((w) => w.message).join(" / "),
    res.warnings.filter((w) => (w.code === "ai_generated" || w.code === "inferred_door_wall" || w.code === "room_overlap") && (w.contour_id === null || w.contour_id === r.id)).map((w) => w.message).join(" / "),
  ]);
  rows.push([
    "合計",
    res.summary.total_floor_area_m2.toFixed(3),
    "", "", "", "", "", "", "",
    res.summary.total_wall_area_m2.toFixed(3),
    res.warnings.some(isWallWarning) ? "要確認の壁面積を含みます" : "",
    res.warnings.filter((w) => ["ai_generated", "inferred_door_wall", "room_overlap"].includes(w.code)).map((w) => w.message).join(" / "),
  ]);
  if ((res.summary.overlap_floor_area_m2 ?? 0) > 0) {
    rows.push(["重複を除いた床面積", res.summary.union_floor_area_m2!.toFixed(3), "", "", "", "", "", "", "", "", "", "部屋別の帰属は未確定"]);
  }
  // 外部由来の文字列 (部屋名) が表計算ソフトで数式として評価されないようにする
  const safeText = (s: string) => (/^[\s\u0000-\u001f]*[=+\-@]/.test(s) ? "'" + s : s);
  const esc = (s: string) => (/[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s);
  const safeRows = rows.map((r) => [safeText(r[0]), ...r.slice(1, -2), ...r.slice(-2).map(safeText)]);
  return "\ufeff" + [header, ...safeRows].map((r) => r.map(esc).join(",")).join("\r\n");
}

export function downloadText(filename: string, text: string, mime = "text/csv"): void {
  const blob = new Blob([text], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function pointInPolygon(p: Vertex, pts: Vertex[]): boolean {
  let inside = false;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const a = pts[i], b = pts[j];
    if (a.y > p.y !== b.y > p.y && p.x < ((b.x - a.x) * (p.y - a.y)) / (b.y - a.y) + a.x) inside = !inside;
  }
  return inside;
}

function distToEdges(p: Vertex, pts: Vertex[]): number {
  let best = Infinity;
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i], b = pts[(i + 1) % pts.length];
    const dx = b.x - a.x, dy = b.y - a.y;
    const len2 = dx * dx + dy * dy || 1;
    const t = Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / len2));
    best = Math.min(best, Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy)));
  }
  return best;
}

export function bounds(pts: Vertex[]): { minX: number; minY: number; maxX: number; maxY: number } {
  return pts.reduce(
    (b, p) => ({ minX: Math.min(b.minX, p.x), minY: Math.min(b.minY, p.y), maxX: Math.max(b.maxX, p.x), maxY: Math.max(b.maxY, p.y) }),
    { minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity },
  );
}

/**
 * ラベル配置点。重心が多角形の内側ならそれを使い、凹多角形などで外に出る場合は
 * 格子サンプリングで「辺から最も遠い内部点」を選ぶ (簡易 pole of inaccessibility)。
 */
export function labelPoint(pts: Vertex[]): Vertex {
  const c = centroid(pts);
  if (pointInPolygon(c, pts)) return c;
  const b = bounds(pts);
  const n = 12;
  let best = c, bestD = -1;
  for (let i = 1; i < n; i++) {
    for (let j = 1; j < n; j++) {
      const p = { x: b.minX + ((b.maxX - b.minX) * i) / n, y: b.minY + ((b.maxY - b.minY) * j) / n };
      if (!pointInPolygon(p, pts)) continue;
      const d = distToEdges(p, pts);
      if (d > bestD) { bestD = d; best = p; }
    }
  }
  if (bestD >= 0) return best;
  // 格子が内部点を 1 つも拾えない細長い形状: 中央の水平走査線と辺の交点から内部区間の中点を取る
  const y = (b.minY + b.maxY) / 2;
  const xs: number[] = [];
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i], q = pts[(i + 1) % pts.length];
    if (a.y > y !== q.y > y) xs.push(a.x + ((y - a.y) * (q.x - a.x)) / (q.y - a.y));
  }
  xs.sort((p, q) => p - q);
  if (xs.length >= 2) return { x: (xs[0] + xs[1]) / 2, y };
  return c;
}

/** 多角形の重心 (面積加重)。凹多角形では外に出ることがあるので、ラベルには labelPoint を使う */
export function centroid(pts: Vertex[]): Vertex {
  let a = 0, cx = 0, cy = 0;
  for (let i = 0; i < pts.length; i++) {
    const p = pts[i], q = pts[(i + 1) % pts.length];
    const cross = p.x * q.y - q.x * p.y;
    a += cross;
    cx += (p.x + q.x) * cross;
    cy += (p.y + q.y) * cross;
  }
  if (Math.abs(a) < 1e-9) {
    const n = pts.length || 1;
    return { x: pts.reduce((s, p) => s + p.x, 0) / n, y: pts.reduce((s, p) => s + p.y, 0) / n };
  }
  return { x: cx / (3 * a), y: cy / (3 * a) };
}

/** 穴を含む領域を偶奇規則で描画するSVGパス。 */
export function regionPath(vertices: Vertex[], holes: Vertex[][] = []): string {
  return [vertices, ...holes].filter(ring => ring.length).map(ring => `M ${ring.map(p => `${p.x},${p.y}`).join(" L ")} Z`).join(" ");
}
