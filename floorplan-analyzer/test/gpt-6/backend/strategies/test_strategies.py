"""Exact strategies, profile isolation, and the existing fixture contracts."""
import math
import random
from dataclasses import FrozenInstanceError, replace

import pytest

from app import analyzer, geometry as g, topology
from app.strategies import AlgorithmProfile, PROFILES, REGISTRIES, get, register, resolve_profile
from app.schemas import AnalysisSettings, MaskFile
from benchmarks.performance import fixtures, settings_cases
from ..factories import make_mask, room, rect, wall, door
from ..analyzer.test_door_openings import shared_mask
from ..performance.test_cold_batch_exact import mixed_data
from ..performance.test_cold_exact import assert_bits
from ..geometry.test_event_sweep import signature


@pytest.mark.parametrize('seam,names', [
    ('candidate_search', ['auto', 'scan', 'strtree']),
    ('interval_clip', ['auto', 'all_pairs', 'sweep']),
    ('self_intersection', ['auto', 'sweep', 'all_pairs']),
    ('room_polygons', ['batch', 'per_room']),
    ('overlap_pairs', ['auto', 'brute', 'strtree']),
])
def test_registry(seam, names):
    assert set(names) <= REGISTRIES[seam].keys()
    assert all(callable(get(seam, name)) for name in names)
    with pytest.raises(KeyError) as error:
        get(seam, 'missing')
    assert all(name in str(error.value) for name in names)


def test_profiles_and_default_thresholds():
    from app.spatial import SegmentIndex, overlap_pairs
    default = resolve_profile('default')
    assert default == AlgorithmProfile()
    assert resolve_profile(default) is default
    assert resolve_profile(None) is default
    with pytest.raises(FrozenInstanceError):
        default.interval_clip = 'sweep'
    assert get('candidate_search', default.candidate_search) is SegmentIndex
    assert get('interval_clip', default.interval_clip) is g.clip_intervals
    assert get('self_intersection', default.self_intersection) is g.is_self_intersecting
    assert get('room_polygons', default.room_polygons) is topology.simple_room_polygons
    assert get('overlap_pairs', default.overlap_pairs) is overlap_pairs
    segments = [(i, ((float(i), 0.), (float(i + 1), 0.))) for i in range(64)]
    assert SegmentIndex(segments[:63]).tree is None
    assert SegmentIndex(segments).tree is not None
    assert get('candidate_search', 'scan')(segments).tree is None
    assert get('candidate_search', 'strtree')(segments[:1]).tree is not None
    with pytest.raises(KeyError) as error:
        resolve_profile('missing')
    assert all(name in str(error.value) for name in PROFILES)
    with pytest.raises(KeyError) as error:
        get('missing', 'auto')
    assert all(name in str(error.value) for name in REGISTRIES)
    with pytest.raises(ValueError):
        register('interval_clip', 'auto')(lambda a, b: [])


def check_profiles(mask, settings, profiles=None):
    before = mask.model_dump_json()
    expected = analyzer.analyze_uncached(mask, settings)
    for profile in PROFILES if profiles is None else profiles:
        actual = analyzer.analyze_uncached(mask, settings, profile=profile)
        for options in ({}, {'exclude_unset': True}):
            assert_bits(expected.model_dump(mode='json', **options), actual.model_dump(mode='json', **options))
            assert expected.model_dump_json(**options) == actual.model_dump_json(**options)
    assert mask.model_dump_json() == before


@pytest.mark.parametrize('name,data', list(fixtures()))
def test_all_registered_profiles_on_existing_fixtures(name, data):
    mask = MaskFile.model_validate(data)
    for _, settings in settings_cases():
        check_profiles(mask, AnalysisSettings(**settings))


@pytest.mark.parametrize('angle', [0., .13, 1.3])
@pytest.mark.parametrize('tolerance', [0., 1e-9, 10.])
def test_invalid_holes_overlaps_crossings_and_warnings(angle, tolerance):
    check_profiles(MaskFile.model_validate(mixed_data(angle)),
                   AnalysisSettings(tolerance_px=tolerance, scale_m=2.345, scale_px=123.4))


@pytest.mark.parametrize('options', [{}, {'split': True}, {'equal': True}, {'third': True}, {'duplicate_id': True}])
def test_opening_transfers(options):
    check_profiles(shared_mask(**options), AnalysisSettings(door_opening_depth_m=.37))


def test_gap_and_empty():
    check_profiles(make_mask([]), AnalysisSettings())
    check_profiles(make_mask([room(1, rect(0, 0, 100, 100)),
                              wall(2, (0, 0), (30, 0)), wall(3, (70, 0), (100, 0)),
                              door(4, (30, 0), (70, 0))]), AnalysisSettings(tolerance_px=1))


@pytest.mark.parametrize('mode', ['raw', 'regularized_shared'])
def test_custom_sweep_combination_and_cached_default(sample_json, mode):
    mask, settings = MaskFile.model_validate(sample_json), AnalysisSettings(geometry_mode=mode)
    sweep = AlgorithmProfile(candidate_search='strtree', interval_clip='sweep',
                             self_intersection='sweep', overlap_pairs='strtree')
    check_profiles(mask, settings, [*PROFILES, sweep])
    expected = analyzer.analyze_uncached(mask, settings).model_dump_json()
    analyzer.clear_geometry_cache()
    analyzer.analyze_uncached(mask, settings, profile='all_pairs')
    assert analyzer.analyze(mask, settings).model_dump_json() == expected
    assert analyzer.analyze(mask, settings).model_dump_json() == expected


@pytest.mark.parametrize('count', [0, 1, 31, 32, 33])
def test_overlap_strategies_at_threshold(count):
    from shapely.geometry import Polygon
    shapes = [Polygon(rect(i * 10., 0., i * 10. + 15., 20.)) for i in range(count)]
    expected = list(get('overlap_pairs', 'brute')(shapes))
    for implementation in REGISTRIES['overlap_pairs'].values():
        assert list(implementation(shapes)) == expected


@pytest.mark.parametrize('count', [0, 1, 63, 64, 100])
def test_clip_all_strategies_with_signed_zero_and_events(count):
    rng = random.Random(count)
    def intervals():
        return [g.Interval(start, start + rng.choice([1e-10, 1e-9, 1., 10.]), {i})
                for i in range(count) for start in [rng.choice([-0., 0., rng.uniform(-100, 100)])]]
    a, b = intervals(), intervals()
    original = signature(a), signature(b)
    expected = signature(g.clip_intervals(a, b))
    for impl in REGISTRIES['interval_clip'].values():
        assert signature(impl(a, b)) == expected
        assert signature(impl(iter(a), iter(b))) == expected
    assert (signature(a), signature(b)) == original


@pytest.mark.parametrize('count', [3, 4, 63, 64, 65, 128])
@pytest.mark.parametrize('scale,offset', [(1., 0.), (1e-6, 0.), (1., 1e12), (1e101, 0.)])
def test_forced_self_intersection_strategies(count, scale, offset):
    points = [(offset + scale * math.cos(i * math.tau / count),
               offset + scale * math.sin(i * math.tau / count)) for i in range(count)]
    shuffled = points[:]
    random.Random(count).shuffle(shuffled)
    for contour in (points, shuffled):
        expected = g.is_self_intersecting(contour)
        for impl in REGISTRIES['self_intersection'].values():
            assert impl(contour) == expected


def test_profile_is_forwarded_through_regularization(monkeypatch, sample_json):
    calls = []
    registry = REGISTRIES['interval_clip']
    monkeypatch.setitem(registry, 'record', lambda a, b: (calls.append(1), g.clip_intervals(a, b))[1])
    analyzer.analyze_uncached(MaskFile.model_validate(sample_json),
                             AnalysisSettings(geometry_mode='regularized_shared'),
                             replace(AlgorithmProfile(), interval_clip='record'))
    assert calls
