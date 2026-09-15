"""純粋な幾何計算ユーティリティ。

外部ライブラリに依存せず、テストしやすいように副作用のない関数のみを置く。
座標系は画像ピクセル座標 (x: 右向き, y: 下向き)。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, List, Sequence, Set, Tuple

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


def project_segments_onto_edge(
    edge_start: Point,
    edge_end: Point,
    segments: Iterable[Tuple[int, Segment]],
    tolerance_px: float,
    max_angle_deg: float = DEFAULT_MAX_ANGLE_DEG,
) -> List[Interval]:
    """辺 (edge_start→edge_end) に「沿っている」線分を辺上の区間として射影する。

    採用条件:
      1. 線分と辺のなす角が max_angle_deg 以内 (平行性)
      2. 線分の両端点が辺を含む直線から tolerance_px 以内 (近接性)
    これにより、辺に直交して突き当たる壁 (T字接合) や、tolerance 帯の中を斜めに横切る
    短い線分は除外され、辺と平行に重なる壁だけが採用される。辺の範囲外は切り落とす。
    ゼロ長の線分は無視する。
    """
    ax, ay = edge_start
    bx, by = edge_end
    length = distance(edge_start, edge_end)
    if length <= EPS_PX:
        return []
    ux, uy = (bx - ax) / length, (by - ay) / length  # 辺方向の単位ベクトル
    nx, ny = -uy, ux  # 法線
    max_sin = math.sin(math.radians(max_angle_deg))

    intervals: List[Interval] = []
    for seg_id, (p, q) in segments:
        vx, vy = q[0] - p[0], q[1] - p[1]
        seg_len = math.hypot(vx, vy)
        if seg_len <= EPS_PX:
            continue
        if abs(ux * vy - uy * vx) / seg_len > max_sin:  # |sin θ| が閾値超 → 平行でない
            continue
        dp = abs((p[0] - ax) * nx + (p[1] - ay) * ny)
        dq = abs((q[0] - ax) * nx + (q[1] - ay) * ny)
        if dp > tolerance_px or dq > tolerance_px:
            continue
        tp = (p[0] - ax) * ux + (p[1] - ay) * uy
        tq = (q[0] - ax) * ux + (q[1] - ay) * uy
        lo, hi = max(0.0, min(tp, tq)), min(length, max(tp, tq))
        if hi - lo > EPS_PX:
            intervals.append(Interval(lo, hi, {seg_id}))
    return intervals


def merge_intervals(intervals: Iterable[Interval], gap_tolerance_px: float = 0.0) -> List[Interval]:
    """重なり・近接 (gap <= gap_tolerance_px) する区間を併合する。"""
    merged: List[Interval] = []
    for iv in sorted(intervals, key=lambda i: (i.start, i.end)):
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
    """a ∩ b (区間同士の共通部分)。ids は a 側を引き継ぐ。"""
    result: List[Interval] = []
    b_list = list(b)
    for ia in a:
        for ib in b_list:
            lo, hi = max(ia.start, ib.start), min(ia.end, ib.end)
            if hi - lo > EPS_PX:
                result.append(Interval(lo, hi, set(ia.ids)))
    return merge_intervals(result)


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


def _segments_intersect(p1: Point, p2: Point, q1: Point, q2: Point) -> bool:
    """線分 p1p2 と q1q2 が交差するか (端点接触は交差とみなさない)。"""

    def orient(a: Point, b: Point, c: Point) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    d1, d2 = orient(q1, q2, p1), orient(q1, q2, p2)
    d3, d4 = orient(p1, p2, q1), orient(p1, p2, q2)
    return (d1 * d2 < -EPS_PX) and (d3 * d4 < -EPS_PX)


def is_self_intersecting(vertices: Sequence[Point]) -> bool:
    """非隣接の辺同士が交差していれば True (蝶ネクタイ形など)。O(n²) だが頂点数は小さい。"""
    n = len(vertices)
    if n < 4:
        return False
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
