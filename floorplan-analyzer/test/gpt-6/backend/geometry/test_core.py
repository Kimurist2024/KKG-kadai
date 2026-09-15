import math

from app import geometry as g


def test_polygon_area_and_perimeter_rectangle():
    rect = [(0, 0), (100, 0), (100, 50), (0, 50)]
    assert g.polygon_area(rect) == 5000
    assert g.polygon_perimeter(rect) == 300
    # 頂点順が逆でも面積は正
    assert g.polygon_area(list(reversed(rect))) == 5000


def test_polygon_area_degenerate():
    assert g.polygon_area([(0, 0), (1, 1)]) == 0


def test_projection_keeps_parallel_and_rejects_perpendicular():
    a, b = (0.0, 0.0), (100.0, 0.0)
    segs = [
        (1, ((10.0, 2.0), (60.0, 2.0))),   # 平行・近接 → 採用
        (2, ((50.0, 0.0), (50.0, 80.0))),  # 直交 (T字) → 除外
        (3, ((0.0, 30.0), (100.0, 30.0))),  # 平行だが遠い → 除外
        (4, ((-50.0, -1.0), (150.0, 1.0))),  # 辺をはみ出す → クリップ
    ]
    ivs = g.project_segments_onto_edge(a, b, segs, tolerance_px=5)
    assert {tuple(sorted(i.ids)) for i in ivs} == {(1,), (4,)}
    full = next(i for i in ivs if i.ids == {4})
    assert (full.start, full.end) == (0.0, 100.0)


def test_merge_snap_drop_complement():
    ivs = [g.Interval(3, 40, {1}), g.Interval(42, 60, {2}), g.Interval(70, 71, {3})]
    merged = g.merge_intervals(ivs, gap_tolerance_px=5)
    assert [(i.start, i.end) for i in merged] == [(3, 60), (70, 71)]
    assert merged[0].ids == {1, 2}
    snapped = g.snap_to_edge_ends(merged, edge_length=100, tolerance_px=5)
    assert snapped[0].start == 0
    kept = g.drop_short(snapped, min_length_px=5)
    assert len(kept) == 1
    openings = g.complement_intervals(kept, 100)
    assert [(o.start, o.end) for o in openings] == [(60, 100)]


def test_clip_intervals():
    a = [g.Interval(10, 50, {9})]
    b = [g.Interval(0, 20), g.Interval(40, 100)]
    clipped = g.clip_intervals(a, b)
    assert [(c.start, c.end) for c in clipped] == [(10, 20), (40, 50)]
    assert all(c.ids == {9} for c in clipped)


def test_point_at():
    p = g.point_at((0, 0), (0, 10), 2.5)
    assert math.isclose(p[1], 2.5) and p[0] == 0


def test_projection_rejects_diagonal_segment_within_tolerance_band():
    # 両端が tolerance 帯の中にあっても、斜めに横切る線分は「沿う壁」ではない
    a, b = (0.0, 0.0), (100.0, 0.0)
    diag = [(1, ((40.0, -9.0), (60.0, 9.0)))]
    assert g.project_segments_onto_edge(a, b, diag, tolerance_px=10) == []
    # 1 度未満の傾きは採用される (セグメンテーション由来の微小な傾き)
    slight = [(2, ((0.0, 0.0), (100.0, 1.0)))]
    assert len(g.project_segments_onto_edge(a, b, slight, tolerance_px=10)) == 1


def test_projection_ignores_zero_length_segment_and_reversed_direction():
    a, b = (0.0, 0.0), (100.0, 0.0)
    segs = [(1, ((50.0, 0.0), (50.0, 0.0))), (2, ((80.0, 1.0), (20.0, 1.0)))]
    ivs = g.project_segments_onto_edge(a, b, segs, tolerance_px=5)
    assert [(i.start, i.end, i.ids) for i in ivs] == [(20.0, 80.0, {2})]


def test_complement_clips_out_of_range_intervals():
    out = g.complement_intervals([g.Interval(-10, 30), g.Interval(90, 200)], 100)
    assert [(o.start, o.end) for o in out] == [(30, 90)]
    assert g.complement_intervals([], 0) == []
