"""Proper crossing predicates: (vertices) -> bool."""
from __future__ import annotations
import math
import heapq
from typing import Sequence
from ..geometry_primitives import EPS_PX, Point
from . import register

@register("self_intersection", "auto")
def auto(vertices: Sequence[Point]) -> bool:
    """大きな輪郭は境界イベントで候補を絞り、従来の交差式で判定する。"""
    n = len(vertices)
    if n < 4:
        return False
    if n >= 64:
        magnitude = max(abs(v) for point in vertices for v in point)
        if math.isfinite(magnitude) and magnitude < 1e100:
            return _self_intersection_sweep(vertices, EPS_PX + 16 * math.ulp(magnitude))
    return _self_intersection_all_pairs(vertices)


def _self_intersection_sweep(vertices, pad):
    from ..geometry import _segments_intersect

    n = len(vertices)
    boxes = []
    for i, a in enumerate(vertices):
        b = vertices[(i + 1) % n]
        boxes.append((min(a[0], b[0]) - pad, max(a[0], b[0]) + pad,
                      min(a[1], b[1]) - pad, max(a[1], b[1]) + pad, i))
    active = {}
    ends = []
    for left, right, bottom, top, i in sorted(boxes):
        while ends and ends[0][0] < left:
            _, expired = heapq.heappop(ends)
            active.pop(expired)
        for j, (low, high) in active.items():
            first, second = min(i, j), max(i, j)
            if second == first + 1 or (first == 0 and second == n - 1):
                continue
            if high < bottom or top < low:
                continue
            if _segments_intersect(vertices[first], vertices[(first + 1) % n],
                                   vertices[second], vertices[(second + 1) % n]):
                return True
        active[i] = (bottom, top)
        heapq.heappush(ends, (right, i))
    return False


@register("self_intersection", "all_pairs")
def _self_intersection_all_pairs(vertices):
    from ..geometry import _segments_intersect

    n = len(vertices)
    for i in range(n):
        p1, p2 = vertices[i], vertices[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue  # 最初と最後の辺は隣接
            q1, q2 = vertices[j], vertices[(j + 1) % n]
            if _segments_intersect(p1, p2, q1, q2):
                return True
    return False


@register("self_intersection", "sweep")
def sweep(vertices):
    """Force sweep when bounding boxes are numerically safe."""
    if len(vertices) < 4:
        return False
    magnitude = max(abs(v) for point in vertices for v in point)
    if math.isfinite(magnitude) and magnitude < 1e100:
        return _self_intersection_sweep(vertices, EPS_PX + 16 * math.ulp(magnitude))
    return _self_intersection_all_pairs(vertices)
