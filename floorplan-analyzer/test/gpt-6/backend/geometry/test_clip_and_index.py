import math
import random

import pytest

from app import analyzer, geometry as g
from app.analysis_cache import GeometryCache
from app.schemas import AnalysisSettings
from app.spatial import SegmentIndex
from ..analyzer.test_analyze import room, line, make_mask


def old_clip(a, b):
    return g.merge_intervals([
        g.Interval(max(x.start, y.start), min(x.end, y.end), set(x.ids))
        for x in a for y in b
        if min(x.end, y.end) - max(x.start, y.start) > g.EPS_PX
    ])


def test_interval_scan_matches_nested_oracle():
    rng = random.Random(17)
    for _ in range(500):
        a = [g.Interval(start, start + rng.uniform(0, 50), {i})
             for i, start in enumerate(rng.uniform(-10, 100) for _ in range(25))]
        b = [g.Interval(start, start + rng.uniform(0, 10), {i + 100})
             for i, start in enumerate(rng.uniform(-10, 100) for _ in range(25))]
        assert g.clip_intervals(a, b) == old_clip(a, b)
        b = g.merge_intervals(b)
        assert g.clip_intervals(a, b) == old_clip(a, b)


def test_scan_keeps_tiny_fragment_and_id_semantics():
    # Two sub-EPS fragments must not be merged into an accepted interval first.
    a = [g.Interval(0, 1.5e-9, {1}), g.Interval(2, 5, {2}),
         g.Interval(5, 8, {3}), g.Interval(4, 6, {4})]
    b = [g.Interval(0, .75e-9), g.Interval(.75e-9, 1.5e-9), g.Interval(6, 7)]
    result = g.clip_intervals(a, b)
    assert result == old_clip(a, b)
    assert result == [g.Interval(6, 7, {3})]


def test_door_projection_runs_once(monkeypatch):
    original = g.project_segments_onto_edge
    calls = []
    def counted(a, b, segments, tolerance):
        calls.append(segments)
        return original(a, b, segments, tolerance)
    monkeypatch.setattr(g, 'project_segments_onto_edge', counted)
    walls = [(1, ((0, 0), (100, 0)))]
    doors = [(2, ((20, 0), (40, 0)))]
    analyzer.analyze_edge(0, (0, 0), (100, 0), walls, doors, AnalysisSettings())
    assert len(calls) == 2  # one walls + one doors


@pytest.mark.parametrize('angle', [0, .13, math.pi / 2, 2.7])
@pytest.mark.parametrize('tolerance', [0, 1, 10])
def test_index_never_drops_accepted_segments(angle, tolerance):
    def transform(x, y):
        return (x * math.cos(angle) - y * math.sin(angle),
                x * math.sin(angle) + y * math.cos(angle))
    a, b = transform(0, 0), transform(100, 0)
    segments = [(i, (transform(-100 + i*5, offset), transform(10+i*5, offset)))
                for i, offset in enumerate([0, tolerance, -tolerance,
                    tolerance + 1e-8] * 30)]
    index = SegmentIndex(segments)
    assert index.tree is not None
    assert g.project_segments_onto_edge(a, b, index.near(a, b, tolerance), tolerance) == g.project_segments_onto_edge(a, b, segments, tolerance)


def test_cache_reuses_geometry_and_isolates_responses(monkeypatch):
    mask = make_mask([room(1, [(0,0),(100,0),(100,100),(0,100)]),
                      line(2, (0,0), (100,0), 2)])
    original = analyzer._analyze_core
    calls = []
    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(analyzer, '_analyze_core', counted)
    first = analyzer.analyze(mask)
    first.rooms[0].vertices[0].x = -999
    first.rooms[0].edges[0].wall_intervals[0].ids.append(999)
    # Metadata is current even when geometry is reused.
    mask.timestamp = 'updated'
    mask.image_width += 1
    settings = AnalysisSettings(scale_m=2, ceiling_height_m=3, door_height_m=1)
    second = analyzer.analyze(mask, settings)
    assert len(calls) == 1
    assert second.timestamp == 'updated'
    assert second.image.width == mask.image_width
    assert second.rooms[0].vertices[0].x == 0
    assert 999 not in second.rooms[0].edges[0].wall_intervals[0].ids
    assert second.model_dump() == analyzer.analyze_uncached(mask, settings).model_dump()
    calls.clear()
    analyzer.analyze(mask, AnalysisSettings(tolerance_px=1))
    mask.contours[0].vertices[1].x += .1
    analyzer.analyze(mask, AnalysisSettings(tolerance_px=1))
    assert len(calls) == 2


def test_cache_bounds_lru_and_expiration(monkeypatch):
    now = [100.0]
    monkeypatch.setattr('app.analysis_cache.time.monotonic', lambda: now[0])
    cache = GeometryCache(max_bytes=5, max_entries=2, ttl=10)
    cache.put('a', b'aa')
    cache.put('b', b'bb')
    assert cache.get('a') == b'aa'
    cache.put('c', b'cc')
    assert cache.get('b') is None
    cache.put('large', b'123456')
    assert cache.get('large') is None
    cache.put('a', b'aaa')
    assert cache._bytes == 5
    now[0] += 10
    assert cache.get('a') is None
    assert cache.get('c') is None
    assert cache._bytes == 0


def test_concurrent_settings_do_not_leak_between_responses():
    from concurrent.futures import ThreadPoolExecutor
    mask = make_mask([room(1, [(0,0),(100,0),(100,100),(0,100)]),
                      room(3, [(90,0),(110,0),(110,100),(90,100)]),
                      line(2, (0,0), (100,0), 2)])
    variants = [AnalysisSettings(scale_m=1 + i * .1, ceiling_height_m=3 + i*.1)
                for i in range(12)]
    expected = [analyzer.analyze_uncached(mask, s).model_dump() for s in variants]
    with ThreadPoolExecutor(max_workers=4) as pool:
        actual = list(pool.map(lambda s: analyzer.analyze(mask, s).model_dump(), variants))
    assert actual == expected
