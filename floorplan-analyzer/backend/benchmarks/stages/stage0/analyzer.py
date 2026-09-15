"""部屋ごとの床面積・周長・壁面積を算出するコアロジック。

計算要件 (課題 2-2):
  * 壁面積 = 辺の長さ × 天井高 (2.4 m)
  * ドア部分の面積は壁面積から控除する (ドア高さ 2.0 m)
  * 部屋によっては壁が存在しない輪郭区間がある
  * スケール: 96.7 px = 1.365 m

方針:
  1. 部屋の各辺について、壁線分 (label_id=2) を辺上に射影し「壁あり区間」を求める
  2. 壁あり区間の補集合が「開口 (壁なし) 区間」
  3. ドア線分 (label_id=3) も同様に射影し、壁あり区間との共通部分だけを控除対象にする
  4. 辺ごとの壁面積 = 壁あり長 × 天井高 − ドア長 × ドア高。部屋の壁面積はその合計
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from shapely.errors import GEOSException
from shapely.ops import unary_union

from . import geometry as g
from .topology import room_polygon, polygon_regions
from .schemas import (
    AnalysisSettings,
    AnalyzeResponse,
    Contour,
    EdgeResult,
    ImageInfo,
    IntervalOut,
    MaskFile,
    RoomResult,
    OverlapResult,
    SegmentOut,
    Summary,
    Vertex,
    Warning,
)

LABEL_WALL = 2
LABEL_DOOR = 3


def classify(
    contours: List[Contour], warnings: Optional[List[Warning]] = None
) -> Tuple[List[Contour], List[Contour], List[Contour]]:
    """輪郭を (部屋, 壁, ドア) に分類する。

    壁 = isLine かつ label_id=2、ドア = isLine かつ label_id=3。部屋は isLine が偽の多角形。
    未知のラベルを持つ線分は壁として計算せず、警告だけ出す。
    """
    rooms: List[Contour] = []
    walls: List[Contour] = []
    doors: List[Contour] = []
    for c in contours:
        if c.isLine:
            if c.label_id == LABEL_WALL:
                walls.append(c)
            elif c.label_id == LABEL_DOOR:
                doors.append(c)
            elif warnings is not None:
                warnings.append(Warning(code="ignored_contour", contour_id=c.id, message=f"線分 id={c.id}: 未知の label_id={c.label_id} のため無視しました"))
        else:
            rooms.append(c)
    return rooms, walls, doors


def _segment_of(c: Contour) -> Optional[g.Segment]:
    if len(c.vertices) < 2:
        return None
    p, q = c.vertices[0], c.vertices[-1]
    return ((p.x, p.y), (q.x, q.y))


def _interval_out(a: g.Point, b: g.Point, iv: g.Interval, mpp: float) -> IntervalOut:
    s = g.point_at(a, b, iv.start)
    e = g.point_at(a, b, iv.end)
    return IntervalOut(
        start_px=iv.start,
        end_px=iv.end,
        start=Vertex(x=s[0], y=s[1]),
        end=Vertex(x=e[0], y=e[1]),
        length_px=iv.length,
        length_m=iv.length * mpp,
        ids=sorted(iv.ids),
    )


def wall_intervals_on_edge(
    a: g.Point, b: g.Point, wall_segments: List[Tuple[int, g.Segment]], tolerance_px: float
) -> List[g.Interval]:
    """辺 a→b 上の「壁あり区間」。

    手順: 射影 → 重なりのみ併合 → 極短ノイズ除去 → 隙間併合 (tol 以下) → 端点スナップ → 再併合。
    ノイズ除去を隙間併合・スナップより先に行うことで、tol 未満の断片同士が併合や
    スナップで膨らんで生き残るのを防ぐ。スナップ・併合は [0, 辺長] を超えない。
    隙間併合と端点スナップは「セグメンテーションで分断・短縮された壁の補完」であり、
    許容誤差 tolerance_px より短い開口は検出しない仕様 (README 5-3, 5-5)。
    """
    length = g.distance(a, b)
    raw = g.project_segments_onto_edge(a, b, wall_segments, tolerance_px)
    walls = g.merge_intervals(raw)
    # ノイズ閾値は辺長の半分を上限にする: 輪郭の辺が tol より細かく分割されていても、
    # 辺の大半を覆う壁を「ノイズ」として捨てない (直交壁の角の 1〜2 px の重なりは引き続き除去)
    walls = g.drop_short(walls, min_length_px=min(tolerance_px, length / 2))
    walls = g.merge_intervals(walls, gap_tolerance_px=tolerance_px)
    walls = g.snap_to_edge_ends(walls, length, tolerance_px)
    return g.merge_intervals(walls, gap_tolerance_px=tolerance_px)


def door_intervals_on_edge(
    a: g.Point,
    b: g.Point,
    door_segments: List[Tuple[int, g.Segment]],
    walls: List[g.Interval],
    tolerance_px: float,
) -> List[g.Interval]:
    """辺 a→b 上のドア区間。壁あり区間との共通部分だけを返す (壁の無い所のドアは控除しない)。

    ドアごとに個別にクリップしてから併合する。先に併合すると、壁と重ならないドアの id が
    隣のドアの区間に紛れ込み、ドア数や警告が誤る。
    """
    raw = g.project_segments_onto_edge(a, b, door_segments, tolerance_px)
    clipped: List[g.Interval] = []
    for door in raw:
        clipped.extend(g.clip_intervals([door], walls))
    return g.merge_intervals([iv for iv in clipped if iv.length > g.EPS_PX])


def analyze_edge(
    index: int,
    a: g.Point,
    b: g.Point,
    wall_segments: List[Tuple[int, g.Segment]],
    door_segments: List[Tuple[int, g.Segment]],
    settings: AnalysisSettings,
) -> EdgeResult:
    mpp = settings.meters_per_px
    length_px = g.distance(a, b)

    walls = wall_intervals_on_edge(a, b, wall_segments, settings.tolerance_px)
    # Only an internal gap supported by walls on BOTH sides can be inferred.
    # Existing tolerance snapping has already filled small gaps; never count them twice.
    raw_doors = g.project_segments_onto_edge(a, b, door_segments, settings.tolerance_px)
    inferred = []
    for left, right in zip(walls, walls[1:]):
        for door in raw_doors:
            if (abs(door.start - left.end) <= settings.tolerance_px + g.EPS_PX
                    and abs(door.end - right.start) <= settings.tolerance_px + g.EPS_PX):
                inferred.append(g.Interval(left.end, right.start, set(door.ids)))
    inferred = g.merge_intervals(inferred)
    # Wall ids remain wall ids; inferred intervals separately retain supporting door ids.
    walls = g.merge_intervals(walls + [g.Interval(iv.start, iv.end) for iv in inferred])
    openings = g.complement_intervals(walls, length_px)
    doors = door_intervals_on_edge(a, b, door_segments, walls, settings.tolerance_px)

    wall_len_m = g.total_length(walls) * mpp
    opening_len_m = g.total_length(openings) * mpp  # 区間の内訳と必ず一致させる
    door_len_m = g.total_length(doors) * mpp
    gross = wall_len_m * settings.ceiling_height_m
    door_area = door_len_m * settings.door_height_m

    return EdgeResult(
        index=index,
        inferred_wall_intervals=[_interval_out(a, b, iv, mpp) for iv in inferred],
        start=Vertex(x=a[0], y=a[1]),
        end=Vertex(x=b[0], y=b[1]),
        length_px=length_px,
        length_m=length_px * mpp,
        wall_intervals=[_interval_out(a, b, iv, mpp) for iv in walls],
        opening_intervals=[_interval_out(a, b, iv, mpp) for iv in openings],
        door_intervals=[_interval_out(a, b, iv, mpp) for iv in doors],
        wall_length_m=wall_len_m,
        opening_length_m=opening_len_m,
        door_length_m=door_len_m,
        wall_area_gross_m2=gross,
        door_area_m2=door_area,
        wall_area_m2=gross - door_area,
    )


def analyze_room(
    room: Contour,
    wall_segments: List[Tuple[int, g.Segment]],
    door_segments: List[Tuple[int, g.Segment]],
    settings: AnalysisSettings,
    display_name: str,
    holes: Optional[List[List[Vertex]]] = None,
    label_point: Optional[Vertex] = None,
) -> RoomResult:
    mpp = settings.meters_per_px
    pts: List[g.Point] = [(v.x, v.y) for v in room.vertices]
    holes = holes or []
    rings = [pts] + [[(v.x, v.y) for v in hole] for hole in holes]
    area_px2 = g.polygon_area(pts) - sum(g.polygon_area(ring) for ring in rings[1:])
    perim_px = sum(g.polygon_perimeter(ring) for ring in rings)

    edges: List[EdgeResult] = []
    offset = 0
    for ring_index, ring in enumerate(rings):
        for i, a in enumerate(ring):
            b = ring[(i + 1) % len(ring)]
            if g.distance(a, b) <= g.EPS_PX:
                continue
            edge = analyze_edge(offset + i, a, b, wall_segments, door_segments, settings)
            edge.boundary_kind = "outer" if ring_index == 0 else "hole"
            edges.append(edge)
        offset += len(ring)

    wall_len = sum(e.wall_length_m for e in edges)
    opening_len = sum(e.opening_length_m for e in edges)
    door_len = sum(e.door_length_m for e in edges)
    gross = sum(e.wall_area_gross_m2 for e in edges)
    door_area = sum(e.door_area_m2 for e in edges)
    door_ids = {i for e in edges for iv in e.door_intervals for i in iv.ids}

    return RoomResult(
        id=room.id,
        name=display_name,
        room_name=room.room_name,
        color=room.color,
        vertices=list(room.vertices),
        holes=holes,
        label_point=label_point,
        floor_area_px2=area_px2,
        floor_area_m2=area_px2 * mpp * mpp,
        perimeter_px=perim_px,
        perimeter_m=perim_px * mpp,
        source_area_px2=room.area,
        source_perimeter_px=room.perimeter,
        wall_length_m=wall_len,
        opening_length_m=opening_len,
        door_length_m=door_len,
        door_count=len(door_ids),
        wall_area_gross_m2=gross,
        door_area_m2=door_area,
        wall_area_m2=gross - door_area,
        edges=edges,
    )


def _extract_segments(
    kind: str, contours: List[Contour], mpp: float, warnings: List[Warning]
) -> Tuple[List[Tuple[int, g.Segment]], List[SegmentOut]]:
    """線分輪郭 (壁/ドア) を幾何計算用の (id, 線分) と描画用の SegmentOut に変換する。"""
    segments: List[Tuple[int, g.Segment]] = []
    outs: List[SegmentOut] = []
    for c in contours:
        seg = _segment_of(c)
        if seg is None:
            warnings.append(Warning(code="ignored_contour", contour_id=c.id, message=f"{kind} id={c.id}: 頂点が 2 点未満のため無視しました"))
            continue
        if len(c.vertices) > 2:
            warnings.append(Warning(code="invalid_shape", contour_id=c.id, message=f"{kind} id={c.id}: 頂点が {len(c.vertices)} 点あるため、始点と終点を結ぶ線分として扱います"))
        length_px = g.distance(*seg)
        if length_px <= g.EPS_PX:
            warnings.append(Warning(code="ignored_contour", contour_id=c.id, message=f"{kind} id={c.id}: 長さ 0 のため無視しました"))
            continue
        segments.append((c.id, seg))
        outs.append(
            SegmentOut(
                id=c.id,
                kind=kind,
                start=Vertex(x=seg[0][0], y=seg[0][1]),
                end=Vertex(x=seg[1][0], y=seg[1][1]),
                length_px=length_px,
                length_m=length_px * mpp,
                color=c.color,
            )
        )
    return segments, outs


def analyze(mask: MaskFile, settings: Optional[AnalysisSettings] = None) -> AnalyzeResponse:
    settings = settings or AnalysisSettings()
    mpp = settings.meters_per_px
    warnings: List[Warning] = []
    if mask.ai_recognition is not None:
        warnings.append(Warning(code="ai_generated", message="AI が作成した輪郭に基づく参考値です。部屋・壁・ドアの認識漏れや位置ずれを元画像と照合してください。"))

    seen_ids: Dict[int, int] = {}
    for c in mask.contours:
        seen_ids[c.id] = seen_ids.get(c.id, 0) + 1
    for cid, n in seen_ids.items():
        if n > 1:
            warnings.append(Warning(code="duplicate_id", contour_id=cid, message=f"輪郭 id={cid} が {n} 回出現しています (id は一意である前提です)"))

    rooms, walls, doors = classify(mask.contours, warnings)

    wall_segments, walls_out = _extract_segments("wall", walls, mpp, warnings)
    door_segments, doors_out = _extract_segments("door", doors, mpp, warnings)

    room_results: List[RoomResult] = []
    polygons = []
    for room in rooms:
        if len(room.vertices) < 3:
            warnings.append(Warning(code="ignored_contour", contour_id=room.id, message=f"部屋 id={room.id}: 頂点が 3 点未満のため無視しました"))
            continue
        pts = [(v.x, v.y) for v in room.vertices]
        if g.polygon_area(pts) <= g.EPS_PX:
            warnings.append(Warning(code="ignored_contour", contour_id=room.id, message=f"部屋 id={room.id}: 面積が 0 (一直線または全点一致) のため無視しました"))
            continue
        if g.is_self_intersecting(pts):
            warnings.append(Warning(code="ignored_contour", contour_id=room.id, message=f"部屋 id={room.id}: 輪郭が自己交差しているため無視しました (面積を正しく定義できません)"))
            continue
        try:
            polygon, holes = room_polygon(room)
        except (ValueError, GEOSException) as exc:
            warnings.append(Warning(code="invalid_shape", contour_id=room.id, message=f"部屋 id={room.id}: {exc}。この部屋を集計から除外しました"))
            continue
        if room.room_name:
            display = room.room_name
        else:
            display = f"未命名 #{room.id}"
            warnings.append(Warning(code="unnamed_room", contour_id=room.id, message=f"部屋 id={room.id}: room_name がありません。'{display}' として扱います"))
        point = polygon.representative_point()
        result = analyze_room(room, wall_segments, door_segments, settings, display, holes,
                              Vertex(x=point.x, y=point.y))
        polygons.append(polygon)
        if any(e.inferred_wall_intervals for e in result.edges):
            warnings.append(Warning(code="inferred_door_wall", contour_id=room.id,
                message=f"部屋 '{display}': 両側の壁とドア線から扉開口の壁区間を補完し、扉上部を計上しました。位置と高さを確認してください。"))
        if result.source_area_px2 is not None and abs(result.source_area_px2 - result.floor_area_px2) > 1.0:
            warnings.append(Warning(
                code="data_mismatch",
                contour_id=room.id,
                message=(
                    f"部屋 '{display}': JSON 記載の面積 ({result.source_area_px2:.1f} px²) と"
                    f"頂点から再計算した面積 ({result.floor_area_px2:.1f} px²) が一致しません"
                ),
            ))
        room_results.append(result)

    # 数値は変更せず、未入力・対応失敗・低い対応率を区別して知らせる。
    # 開放空間の可能性があるため、20% 未満はエラーではなく確認用の目安。
    if room_results and not wall_segments:
        warnings.append(Warning(code="missing_wall_data", message="有効な壁線がありません。壁面積 0 は壁がないことを確認した値ではありません。壁データを追加するか、床面積のみの結果として利用してください。"))
    else:
        for r in room_results:
            wall_px = sum(iv.length_px for e in r.edges for iv in e.wall_intervals)
            coverage = wall_px / r.perimeter_px
            if wall_px <= g.EPS_PX:
                warnings.append(Warning(code="no_room_walls", contour_id=r.id, message=f"部屋 '{r.name}': 輪郭に対応する壁が見つかりません（対応率 0%）。壁線の位置・ラベル・許容誤差を確認してください。壁面積は要確認です。"))
            elif coverage < 0.2:
                warnings.append(Warning(code="low_wall_coverage", contour_id=r.id, message=f"部屋 '{r.name}': 輪郭のうち壁として検出された長さが {coverage:.1%} です（確認目安 20% 未満）。開放空間でなければ、壁データの欠落・位置ずれ・許容誤差を確認してください。"))

    # ドアがどの部屋の壁にも乗っていない場合は警告 (控除されない)
    used_door_ids = {i for r in room_results for e in r.edges for iv in e.door_intervals for i in iv.ids}
    for d in doors_out:
        if d.id not in used_door_ids:
            warnings.append(Warning(code="unmatched_door", contour_id=d.id, message=f"ドア id={d.id}: どの部屋の壁にも対応付けられませんでした (控除されていません)"))

    # 重複する部屋名にはサフィックスを付けて区別できるようにする
    name_counts: Dict[str, int] = {}
    for r in room_results:
        name_counts[r.name] = name_counts.get(r.name, 0) + 1
    seen: Dict[str, int] = {}
    for r in room_results:
        if name_counts[r.name] > 1:
            seen[r.name] = seen.get(r.name, 0) + 1
            r.name = f"{r.name} ({seen[r.name]})"

    overlaps = []
    for i, polygon in enumerate(polygons):
        for j in range(i + 1, len(polygons)):
            other = polygons[j]
            if not polygon.intersects(other):
                continue
            shared = polygon.intersection(other)
            if shared.area <= g.EPS_PX:
                continue
            overlaps.append(OverlapResult(room_ids=[room_results[i].id, room_results[j].id],
                area_m2=shared.area * mpp * mpp, regions=polygon_regions(shared)))
            for a, b in [(i, j), (j, i)]:
                warnings.append(Warning(code="room_overlap", contour_id=room_results[a].id,
                    message=f"部屋 '{room_results[a].name}' と '{room_results[b].name}' の床領域が {shared.area * mpp * mpp:.4f} m² 重複しています。部屋別面積は自動で削減していません。"))
    union_area = unary_union(polygons).area * mpp * mpp if polygons else 0.0
    total_area = sum(r.floor_area_m2 for r in room_results)

    return AnalyzeResponse(
        overlaps=overlaps,
        image=ImageInfo(
            width=mask.image_width,
            height=mask.image_height,
            mime_type=mask.image_data.mime_type if mask.image_data else None,
            has_image=bool(mask.image_data and mask.image_data.base64),
        ),
        timestamp=mask.timestamp,
        settings=settings,
        summary=Summary(
            room_count=len(room_results),
            wall_count=len(walls_out),
            door_count=len(doors_out),
            total_floor_area_m2=total_area,
            union_floor_area_m2=union_area,
            overlap_floor_area_m2=max(0.0, total_area-union_area) if overlaps else 0.0,
            total_wall_area_m2=sum(r.wall_area_m2 for r in room_results),
        ),
        rooms=room_results,
        walls=walls_out,
        doors=doors_out,
        warnings=warnings,
    )
