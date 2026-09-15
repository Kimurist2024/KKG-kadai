import math

import pytest

from app.analyzer import analyze, classify
from app.schemas import AnalysisSettings, MaskFile

MPP = 1.365 / 96.7


def make_mask(contours):
    return MaskFile(contours=contours, image_width=1000, image_height=1000)


def room(id_, pts, name="R"):
    return {
        "id": id_,
        "vertices": [{"x": x, "y": y} for x, y in pts],
        "color": "#123456",
        "room_name": name,
        "label_id": 1,
    }


def line(id_, p, q, label):
    return {
        "id": id_,
        "vertices": [{"x": p[0], "y": p[1]}, {"x": q[0], "y": q[1]}],
        "color": "#FF0000",
        "room_name": None,
        "label_id": label,
        "isLine": True,
        "lineWidth": 5,
    }


def test_full_rectangle_with_walls_and_door():
    # 100px × 200px の部屋。4 辺すべてに壁、下辺に 50px のドア。
    pts = [(0, 0), (100, 0), (100, 200), (0, 200)]
    contours = [
        room(1, pts, "LD"),
        line(10, (0, 0), (100, 0), 2),
        line(11, (100, 0), (100, 200), 2),
        line(12, (100, 200), (0, 200), 2),
        line(13, (0, 200), (0, 0), 2),
        line(20, (20, 201), (70, 201), 3),  # 1px ずれたドア
    ]
    res = analyze(make_mask(contours))
    assert len(res.rooms) == 1
    r = res.rooms[0]
    assert math.isclose(r.floor_area_m2, 100 * 200 * MPP * MPP)
    assert math.isclose(r.perimeter_m, 600 * MPP)
    assert math.isclose(r.wall_length_m, 600 * MPP, rel_tol=1e-9)
    assert math.isclose(r.opening_length_m, 0, abs_tol=1e-9)
    assert math.isclose(r.door_length_m, 50 * MPP, rel_tol=1e-9)
    assert r.door_count == 1
    expected = 600 * MPP * 2.4 - 50 * MPP * 2.0
    assert math.isclose(r.wall_area_m2, expected, rel_tol=1e-9)
    assert res.warnings == []


def test_missing_wall_section_is_not_counted():
    # 上辺に壁が無く、右辺は半分だけ壁
    pts = [(0, 0), (100, 0), (100, 200), (0, 200)]
    contours = [
        room(1, pts),
        line(11, (100, 0), (100, 100), 2),  # 右辺の上半分だけ
        line(12, (100, 200), (0, 200), 2),
        line(13, (0, 200), (0, 0), 2),
    ]
    r = analyze(make_mask(contours)).rooms[0]
    assert math.isclose(r.wall_length_m, (100 + 100 + 200) * MPP, rel_tol=1e-9)
    assert math.isclose(r.opening_length_m, (100 + 100) * MPP, rel_tol=1e-9)
    right = next(e for e in r.edges if e.index == 1)
    assert len(right.wall_intervals) == 1 and len(right.opening_intervals) == 1
    assert math.isclose(right.opening_intervals[0].length_px, 100, rel_tol=1e-9)


def test_door_on_open_section_is_not_deducted_and_warned():
    pts = [(0, 0), (100, 0), (100, 200), (0, 200)]
    contours = [
        room(1, pts),
        line(12, (100, 200), (0, 200), 2),
        line(20, (20, 0), (70, 0), 3),  # 壁の無い上辺にドア
    ]
    res = analyze(make_mask(contours))
    r = res.rooms[0]
    assert r.door_length_m == 0
    assert any("ドア id=20" in w.message for w in res.warnings)


def test_shared_wall_counts_for_both_rooms():
    a = room(1, [(0, 0), (100, 0), (100, 100), (0, 100)], "A")
    b = room(2, [(100, 0), (200, 0), (200, 100), (100, 100)], "B")
    shared = line(10, (100, 0), (100, 100), 2)
    res = analyze(make_mask([a, b, shared]))
    for r in res.rooms:
        assert math.isclose(r.wall_length_m, 100 * MPP, rel_tol=1e-9)


def test_unnamed_room_gets_display_name_and_warning():
    res = analyze(make_mask([room(7, [(0, 0), (10, 0), (10, 10), (0, 10)], name=None)]))
    assert res.rooms[0].name == "未命名 #7"
    assert any("id=7" in w.message for w in res.warnings)


def test_duplicate_names_get_suffix():
    res = analyze(
        make_mask(
            [
                room(1, [(0, 0), (10, 0), (10, 10), (0, 10)], "収納"),
                room(2, [(20, 0), (30, 0), (30, 10), (20, 10)], "収納"),
            ]
        )
    )
    assert [r.name for r in res.rooms] == ["収納 (1)", "収納 (2)"]


def test_settings_change_results():
    pts = [(0, 0), (100, 0), (100, 100), (0, 100)]
    contours = [room(1, pts), line(10, (0, 0), (100, 0), 2)]
    s = AnalysisSettings(ceiling_height_m=3.0, scale_px=100, scale_m=1.0)
    r = analyze(make_mask(contours), s).rooms[0]
    assert math.isclose(r.floor_area_m2, 1.0)
    assert math.isclose(r.wall_area_m2, 1.0 * 3.0)


def test_classify_sample(sample_json):
    mask = MaskFile.model_validate(sample_json)
    rooms, walls, doors = classify(mask.contours)
    assert (len(rooms), len(walls), len(doors)) == (11, 21, 9)


def test_sample_file_results(sample_json):
    """実データ: JSON 記載値との整合と、既知の壁なし区間の検出。"""
    res = analyze(MaskFile.model_validate(sample_json))
    assert res.summary.room_count == 11
    by_name = {r.name: r for r in res.rooms}
    for r in res.rooms:
        assert math.isclose(r.floor_area_px2, r.source_area_px2, abs_tol=0.5)
        assert math.isclose(r.perimeter_px, r.source_perimeter_px, abs_tol=0.5)
    # LD + K ≒ 図面上の LDK 27.22 m² (誤差はマスク境界の取り方による)
    ldk = by_name["LD"].floor_area_m2 + by_name["K"].floor_area_m2
    assert 26.5 < ldk < 28.5
    # 階段はホール側 (上辺) に壁が無い
    stairs = by_name["階段"]
    assert stairs.opening_length_m > 0.8
    # LD と K の境界は一部しか壁が無い
    ld = by_name["LD"]
    assert ld.opening_length_m > 3.0
    # ドア控除が行われている
    assert by_name["浴室"].door_length_m > 0.5
    assert all("一致しません" not in w.message for w in res.warnings)


def test_door_ids_are_clipped_per_door_before_merge():
    from app import geometry as g
    from app.analyzer import door_intervals_on_edge

    doors = [(1, ((0.0, 0.0), (20.0, 0.0))), (2, ((20.0, 0.0), (40.0, 0.0)))]
    result = door_intervals_on_edge((0.0, 0.0), (100.0, 0.0), doors, [g.Interval(0, 10)], tolerance_px=0)
    assert {sid for iv in result for sid in iv.ids} == {1}  # ドア 2 は壁と重ならない
    assert g.total_length(result) == pytest.approx(10)


def test_endpoint_noise_is_dropped_before_snapping():
    from app.analyzer import wall_intervals_on_edge

    # 辺の端にある 1px のノイズは、スナップで tol 長に膨らむ前に除去される
    noise = [(1, ((9.0, 0.0), (10.0, 0.0)))]
    assert wall_intervals_on_edge((0.0, 0.0), (100.0, 0.0), noise, tolerance_px=10) == []


def test_unknown_line_label_is_ignored_with_warning():
    pts = [(0, 0), (100, 0), (100, 100), (0, 100)]
    contours = [room(1, pts), line(10, (0, 0), (100, 0), 2), line(11, (100, 0), (100, 100), 9)]
    res = analyze(make_mask(contours))
    assert math.isclose(res.rooms[0].wall_length_m, 100 * MPP, rel_tol=1e-9)
    assert any("未知の label_id=9" in w.message for w in res.warnings)


def test_duplicate_ids_and_holes_are_warned():
    pts = [(0, 0), (100, 0), (100, 100), (0, 100)]
    r = room(1, pts)
    r["holes"] = [[{"x": 10, "y": 10}]]
    res = analyze(make_mask([r, line(1, (0, 0), (100, 0), 2)]))
    assert any("id=1 が 2 回" in w.message for w in res.warnings)
    assert not res.rooms
    assert any(w.code == "invalid_shape" for w in res.warnings)


def test_invariants_and_orientation_independence(sample_json):
    """辺ごとの不変条件と、頂点順を反転しても結果が変わらないこと。"""
    mask = MaskFile.model_validate(sample_json)
    res = analyze(mask)
    for r in res.rooms:
        assert math.isclose(sum(e.length_m for e in r.edges), r.perimeter_m, rel_tol=1e-9)
        for e in r.edges:
            assert e.wall_length_m + e.opening_length_m == pytest.approx(e.length_m)
            assert 0 <= e.door_length_m <= e.wall_length_m + 1e-9
            assert e.wall_area_m2 == pytest.approx(e.wall_area_gross_m2 - e.door_area_m2)
    reversed_json = dict(sample_json)
    reversed_json["contours"] = [
        {**c, "vertices": list(reversed(c["vertices"]))} for c in sample_json["contours"]
    ]
    res2 = analyze(MaskFile.model_validate(reversed_json))
    for a, b in zip(res.rooms, res2.rooms):
        assert a.floor_area_m2 == pytest.approx(b.floor_area_m2)
        assert a.wall_area_m2 == pytest.approx(b.wall_area_m2)
        assert a.opening_length_m == pytest.approx(b.opening_length_m)


def test_door_taller_than_ceiling_is_rejected():
    with pytest.raises(ValueError):
        AnalysisSettings(ceiling_height_m=2.0, door_height_m=2.4)


def test_multiple_noise_fragments_are_not_merged_into_wall():
    from app.analyzer import wall_intervals_on_edge

    # tol 未満の断片が 2 つ近接していても、併合・スナップで壁に化けない
    noise = [(1, ((9.0, 0.0), (10.0, 0.0))), (2, ((19.0, 0.0), (20.0, 0.0)))]
    assert wall_intervals_on_edge((0.0, 0.0), (100.0, 0.0), noise, tolerance_px=10) == []
    # 一方、分断された本物の壁 (各 40px 以上) は隙間 8px を埋めて 1 本になる
    split = [(1, ((0.0, 0.0), (40.0, 0.0))), (2, ((48.0, 0.0), (100.0, 0.0)))]
    ivs = wall_intervals_on_edge((0.0, 0.0), (100.0, 0.0), split, tolerance_px=10)
    assert [(i.start, i.end) for i in ivs] == [(0.0, 100.0)]


def test_degenerate_and_self_intersecting_rooms_are_flagged():
    flat = room(1, [(0, 0), (50, 0), (100, 0)], "flat")
    bowtie = room(2, [(0, 0), (100, 100), (100, 0), (0, 80)], "bowtie")  # 非対称 (面積 ≠ 0) の蝶ネクタイ
    ok = room(3, [(200, 0), (300, 0), (300, 100), (200, 100)], "ok")
    res = analyze(make_mask([flat, bowtie, ok]))
    assert [r.name for r in res.rooms] == ["ok"]  # 不正形状は集計に含めない
    assert any("面積が 0" in w.message for w in res.warnings)
    assert any("自己交差" in w.message for w in res.warnings)


def test_finely_subdivided_edge_keeps_full_wall():
    """辺が tol より細かく (5px 刻みで) 分割されていても、壁長は変わらない。"""
    top = [(x, 0) for x in range(0, 101, 5)]  # (0,0) … (100,0) の 21 頂点
    pts = top + [(100, 100), (0, 100)]
    contours = [room(1, pts), line(10, (0, 0), (100, 0), 2)]
    r = analyze(make_mask(contours)).rooms[0]
    assert math.isclose(r.wall_length_m, 100 * MPP, rel_tol=1e-9)
    assert math.isclose(r.opening_length_m, 300 * MPP, rel_tol=1e-9)
    # 同じ形を 4 頂点で表しても結果が一致する
    r2 = analyze(make_mask([room(1, [(0, 0), (100, 0), (100, 100), (0, 100)]), line(10, (0, 0), (100, 0), 2)])).rooms[0]
    assert math.isclose(r.wall_area_m2, r2.wall_area_m2, rel_tol=1e-9)
