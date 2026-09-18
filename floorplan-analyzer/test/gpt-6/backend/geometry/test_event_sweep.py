"""Event broad phases must preserve the old arithmetic, IDs and predicates."""
import math
import random

import pytest
from app import geometry as g


def signature(intervals):
    return [(float(x.start).hex(), float(x.end).hex(), sorted(x.ids)) for x in intervals]


@pytest.mark.parametrize("seed", range(20))
def test_interval_events_match_all_pairs(seed):
    rng = random.Random(seed)
    def intervals():
        result = []
        for i in range(100):
            start = rng.choice([-0.0, 0.0, rng.uniform(-100, 100)])
            result.append(g.Interval(start, start + rng.choice([1e-10, 1e-9, 1.0, 10.0]), {i}))
        return sorted(result, key=g._interval_sort_key)
    a, b = intervals(), intervals()
    original = signature(a), signature(b)
    assert signature(g._clip_overlapping_intervals(a, b)) == signature(g._clip_all_pairs(a, b))
    assert signature(g.clip_intervals(a, b)) == signature(g.merge_intervals(g._clip_all_pairs(a, b)))
    assert (signature(a), signature(b)) == original


@pytest.mark.parametrize("n", [63, 64, 65, 128, 256])
@pytest.mark.parametrize("scale,offset", [(1.0, 0.0), (1e-6, 0.0), (1.0, 1e12), (1e101, 0.0)])
def test_self_intersection_matches_all_pairs(n, scale, offset):
    rng = random.Random(n)
    circle = [(offset + scale * math.cos(i * 2 * math.pi / n),
               offset + scale * math.sin(i * 2 * math.pi / n)) for i in range(n)]
    shuffled = circle[:]
    rng.shuffle(shuffled)
    duplicate = circle[:]
    duplicate[n // 2] = duplicate[n // 2 - 1]
    near_line = [(offset + scale * i, offset + scale * rng.uniform(-1e-12, 1e-12)) for i in range(n)]
    for points in (circle, circle[::-1], shuffled, duplicate, near_line):
        assert g.is_self_intersecting(points) == g._self_intersection_all_pairs(points)


def test_sweep_reduces_predicate_calls(monkeypatch):
    points = [(math.cos(i * math.tau / 1024), math.sin(i * math.tau / 1024)) for i in range(1024)]
    original = g._segments_intersect
    calls = []
    def counted(*args):
        calls.append(1)
        return original(*args)
    monkeypatch.setattr(g, "_segments_intersect", counted)
    assert not g.is_self_intersecting(points)
    assert len(calls) < 1024
