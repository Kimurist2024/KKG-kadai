"""純粋な幾何計算ユーティリティ。

外部ライブラリに依存せず、テストしやすいように副作用のない関数のみを置く。
座標系は画像ピクセル座標 (x: 右向き, y: 下向き)。
"""
from __future__ import annotations

import math
import heapq
from dataclasses import dataclass, field
from typing import Iterable, List, NamedTuple, Optional, Sequence, Set, Tuple

Point = Tuple[float, float]
Segment = Tuple[Point, Point]

EPS_PX = 1e-9  # 浮動小数点の丸め誤差用。セグメンテーションの許容誤差 (tolerance_px) とは別物
DEFAULT_MAX_ANGLE_DEG = 10.0  # 辺と線分のなす角がこれ以下なら「平行」とみなす


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


@dataclass
class Interval:
    """辺上の 1 次元区間。start/end は辺の始点からの距離 (px)。"""

    start: float
    end: float
    ids: Set[int] = field(default_factory=set)

    @property
    def length(self) -> float:
        return max(0.0, self.end - self.start)


def _interval_sort_key(interval: Interval) -> Tuple[float, float]:
    """区間の安定ソート順を返す。"""
    return interval.start, interval.end


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


def merge_intervals(intervals: Iterable[Interval], gap_tolerance_px: float = 0.0) -> List[Interval]:
    """重なり・近接 (gap <= gap_tolerance_px) する区間を併合する。"""
    merged: List[Interval] = []
    for iv in sorted(intervals, key=_interval_sort_key):
        if merged and iv.start <= merged[-1].end + gap_tolerance_px:
            last = merged[-1]
            last.end = max(last.end, iv.end)
            last.ids |= iv.ids
        else:
            merged.append(Interval(iv.start, iv.end, set(iv.ids)))
    return merged


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


def clip_intervals(a: Iterable[Interval], b: Iterable[Interval]) -> List[Interval]:
    """a ∩ b。b が非重複なら開始位置の走査で不要な比較を省く。

    非重複判定と二つの交差処理を分け、公開関数で方式の選択と併合を行う。
    a は重複していてもよく、交差前に併合しない（ids の混入を防止）。
    b の重複時は端点イベントで候補を列挙し、EPS 以下の断片を除く順序も維持する。
    非重複 b の走査はソート後 O(len(a) + len(b) + 候補交差数)。
    """
    b_list = sorted(b, key=_interval_sort_key)
    if _intervals_are_disjoint(b_list):
        result = _clip_disjoint_intervals(a, b_list)
    else:
        result = _clip_overlapping_intervals(a, b_list)
    return merge_intervals(result)


def _intervals_are_disjoint(intervals: Sequence[Interval]) -> bool:
    """走査方式の選択理由を明示するため、ソート済み区間の非重複判定を分ける。"""
    return all(left.end <= right.start for left, right in zip(intervals, intervals[1:]))


def _clip_disjoint_intervals(a: Iterable[Interval], b_list: Sequence[Interval]) -> List[Interval]:
    """非重複時だけ使えるカーソル走査を総当たりの処理から分ける。"""
    result: List[Interval] = []
    cursor = 0
    for ia in sorted(a, key=_interval_sort_key):
        while cursor < len(b_list) and b_list[cursor].end <= ia.start:
            cursor += 1
        for index in range(cursor, len(b_list)):
            ib = b_list[index]
            if ib.start >= ia.end:
                break
            lo, hi = max(ia.start, ib.start), min(ia.end, ib.end)
            if hi - lo > EPS_PX:
                result.append(Interval(lo, hi, set(ia.ids)))
    return result


def _clip_overlapping_intervals(a: Iterable[Interval], b_list: Sequence[Interval]) -> List[Interval]:
    """端点イベントを走査して交差候補を列挙する。座標の量子化はしない。"""
    a_list = sorted(a, key=_interval_sort_key)
    if len(a_list) * len(b_list) < 4096 or any(
        not math.isfinite(iv.start) or not math.isfinite(iv.end) or iv.start >= iv.end
        for iv in (*a_list, *b_list)
    ):
        return _clip_all_pairs(a_list, b_list)
    # いもす法と同じ開始/終了イベントを使うが、根拠IDとEPS判定を
    # 維持するため被覆数だけに集約せず、交差する元区間を記録する。
    events = []
    for side, intervals in enumerate((a_list, b_list)):
        for index, iv in enumerate(intervals):
            events.append((iv.start, 1, side, index))
            events.append((iv.end, 0, side, index))
    active = (set(), set())
    candidates = [[] for _ in a_list]
    for _, entering, side, index in sorted(events):
        if not entering:
            active[side].discard(index)
            continue
        for other in active[1 - side]:
            i, j = (index, other) if side == 0 else (other, index)
            candidates[i].append(j)
        active[side].add(index)
    result = []
    # 従来の a,b 順序で演算し、同値端点（負のゼロ含む）の選択も維持。
    for ia, indices in zip(a_list, candidates):
        for j in sorted(indices):
            ib = b_list[j]
            lo, hi = max(ia.start, ib.start), min(ia.end, ib.end)
            if hi - lo > EPS_PX:
                result.append(Interval(lo, hi, set(ia.ids)))
    return result


def _clip_all_pairs(a_list, b_list):
    """小規模・特殊入力の従来経路。"""
    result: List[Interval] = []
    for ia in a_list:
        for ib in b_list:
            lo, hi = max(ia.start, ib.start), min(ia.end, ib.end)
            if hi - lo > EPS_PX:
                result.append(Interval(lo, hi, set(ia.ids)))
    return result


def complement_intervals(intervals: Iterable[Interval], edge_length: float) -> List[Interval]:
    """[0, edge_length] のうち intervals に含まれない部分 (= 壁のない開口区間)。

    intervals が [0, edge_length] の外にはみ出していても正しく動くよう、先にクリップする。
    """
    if not math.isfinite(edge_length) or edge_length <= 0:
        return []
    covered = clip_intervals(intervals, [Interval(0.0, edge_length)])
    out: List[Interval] = []
    cursor = 0.0
    for iv in covered:
        if iv.start - cursor > EPS_PX:
            out.append(Interval(cursor, iv.start))
        cursor = max(cursor, iv.end)
    if edge_length - cursor > EPS_PX:
        out.append(Interval(cursor, edge_length))
    return out


def _orientation(a: Point, b: Point, c: Point) -> float:
    """a→b に対するcの有向面積（外積）。"""
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_intersect(p1: Point, p2: Point, q1: Point, q2: Point) -> bool:
    """線分 p1p2 と q1q2 が交差するか (端点接触は交差とみなさない)。"""

    d1, d2 = _orientation(q1, q2, p1), _orientation(q1, q2, p2)
    d3, d4 = _orientation(p1, p2, q1), _orientation(p1, p2, q2)
    return (d1 * d2 < -EPS_PX) and (d3 * d4 < -EPS_PX)


def is_self_intersecting(vertices: Sequence[Point]) -> bool:
    """大きな輪郭は境界イベントで候補を絞り、従来の交差式で判定する。"""
    n = len(vertices)
    if n < 4:
        return False
    if n >= 64:
        magnitude = max(abs(v) for point in vertices for v in point)
        if math.isfinite(magnitude) and magnitude < 1e100:
            return _self_intersection_sweep(vertices, EPS_PX + 16 * math.ulp(magnitude))
    return _self_intersection_all_pairs(vertices)


def _self_intersection_sweep(vertices, pad):
    n = len(vertices)
    boxes = []
    for i, a in enumerate(vertices):
        b = vertices[(i + 1) % n]
        boxes.append((min(a[0], b[0]) - pad, max(a[0], b[0]) + pad,
                      min(a[1], b[1]) - pad, max(a[1], b[1]) + pad, i))
    active = {}
    ends = []
    for left, right, bottom, top, i in sorted(boxes):
        while ends and ends[0][0] < left:
            _, expired = heapq.heappop(ends)
            active.pop(expired)
        for j, (low, high) in active.items():
            first, second = min(i, j), max(i, j)
            if second == first + 1 or (first == 0 and second == n - 1):
                continue
            if high < bottom or top < low:
                continue
            if _segments_intersect(vertices[first], vertices[(first + 1) % n],
                                   vertices[second], vertices[(second + 1) % n]):
                return True
        active[i] = (bottom, top)
        heapq.heappush(ends, (right, i))
    return False


def _self_intersection_all_pairs(vertices):
    n = len(vertices)
    for i in range(n):
        p1, p2 = vertices[i], vertices[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue  # 最初と最後の辺は隣接
            q1, q2 = vertices[j], vertices[(j + 1) % n]
            if _segments_intersect(p1, p2, q1, q2):
                return True
    return False


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
