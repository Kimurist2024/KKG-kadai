"""Shapely による部屋・穴の妥当性検証と、重複領域の描画データ化。単位は px。"""
from shapely.geometry import Polygon
from shapely.validation import explain_validity
from shapely import (linearrings, polygons, is_valid, area, point_on_surface,
                     get_coordinates, get_rings, get_num_coordinates, get_type_id)
from shapely.errors import GEOSException
from .schemas import Vertex, PolygonRegion


def simple_room_polygons(rooms):
    """穴のない有効な外周だけを一括処理する。未確定の部屋は従来経路へ戻す。

    警告や除外の判断は呼出元の元の順序で行う。ここでは座標を補正しない。
    """
    candidates = [room for room in rooms if len(room.vertices) >= 3
                  and (room.holes is None or isinstance(room.holes, list) and not room.holes)]
    # 1 部屋では配列の準備を償却できないので、従来の検証入口を使う。
    if len(candidates) < 2:
        return {}
    coords, indices = [], []
    for i, room in enumerate(candidates):
        coords.extend((v.x, v.y) for v in room.vertices)
        indices.extend([i] * len(room.vertices))
    try:
        shapes = polygons(linearrings(coords, indices=indices))
        valid = is_valid(shapes) & (area(shapes) > 0)
        selected = shapes[valid]
        points = get_coordinates(point_on_surface(selected)).tolist()
    except (ValueError, GEOSException):
        # 例外文言も従来の room_polygon が部屋ごとに確定する。
        return {}
    return {id(room): (shape, point) for room, shape, point in zip(
        (room for room, ok in zip(candidates, valid) if ok), selected, points)}


def room_polygon(room):
    """外周・穴を検証する。不正形状は自動修正せず、呼出元で除外・警告できるよう例外にする。

    入力パースを分け、ここでは外周・穴の幾何的な妥当性を順に検証する。
    """
    holes = _hole_rings(room)
    shell = [(v.x, v.y) for v in room.vertices]
    outer = Polygon(shell)
    if not outer.is_valid or outer.area <= 0:
        raise ValueError("外周が不正です: " + explain_validity(outer))
    if not holes:
        return outer, []
    for hole in holes:
        hole_polygon = Polygon(hole)
        if not hole_polygon.is_valid or hole_polygon.area <= 0:
            raise ValueError('穴の輪郭が不正です')
        if not outer.contains(hole_polygon) or not outer.boundary.disjoint(hole_polygon):
            raise ValueError('穴は外周に接せず、完全に部屋の内部にある必要があります')
    room_shape = Polygon(shell, holes)
    if not room_shape.is_valid:
        raise ValueError('外周・穴の交差や重複があります: ' + explain_validity(room_shape))
    return room_shape, [[Vertex(x=x, y=y) for x, y in ring] for ring in holes]


def _hole_rings(room):
    """穴の入力形式と頂点のパースを幾何的な妥当性検証から分ける。"""
    raw_holes = room.holes if room.holes is not None else []
    if not isinstance(raw_holes, list):
        raise ValueError('holes は頂点配列の配列で指定してください')
    holes = []
    for raw in raw_holes:
        if not isinstance(raw, list) or len(raw) < 3:
            raise ValueError('穴の輪郭には 3 頂点以上が必要です')
        ring = [Vertex.model_validate(v) for v in raw]
        holes.append([(v.x, v.y) for v in ring])
    return holes


def _ring_vertices(ring):
    # Shapely は末尾に始点を重ねる。API の頂点配列にはその閉じ点を含めない。
    # PolygonRegion がまとめて Vertex に検証・変換する。
    return [dict(x=x, y=y) for x, y in list(ring.coords)[:-1]]


def polygon_regions(geometry):
    """交差結果から面だけを取り出す。線・点の接触は描画領域に含めない。"""
    if geometry.geom_type == 'Polygon':
        return [PolygonRegion(
            vertices=_ring_vertices(geometry.exterior),
            holes=[_ring_vertices(ring) for ring in geometry.interiors],
        )]
    return [
        region
        for part in getattr(geometry, 'geoms', [])
        for region in polygon_regions(part)
    ]


def polygon_regions_many(geometries):
    """Polygon の輪と座標をまとめて取得する。複合形状は従来の再帰順を保つ。"""
    if not len(geometries):
        return []
    if not all(get_type_id(geometries) == 3):
        return [polygon_regions(geometry) for geometry in geometries]
    rings, owners = get_rings(geometries, return_index=True)
    coordinates = get_coordinates(rings).tolist()
    counts = get_num_coordinates(rings).tolist()
    grouped = [[] for _ in geometries]
    offset = 0
    for owner, count in zip(owners, counts):
        ring_coords = coordinates[offset:offset + count - 1] if count else []
        grouped[owner].append([dict(x=x, y=y) for x, y in ring_coords])
        offset += count
    return [[PolygonRegion(vertices=rings[0], holes=rings[1:])] if rings
            else [PolygonRegion(vertices=[], holes=[])] for rings in grouped]
