"""Evidence-preserving direction regularization and a shared room-boundary graph.

The feature is deliberately opt-in.  It only changes a plan when a dominant
orthogonal frame is unambiguous and every corrected polygon remains valid.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from shapely.geometry import Polygon

from .schemas import (
    CanonicalEdge,
    CanonicalNode,
    Contour,
    GeometryProcessing,
    MaskFile,
    PlanarGraph,
    Vertex,
)

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
        rings.append(_Ring(contour_index, contour.id, "outer", 0, outer, list(outer)))
        raw_holes = contour.holes if isinstance(contour.holes, list) else []
        for hole_index, raw_hole in enumerate(raw_holes):
            if not isinstance(raw_hole, list) or len(raw_hole) < 3:
                continue
            try:
                hole = [Vertex.model_validate(p) for p in raw_hole]
            except Exception:
                continue
            points = [(float(p.x), float(p.y)) for p in hole]
            rings.append(_Ring(contour_index, contour.id, "hole", hole_index, points, list(points)))
    return rings


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
        holes_by_index = record["holes"]
        holes = [holes_by_index[index].points for index in sorted(holes_by_index)]  # type: ignore[index]
        raw_holes = [holes_by_index[index].raw for index in sorted(holes_by_index)]  # type: ignore[index]
        raw_polygon, polygon = Polygon(outer.raw, raw_holes), Polygon(outer.points, holes)
        if not raw_polygon.is_valid or not polygon.is_valid or polygon.area <= 0:
            return False, max_ratio, "invalid_topology"
        ratio = abs(polygon.area - raw_polygon.area) / max(raw_polygon.area, 1e-12)
        max_ratio = max(max_ratio, ratio)
        if ratio > MAX_AREA_CHANGE_RATIO:
            return False, max_ratio, "area_change_limit"
    return True, max_ratio, None


def _build_graph(rings: Sequence[_Ring]) -> Tuple[PlanarGraph, Dict[Tuple[int, str, int], int]]:
    nodes: List[CanonicalNode] = []
    node_by_point: Dict[Point, int] = {}
    node_rooms: Dict[int, set] = {}
    max_shift: Dict[int, float] = {}
    vertex_nodes: Dict[Tuple[int, str, int, int], int] = {}
    for ring in rings:
        for vertex_index, point in enumerate(ring.points):
            node_id = node_by_point.get(point)
            if node_id is None:
                node_id = len(nodes) + 1
                node_by_point[point] = node_id
                nodes.append(CanonicalNode(id=node_id, point=Vertex(x=point[0], y=point[1]), room_ids=[]))
                node_rooms[node_id] = set()
                max_shift[node_id] = 0.0
            node_rooms[node_id].add(ring.contour_id)
            raw = ring.raw[vertex_index]
            max_shift[node_id] = max(max_shift[node_id], math.hypot(point[0] - raw[0], point[1] - raw[1]))
            vertex_nodes[(ring.contour_index, ring.kind, ring.index, vertex_index)] = node_id
    for node in nodes:
        node.room_ids = sorted(node_rooms[node.id])
        node.max_displacement_px = max_shift[node.id]

    edges: List[CanonicalEdge] = []
    edge_by_nodes: Dict[Tuple[int, int], int] = {}
    edge_rooms: Dict[int, set] = {}
    edge_kinds: Dict[int, set] = {}
    edge_lookup: Dict[Tuple[int, str, int], int] = {}
    ring_offsets: Dict[Tuple[int, str, int], int] = {}
    for contour_index in sorted({ring.contour_index for ring in rings}):
        contour_rings = [ring for ring in rings if ring.contour_index == contour_index]
        outer_length = next((len(ring.points) for ring in contour_rings if ring.kind == "outer"), 0)
        for ring in contour_rings:
            ring_offsets[(ring.contour_index, ring.kind, ring.index)] = (
                0 if ring.kind == "outer" else outer_length + sum(
                    len(other.points) for other in contour_rings
                    if other.kind == "hole" and other.index < ring.index
                )
            )
    for ring in rings:
        for edge_index in range(len(ring.points)):
            start_id = vertex_nodes[(ring.contour_index, ring.kind, ring.index, edge_index)]
            end_id = vertex_nodes[(ring.contour_index, ring.kind, ring.index, (edge_index + 1) % len(ring.points))]
            if start_id == end_id:
                continue
            key = (min(start_id, end_id), max(start_id, end_id))
            edge_id = edge_by_nodes.get(key)
            if edge_id is None:
                edge_id = len(edges) + 1
                edge_by_nodes[key] = edge_id
                start, end = nodes[start_id - 1].point, nodes[end_id - 1].point
                edges.append(CanonicalEdge(id=edge_id, start_node_id=start_id, end_node_id=end_id,
                    start=start, end=end, room_ids=[], boundary_kinds=[],
                    length_px=math.hypot(end.x - start.x, end.y - start.y)))
                edge_rooms[edge_id] = set()
                edge_kinds[edge_id] = set()
            edge_rooms[edge_id].add(ring.contour_id)
            edge_kinds[edge_id].add(ring.kind)
            result_edge_index = ring_offsets[(ring.contour_index, ring.kind, ring.index)] + edge_index
            edge_lookup[(ring.contour_id, ring.kind, result_edge_index)] = edge_id
    non_manifold = 0
    for edge in edges:
        edge.room_ids = sorted(edge_rooms[edge.id])
        edge.boundary_kinds = sorted(edge_kinds[edge.id])
        if len(edge.room_ids) > 2:
            non_manifold += 1
    return PlanarGraph(nodes=nodes, edges=edges,
        shared_edge_count=sum(len(edge.room_ids) == 2 for edge in edges),
        non_manifold_edge_count=non_manifold), edge_lookup


def regularize_mask(mask: MaskFile, boundary_reference: str):
    """Return a corrected copy, diagnostics and room-edge to canonical-edge IDs."""
    rings = _rings(mask)
    direction = estimate_direction(rings)
    requested = "regularized_shared"
    if not direction.accepted:
        graph, lookup = _build_graph(rings)
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
        _snap_shared_vertices(rings)
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
        vertices = [Vertex(x=x, y=y) for x, y in ring.points]
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
