"""純粋な幾何計算ユーティリティ。

外部ライブラリに依存せず、テストしやすいように副作用のない関数のみを置く。
座標系は画像ピクセル座標 (x: 右向き, y: 下向き)。
"""
from __future__ import annotations

import math
from typing import Iterable, List, NamedTuple, Optional, Sequence, Tuple

from .geometry_primitives import (Point, Segment, EPS_PX, DEFAULT_MAX_ANGLE_DEG,
                                  Interval, _interval_sort_key, merge_intervals,
                                  _orientation, _segments_intersect)
from .strategies.interval_clip import (auto as clip_intervals, _intervals_are_disjoint,
                                      _clip_disjoint_intervals, _clip_overlapping_intervals,
                                      _clip_all_pairs)
from .strategies.self_intersection import (auto as is_self_intersecting,
                                          _self_intersection_sweep,
                                          _self_intersection_all_pairs)

def polygon_area(vertices: Sequence[Point]) -> float:
    """シューレース (Gauss) の公式で多角形の面積を返す (px^2, 常に非負)。"""
    n = len(vertices)
    if n < 3:
        return 0.0
    total = 0.0
    for i in range(n):
        x1, y1 = vertices[i]
        x2, y2 = vertices[(i + 1) % n]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def polygon_perimeter(vertices: Sequence[Point]) -> float:
    """閉多角形の周長 (px)。"""
    n = len(vertices)
    if n < 2:
        return 0.0
    return sum(distance(vertices[i], vertices[(i + 1) % n]) for i in range(n))


def distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def project_segments_onto_edge(
    edge_start: Point,
    edge_end: Point,
    segments: Iterable[Tuple[int, Segment]],
    tolerance_px: float,
    max_angle_deg: float = DEFAULT_MAX_ANGLE_DEG,
) -> List[Interval]:
    """辺 (edge_start→edge_end) に「沿っている」線分を辺上の区間として射影する。

    座標系の構築と線分ごとの判定を分け、公開関数は採用区間の収集を担う。

    採用条件:
      1. 線分と辺のなす角が max_angle_deg 以内 (平行性)
      2. 線分の両端点が辺を含む直線から tolerance_px 以内 (近接性)
    これにより、辺に直交して突き当たる壁 (T字接合) や、tolerance 帯の中を斜めに横切る
    短い線分は除外され、辺と平行に重なる壁だけが採用される。辺の範囲外は切り落とす。
    ゼロ長の線分は無視する。
    """
    if not segments:
        return []
    axes = _edge_axes(edge_start, edge_end)
    if axes is None:
        return []
    max_sin = math.sin(math.radians(max_angle_deg))

    intervals: List[Interval] = []
    for seg_id, segment in segments:
        interval = _project_segment(
            axes, edge_start, seg_id, segment, tolerance_px, max_sin
        )
        if interval is not None:
            intervals.append(interval)
    return intervals


class _EdgeAxes(NamedTuple):
    length: float
    direction: Point
    normal: Point


def _edge_axes(edge_start: Point, edge_end: Point) -> Optional[_EdgeAxes]:
    """辺の座標系の構築を線分ごとの採否判定から分けるためにまとめる。"""
    start_x, start_y = edge_start
    end_x, end_y = edge_end
    length = distance(edge_start, edge_end)
    if length <= EPS_PX:
        return None
    direction_x, direction_y = (end_x - start_x) / length, (end_y - start_y) / length
    normal_x, normal_y = -direction_y, direction_x
    return _EdgeAxes(length, (direction_x, direction_y), (normal_x, normal_y))


def _project_segment(
    axes: _EdgeAxes,
    edge_start: Point,
    segment_id: int,
    segment: Segment,
    tolerance_px: float,
    max_sin: float,
) -> Optional[Interval]:
    """1 本の線分の採否と射影をまとめ、線分列の走査から切り離す。"""
    edge_length, direction, normal = axes
    start_x, start_y = edge_start
    direction_x, direction_y = direction
    normal_x, normal_y = normal
    segment_start, segment_end = segment
    delta_x, delta_y = segment_end[0] - segment_start[0], segment_end[1] - segment_start[1]
    segment_length = math.hypot(delta_x, delta_y)
    # 方向を定められないゼロ長の線分を弾く。
    if segment_length <= EPS_PX:
        return None
    # 採用条件 1: 辺との角度が許容値を超える線分を弾く。
    if abs(direction_x * delta_y - direction_y * delta_x) / segment_length > max_sin:
        return None
    start_normal_distance = abs(
        (segment_start[0] - start_x) * normal_x + (segment_start[1] - start_y) * normal_y
    )
    end_normal_distance = abs(
        (segment_end[0] - start_x) * normal_x + (segment_end[1] - start_y) * normal_y
    )
    # 採用条件 2: 片端でも辺の許容距離帯から外れる線分を弾く。
    if start_normal_distance > tolerance_px or end_normal_distance > tolerance_px:
        return None
    start_arclength = (
        (segment_start[0] - start_x) * direction_x + (segment_start[1] - start_y) * direction_y
    )
    end_arclength = (
        (segment_end[0] - start_x) * direction_x + (segment_end[1] - start_y) * direction_y
    )
    clipped_start, clipped_end = (
        max(0.0, min(start_arclength, end_arclength)),
        min(edge_length, max(start_arclength, end_arclength)),
    )
    if clipped_end - clipped_start > EPS_PX:
        return Interval(clipped_start, clipped_end, {segment_id})
    return None


def snap_to_edge_ends(intervals: List[Interval], edge_length: float, tolerance_px: float) -> List[Interval]:
    """辺の端に tolerance 以内で届いている区間を端まで延ばす (セグメンテーション誤差の吸収)。"""
    out: List[Interval] = []
    for iv in intervals:
        start = 0.0 if iv.start <= tolerance_px else iv.start
        end = edge_length if iv.end >= edge_length - tolerance_px else iv.end
        out.append(Interval(start, end, set(iv.ids)))
    return out


def drop_short(intervals: Iterable[Interval], min_length_px: float) -> List[Interval]:
    """ノイズ (例: 直交する壁の端がわずかに重なった部分) を除去する。"""
    return [iv for iv in intervals if iv.length >= min_length_px]


def complement_intervals(intervals: Iterable[Interval], edge_length: float, *, normalized=False) -> List[Interval]:
    """[0, edge_length] のうち intervals に含まれない部分 (= 壁のない開口区間)。

    intervals が [0, edge_length] の外にはみ出していても正しく動くよう、先にクリップする。
    normalized は射影・併合済みで範囲内かつ長さ > EPS の区間列だけに指定する。
    """
    if not math.isfinite(edge_length) or edge_length <= 0:
        return []
    covered = intervals if normalized else clip_intervals(intervals, [Interval(0.0, edge_length)])
    out: List[Interval] = []
    cursor = 0.0
    for iv in covered:
        if iv.start - cursor > EPS_PX:
            out.append(Interval(cursor, iv.start))
        cursor = max(cursor, iv.end)
    if edge_length - cursor > EPS_PX:
        out.append(Interval(cursor, edge_length))
    return out


def total_length(intervals: Iterable[Interval]) -> float:
    """区間長の合計。重なりのない (merge_intervals 済みの) 区間列を前提とする。"""
    return sum(iv.length for iv in intervals)


def point_at(edge_start: Point, edge_end: Point, t_px: float) -> Point:
    """辺の始点から t_px 進んだ点の座標。"""
    length = distance(edge_start, edge_end)
    if length <= EPS_PX:
        return edge_start
    r = t_px / length
    return (
        edge_start[0] + (edge_end[0] - edge_start[0]) * r,
        edge_start[1] + (edge_end[1] - edge_start[1]) * r,
    )
