"""Bounded model output; normalized image-edge coordinates (0..1)."""
from typing import Annotated, List
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat
from .schemas import MaskFile


class StrictObject(BaseModel):
    """AI 出力用の共通制約。未知の項目と暗黙の型変換を拒否する。"""

    model_config = ConfigDict(extra="forbid", strict=True)


class Point(StrictObject):
    """AI が返す画像内の位置。画像端を 0〜1 とする正規化座標。"""

    x: FiniteFloat = Field(ge=0, le=1)
    y: FiniteFloat = Field(ge=0, le=1)


class Room(StrictObject):
    """AI が推定した部屋名と外周の候補。実寸面積はここでは決めない。"""

    name: str = Field(max_length=100)
    vertices: List[Point] = Field(min_length=3, max_length=100)


class Line(StrictObject):
    """AI が推定した壁または扉の線分候補。"""

    start: Point
    end: Point


class Recognition(StrictObject):
    """件数と頂点数を制限した AI 出力。人の確認を前提とする。"""

    rooms: List[Room] = Field(max_length=100)
    walls: List[Line] = Field(max_length=500)
    doors: List[Line] = Field(max_length=200)
    warnings: List[Annotated[str, Field(max_length=500)]] = Field(max_length=20)


class RecognizeResponse(BaseModel):
    """AI 候補を通常のマスク形式に変換した結果と、認識時の注意事項。"""

    mask: MaskFile
    warnings: List[str]
    model: str
