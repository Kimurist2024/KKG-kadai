"""Shapely による部屋・穴の妥当性検証と、重複領域の描画データ化。単位は px。"""
# Keep linearrings as the batch-construction hook used by existing callers/tests.
from shapely import linearrings, get_coordinates, get_rings, get_num_coordinates, get_type_id
from .schemas import PolygonRegion
from .strategies.room_polygons import batch as simple_room_polygons, room_polygon, _hole_rings


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
