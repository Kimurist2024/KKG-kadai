"""ドア開口部の床の配分契約。幾何・API・cold/warm の不変条件。"""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import analyzer
from app.analysis_cache import cache
from app.door_openings import opening_geometry
from app.main import app
from app.schemas import AnalysisSettings, MaskFile
from ..factories import make_mask, room, rect, wall, door, unit_settings
from ..performance.test_cold_exact import assert_bits


def shared_mask(*, equal=False, split=False, third=False, duplicate_id=False):
    left = rect(0, 0, 100, 100)
    if split:
        left.insert(2, (100, 50))
    return make_mask([
        room(9, left, '同名'),
        room(9 if duplicate_id else 2, rect(100, 0, 200 if equal else 150, 100), '同名'),
        *([room(3, rect(100, 0, 170, 100))] if third else []),
        wall(10, (100, 0), (100, 100)),
        door(20, (100, 20), (100, 80)),
    ])


def opening_mask(*doors):
    return make_mask([
        room(1, rect(0, 0, 200, 200)),
        room(2, rect(200, 0, 300, 200)),
        wall(10, (200, 0), (200, 200)),
        *doors,
    ])


def analyze_opening(mask, path):
    if path == 'uncached':
        return analyzer.analyze_uncached(mask)
    analyzer.clear_geometry_cache()
    result = analyzer.analyze(mask)
    return analyzer.analyze(mask) if path == 'warm' else result


@pytest.mark.parametrize('path', ['cold', 'warm', 'uncached'])
def test_adjacent_doors_preserve_union_floor_adjustment(path):
    single = analyze_opening(opening_mask(door(20, (200, 40), (200, 160))), path)
    split = analyze_opening(opening_mask(
        door(20, (200, 40), (200, 100)),
        door(21, (200, 100), (200, 160))), path)
    for expected, actual in zip(single.rooms, split.rooms):
        intervals = [iv for edge in actual.edges for iv in edge.door_intervals]
        assert len(intervals) == 1
        assert set(intervals[0].ids) == {20, 21}
        assert intervals[0].length_px == 120
        assert actual.door_opening_adjustment_m2 == pytest.approx(
            expected.door_opening_adjustment_m2, rel=0, abs=1e-9)
        assert len(actual.door_opening_transfers) == 2
        assert sum(t.width_m for t in actual.door_opening_transfers) == pytest.approx(
            expected.door_opening_transfers[0].width_m, rel=0, abs=1e-9)
        assert_bits(expected.wall_area_m2, actual.wall_area_m2)
    assert split.summary.total_floor_area_m2 == pytest.approx(
        single.summary.total_floor_area_m2, rel=0, abs=1e-9)


@pytest.mark.parametrize('path', ['cold', 'warm', 'uncached'])
def test_duplicate_doors_preserve_union_floor_adjustment(path):
    single = analyze_opening(opening_mask(door(20, (200, 40), (200, 160))), path)
    duplicate = analyze_opening(opening_mask(
        door(20, (200, 40), (200, 160)),
        door(21, (200, 40), (200, 160))), path)
    for expected, actual in zip(single.rooms, duplicate.rooms):
        assert actual.door_opening_adjustment_m2 == pytest.approx(
            expected.door_opening_adjustment_m2, rel=0, abs=1e-9)
        assert len(actual.door_opening_transfers) == 2
        assert sum(t.width_m for t in actual.door_opening_transfers) == pytest.approx(
            expected.door_opening_transfers[0].width_m, rel=0, abs=1e-9)


def test_opening_geometry_weights_by_original_door_lengths():
    response = analyzer.analyze(opening_mask(
        door(20, (200, 40), (200, 70)),
        door(21, (200, 70), (200, 160))))
    # 区間幅は線分長の合計と異なっても、元のドア長30:90で配分する。
    for room in response.rooms:
        for edge in room.edges:
            for interval in edge.door_intervals:
                interval.length_px = 100.1
                interval.ids.reverse()
    weighted = opening_geometry(response.rooms, response.doors)
    equal = opening_geometry(response.rooms)
    for index in range(2):
        assert list(weighted[index]) == [20, 21]
        assert weighted[index][20][1] == pytest.approx(100.1 / 4)
        assert weighted[index][21][1] == pytest.approx(100.1 * 3 / 4)
        assert sum(value[1] for value in weighted[index].values()) == pytest.approx(100.1, rel=0, abs=1e-9)
        assert [value[1] for value in equal[index].values()] == [100.1 / 2] * 2


@pytest.mark.parametrize('with_doors', [False, True])
def test_opening_geometry_last_id_receives_remainder(with_doors):
    response = analyzer.analyze(opening_mask(*[
        door(id_, (200, 40), (200, 160)) for id_ in (22, 20, 21)]))
    for room in response.rooms:
        for edge in room.edges:
            for interval in edge.door_intervals:
                interval.length_px = .1
    geometry = (opening_geometry(response.rooms, response.doors) if with_doors
                else opening_geometry(response.rooms))
    for openings in geometry:
        widths = [value[1] for value in openings.values()]
        assert list(openings) == [20, 21, 22]
        assert sum(widths) == pytest.approx(.1, rel=0, abs=1e-9)
        assert_bits(.1 - sum(widths[:-1]), widths[-1])
        assert widths[-1] != widths[0]


def test_single_id_width_preserves_float_bits():
    response = analyzer.analyze(shared_mask())
    response.doors[0].length_px = 3.0
    for room in response.rooms:
        for edge in room.edges:
            for interval in edge.door_intervals:
                interval.length_px = .1  # .1 * 3 / 3 は .1 とビットが異なる。
    for geometry in (opening_geometry(response.rooms),
                     opening_geometry(response.rooms, response.doors)):
        for openings in geometry:
            assert_bits(.1, openings[20][1])


def test_sample_default_rooms_and_summary_match_fixture(sample_json):
    """環境（GEOS の版）による末尾桁の差は許容し、値の同一性を確かめる。"""
    response = analyzer.analyze(MaskFile.model_validate(sample_json)).model_dump(mode='json')
    fixture_path = Path(__file__).resolve().parents[2] / 'frontend/fixtures/sample-result.json'
    expected = json.loads(fixture_path.read_text(encoding='utf-8'))

    def assert_matches(actual, expected, path):
        assert type(actual) is type(expected), path
        if isinstance(expected, dict):
            assert actual.keys() == expected.keys(), path
            for key in expected:
                assert_matches(actual[key], expected[key], f'{path}.{key}')
        elif isinstance(expected, list):
            assert len(actual) == len(expected), path
            for index, (actual_item, expected_item) in enumerate(zip(actual, expected)):
                assert_matches(actual_item, expected_item, f'{path}[{index}]')
        elif isinstance(expected, float):
            assert actual == pytest.approx(expected, rel=1e-9, abs=1e-9), path
        else:
            assert actual == expected, path

    for key in ('rooms', 'summary'):
        assert_matches(response[key], expected[key], key)


def test_sample_contract_and_geometry_unchanged(sample_json):
    mask = MaskFile.model_validate(sample_json)
    zero = analyzer.analyze(mask, AnalysisSettings(door_opening_depth_m=0))
    result = analyzer.analyze(mask)
    rooms = {r.name: r for r in result.rooms}
    ld = rooms['LD']
    assert ld.door_opening_adjustment_m2 == pytest.approx(-2.4495 * .126, abs=1e-5)
    assert [(t.door_id, t.other_room_name) for t in ld.door_opening_transfers] == [
        (33, '洗面所'), (34, '未命名 #3'), (38, 'ホール')]
    assert all(t.area_m2 < 0 for t in ld.door_opening_transfers)
    assert rooms['K'].door_opening_adjustment_m2 == 0.0
    assert round(ld.floor_area_m2 + rooms['K'].floor_area_m2, 2) == 27.22
    assert round(result.summary.total_floor_area_m2, 2) == 48.75
    assert result.summary.door_opening_adjusted_room_count == 9
    assert abs(result.summary.total_floor_area_m2 - zero.summary.total_floor_area_m2) < 1e-9
    assert abs(sum(r.door_opening_adjustment_m2 for r in result.rooms)) < 1e-9
    assert [t.door_id for t in rooms['玄関'].door_opening_transfers] == [40]
    for current, raw in zip(result.rooms, zero.rooms):
        assert current.floor_area_m2 == current.floor_area_raw_m2 + current.door_opening_adjustment_m2
        assert current.door_opening_adjustment_m2 == sum(t.area_m2 for t in current.door_opening_transfers)
        assert [t.door_id for t in current.door_opening_transfers] == sorted(t.door_id for t in current.door_opening_transfers)
        exclude = {'floor_area_m2', 'door_opening_adjustment_m2', 'door_opening_transfers'}
        assert_bits(raw.model_dump(exclude=exclude), current.model_dump(exclude=exclude))
    exclude = {'rooms', 'settings', 'summary'}
    assert_bits(zero.model_dump(exclude=exclude), result.model_dump(exclude=exclude))
    exclude = {'total_floor_area_m2', 'door_opening_adjusted_room_count'}
    assert_bits(zero.summary.model_dump(exclude=exclude), result.summary.model_dump(exclude=exclude))


@pytest.mark.parametrize('equal,split,duplicate_id', [(False, False, False), (True, False, False),
                                                     (False, True, False), (False, False, True)])
def test_direction_names_multiple_edges_and_duplicate_room_ids(equal, split, duplicate_id):
    result = analyzer.analyze(shared_mask(equal=equal, split=split, duplicate_id=duplicate_id),
                              unit_settings(door_opening_depth_m=.2))
    a, b = result.rooms
    sign = 1 if equal else -1  # 同面積は id=2 -> id=9。入力順ではない。
    assert a.door_opening_adjustment_m2 == sign * 12.0
    assert b.door_opening_adjustment_m2 == -sign * 12.0
    ta, tb = a.door_opening_transfers[0], b.door_opening_transfers[0]
    assert ta.width_m == tb.width_m == 60
    assert ta.area_m2 == -tb.area_m2
    assert (ta.other_room_id, ta.other_room_name) == (b.id, '同名 (2)')
    assert (tb.other_room_id, tb.other_room_name) == (a.id, '同名 (1)')


def test_clipped_width_uses_smaller_side():
    mask = shared_mask()
    # 右の部屋の下辺を y=60 に切り詰める。ドア幅は左60px、右40px。
    mask.contours[1].vertices = make_mask([room(2, rect(100, 0, 150, 60))]).contours[0].vertices
    result = analyzer.analyze(mask, unit_settings(door_opening_depth_m=.2))
    widths = [sum(iv.length_px for e in r.edges for iv in e.door_intervals if 20 in iv.ids)
              for r in result.rooms]
    assert widths == [60, 40]
    a, b = [r.door_opening_transfers[0] for r in result.rooms]
    assert a.width_m == b.width_m == 40
    assert a.area_m2 == -b.area_m2 == -8


@pytest.mark.parametrize('count', [0, 1, 3])
def test_only_exactly_two_rooms_are_eligible(count):
    mask = shared_mask(third=True)
    mask.contours = mask.contours[:count] + mask.contours[-2:]
    result = analyzer.analyze(mask, unit_settings())
    assert result.summary.door_opening_adjusted_room_count == 0
    for r in result.rooms:
        assert r.door_opening_transfers == []
        assert r.door_opening_adjustment_m2 == 0.0
        assert_bits(r.floor_area_m2, r.floor_area_raw_m2)


@pytest.mark.parametrize('mode', ['raw', 'regularized_shared'])
@pytest.mark.parametrize('depth', [0, .126, .37, 1])
def test_cold_warm_uncached_bits_and_depth_is_not_cache_key(sample_json, monkeypatch, mode, depth):
    mask = MaskFile.model_validate(sample_json)
    settings = AnalysisSettings(door_opening_depth_m=depth, geometry_mode=mode,
                                scale_m=2.345, scale_px=123.4, ceiling_height_m=3.1)
    expected = analyzer.analyze_uncached(mask, settings)
    assert_bits(expected.model_dump(), analyzer.analyze(mask, settings).model_dump())
    analyzer.clear_geometry_cache()
    analyzer.analyze(mask, AnalysisSettings(door_opening_depth_m=.8, geometry_mode=mode))
    assert len(cache._entries) == 1
    stored = json.loads(next(iter(cache._entries.values()))[1])
    assert any(stored['door_openings'])
    def fail(*args):
        pytest.fail('depth/scale/height changes must reuse geometry')
    monkeypatch.setattr(analyzer, '_compute_geometry', fail)
    actual = analyzer.analyze(mask, settings)
    assert_bits(expected.model_dump(), actual.model_dump())
    assert expected.model_dump_json() == actual.model_dump_json()


def test_transfer_response_does_not_alias_cache(sample_json):
    mask = MaskFile.model_validate(sample_json)
    response = analyzer.analyze(mask)
    expected = response.model_dump()
    response.rooms[0].door_opening_transfers[0].area_m2 = 999
    response.rooms[0].door_opening_transfers.clear()
    assert_bits(expected, analyzer.analyze(mask).model_dump())


@pytest.mark.parametrize('depth', [0, .37, 1])
def test_query_and_json_body_settings(sample_json, depth):
    settings = dict(door_opening_depth_m=depth, scale_m=1.75, ceiling_height_m=3.1)
    with TestClient(app) as client:
        uploaded = client.post('/api/analyze', params=settings,
                               files={'file': ('mask.json', json.dumps(sample_json), 'application/json')})
        body = client.post('/api/analyze/json', json={'mask': sample_json, 'settings': settings})
        assert uploaded.status_code == body.status_code == 200
        assert_bits(uploaded.json(), body.json())
        assert body.json()['settings']['door_opening_depth_m'] == depth
        assert client.get('/api/defaults').json()['door_opening_depth_m'] == .126


@pytest.mark.parametrize('depth', [-.01, 1.01, float('nan'), float('inf')])
@pytest.mark.parametrize('source', ['upload-query', 'json-body', 'json-query'])
def test_invalid_depth_returns_422(depth, source):
    mask = dict(contours=[], image_width=1, image_height=1)
    settings = {'door_opening_depth_m': depth}
    with TestClient(app) as client:
        if source == 'upload-query':
            response = client.post('/api/analyze', params=settings,
                                   files={'file': ('mask.json', json.dumps(mask), 'application/json')})
        elif source == 'json-query':
            response = client.post('/api/analyze/json', params=settings, json=mask)
        else:
            response = client.post('/api/analyze/json', content=json.dumps({'mask': mask, 'settings': settings}),
                                   headers={'content-type': 'application/json'})
    assert response.status_code == 422, response.text
    assert 'door_opening_depth_m' in response.text
