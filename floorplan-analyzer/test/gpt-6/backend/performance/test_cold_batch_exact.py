"""Batch topology must preserve the frozen scalar oracle, warning order and float bits."""
import json
import math

import pytest
from fastapi.testclient import TestClient
from shapely.errors import GEOSException
from shapely.geometry import GeometryCollection, LineString, MultiPolygon, Point, Polygon

from app import analyzer, topology
from app.main import app
from app.schemas import AnalysisSettings, MaskFile
from benchmarks.baseline import analyzer as baseline, topology as old_topology
from benchmarks.baseline.schemas import MaskFile as OldMask, AnalysisSettings as OldSettings
from .test_cold_exact import assert_bits
from ..factories import room, wall, door, rect, vertices


def mixed_data(angle=0):
    contours = [
        room(1, rect(-0., 0., 100., 100.), name=None),
        room(2, rect(50., 50., 150., 150.), holes=[vertices(rect(70., 70., 80., 80.))]),
        room(1, rect(50., 50., 150., 150.)),  # duplicate ID and overlapping rooms
        room(3, rect(200., 0., 300., 100.), holes=[vertices(rect(0., 0., 10., 10.))]),
        room(4, [(0., 0.), (100., 100.), (0., 100.), (50., 0.)]),
        room(5, rect(300., 0., 400., 100.), holes='invalid'),
        room(6, [(0., 0.), (0., 0.), (0., 0.)]),
        room(7, [(0., 0.), (0., 1.)]),
        room(8, [(200., 200.), (210., 200.), (210., 210.), (220., 210.),
                 (220., 220.), (210., 220.), (210., 210.), (200., 210.)]),
        wall(10, (0., 0.), (100., 0.)),
        wall(11, (0., 0.), (0., 0.)),
        wall(12, (100., 0.), (100., 100.)),
        door(13, (20., 0.), (40., 0.)),
    ]
    for contour in contours:
        rings = [contour['vertices']]
        if isinstance(contour.get('holes'), list):
            rings += contour['holes']
        for ring in rings:
            for v in ring:
                x, y = v['x'], v['y']
                if angle:
                    v.update(x=x * math.cos(angle) - y * math.sin(angle),
                             y=x * math.sin(angle) + y * math.cos(angle))
    return dict(contours=contours, image_width=1000, image_height=1000)


@pytest.mark.parametrize('angle', [0., .13, 1.3])
@pytest.mark.parametrize('tolerance', [0., 1e-9, 10.])
def test_mixed_batch_and_fallback_match_frozen_bits(angle, tolerance):
    data = mixed_data(angle)
    settings = dict(tolerance_px=tolerance, scale_m=2.345, scale_px=123.4)
    expected = baseline.analyze(OldMask.model_validate(data), OldSettings(**settings))
    mask = MaskFile.model_validate(data)
    for actual in (analyzer.analyze_uncached(mask, AnalysisSettings(**settings)),
                   analyzer.analyze(mask, AnalysisSettings(**settings)),
                   analyzer.analyze(mask, AnalysisSettings(**settings))):
        assert_bits(expected.model_dump(mode='json'), actual.model_dump(mode='json'))
    # Uncached uses the original explicit/default field selection as well.
    actual = analyzer.analyze_uncached(mask, AnalysisSettings(**settings))
    assert_bits(expected.model_dump(mode='json', exclude_unset=True),
                actual.model_dump(mode='json', exclude_unset=True))


@pytest.mark.parametrize('failure', [ValueError, GEOSException])
def test_batch_construction_failure_uses_scalar_warnings(monkeypatch, failure):
    data = mixed_data()
    expected = baseline.analyze(OldMask.model_validate(data)).model_dump(mode='json')
    def fail(*args, **kwargs):
        raise failure('forced batch failure')
    monkeypatch.setattr(topology, 'linearrings', fail)
    assert_bits(expected, analyzer.analyze(MaskFile.model_validate(data)).model_dump(mode='json'))


def test_simple_batch_shape_and_representative_point_bits():
    data = mixed_data(.13)
    # Explicitly closed and repeated vertices, reversed winding, and signed zero.
    data['contours'] += [room(20, rect(-0., -0., 30., 50.) + [(-0., -0.)]),
                         room(21, list(reversed(rect(-10., -20., 50., 70.))))]
    rooms = [r for r in MaskFile.model_validate(data).contours if not r.isLine]
    prepared = topology.simple_room_polygons(rooms)
    assert prepared
    for item in rooms:
        if id(item) not in prepared:
            continue
        polygon, coords = prepared[id(item)]
        expected, _ = topology.room_polygon(item)
        assert expected.wkb == polygon.wkb
        point = expected.representative_point()
        assert_bits([point.x, point.y], coords)
    assert id(rooms[1]) not in prepared  # holes use full containment validation
    assert id(rooms[3]) not in prepared  # invalid hole
    assert id(rooms[4]) not in prepared  # self-intersection
    assert topology.simple_room_polygons([rooms[0]]) == {}


def test_invalid_outer_uses_scalar_fallback_in_original_order(monkeypatch):
    calls = []
    scalar = analyzer.room_polygon
    def record(room):
        calls.append(room.id)
        return scalar(room)
    monkeypatch.setattr(analyzer, 'room_polygon', record)
    data = mixed_data()
    actual = analyzer.analyze_uncached(MaskFile.model_validate(data))
    assert calls == [2, 3, 5, 8]
    assert_bits(baseline.analyze(OldMask.model_validate(data)).model_dump(mode='json'),
                actual.model_dump(mode='json'))


def test_bulk_models_preserve_nested_fields_set():
    from pydantic import BaseModel
    def compare_fields(expected, actual):
        if isinstance(expected, BaseModel):
            assert isinstance(actual, BaseModel)
            # 凍結 baseline には共有境界フィールドがまだない。変更前の現行実装は
            # この二つを常に明示設定する（値が空なら serializer が省略する）。
            added = {'canonical_edge_id', 'canonical_edge_ids'} if type(actual).__name__ == 'EdgeResult' else set()
            assert expected.model_fields_set | added == actual.model_fields_set
            for key in expected.__dict__:
                compare_fields(getattr(expected, key), getattr(actual, key))
        elif isinstance(expected, list):
            assert len(expected) == len(actual)
            for left, right in zip(expected, actual):
                compare_fields(left, right)
    data = mixed_data(.13)
    expected = baseline.analyze(OldMask.model_validate(data))
    actual = analyzer.analyze_uncached(MaskFile.model_validate(data))
    for key in ('rooms', 'walls', 'doors', 'overlaps', 'warnings'):
        compare_fields(getattr(expected, key), getattr(actual, key))
    args = (0, (0., 0.), (100., 0.), [(1, ((0., 0.), (100., 0.)))], [])
    expected_edge = baseline.analyze_edge(*args, OldSettings())
    actual_edge = analyzer.analyze_edge(*args, AnalysisSettings())
    compare_fields(expected_edge, actual_edge)
    assert_bits(expected_edge.model_dump(mode='json', exclude_unset=True),
                actual_edge.model_dump(mode='json', exclude_unset=True))


@pytest.mark.parametrize('mixed', [False, True])
def test_batch_region_ring_order_bits_and_fields_set(mixed):
    outer = Polygon(rect(-0., -0., 100., 100.), [rect(10., 10., 20., 20.), rect(30., 30., 40., 40.)])
    simple = Polygon(rect(200., 200., 220., 220.))
    geometries = [Polygon(), outer, Polygon(), simple, Polygon()]
    if mixed:
        geometries += [MultiPolygon([outer, simple]),
                       GeometryCollection([Point(0, 0), GeometryCollection([outer, LineString([(0, 0), (1, 1)])])])]
    expected = [old_topology.polygon_regions(geom) for geom in geometries]
    actual = topology.polygon_regions_many(geometries)
    for opts in ({}, {'exclude_unset': True}):
        assert_bits([[r.model_dump(mode='json', **opts) for r in group] for group in expected],
                    [[r.model_dump(mode='json', **opts) for r in group] for group in actual])
    assert topology.polygon_regions_many([]) == []


@pytest.mark.parametrize('route', ['/api/analyze', '/api/analyze/json'])
def test_api_mixed_input_full_response_bits_and_order(route):
    data = mixed_data(.13)
    expected = baseline.analyze(OldMask.model_validate(data)).model_dump(mode='json')
    with TestClient(app) as client:
        for _ in range(2):  # cold and warm
            if route == '/api/analyze':
                response = client.post(route, files={'file': ('mask.json', json.dumps(data), 'application/json')})
            else:
                response = client.post(route, json=data)
            assert response.status_code == 200, response.text
            assert_bits(expected, response.json())
