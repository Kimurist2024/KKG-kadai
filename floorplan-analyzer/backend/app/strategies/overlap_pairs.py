"""(polygons) -> iterator of candidate (i, j) in lexicographic input order."""
from shapely.strtree import STRtree
from . import register


@register("overlap_pairs", "auto")
def auto(polygons):
    return brute(polygons) if len(polygons) < 32 else strtree(polygons)


@register("overlap_pairs", "brute")
def brute(polygons):
    bounds = [polygon.bounds for polygon in polygons]
    for i in range(len(polygons)):
        left, bottom, right, top = bounds[i]
        for j in range(i + 1, len(polygons)):
            xmin, ymin, xmax, ymax = bounds[j]
            if xmax < left or right < xmin or ymax < bottom or top < ymin:
                continue
            yield i, j


@register("overlap_pairs", "strtree")
def strtree(polygons):
    tree = STRtree(polygons)
    for i, polygon in enumerate(polygons):
        for j in sorted(tree.query(polygon)):
            if j > i:
                yield i, int(j)
