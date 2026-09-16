"""Shapely による部屋・穴の妥当性検証と、重複領域の描画データ化。単位は px。"""
from shapely.geometry import Polygon
from shapely.validation import explain_validity
from .schemas import Vertex, PolygonRegion


def room_polygon(room):
    """外周・穴を検証する。不正形状は自動修正せず、呼出元で除外・警告できるよう例外にする。

    入力パースを分け、ここでは外周・穴の幾何的な妥当性を順に検証する。
    """
    holes = _hole_rings(room)
    shell = [(v.x, v.y) for v in room.vertices]
    outer = Polygon(shell)
    if not outer.is_valid or outer.area <= 0:
        raise ValueError("外周が不正です: " + explain_validity(outer))
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
    return [Vertex(x=x, y=y) for x, y in list(ring.coords)[:-1]]


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
