import type { AnalyzeResponse, Warning } from "./types";

export const isWallWarning = (w: Warning) =>
  w.code === "missing_wall_data" || w.code === "no_room_walls" || w.code === "low_wall_coverage";

export const wallWarningsForRoom = (result: AnalyzeResponse, id: number) =>
  result.warnings.filter((w) => isWallWarning(w) && (w.contour_id === null || w.contour_id === id));
