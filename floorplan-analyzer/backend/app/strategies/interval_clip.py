"""Interval intersection strategies: (a, b) -> merged Interval list."""
from __future__ import annotations
import math
from typing import Iterable, List, Sequence
from ..geometry_primitives import EPS_PX, Interval, _interval_sort_key, merge_intervals
from . import register

@register("interval_clip", "auto")
def auto(a: Iterable[Interval], b: Iterable[Interval]) -> List[Interval]:
    """a ∩ b。b が非重複なら開始位置の走査で不要な比較を省く。

    非重複判定と二つの交差処理を分け、公開関数で方式の選択と併合を行う。
    a は重複していてもよく、交差前に併合しない（ids の混入を防止）。
    b の重複時は端点イベントで候補を列挙し、EPS 以下の断片を除く順序も維持する。
    非重複 b の走査はソート後 O(len(a) + len(b) + 候補交差数)。
    """
    # 解析では空または単一区間が多い。単一区間でも従来の比較・max/min 順を守る。
    if isinstance(a, list) and isinstance(b, list):
        if not a or not b:
            return []
        if len(a) == len(b) == 1:
            ia, ib = a[0], b[0]
            if ib.end <= ia.start or ib.start >= ia.end:
                return []
            lo, hi = max(ia.start, ib.start), min(ia.end, ib.end)
            return [Interval(lo, hi, set(ia.ids))] if hi - lo > EPS_PX else []
    b_list = sorted(b, key=_interval_sort_key)
    if not b_list:
        return []
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
    return _clip_event_sweep(a_list, b_list)


def _clip_event_sweep(a_list, b_list):
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


@register("interval_clip", "all_pairs")
def all_pairs(a, b):
    """Same stable operand order, EPS filtering and final merge as auto."""
    return merge_intervals(_clip_all_pairs(sorted(a, key=_interval_sort_key),
                                           sorted(b, key=_interval_sort_key)))


@register("interval_clip", "sweep")
def sweep(a, b):
    """Force endpoint events; retain the exact fallback for degenerate inputs."""
    a_list, b_list = sorted(a, key=_interval_sort_key), sorted(b, key=_interval_sort_key)
    if any(not math.isfinite(iv.start) or not math.isfinite(iv.end) or iv.start >= iv.end
           for iv in (*a_list, *b_list)):
        return merge_intervals(_clip_all_pairs(a_list, b_list))
    return merge_intervals(_clip_event_sweep(a_list, b_list))
