"""Regression oracle against the frozen pre-optimization implementation."""
import copy
import pytest
from app import analyzer
from app.schemas import MaskFile, AnalysisSettings
from benchmarks.baseline.analyzer import analyze as old_analyze
from benchmarks.baseline.schemas import MaskFile as OldMask, AnalysisSettings as OldSettings
from benchmarks.performance import fixtures, settings_cases, compare as compare_tolerant

def compare(expected, actual):
    stats = compare_tolerant(expected, actual)
    assert stats['different_numeric_fields'] == 0, stats


@pytest.mark.parametrize('name,data', list(fixtures())[:3])
@pytest.mark.parametrize('case,values', settings_cases())
def test_complete_response_matches_baseline(name, data, case, values):
    expected = old_analyze(OldMask.model_validate(data), OldSettings(**values)).model_dump(mode='json')
    mask = MaskFile.model_validate(data)
    analyzer.clear_geometry_cache()
    compare(expected, analyzer.analyze(mask, AnalysisSettings(**values)).model_dump(mode='json'))
    analyzer.analyze(mask, AnalysisSettings())
    compare(expected, analyzer.analyze(mask, AnalysisSettings(**values)).model_dump(mode='json'))

@pytest.mark.parametrize('mutation', ['holes-outside', 'holes-overlap', 'bowtie', 'duplicate-id', 'no-walls', 'line-3-points', 'metadata'])
def test_unusual_inputs_match_baseline(mutation):
    data = copy.deepcopy(next(fixtures())[1])
    room = data['contours'][0]
    if mutation == 'holes-outside':
        room['holes'] = [[dict(x=0,y=0),dict(x=10,y=0),dict(x=10,y=10),dict(x=0,y=10)]]
    elif mutation == 'holes-overlap':
        hole = [dict(x=300,y=200),dict(x=320,y=200),dict(x=320,y=220),dict(x=300,y=220)]
        room['holes'] = [hole, copy.deepcopy(hole)]
    elif mutation == 'bowtie':
        room['vertices'] = [dict(x=0,y=0),dict(x=100,y=100),dict(x=0,y=100),dict(x=100,y=0)]
    elif mutation == 'duplicate-id':
        data['contours'][1]['id'] = room['id']
    elif mutation == 'no-walls':
        data['contours'] = [c for c in data['contours'] if not c.get('isLine')]
    elif mutation == 'line-3-points':
        line = next(c for c in data['contours'] if c.get('isLine'))
        line['vertices'].insert(1, dict(x=1,y=1))
    else:
        room.update(room_name='変更した部屋',color='#123456',area=123.)
        data['timestamp'] = 'changed'
        data['image_data'] = None
    expected = old_analyze(OldMask.model_validate(data)).model_dump(mode='json')
    mask = MaskFile.model_validate(data)
    analyzer.clear_geometry_cache()
    compare(expected, analyzer.analyze(mask).model_dump(mode='json'))
    compare(expected, analyzer.analyze(mask).model_dump(mode='json'))
