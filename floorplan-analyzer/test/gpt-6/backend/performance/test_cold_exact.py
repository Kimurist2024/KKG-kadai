"""Cold-path changes must preserve float bits, serialization and ownership."""
import copy
import math
import random
import struct

import pytest
from pydantic import BaseModel

from app import analyzer, geometry as g
from app.analysis_cache import materialize
from app.schemas import AnalysisSettings, MaskFile
from app.spatial import SegmentIndex
from benchmarks.baseline import analyzer as baseline
from benchmarks.baseline.schemas import AnalysisSettings as OldSettings, MaskFile as OldMask
from benchmarks.performance import fixtures, settings_cases
from .legacy_response import without_openings
from app.door_openings import opening_geometry


def assert_bits(expected, actual):
    assert type(actual) is type(expected)
    if isinstance(expected, dict):
        assert list(actual) == list(expected)
        for key in expected:
            assert_bits(expected[key], actual[key])
    elif isinstance(expected, list):
        assert len(actual) == len(expected)
        for left, right in zip(expected, actual):
            assert_bits(left, right)
    elif isinstance(expected, float):
        assert struct.pack('!d', actual) == struct.pack('!d', expected)
    else:
        assert actual == expected


@pytest.mark.parametrize('name,data', list(fixtures()))
def test_all_fixtures_bits_cold_warm_and_uncached(name, data):
    mask, old_mask = MaskFile.model_validate(data), OldMask.model_validate(data)
    for _, values in settings_cases():
        settings = AnalysisSettings(**values, door_opening_depth_m=0)
        expected = baseline.analyze(old_mask, OldSettings(**values)).model_dump(mode='json')
        analyzer.clear_geometry_cache()
        assert_bits(expected, without_openings(analyzer.analyze(mask, settings).model_dump(mode='json')))
        assert_bits(expected, without_openings(analyzer.analyze_uncached(mask, settings).model_dump(mode='json')))
        # Start the cache at a different scale/height, not just default settings.
        analyzer.clear_geometry_cache()
        analyzer.analyze(mask, AnalysisSettings(scale_m=2.345, scale_px=123.4,
                         ceiling_height_m=3.1, door_height_m=0, door_opening_depth_m=0,
                         tolerance_px=settings.tolerance_px))
        assert_bits(expected, without_openings(analyzer.analyze(mask, settings).model_dump(mode='json')))


@pytest.mark.parametrize('mode', ['raw', 'regularized_shared'])
@pytest.mark.parametrize('walls', [True, False])
def test_cold_serialization_matches_dictionary_materialization(sample_json, mode, walls):
    data = copy.deepcopy(sample_json)
    if not walls:
        data['contours'] = [c for c in data['contours'] if not c.get('isLine')]
    mask = MaskFile.model_validate(data)
    settings = AnalysisSettings(geometry_mode=mode, scale_m=2.345, scale_px=123.4)
    unit = AnalysisSettings(geometry_mode=mode, scale_m=1, scale_px=1,
                            ceiling_height_m=1, door_height_m=0)
    response, pairs = analyzer._analyze_core(mask, unit, geometry_only=True)
    expected = materialize({'response': response.model_dump(mode='json'), 'pairs': pairs,
                            'door_openings': opening_geometry(response.rooms)}, mask, settings)
    actual = analyzer.analyze(mask, settings)
    for options in ({}, {'exclude_unset': True}, {'exclude_defaults': True},
                    {'exclude_none': True}, {'exclude': {'image', 'settings'}},
                    {'include': {'rooms', 'overlaps', 'geometry_processing', 'warnings'}}):
        assert_bits(expected.model_dump(mode='json', **options), actual.model_dump(mode='json', **options))
        assert expected.model_dump_json(**options) == actual.model_dump_json(**options)
    # Cold responses must contain models, not unvalidated nested dictionaries.
    def check_models(value):
        if isinstance(value, BaseModel):
            for child in value.__dict__.values():
                check_models(child)
        elif isinstance(value, list):
            for child in value:
                check_models(child)
        else:
            assert not isinstance(value, dict)
    check_models(actual)


def test_cold_response_does_not_alias_input_or_cache(sample_json):
    mask = MaskFile.model_validate(sample_json)
    settings = AnalysisSettings()
    before = mask.model_dump(mode='json')
    response = analyzer.analyze(mask, settings)
    expected = response.model_dump(mode='json')
    response.rooms[0].vertices[0].x = -999
    response.rooms[0].edges[0].wall_intervals[0].ids.append(-999)
    response.settings.scale_m = 999
    response.warnings.clear()
    assert_bits(before, mask.model_dump(mode='json'))
    assert settings.scale_m == AnalysisSettings().scale_m
    assert_bits(expected, analyzer.analyze(mask, settings).model_dump(mode='json'))


@pytest.mark.parametrize('offset', [0., 1e12, -1e12, 1e100])
def test_small_index_keeps_all_accepted_segments(offset):
    rng = random.Random(552)
    size = max(100., 32 * math.ulp(offset))
    for angle in (0., .13, math.pi / 2, 2.7):
        def point(x, y):
            return (offset + x * math.cos(angle) - y * math.sin(angle),
                    offset + x * math.sin(angle) + y * math.cos(angle))
        a, b = point(0, 0), point(size, 0)
        for tolerance in (0., 1e-9, size / 10):
            segments = [(i, (point(-size + i * size / 10, delta),
                              point(i * size / 10, delta)))
                        for i, delta in enumerate([0., tolerance, -tolerance,
                            math.nextafter(tolerance, math.inf)] * 10)]
            rng.shuffle(segments)
            index = SegmentIndex(segments)
            assert index.tree is None
            candidates = index.near(a, b, tolerance)
            assert [s for s in segments if s in candidates] == candidates
            assert g.project_segments_onto_edge(a, b, candidates, tolerance) == g.project_segments_onto_edge(a, b, segments, tolerance)
    index = SegmentIndex([(1, ((0., 0.), (1., 0.)))])
    assert index.near((1e308, 0.), (1.1e308, 1.), 1e308) == index.segments


def test_edge_fast_paths_match_frozen_pipeline():
    rng = random.Random(320)
    for _ in range(400):
        length = rng.choice([2e-9, 1., 100.])
        a, b = (-0., 0.), (length, 0.)
        tolerance = rng.choice([0., 1e-9, 2.5, 10.])
        segments = [(i, ((rng.uniform(-.1, 1.1) * length, 0.),
                         (rng.uniform(-.1, 1.1) * length, 0.))) for i in range(rng.randrange(8))]
        walls, doors = segments[:len(segments)//2], segments[len(segments)//2:]
        values = dict(tolerance_px=tolerance, scale_m=2.345, scale_px=123.4)
        actual = analyzer.analyze_edge(0, a, b, walls, doors, AnalysisSettings(**values, door_opening_depth_m=0))
        expected = baseline.analyze_edge(0, a, b, walls, doors, OldSettings(**values))
        assert_bits(expected.model_dump(mode='json'), actual.model_dump(mode='json'))
