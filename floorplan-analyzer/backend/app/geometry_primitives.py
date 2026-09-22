"""Shared exact arithmetic and interval types; no strategy dependencies."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterable, List, Set, Tuple

Point = Tuple[float, float]
Segment = Tuple[Point, Point]

EPS_PX = 1e-9  # 浮動小数点の丸め誤差用。セグメンテーションの許容誤差 (tolerance_px) とは別物
DEFAULT_MAX_ANGLE_DEG = 10.0  # 辺と線分のなす角がこれ以下なら「平行」とみなす


@dataclass
class Interval:
    """辺上の 1 次元区間。start/end は辺の始点からの距離 (px)。"""

    start: float
    end: float
    ids: Set[int] = field(default_factory=set)

    @property
    def length(self) -> float:
        return max(0.0, self.end - self.start)


def _interval_sort_key(interval: Interval) -> Tuple[float, float]:
    """区間の安定ソート順を返す。"""
    return interval.start, interval.end


def merge_intervals(intervals: Iterable[Interval], gap_tolerance_px: float = 0.0) -> List[Interval]:
    """重なり・近接 (gap <= gap_tolerance_px) する区間を併合する。"""
    merged: List[Interval] = []
    for iv in sorted(intervals, key=_interval_sort_key):
        if merged and iv.start <= merged[-1].end + gap_tolerance_px:
            last = merged[-1]
            last.end = max(last.end, iv.end)
            last.ids |= iv.ids
        else:
            merged.append(Interval(iv.start, iv.end, set(iv.ids)))
    return merged


def _orientation(a: Point, b: Point, c: Point) -> float:
    """a→b に対するcの有向面積（外積）。"""
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_intersect(p1: Point, p2: Point, q1: Point, q2: Point) -> bool:
    """線分 p1p2 と q1q2 が交差するか (端点接触は交差とみなさない)。"""

    d1, d2 = _orientation(q1, q2, p1), _orientation(q1, q2, p2)
    d3, d4 = _orientation(p1, p2, q1), _orientation(p1, p2, q2)
    return (d1 * d2 < -EPS_PX) and (d3 * d4 < -EPS_PX)


