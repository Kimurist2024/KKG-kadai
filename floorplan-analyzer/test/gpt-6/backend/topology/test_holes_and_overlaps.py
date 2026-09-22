import pytest
from app.analyzer import analyze
from app.schemas import AnalysisSettings
from ..analyzer.test_analyze import room, line, make_mask
S=AnalysisSettings(scale_px=1,scale_m=1,tolerance_px=1)
OUT=[(0,0),(100,0),(100,100),(0,100)]
HOLE=[(20,20),(40,20),(40,40),(20,40)]
def verts(ps): return [dict(x=x,y=y) for x,y in ps]
def test_hole():
    r=room(1,OUT); r['holes']=[verts(HOLE)]
    a=analyze(make_mask([r,line(2,(20,20),(40,20),2)]),S).rooms[0]
    assert a.floor_area_m2==9600
    assert a.perimeter_m==480
    assert a.wall_length_m==20
    assert [e.index for e in a.edges]==list(range(8))
    assert [e.boundary_kind for e in a.edges]==['outer']*4+['hole']*4
    assert not (20<=a.label_point.x<=40 and 20<=a.label_point.y<=40)
@pytest.mark.parametrize('holes',[[verts([(0,20),(20,20),(20,40),(0,40)])],[verts([(200,0),(220,0),(220,20)])],[verts([(1,1)])],{'bad':True},[verts(HOLE),verts(HOLE)]])
def test_invalid_holes(holes):
    r=room(1,OUT); r['holes']=holes
    a=analyze(make_mask([r]),S)
    assert not a.rooms
    assert any(w.code=='invalid_shape' for w in a.warnings)
def test_triple_overlap():
    a=analyze(make_mask([room(i,OUT,str(i)) for i in range(1,4)]),S)
    assert a.summary.total_floor_area_m2==30000
    assert a.summary.union_floor_area_m2==10000
    assert a.summary.overlap_floor_area_m2==20000
    assert len(a.overlaps)==3
    assert a.overlaps[0].area_m2==10000
def test_hole_touch_and_containment():
    r=room(1,OUT); r['holes']=[verts(HOLE)]
    a=analyze(make_mask([r,room(2,HOLE)]),S)
    assert not a.overlaps
    assert a.summary.union_floor_area_m2==10000
    b=analyze(make_mask([room(1,OUT),room(2,HOLE)]),S)
    assert b.overlaps[0].area_m2==400
def test_door_gap_equivalence():
    base=[room(1,OUT),line(5,(30,0),(70,0),3)]
    a=analyze(make_mask(base+[line(2,(0,0),(100,0),2)]),S).rooms[0]
    b=analyze(make_mask(base+[line(2,(0,0),(30,0),2),line(3,(70,0),(100,0),2)]),S).rooms[0]
    assert a.wall_area_m2==pytest.approx(b.wall_area_m2)
    assert b.wall_area_m2==160
    assert b.edges[0].inferred_wall_intervals[0].length_px==40
    assert b.edges[0].inferred_wall_intervals[0].ids==[5]
@pytest.mark.parametrize('walls',[[line(2,(0,0),(30,0),2)],[line(2,(0,0),(20,0),2),line(3,(80,0),(100,0),2)],[]])
def test_unsupported_gap(walls):
    a=analyze(make_mask([room(1,OUT),line(5,(30,0),(70,0),3)]+walls),S)
    assert not a.rooms[0].edges[0].inferred_wall_intervals
def test_tiny_gap_no_double_count():
    a=analyze(make_mask([room(1,OUT),line(5,(49,0),(50,0),3),line(2,(0,0),(49,0),2),line(3,(50,0),(100,0),2)]),S).rooms[0].edges[0]
    assert a.wall_length_m==100
    assert not a.inferred_wall_intervals
    assert a.door_length_m==1


def test_hole_ring_orientation_does_not_change_quantities():
    first = room(1, OUT)
    first['holes'] = [verts(HOLE)]
    second = room(1, list(reversed(OUT)))
    second['holes'] = [verts(list(reversed(HOLE)))]
    wall = line(2, (20, 20), (40, 20), 2)
    a = analyze(make_mask([first, wall]), S).rooms[0]
    b = analyze(make_mask([second, wall]), S).rooms[0]
    assert a.floor_area_m2 == b.floor_area_m2
    assert a.perimeter_m == b.perimeter_m
    assert a.wall_area_m2 == b.wall_area_m2


def test_door_gap_reversal_and_misaligned_door():
    walls = [line(2, (0, 0), (30, 0), 2), line(3, (70, 0), (100, 0), 2)]
    reversed_room = room(1, list(reversed(OUT)))
    a = analyze(make_mask([reversed_room, line(5, (70, 0), (30, 0), 3)] + walls), S)
    assert a.rooms[0].wall_area_m2 == pytest.approx(160)
    assert any(w.code == 'inferred_door_wall' for w in a.warnings)
    assert not any(w.code == 'unmatched_door' for w in a.warnings)
    b = analyze(make_mask([room(1, OUT), line(5, (30, 2), (70, 2), 3)] + walls), S)
    assert not any(e.inferred_wall_intervals for e in b.rooms[0].edges)
    assert any(w.code == 'unmatched_door' for w in b.warnings)


def test_sample_original_totals_and_no_inferred_walls(sample_json):
    from app.schemas import MaskFile
    result = analyze(MaskFile.model_validate(sample_json))
    assert result.summary.total_floor_area_m2 == pytest.approx(48.75334707816534)
    assert result.summary.total_wall_area_m2 == pytest.approx(155.53741974532744)
    assert not any(e.inferred_wall_intervals for r in result.rooms for e in r.edges)
    assert result.summary.overlap_floor_area_m2 > 0
    assert result.summary.total_floor_area_m2 == pytest.approx(
        result.summary.union_floor_area_m2 + result.summary.overlap_floor_area_m2)


def test_point_touching_rooms_are_not_overlap():
    a = room(1, [(0,0),(10,0),(10,10),(0,10)])
    b = room(2, [(10,10),(20,10),(20,20),(10,20)])
    result = analyze(make_mask([a,b]), S)
    assert not result.overlaps
    assert result.summary.overlap_floor_area_m2 == 0


def test_invalid_outer_with_hole_is_rejected_without_topology_error():
    # A repeated crossing point can evade the older proper-crossing test.
    malformed = room(1, [(0, 0), (100, 0), (100, 100), (50, 0), (0, 100)])
    malformed['holes'] = [verts([(10, 10), (20, 10), (20, 20), (10, 20)])]
    result = analyze(make_mask([malformed]), S)
    assert not result.rooms
    assert any(w.code in ('invalid_shape', 'ignored_contour') for w in result.warnings)


def test_disjoint_fractional_rooms_have_no_phantom_overlap():
    shapes = [room(i, [(i*1.37, 0.13), (i*1.37+0.71, 0.13),
                       (i*1.37+0.71, 0.91), (i*1.37, 0.91)]) for i in range(1, 18)]
    settings = AnalysisSettings(scale_px=96.7, scale_m=1.365, tolerance_px=0)
    result = analyze(make_mask(shapes), settings)
    assert not result.overlaps
    assert result.summary.overlap_floor_area_m2 == 0


def test_geos_validation_failure_becomes_room_warning(monkeypatch):
    from shapely.errors import GEOSException
    def fail_validation(_room):
        raise GEOSException('TopologyException: invalid coordinate topology')
    monkeypatch.setattr('app.analyzer.room_polygon', fail_validation)
    result = analyze(make_mask([room(1, OUT)]), S)
    assert not result.rooms
    assert any(w.code == 'invalid_shape' and w.contour_id == 1 for w in result.warnings)
