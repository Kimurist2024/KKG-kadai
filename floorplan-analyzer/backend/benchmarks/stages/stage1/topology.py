"""Validated floor polygons and positive-area intersections (pixel coordinates)."""
from shapely.geometry import Polygon
from shapely.validation import explain_validity
from .schemas import Vertex, PolygonRegion


def room_polygon(room):
    raw_holes = room.holes if room.holes is not None else []
    if not isinstance(raw_holes, list):
        raise ValueError('holes は頂点配列の配列で指定してください')
    holes = []
    for raw in raw_holes:
        if not isinstance(raw, list) or len(raw) < 3:
            raise ValueError('穴の輪郭には 3 頂点以上が必要です')
        ring = [Vertex.model_validate(v) for v in raw]
        holes.append([(v.x,v.y) for v in ring])
    shell = [(v.x,v.y) for v in room.vertices]
    outer = Polygon(shell)
    if not outer.is_valid or outer.area <= 0:
        raise ValueError("外周が不正です: " + explain_validity(outer))
    for hole in holes:
        polygon = Polygon(hole)
        if not polygon.is_valid or polygon.area <= 0:
            raise ValueError('穴の輪郭が不正です')
        if not outer.contains(polygon) or not outer.boundary.disjoint(polygon):
            raise ValueError('穴は外周に接せず、完全に部屋の内部にある必要があります')
    polygon = Polygon(shell, holes)
    if not polygon.is_valid:
        raise ValueError('外周・穴の交差や重複があります: '+explain_validity(polygon))
    return polygon, [[Vertex(x=x,y=y) for x,y in ring] for ring in holes]


def polygon_regions(geometry):
    if geometry.geom_type == 'Polygon':
        return [PolygonRegion(vertices=[Vertex(x=x,y=y) for x,y in list(geometry.exterior.coords)[:-1]], holes=[[Vertex(x=x,y=y) for x,y in list(r.coords)[:-1]] for r in geometry.interiors])]
    return [region for part in getattr(geometry,'geoms',[]) for region in polygon_regions(part)]
