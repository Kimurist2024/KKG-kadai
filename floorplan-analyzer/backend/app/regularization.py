"""Evidence-preserving direction regularization and a shared room-boundary graph.

The feature is deliberately opt-in.  It only changes a plan when a dominant
orthogonal frame is unambiguous and every corrected polygon remains valid.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from shapely.geometry import LineString, Point as ShapelyPoint, Polygon
from shapely.ops import unary_union

from .schemas import (
    CanonicalEdge,
    CanonicalNode,
    Contour,
    GeometryProcessing,
    MaskFile,
    PlanarGraph,
    Vertex,
)
from .topology import room_polygon

Point = Tuple[float, float]
MAX_ANGLE_DEG = 7.0
MIN_CONCENTRATION = 0.80
MIN_INLIER_RATIO = 0.75
MIN_AXIS_WEIGHT_RATIO = 0.15
STRENGTH = 0.50
MAX_DISPLACEMENT_PX = 3.0
NODE_SNAP_PX = 3.0
MAX_AREA_CHANGE_RATIO = 0.005
ITERATIONS = 8


@dataclass
class _Ring:
    contour_index: int
    contour_id: int
    kind: str
    index: int
    raw: List[Point]
    points: List[Point]
    output_offset: int
    source_edges: List[int]


@dataclass(frozen=True)
class _Direction:
    angle: float
    concentration: float
    inlier_ratio: float
    axis_ratios: Tuple[float, float]
    accepted: bool
    reason: Optional[str]


def _angular_distance(a: float, b: float) -> float:
    """Smallest undirected angle between two line orientations."""
    diff = abs((a - b) % math.pi)
    return min(diff, math.pi - diff)


def _nearest_axis(angle: float, base: float) -> Tuple[float, int, float]:
    axes = (base, (base + math.pi / 2) % math.pi)
    choices = [(_angular_distance(angle, axis), index, axis) for index, axis in enumerate(axes)]
    distance, index, axis = min(choices)
    return axis, index, distance


def _rings(mask: MaskFile) -> List[_Ring]:
    rings: List[_Ring] = []
    for contour_index, contour in enumerate(mask.contours):
        if contour.isLine or len(contour.vertices) < 3:
            continue
        outer = [(float(p.x), float(p.y)) for p in contour.vertices]
        rings.append(_Ring(contour_index, contour.id, "outer", 0, outer, list(outer), 0,
                           list(range(len(outer)))))
        raw_holes = contour.holes if isinstance(contour.holes, list) else []
        hole_offset = len(outer)
        for hole_index, raw_hole in enumerate(raw_holes):
            if not isinstance(raw_hole, list) or len(raw_hole) < 3:
                continue
            try:
                hole = [Vertex.model_validate(p) for p in raw_hole]
            except Exception:
                continue
            points = [(float(p.x), float(p.y)) for p in hole]
            rings.append(_Ring(contour_index, contour.id, "hole", hole_index, points, list(points),
                               hole_offset, list(range(len(points)))))
            hole_offset += len(points)
    return rings


def _input_topology_valid(mask: MaskFile) -> bool:
    """補正前に部屋と穴の全入力を検査する。

    不正な穴を黙って除外すると、異なる図形を「補正済み」として返すため、
    一つでも解釈できない穴があれば全体を raw に戻す。
    """
    for contour in mask.contours:
        if contour.isLine:
            continue
        sequences = [contour.vertices]
        if isinstance(contour.holes, list):
            for raw_hole in contour.holes:
                if isinstance(raw_hole, list):
                    try:
                        sequences.append([Vertex.model_validate(point) for point in raw_hole])
                    except Exception:
                        return False
        # 連続重複点や、始点を末尾に再記した輪は、元辺IDと
        # 補正後の辺の対応が曖昧になるため raw に戻す。
        for sequence in sequences:
            points = [(float(point.x), float(point.y)) for point in sequence]
            if len(points) < 3 or any(
                points[index] == points[(index + 1) % len(points)] for index in range(len(points))
            ):
                return False
        try:
            room_polygon(contour)
        except Exception:
            return False
    return True


def _node_rings(rings: Sequence[_Ring]) -> None:
    """補正前の全境界を交点と部分重なり端点で分割する。"""
    source_lines = [
        LineString([start, ring.raw[(index + 1) % len(ring.raw)]])
        for ring in rings for index, start in enumerate(ring.raw)
        if start != ring.raw[(index + 1) % len(ring.raw)]
    ]
    if not source_lines:
        return
    merged = unary_union(source_lines)
    node_points: set[Point] = set()

    def collect(geometry) -> None:
        if geometry.is_empty:
            return
        if geometry.geom_type == "LineString":
            node_points.update((float(x), float(y)) for x, y in geometry.coords)
        elif hasattr(geometry, "geoms"):
            for part in geometry.geoms:
                collect(part)

    collect(merged)
    tolerance = 1e-7
    for ring in rings:
        noded: List[Point] = []
        noded_sources: List[int] = []
        original = list(ring.raw)
        original_sources = list(ring.source_edges)
        for index, start in enumerate(original):
            end = original[(index + 1) % len(original)]
            line = LineString([start, end])
            points = [point for point in node_points if line.distance(ShapelyPoint(point)) <= tolerance]
            points.sort(key=lambda point: line.project(ShapelyPoint(point)))
            for point in points[:-1]:
                if not noded or point != noded[-1]:
                    noded.append(point)
                    noded_sources.append(original_sources[index])
        if len(noded) >= 3:
            ring.raw = noded
            ring.points = list(noded)
            ring.source_edges = noded_sources


def _coalesce_preexisting_shared_nodes(rings: Sequence[_Ring]) -> None:
    """補正前から同一だった異なる部屋の接合点を同じ補正座標にする。"""
    groups: Dict[Point, List[Tuple[_Ring, int]]] = {}
    for ring in rings:
        for index, raw in enumerate(ring.raw):
            groups.setdefault(raw, []).append((ring, index))
    for refs in groups.values():
        if len({ring.contour_index for ring, _ in refs}) < 2:
            continue
        target = (
            math.fsum(ring.points[index][0] for ring, index in refs) / len(refs),
            math.fsum(ring.points[index][1] for ring, index in refs) / len(refs),
        )
        for ring, index in refs:
            ring.points[index] = target


def _noded_points_preserve_source_edges(rings: Sequence[_Ring]) -> bool:
    """共有接合点を拘束しても、元の1辺が折れ線にならないことを確認する。"""
    tolerance = 1e-7
    for ring in rings:
        original_count = max(ring.source_edges, default=-1) + 1
        if original_count < 1:
            continue
        starts = [ring.source_edges.index(index) for index in range(original_count)]
        for source_index, start_index in enumerate(starts):
            end_index = starts[(source_index + 1) % original_count]
            line = LineString([ring.points[start_index], ring.points[end_index]])
            for index, owner in enumerate(ring.source_edges):
                if owner == source_index and line.distance(ShapelyPoint(ring.points[index])) > tolerance:
                    return False
    return True


def estimate_direction(rings: Sequence[_Ring]) -> _Direction:
    observations: List[Tuple[float, float]] = []
    for ring in rings:
        for index, start in enumerate(ring.raw):
            end = ring.raw[(index + 1) % len(ring.raw)]
            dx, dy = end[0] - start[0], end[1] - start[1]
            length = math.hypot(dx, dy)
            if length >= 3.0:
                observations.append((math.atan2(dy, dx) % math.pi, min(length, 500.0)))
    if len(observations) < 4:
        return _Direction(0, 0, 0, (0, 0), False, "insufficient_edges")
    total = math.fsum(weight for _, weight in observations)
    cosine = math.fsum(weight * math.cos(4 * angle) for angle, weight in observations)
    sine = math.fsum(weight * math.sin(4 * angle) for angle, weight in observations)
    base = (math.atan2(sine, cosine) / 4) % (math.pi / 2)
    concentration = math.hypot(cosine, sine) / total
    inlier_weight = 0.0
    axis_weights = [0.0, 0.0]
    threshold = math.radians(MAX_ANGLE_DEG) + 1e-12
    for angle, weight in observations:
        _, axis_index, distance = _nearest_axis(angle, base)
        if distance <= threshold:
            inlier_weight += weight
            axis_weights[axis_index] += weight
    inlier_ratio = inlier_weight / total
    ratios = (axis_weights[0] / total, axis_weights[1] / total)
    reason = None
    if concentration < MIN_CONCENTRATION or inlier_ratio < MIN_INLIER_RATIO:
        reason = "non_manhattan"
    elif min(ratios) < MIN_AXIS_WEIGHT_RATIO:
        reason = "insufficient_two_axis_support"
    return _Direction(base, concentration, inlier_ratio, ratios, reason is None, reason)


def _regularize_ring(ring: _Ring, direction: _Direction) -> List[Point]:
    original = ring.raw
    current = list(original)
    targets: List[Optional[float]] = []
    threshold = math.radians(MAX_ANGLE_DEG) + 1e-12
    for index, start in enumerate(original):
        end = original[(index + 1) % len(original)]
        angle = math.atan2(end[1] - start[1], end[0] - start[0]) % math.pi
        axis, _, distance = _nearest_axis(angle, direction.angle)
        targets.append(axis if distance <= threshold else None)
    for _ in range(ITERATIONS):
        corrections = [[0.0, 0.0, 0] for _ in current]
        for index, axis in enumerate(targets):
            if axis is None:
                continue
            nxt = (index + 1) % len(current)
            start, end = current[index], current[nxt]
            normal = (-math.sin(axis), math.cos(axis))
            error = (end[0] - start[0]) * normal[0] + (end[1] - start[1]) * normal[1]
            cx, cy = error * normal[0] / 2, error * normal[1] / 2
            corrections[index][0] += cx
            corrections[index][1] += cy
            corrections[index][2] += 1
            corrections[nxt][0] -= cx
            corrections[nxt][1] -= cy
            corrections[nxt][2] += 1
        updated: List[Point] = []
        for index, point in enumerate(current):
            dx = corrections[index][0] / max(1, corrections[index][2]) * STRENGTH
            dy = corrections[index][1] / max(1, corrections[index][2]) * STRENGTH
            # The original observation remains an explicit data-fidelity anchor.
            dx += (original[index][0] - point[0]) * 0.20
            dy += (original[index][1] - point[1]) * 0.20
            candidate = (point[0] + dx, point[1] + dy)
            ox, oy = original[index]
            shift = math.hypot(candidate[0] - ox, candidate[1] - oy)
            if shift > MAX_DISPLACEMENT_PX:
                ratio = MAX_DISPLACEMENT_PX / shift
                candidate = (ox + (candidate[0] - ox) * ratio, oy + (candidate[1] - oy) * ratio)
            updated.append(candidate)
        current = updated
    return current


def _snap_shared_vertices(rings: Sequence[_Ring]) -> None:
    refs: List[Tuple[int, int]] = [
        (ring_index, vertex_index)
        for ring_index, ring in enumerate(rings)
        for vertex_index in range(len(ring.points))
    ]
    parent = list(range(len(refs)))
    members: Dict[int, List[int]] = {index: [index] for index in range(len(refs))}

    def find(value: int) -> int:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(left: int, right: int) -> None:
        a, b = find(left), find(right)
        if a == b:
            return
        combined = members[a] + members[b]
        points = [rings[refs[item][0]].points[refs[item][1]] for item in combined]
        if max(math.hypot(x[0] - y[0], x[1] - y[1]) for x in points for y in points) > NODE_SNAP_PX:
            return
        parent[b] = a
        members[a] = combined
        del members[b]

    for left, (left_ring, left_vertex) in enumerate(refs):
        lp = rings[left_ring].points[left_vertex]
        for right in range(left + 1, len(refs)):
            right_ring, right_vertex = refs[right]
            # Never collapse two distinct vertices belonging to the same room.
            if rings[left_ring].contour_index == rings[right_ring].contour_index:
                continue
            rp = rings[right_ring].points[right_vertex]
            if math.hypot(lp[0] - rp[0], lp[1] - rp[1]) <= NODE_SNAP_PX:
                union(left, right)
    for group in list(members.values()):
        if len(group) < 2:
            continue
        points = [rings[refs[item][0]].points[refs[item][1]] for item in group]
        target = (math.fsum(p[0] for p in points) / len(points), math.fsum(p[1] for p in points) / len(points))
        for item in group:
            ring_index, vertex_index = refs[item]
            rings[ring_index].points[vertex_index] = target


def _valid_changes(mask: MaskFile, rings: Sequence[_Ring]) -> Tuple[bool, float, Optional[str]]:
    by_contour: Dict[int, Dict[str, object]] = {}
    for ring in rings:
        record = by_contour.setdefault(ring.contour_index, {"outer": None, "holes": {}})
        if ring.kind == "outer":
            record["outer"] = ring
        else:
            record["holes"][ring.index] = ring  # type: ignore[index]
    max_ratio = 0.0
    for contour_index, record in by_contour.items():
        outer = record["outer"]
        if not isinstance(outer, _Ring):
            continue
        contour_rings = [outer, *record["holes"].values()]  # type: ignore[union-attr]
        if any(
            math.hypot(
                ring.points[(index + 1) % len(ring.points)][0] - point[0],
                ring.points[(index + 1) % len(ring.points)][1] - point[1],
            ) <= 1e-9
            for ring in contour_rings for index, point in enumerate(ring.points)
        ):
            return False, max_ratio, "degenerate_edge"
        holes_by_index = record["holes"]
        holes = [holes_by_index[index].points for index in sorted(holes_by_index)]  # type: ignore[index]
        raw_holes = [holes_by_index[index].raw for index in sorted(holes_by_index)]  # type: ignore[index]
        raw_polygon, polygon = Polygon(outer.raw, raw_holes), Polygon(outer.points, holes)
        corrected_outer = Polygon(outer.points)
        for hole in holes:
            corrected_hole = Polygon(hole)
            if (not corrected_hole.is_valid or corrected_hole.area <= 0
                    or not corrected_outer.contains(corrected_hole)
                    or not corrected_outer.boundary.disjoint(corrected_hole)):
                return False, max_ratio, "invalid_hole_topology"
        if not raw_polygon.is_valid or not polygon.is_valid or polygon.area <= 0:
            return False, max_ratio, "invalid_topology"
        ratio = abs(polygon.area - raw_polygon.area) / max(raw_polygon.area, 1e-12)
        max_ratio = max(max_ratio, ratio)
        if ratio > MAX_AREA_CHANGE_RATIO:
            return False, max_ratio, "area_change_limit"
    return True, max_ratio, None


def _build_graph(rings: Sequence[_Ring]) -> Tuple[PlanarGraph, Dict[Tuple[int, str, int], List[int]]]:
    """全境界線を一度 noding し、T字接合と部分重なりも原子辺に分割する。"""
    sources: List[Tuple[_Ring, int, LineString, Tuple[int, str, int]]] = []
    for ring in rings:
        for edge_index, start in enumerate(ring.points):
            end = ring.points[(edge_index + 1) % len(ring.points)]
            if math.hypot(end[0] - start[0], end[1] - start[1]) <= 1e-9:
                continue
            result_index = ring.output_offset + ring.source_edges[edge_index]
            sources.append((ring, edge_index, LineString([start, end]),
                            (ring.contour_index, ring.kind, result_index)))

    merged = unary_union([source[2] for source in sources]) if sources else None
    atomic: List[Tuple[Point, Point]] = []

    def collect(geometry) -> None:
        if geometry is None or geometry.is_empty:
            return
        if geometry.geom_type == "LineString":
            coords = list(geometry.coords)
            for start, end in zip(coords, coords[1:]):
                a, b = (float(start[0]), float(start[1])), (float(end[0]), float(end[1]))
                if a != b:
                    atomic.append((min(a, b), max(a, b)))
        elif hasattr(geometry, "geoms"):
            for part in geometry.geoms:
                collect(part)

    collect(merged)
    atomic = sorted(set(atomic))
    node_points = sorted({point for edge in atomic for point in edge})
    node_ids = {point: index + 1 for index, point in enumerate(node_points)}
    nodes = [CanonicalNode(id=node_ids[point], point=Vertex(x=point[0], y=point[1]), room_ids=[])
             for point in node_points]
    node_rooms: Dict[int, set] = {node.id: set() for node in nodes}
    node_shift: Dict[int, float] = {node.id: 0.0 for node in nodes}
    edge_lookup: Dict[Tuple[int, str, int], List[int]] = {}
    edges: List[CanonicalEdge] = []
    tolerance = 1e-7
    for edge_id, (start, end) in enumerate(atomic, 1):
        atom = LineString([start, end])
        owners = []
        for ring, source_index, source_line, ref in sources:
            if (source_line.distance(atom) <= tolerance
                    and source_line.distance(atom.boundary.geoms[0]) <= tolerance
                    and source_line.distance(atom.boundary.geoms[-1]) <= tolerance):
                owners.append((ring, source_index, ref))
                edge_lookup.setdefault(ref, []).append(edge_id)
        room_ids = sorted({owner[0].contour_id for owner in owners})
        kinds = sorted({owner[0].kind for owner in owners})
        start_id, end_id = node_ids[start], node_ids[end]
        for node_id in (start_id, end_id):
            node_rooms[node_id].update(room_ids)
        for ring, source_index, _ in owners:
            for point, raw in ((ring.points[source_index], ring.raw[source_index]),
                               (ring.points[(source_index + 1) % len(ring.points)],
                                ring.raw[(source_index + 1) % len(ring.raw)])):
                if point == start:
                    node_shift[start_id] = max(node_shift[start_id], math.hypot(point[0] - raw[0], point[1] - raw[1]))
                if point == end:
                    node_shift[end_id] = max(node_shift[end_id], math.hypot(point[0] - raw[0], point[1] - raw[1]))
        edges.append(CanonicalEdge(id=edge_id, start_node_id=start_id, end_node_id=end_id,
            start=Vertex(x=start[0], y=start[1]), end=Vertex(x=end[0], y=end[1]),
            room_ids=room_ids, boundary_kinds=kinds, length_px=atom.length))
    for node in nodes:
        node.room_ids = sorted(node_rooms[node.id])
        node.max_displacement_px = node_shift[node.id]
    non_manifold = 0
    for edge in edges:
        if len(edge.room_ids) > 2:
            non_manifold += 1
    return PlanarGraph(nodes=nodes, edges=edges,
        shared_edge_count=sum(len(edge.room_ids) == 2 for edge in edges),
        non_manifold_edge_count=non_manifold), edge_lookup


def regularize_mask(mask: MaskFile, boundary_reference: str):
    """Return a corrected copy, diagnostics and room-edge to canonical-edge IDs."""
    rings = _rings(mask)
    if not _input_topology_valid(mask):
        graph, lookup = _build_graph(rings)
        processing = GeometryProcessing(requested_mode="regularized_shared", applied_mode="raw_fallback",
            boundary_reference=boundary_reference, reject_reason="invalid_input_topology", graph=graph)
        return mask, processing, lookup
    if boundary_reference == "centerline":
        # 部分共有辺の中間端点も、独立した部屋補正の前に明示化する。
        _node_rings(rings)
    direction = estimate_direction(rings)
    requested = "regularized_shared"
    if not direction.accepted:
        # 返すのは元輪郭なので、noding 後の辺番号を混ぜない。
        graph, lookup = _build_graph(_rings(mask))
        processing = GeometryProcessing(requested_mode=requested, applied_mode="raw_fallback",
            boundary_reference=boundary_reference, dominant_angle_deg=math.degrees(direction.angle),
            orientation_concentration=direction.concentration,
            orientation_inlier_ratio=direction.inlier_ratio, reject_reason=direction.reason, graph=graph)
        return mask, processing, lookup

    for ring in rings:
        ring.points = _regularize_ring(ring, direction)
    # 異なる部屋の輪郭が同じ壁の中心線を表すと明示された場合だけ、
    # 近接する端点を共有ノードにする。基準不明では証拠のない吸着を行わない。
    if boundary_reference == "centerline":
        _coalesce_preexisting_shared_nodes(rings)
        _snap_shared_vertices(rings)
        if not _noded_points_preserve_source_edges(rings):
            raw_rings = _rings(mask)
            graph, lookup = _build_graph(raw_rings)
            processing = GeometryProcessing(requested_mode=requested, applied_mode="raw_fallback",
                boundary_reference=boundary_reference, dominant_angle_deg=math.degrees(direction.angle),
                orientation_concentration=direction.concentration,
                orientation_inlier_ratio=direction.inlier_ratio,
                reject_reason="shared_constraint_conflict", graph=graph)
            return mask, processing, lookup
    valid, area_ratio, reason = _valid_changes(mask, rings)
    if not valid:
        raw_rings = _rings(mask)
        graph, lookup = _build_graph(raw_rings)
        processing = GeometryProcessing(requested_mode=requested, applied_mode="raw_fallback",
            boundary_reference=boundary_reference, dominant_angle_deg=math.degrees(direction.angle),
            orientation_concentration=direction.concentration, orientation_inlier_ratio=direction.inlier_ratio,
            max_area_change_ratio=area_ratio, reject_reason=reason, graph=graph)
        return mask, processing, lookup

    corrected = mask.model_copy(deep=True)
    for ring in rings:
        contour: Contour = corrected.contours[ring.contour_index]
        # noding 点は正準グラフにだけ残し、壁・ドア区間を計算する
        # 部屋輪郭は元の連続辺構成を保つ。
        original_count = max(ring.source_edges, default=-1) + 1
        output_points = [ring.points[ring.source_edges.index(index)] for index in range(original_count)]
        vertices = [Vertex(x=x, y=y) for x, y in output_points]
        if ring.kind == "outer":
            contour.vertices = vertices
        else:
            holes = list(contour.holes or [])
            holes[ring.index] = [vertex.model_dump() for vertex in vertices]
            contour.holes = holes
    graph, lookup = _build_graph(rings)
    moved = [math.hypot(point[0] - raw[0], point[1] - raw[1])
             for ring in rings for point, raw in zip(ring.points, ring.raw)]
    processing = GeometryProcessing(requested_mode=requested,
        applied_mode="regularized_shared" if any(value > 1e-9 for value in moved) else "unchanged",
        boundary_reference=boundary_reference, dominant_angle_deg=math.degrees(direction.angle),
        orientation_concentration=direction.concentration, orientation_inlier_ratio=direction.inlier_ratio,
        moved_vertex_count=sum(value > 1e-9 for value in moved), max_displacement_px=max(moved, default=0),
        max_area_change_ratio=area_ratio, graph=graph)
    return corrected, processing, lookup
