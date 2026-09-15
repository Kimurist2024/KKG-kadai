"""Conservative candidate search; exact geometry rules remain in the analyzer."""
import math

from shapely.geometry import LineString, box
from shapely.strtree import STRtree

from .geometry import EPS_PX


class SegmentIndex:
    def __init__(self, segments):
        self.segments = segments
        # Building/querying a tree costs more than checking a handful of lines.
        self.tree = STRtree([LineString(s) for _, s in segments]) if len(segments) >= 64 else None

    def near(self, a, b, tolerance):
        if self.tree is None:
            return self.segments
        # Pad outwards for rounding at the tolerance boundary, never snap inputs.
        pad = tolerance + EPS_PX + 8 * math.ulp(max(abs(v) for v in (*a, *b)))
        bounds = (min(a[0], b[0]) - pad, min(a[1], b[1]) - pad,
                  max(a[0], b[0]) + pad, max(a[1], b[1]) + pad)
        if not all(math.isfinite(v) for v in bounds):
            return self.segments
        return [self.segments[int(i)] for i in sorted(self.tree.query(box(*bounds)))]


def overlap_pairs(polygons):
    """Yield candidate indices in the original stable i,j order (including containment)."""
    if len(polygons) < 32:
        for i in range(len(polygons)):
            for j in range(i + 1, len(polygons)):
                yield i, j
        return
    tree = STRtree(polygons)
    for i, polygon in enumerate(polygons):
        for j in sorted(tree.query(polygon)):
            if j > i:
                yield i, int(j)
