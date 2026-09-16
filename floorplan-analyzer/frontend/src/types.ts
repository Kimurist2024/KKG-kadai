// バックエンド (backend/app/schemas.py) のレスポンス型を TypeScript で写したもの。

export interface Vertex {
  x: number;
  y: number;
}

export interface Settings {
  ceiling_height_m: number;
  door_height_m: number;
  scale_px: number;
  scale_m: number;
  tolerance_px: number;
  geometry_mode: "raw" | "regularized_shared";
  boundary_reference: "unknown" | "centerline" | "inner_face";
}

export const DEFAULT_SETTINGS: Settings = {
  ceiling_height_m: 2.4,
  door_height_m: 2.0,
  scale_px: 96.7,
  scale_m: 1.365,
  tolerance_px: 10,
  geometry_mode: "raw",
  boundary_reference: "unknown",
};

export interface IntervalOut {
  start_px: number;
  end_px: number;
  start: Vertex;
  end: Vertex;
  length_px: number;
  length_m: number;
  ids: number[];
}

export interface EdgeResult {
  boundary_kind?: "outer" | "hole";
  inferred_wall_intervals?: IntervalOut[];
  canonical_edge_id?: number;
  index: number;
  start: Vertex;
  end: Vertex;
  length_px: number;
  length_m: number;
  wall_intervals: IntervalOut[];
  opening_intervals: IntervalOut[];
  door_intervals: IntervalOut[];
  wall_length_m: number;
  opening_length_m: number;
  door_length_m: number;
  wall_area_gross_m2: number;
  door_area_m2: number;
  wall_area_m2: number;
}

export interface RoomResult {
  holes?: Vertex[][];
  label_point?: Vertex | null;
  id: number;
  name: string;
  room_name: string | null;
  color: string;
  vertices: Vertex[];
  floor_area_px2: number;
  floor_area_m2: number;
  perimeter_px: number;
  perimeter_m: number;
  source_area_px2: number | null;
  source_perimeter_px: number | null;
  wall_length_m: number;
  opening_length_m: number;
  door_length_m: number;
  door_count: number;
  wall_area_gross_m2: number;
  door_area_m2: number;
  wall_area_m2: number;
  edges: EdgeResult[];
}

export interface SegmentOut {
  id: number;
  kind: "wall" | "door";
  start: Vertex;
  end: Vertex;
  length_px: number;
  length_m: number;
  color: string;
}

export type WarningCode = "room_overlap" | "inferred_door_wall" | "ai_generated" | "unnamed_room" | "unmatched_door" | "invalid_shape" | "ignored_contour" | "data_mismatch" | "duplicate_id" | "missing_wall_data" | "no_room_walls" | "low_wall_coverage" | "geometry_regularized" | "regularization_skipped";

export interface Warning {
  code: WarningCode;
  message: string;
  contour_id: number | null;
}

export interface PolygonRegion { vertices: Vertex[]; holes: Vertex[][]; }
export interface RoomOverlap { room_ids: number[]; area_m2: number; regions: PolygonRegion[]; }

export interface PlanarGraph {
  version: string;
  nodes: { id: number; point: Vertex; room_ids: number[]; max_displacement_px: number }[];
  edges: { id: number; start_node_id: number; end_node_id: number; start: Vertex; end: Vertex; room_ids: number[]; boundary_kinds: string[]; length_px: number }[];
  shared_edge_count: number;
  non_manifold_edge_count: number;
}

export interface GeometryProcessing {
  requested_mode: string;
  applied_mode: "regularized_shared" | "raw_fallback" | "unchanged";
  algorithm_version: string;
  boundary_reference: string;
  dominant_angle_deg: number | null;
  orientation_concentration: number;
  orientation_inlier_ratio: number;
  moved_vertex_count: number;
  max_displacement_px: number;
  max_area_change_ratio: number;
  reject_reason: string | null;
  graph: PlanarGraph | null;
}

export interface AnalyzeResponse {
  overlaps?: RoomOverlap[];
  geometry_processing?: GeometryProcessing;
  image: { width: number; height: number; mime_type: string | null; has_image: boolean };
  timestamp: string | null;
  settings: Omit<Settings, "geometry_mode" | "boundary_reference"> &
    Partial<Pick<Settings, "geometry_mode" | "boundary_reference">> & { meters_per_px: number };
  summary: {
    room_count: number;
    wall_count: number;
    door_count: number;
    total_floor_area_m2: number;
    union_floor_area_m2?: number;
    overlap_floor_area_m2?: number;
    total_wall_area_m2: number;
  };
  rooms: RoomResult[];
  walls: SegmentOut[];
  doors: SegmentOut[];
  warnings: Warning[];
}

export interface Layers {
  image: boolean;
  rooms: boolean;
  walls: boolean;
  doors: boolean;
  labels: boolean;
}

/** 画像認識が返す確認前の輪郭。面積や縮尺の確定値ではない。 */
export interface RecognizedMask {
  image_width: number;
  image_height: number;
  image_data: { base64: string; mime_type: string };
  contours: { id: number; label_id: number; isLine?: boolean | null; room_name?: string | null; color: string; vertices: Vertex[] }[];
  ai_recognition: { model: string; warnings: string[] };
}

export interface RecognitionResponse {
  mask: RecognizedMask;
  model: string;
  warnings: string[];
}
