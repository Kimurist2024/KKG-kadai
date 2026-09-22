"""Factories (segments) -> SegmentIndex. New indexes subclass SegmentIndex.

near / near_many return original segments in input order; bounds are conservative.
"""
import math
from shapely.geometry import LineString
from shapely import box
from shapely.strtree import STRtree
from ..geometry_primitives import EPS_PX
from . import register


@register("candidate_search", "auto")
class SegmentIndex:
    """壁・扉線分の候補検索。小規模なら矩形走査、大規模なら STRtree を使う。

    near は候補を絞るだけで、平行性・距離の最終判定は geometry の射影処理で行う。"""

    def __init__(self, segments):
        self.segments = segments
        # 少数の線分は、木を構築せず外接矩形だけを走査する。
        self.tree = self._make_tree(segments)
        self.bounds = [(min(a[0], b[0]), min(a[1], b[1]),
                        max(a[0], b[0]), max(a[1], b[1]))
                       for _, (a, b) in segments] if self.tree is None else []

    @staticmethod
    def _make_tree(segments):
        return STRtree([LineString(s) for _, s in segments]) if len(segments) >= 64 else None

    @staticmethod
    def _bounds(a, b, tolerance):
        ax, ay = a
        bx, by = b
        pad = tolerance + EPS_PX + 8 * math.ulp(max(abs(ax), abs(ay), abs(bx), abs(by)))
        return ((ax if ax <= bx else bx) - pad, (ay if ay <= by else by) - pad,
                (ax if ax >= bx else bx) + pad, (ay if ay >= by else by) + pad)

    def near_many(self, edges, tolerance, *, bounds=None):
        """部屋の辺をまとめて検索する。候補は必ず元の線分順に戻す。"""
        if not self.segments:
            return [self.segments for _ in edges]
        if bounds is None:
            bounds = [self._bounds(a, b, tolerance) for a, b in edges]
        if self.tree is None:
            return [self._near_bounds(row) for row in bounds]
        if not bounds:
            return []
        if not all(math.isfinite(v) for row in bounds for v in row):
            return [self.near(a, b, tolerance) for a, b in edges]
        queries = box(*zip(*bounds))
        matches = self.tree.query(queries)
        indices = [[] for _ in edges]
        for edge, segment in zip(*matches):
            indices[int(edge)].append(int(segment))
        return [[self.segments[i] for i in sorted(group)] for group in indices]

    def near(self, a, b, tolerance):
        if not self.segments:
            return self.segments
        # 丸め誤差で境界付近の候補を落とさないよう検索枠だけ広げる。入力座標は変えない。
        return self._near_bounds(self._bounds(a, b, tolerance))

    def _near_bounds(self, bounds):
        left, bottom, right, top = bounds
        if not (math.isfinite(left) and math.isfinite(bottom)
                and math.isfinite(right) and math.isfinite(top)):
            return self.segments
        if self.tree is None:
            return [segment for segment, (xmin, ymin, xmax, ymax) in zip(self.segments, self.bounds)
                    if not (xmax < left or right < xmin or ymax < bottom or top < ymin)]
        return [self.segments[int(i)] for i in sorted(self.tree.query(box(*bounds)))]


@register("candidate_search", "scan")
class ScanIndex(SegmentIndex):
    @staticmethod
    def _make_tree(segments):
        return None


@register("candidate_search", "strtree")
class TreeIndex(SegmentIndex):
    @staticmethod
    def _make_tree(segments):
        return STRtree([LineString(s) for _, s in segments]) if segments else None
