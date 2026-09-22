"""テスト用の入力データ生成ヘルパー。

課題の JSON 構造 (Contour) を最小の記述で組み立てる。座標は px。
どのテストモジュールからも `from ..factories import ...` で使う。
"""
from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Tuple

from app.schemas import AnalysisSettings, MaskFile

Pt = Tuple[float, float]

# 既定スケール (96.7 px = 1.365 m) での 1 px あたりのメートル数
MPP = 1.365 / 96.7

LABEL_ROOM = 1
LABEL_WALL = 2
LABEL_DOOR = 3


def vertices(points: Iterable[Pt]) -> List[dict]:
    return [{"x": x, "y": y} for x, y in points]


def room(id_: int, points: Sequence[Pt], name: Optional[str] = "R", **extra) -> dict:
    """部屋輪郭 (isLine を持たない多角形)。"""
    return {
        "id": id_,
        "vertices": vertices(points),
        "color": "#123456",
        "room_name": name,
        "label_id": LABEL_ROOM,
        **extra,
    }


def line(id_: int, p: Pt, q: Pt, label: int, **extra) -> dict:
    """壁 (label=2) / ドア (label=3) の線分輪郭。"""
    return {
        "id": id_,
        "vertices": vertices([p, q]),
        "color": "#FF0000",
        "room_name": None,
        "label_id": label,
        "isLine": True,
        "lineWidth": 5,
        **extra,
    }


def wall(id_: int, p: Pt, q: Pt, **extra) -> dict:
    return line(id_, p, q, LABEL_WALL, **extra)


def door(id_: int, p: Pt, q: Pt, **extra) -> dict:
    return line(id_, p, q, LABEL_DOOR, **extra)


def rect(x0: float, y0: float, x1: float, y1: float) -> List[Pt]:
    """左上 (x0, y0)・右下 (x1, y1) の長方形を時計回り (画像座標) で返す。"""
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def make_mask(contours: List[dict], width: int = 1000, height: int = 1000, **extra) -> MaskFile:
    return MaskFile(contours=contours, image_width=width, image_height=height, **extra)


def unit_settings(**overrides) -> AnalysisSettings:
    """1 px = 1 m、許容誤差 1 px。px の値をそのまま m として検算できる。"""
    base = dict(scale_px=1, scale_m=1, tolerance_px=1)
    base.update(overrides)
    return AnalysisSettings(**base)


def segments(*items: Tuple[int, Pt, Pt]) -> List[Tuple[int, Tuple[Pt, Pt]]]:
    """geometry 関数に渡す (id, (始点, 終点)) のリスト。"""
    return [(i, (p, q)) for i, p, q in items]
