import pytest
from app.analyzer import analyze
from app.schemas import AnalysisSettings
from .test_analyze import make_mask, room, line

POINTS = [(0, 0), (100, 0), (100, 100), (0, 100)]

def codes(res):
    return {w.code for w in res.warnings}

def test_missing_or_invalid_wall_data():
    for walls in [[], [line(10, (0, 0), (0, 0), 2)]]:
        res = analyze(make_mask([room(1, POINTS)] + walls))
        assert 'missing_wall_data' in codes(res)
        assert 'no_room_walls' not in codes(res)
        assert res.rooms[0].wall_area_m2 == 0
        assert res.rooms[0].floor_area_m2 > 0

def test_shifted_walls_warn_only_affected_room():
    far = [(x+1000,y) for x,y in POINTS]
    walls=[line(10+i,a,b,2) for i,(a,b) in enumerate(zip(POINTS,POINTS[1:]+POINTS[:1]))]
    res=analyze(make_mask([room(1,POINTS),room(2,far)]+walls))
    assert [(w.code,w.contour_id) for w in res.warnings] == [('no_room_walls',2)]

@pytest.mark.parametrize('length,expected', [(60,True),(80,False),(100,False)])
def test_low_coverage_threshold_and_scale_independence(length, expected):
    mask=make_mask([room(1,POINTS),line(10,(0,0),(length,0),2)])
    for scale in [0.000001,0.01,100]:
        res=analyze(mask,AnalysisSettings(scale_px=1,scale_m=scale,tolerance_px=0))
        assert ('low_wall_coverage' in codes(res)) == expected
        assert res.rooms[0].wall_area_m2 == pytest.approx(length*scale*2.4)

def test_no_rooms_does_not_add_wall_warning():
    assert 'missing_wall_data' not in codes(analyze(make_mask([])))
