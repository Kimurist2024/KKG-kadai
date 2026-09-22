import json
import math
import pathlib
import statistics
import subprocess
import sys
from dataclasses import replace

import pytest

from app import experiments
from app.schemas import AnalysisSettings
from app.strategies import PROFILES, REGISTRIES, register, resolve_profile
from ..factories import make_mask, room, rect, wall, door


def mask():
    return make_mask([room(1, rect(0, 0, 100, 100)), wall(2, (0, 0), (100, 0)),
                      door(3, (30, 0), (40, 0))])


@pytest.mark.parametrize('alternate', [True, False])
def test_warmup_order_statistics_and_reference(monkeypatch, alternate):
    response = experiments.analyze_uncached(mask(), AnalysisSettings())
    calls = []
    def run(mask, settings, profile=None):
        calls.append(resolve_profile(profile))
        return response
    monkeypatch.setattr(experiments, 'analyze_uncached', run)
    reps = 21
    ticks = iter([tick for i in range(2 * (reps + 5)) for tick in (0, (i + 1) * 1_000_000)])
    monkeypatch.setattr(experiments.time, 'perf_counter_ns', lambda: next(ticks))
    names = ['scan_only', 'tree_only']
    rows = experiments.compare(mask(), AnalysisSettings(), names, reps, alternate=alternate)
    expected_calls, samples = [resolve_profile('default')], {name: [] for name in names}
    tick = 0
    for i in range(reps + 5):
        for name in names[::-1] if alternate and i % 2 else names:
            tick += 1
            expected_calls.append(resolve_profile(name))
            if i >= 5:
                samples[name].append(float(tick))
    assert calls == expected_calls
    assert list(rows) == names
    for name, row in rows.items():
        values = samples[name]
        assert row['raw_ms'] == values
        assert row['median_ms'] == statistics.median(values)
        assert row['min_ms'] == min(values)
        assert row['p95_ms'] == sorted(values)[math.ceil(.95 * reps) - 1]
        assert row['json_equal'] and row['bits_equal'] and row['matches_default']
        assert row['difference'] is None


def test_registered_bad_strategy_reports_first_field(monkeypatch):
    # Copy the registry so the decorated registration cannot leak into other tests.
    monkeypatch.setitem(REGISTRIES, 'interval_clip', dict(REGISTRIES['interval_clip']))
    @register('interval_clip', 'missing_doors')
    def missing_doors(a, b):
        return []
    monkeypatch.setitem(PROFILES, 'bad', replace(resolve_profile('default'), interval_clip='missing_doors'))
    rows = experiments.compare(mask(), AnalysisSettings(), ['default', 'bad'], 2)
    assert rows['default']['matches_default']
    bad = rows['bad']
    assert not bad['matches_default'] and not bad['bits_equal'] and not bad['json_equal']
    difference = bad['difference']
    assert difference['path'] == '$.summary.total_wall_area_m2'
    expected = experiments.analyze_uncached(mask(), AnalysisSettings()).summary.total_wall_area_m2
    assert difference['expected'] == expected
    assert difference['actual'] > expected


@pytest.mark.parametrize('expected,actual,path,reason', [
    ({'a': [-0.]}, {'a': [0.]}, '$.a[0]', 'float bits'),
    ({'a': 1}, {'a': 1.}, '$.a', 'type'),
    ({'a': 1, 'b': 2}, {'b': 2, 'a': 1}, '$', 'keys/order'),
    ({'a': [1]}, {'a': [1, 2]}, '$.a', 'length'),
    ({'a': [1, 2]}, {'a': [2, 1]}, '$.a[0]', 'value'),
])
def test_first_difference(expected, actual, path, reason):
    result = experiments.first_difference(expected, actual)
    assert result['path'] == path and result['reason'] == reason


def test_exclude_unset_and_transient_mismatch_are_checked(monkeypatch):
    good = experiments.analyze_uncached(mask(), AnalysisSettings())
    bad = good.model_copy(deep=True)
    bad.model_fields_set.remove('timestamp')
    assert good.model_dump_json() == bad.model_dump_json()
    calls = iter([good, good, bad, good, good, good, good])
    monkeypatch.setattr(experiments, 'analyze_uncached', lambda *a, **kw: next(calls))
    row = experiments.compare(mask(), AnalysisSettings(), ['default'], 1)['default']
    assert not row['matches_default']
    assert row['difference']['path'] == '$[exclude_unset]'
    assert len(row['raw_ms']) == 1


@pytest.mark.parametrize('reps', [0, -1, 1.5, True])
def test_invalid_repetitions(reps):
    with pytest.raises(ValueError, match='reps'):
        experiments.compare(mask(), AnalysisSettings(), ['default'], reps)


def test_profiles_validation():
    with pytest.raises(ValueError, match='empty'):
        experiments.compare(mask(), AnalysisSettings(), [], 1)
    with pytest.raises(ValueError, match='Duplicate'):
        experiments.compare(mask(), AnalysisSettings(), ['default', 'default'], 1)
    with pytest.raises(KeyError, match='registered:'):
        experiments.compare(mask(), AnalysisSettings(), [replace(resolve_profile('default'), interval_clip='missing')], 1)


def test_cli_multiple_inputs_and_legacy_output(tmp_path):
    root = pathlib.Path(__file__).resolve().parents[4]
    source = tmp_path / 'mask.json'
    source.write_text(mask().model_dump_json())
    output = tmp_path / 'comparison.json'
    result = subprocess.run([sys.executable, str(root / 'scripts/compare_algorithms.py'),
                             '--input', str(source), '--input', str(source),
                             '--reps', '1', '--json', str(output)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.count('| profile |') == 2
    report = json.loads(output.read_text())
    assert len(report['inputs']) == 2
    assert all(row['matches_default'] and len(row['raw_ms']) == 1
               for case in report['inputs'] for row in case['results'].values())
    legacy = tmp_path / 'index.json'
    result = subprocess.run([sys.executable, str(root / 'scripts/measure_index_choice.py'), '2', str(legacy)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(legacy.read_text())
    assert list(report) == ['input', 'walls', 'doors', 'reps', 'python', 'stats', 'raw_ms']
    assert list(report['stats']) == ['scan', 'tree']
    assert all(list(stats) == ['median_ms', 'p95_ms'] for stats in report['stats'].values())
    assert all(len(times) == 2 for times in report['raw_ms'].values())


def test_new_module_is_discovered_without_dispatcher_changes(tmp_path):
    import os
    import shutil

    root = pathlib.Path(__file__).resolve().parents[4]
    copied = tmp_path / 'app'
    shutil.copytree(root / 'backend/app', copied, ignore=shutil.ignore_patterns('__pycache__'))
    (copied / 'strategies/new_method.py').write_text('''from . import AlgorithmProfile, PROFILES, register
from .interval_clip import all_pairs

@register("interval_clip", "new_method")
def new_method(a, b):
    return all_pairs(a, b)

PROFILES["new_profile"] = AlgorithmProfile(interval_clip="new_method")
''')
    env = dict(os.environ, PYTHONPATH=str(tmp_path))
    code = '''from app.strategies import PROFILES, get
from app.experiments import compare
from app.schemas import MaskFile, AnalysisSettings
assert "new_profile" in PROFILES
assert callable(get("interval_clip", "new_method"))
mask = MaskFile.model_validate_json(%r)
row = compare(mask, AnalysisSettings(), ["new_profile"], 1)["new_profile"]
assert row["matches_default"]
print("discovered and compared")
''' % mask().model_dump_json()
    result = subprocess.run([sys.executable, '-c', code], cwd=tmp_path, env=env,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'discovered and compared'
