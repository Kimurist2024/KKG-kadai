"""API の入出力スキーマ (pydantic v2)。"""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, computed_field, model_validator

# ---------------------------------------------------------------- 入力 (課題 2-1 のデータ構造)


class Vertex(BaseModel):
    x: FiniteFloat  # NaN / inf は受け付けない
    y: FiniteFloat


class Contour(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    vertices: List[Vertex]
    color: str = "#888888"
    room_name: Optional[str] = None
    area: Optional[FiniteFloat] = None
    perimeter: Optional[FiniteFloat] = None
    label_id: int
    holes: Any = None
    isLine: Optional[bool] = None
    lineWidth: Optional[float] = None
    instanceGroupId: Any = None


class ImageData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    base64: str = ""
    mime_type: str = "image/png"


class AIRecognition(BaseModel):
    model: str = Field(max_length=200)
    warnings: List[str] = Field(default_factory=list, max_length=21)


class MaskFile(BaseModel):
    """アップロードされる JSON ファイル全体。"""

    model_config = ConfigDict(extra="ignore")

    contours: List[Contour]
    image_data: Optional[ImageData] = None
    image_width: int = Field(gt=0)
    image_height: int = Field(gt=0)
    timestamp: Optional[str] = None
    ai_recognition: Optional[AIRecognition] = None


# ---------------------------------------------------------------- 計算パラメータ


class AnalysisSettings(BaseModel):
    ceiling_height_m: FiniteFloat = Field(default=2.4, gt=0, description="天井高 (m)")
    door_height_m: FiniteFloat = Field(default=2.0, ge=0, description="ドア高さ (m)")
    scale_px: FiniteFloat = Field(default=96.7, gt=0, description="スケール基準: ピクセル")
    scale_m: FiniteFloat = Field(default=1.365, gt=0, description="スケール基準: メートル")
    tolerance_px: FiniteFloat = Field(
        default=10.0, ge=0, description="壁/ドアを辺に沿うとみなす許容距離 (px)"
    )

    @model_validator(mode="after")
    def _check_heights(self) -> "AnalysisSettings":
        if self.door_height_m > self.ceiling_height_m:
            raise ValueError("ドア高さは天井高以下にしてください (壁面積が負になります)")
        return self

    @computed_field(description="1 px あたりのメートル数 (scale_m / scale_px)")  # type: ignore[prop-decorator]
    @property
    def meters_per_px(self) -> float:
        return self.scale_m / self.scale_px


# ---------------------------------------------------------------- 出力


class SegmentOut(BaseModel):
    id: int
    kind: str  # "wall" | "door"
    start: Vertex
    end: Vertex
    length_px: float
    length_m: float
    color: str


class IntervalOut(BaseModel):
    """辺上の部分区間 (壁あり / 開口 / ドア)。"""

    start_px: float
    end_px: float
    start: Vertex
    end: Vertex
    length_px: float
    length_m: float
    ids: List[int] = Field(default_factory=list, description="寄与した壁/ドア輪郭の id")


class EdgeResult(BaseModel):
    boundary_kind: str = "outer"
    inferred_wall_intervals: List[IntervalOut] = Field(default_factory=list, description="扉開口から補完した壁区間。ids は補完根拠となったドア輪郭 id。wall_intervals にも含む")
    index: int
    start: Vertex
    end: Vertex
    length_px: float
    length_m: float
    wall_intervals: List[IntervalOut]
    opening_intervals: List[IntervalOut]
    door_intervals: List[IntervalOut]
    wall_length_m: float
    opening_length_m: float
    door_length_m: float
    wall_area_gross_m2: float = Field(description="壁長 × 天井高")
    door_area_m2: float = Field(description="ドア長 × ドア高 (控除分)")
    wall_area_m2: float = Field(description="壁面積 = gross − door")


class RoomResult(BaseModel):
    holes: List[List[Vertex]] = Field(default_factory=list)
    label_point: Optional[Vertex] = None
    id: int
    name: str = Field(description="表示名 (room_name が無い場合は自動命名)")
    room_name: Optional[str]
    color: str
    vertices: List[Vertex]
    floor_area_px2: float
    floor_area_m2: float
    perimeter_px: float
    perimeter_m: float
    source_area_px2: Optional[float] = Field(description="JSON に記載されていた面積 (検証用)")
    source_perimeter_px: Optional[float] = Field(description="JSON に記載されていた周長 (検証用)")
    wall_length_m: float
    opening_length_m: float
    door_length_m: float
    door_count: int
    wall_area_gross_m2: float
    door_area_m2: float
    wall_area_m2: float
    edges: List[EdgeResult]


class PolygonRegion(BaseModel):
    vertices: List[Vertex]
    holes: List[List[Vertex]] = Field(default_factory=list)


class OverlapResult(BaseModel):
    room_ids: List[int]
    area_m2: float
    regions: List[PolygonRegion]


class Summary(BaseModel):
    union_floor_area_m2: float = 0
    overlap_floor_area_m2: float = 0
    room_count: int
    wall_count: int
    door_count: int
    total_floor_area_m2: float
    total_wall_area_m2: float


class ImageInfo(BaseModel):
    width: int
    height: int
    mime_type: Optional[str] = None
    has_image: bool


class Warning(BaseModel):
    """利用者に知らせる注意事項。UI が対象の輪郭へ誘導できるよう id を持つ。"""

    code: str = Field(description="unnamed_room | unmatched_door | invalid_shape | ignored_contour | data_mismatch | duplicate_id | missing_wall_data | no_room_walls | low_wall_coverage | ai_generated | room_overlap | inferred_door_wall")
    message: str
    contour_id: Optional[int] = None


class AnalyzeResponse(BaseModel):
    overlaps: List[OverlapResult] = Field(default_factory=list)
    image: ImageInfo
    timestamp: Optional[str]
    settings: AnalysisSettings
    summary: Summary
    rooms: List[RoomResult]
    walls: List[SegmentOut]
    doors: List[SegmentOut]
    warnings: List[Warning]
