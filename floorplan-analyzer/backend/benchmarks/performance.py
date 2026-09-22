"""Run from backend: .venv/bin/python -m benchmarks.performance --phase baseline|final."""
from __future__ import annotations
import datetime
import argparse, copy, cProfile, hashlib, importlib, io, json, math, platform, pstats, statistics, sys, time
from pathlib import Path
from benchmarks.baseline import analyzer as baseline
from benchmarks.baseline.schemas import MaskFile as OldMask, AnalysisSettings as OldSettings
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/validation/algorithm-performance'

def fixtures():
    sample = json.loads((ROOT / 'sample/sample_mask.json').read_text())
    yield 'sample', sample
    yield 'holes-door-gap-demo', json.loads((ROOT / 'docs/validation/geometry-upgrade/demo-mask.json').read_text())
    for copies in (10, 50):
        data = copy.deepcopy(sample)
        data['contours'] = []
        for n in range(copies):
            dx, dy = n % 10 * 1200, n // 10 * 800
            for original in sample['contours']:
                contour = copy.deepcopy(original)
                contour['id'] += n * 10000
                for ring in [contour['vertices']] + (contour.get('holes') or []):
                    for v in ring:
                        v['x'] += dx
                        v['y'] += dy
                data['contours'].append(contour)
        data.update(image_width=12000, image_height=math.ceil(copies / 10) * 800, image_data=None)
        yield f'sample-{copies * 11}-rooms', data

def settings_cases():
    return [('default', {}), ('height', {'ceiling_height_m': 3.1, 'door_height_m': 2.2}),
            ('scale', {'scale_px': 123.4, 'scale_m': 2.345}),
            ('zero-tolerance', {'tolerance_px': 0}), ('tolerance', {'tolerance_px': 2.5})]

def compare(expected, actual, path='$', stats=None):
    """Compare all fields and list order; strings, IDs, warnings are exact."""
    if stats is None:
        stats = dict(numeric_fields=0, different_numeric_fields=0, max_absolute_difference=0., max_relative_difference=0., max_difference_path=None)
    if isinstance(expected, dict):
        assert isinstance(actual, dict) and expected.keys() == actual.keys(), path
        for k, v in expected.items(): compare(v, actual[k], f'{path}.{k}', stats)
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(expected) == len(actual), (path, len(expected), len(actual))
        for i, (a, b) in enumerate(zip(expected, actual)): compare(a, b, f'{path}[{i}]', stats)
    elif isinstance(expected, float):
        assert isinstance(actual, (int, float)), path
        delta = abs(expected - actual)
        stats['numeric_fields'] += 1
        stats['different_numeric_fields'] += int(delta != 0)
        if delta > stats['max_absolute_difference']:
            stats.update(max_absolute_difference=delta, max_difference_path=path)
        stats['max_relative_difference'] = max(stats['max_relative_difference'], delta / max(abs(expected), abs(actual), 1e-300))
        assert math.isclose(expected, actual, rel_tol=1e-12, abs_tol=1e-10), (path, expected, actual)
    else:
        assert type(expected) is type(actual) and expected == actual, (path, expected, actual)
    return stats

def measure(fn, count):
    samples = []
    for _ in range(count):
        start = time.perf_counter_ns()
        fn()
        samples.append((time.perf_counter_ns()-start)/1e6)
    return dict(count=count, median_ms=statistics.median(samples), p95_ms=sorted(samples)[math.ceil(.95*count)-1], raw_ms=samples)

def profile_call(fn, path):
    p = cProfile.Profile()
    p.runcall(fn)
    stream = io.StringIO()
    pstats.Stats(p, stream=stream).strip_dirs().sort_stats('cumulative').print_stats(35)
    path.write_text(stream.getvalue())

def provenance():
    import shapely, pydantic
    return dict(timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), app_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'backend/app').glob('*.py'))}, python=sys.version, platform=platform.platform(), processor=platform.processor(), machine=platform.machine(),
                shapely=shapely.__version__, geos=shapely.geos_version_string, pydantic=pydantic.__version__,
                baseline_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((Path(__file__).parent/'baseline').glob('*.py'))})

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['baseline','final'], required=True)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    report = dict(metadata=provenance(), phase=args.phase, cases=[], scope='In-process analysis; excludes input validation, HTTP and JSON serialization. Internal cache JSON and hashing included. Cold includes cache clear; warm preloads default then changes scale/height.')
    if args.phase == 'final':
        from app import analyzer as current
        from app.schemas import MaskFile, AnalysisSettings
    for name, data in fixtures():
        old_mask, old_setting = OldMask.model_validate(data), OldSettings()
        count = 30 if len(data['contours']) < 100 else 5
        baseline.analyze(old_mask, old_setting)
        row = dict(fixture=name, input_sha256=hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest(), baseline=measure(lambda:baseline.analyze(old_mask, old_setting), count))
        if args.phase == 'baseline':
            profile_call(lambda:baseline.analyze(old_mask, old_setting), OUT/f'baseline-profile-{name}.txt')
        else:
            mask, setting = MaskFile.model_validate(data), AnalysisSettings()
            row['equivalence'] = []
            for case, values in settings_cases():
                expected = baseline.analyze(old_mask, OldSettings(**values)).model_dump(mode='json')
                current.clear_geometry_cache()
                cold = compare(expected, current.analyze(mask, AnalysisSettings(**values)).model_dump(mode='json'))
                current.analyze(mask, AnalysisSettings())
                warm = compare(expected, current.analyze(mask, AnalysisSettings(**values)).model_dump(mode='json'))
                row['equivalence'].append(dict(settings=case, cold=cold, warm=warm))
            for stage in (1,2,3):
                mod = importlib.import_module(f'benchmarks.stages.stage{stage}.analyzer')
                schema = importlib.import_module(f'benchmarks.stages.stage{stage}.schemas')
                sm, ss = schema.MaskFile.model_validate(data), schema.AnalysisSettings()
                row[f'stage{stage}-equivalence'] = compare(baseline.analyze(old_mask, old_setting).model_dump(mode='json'), mod.analyze(sm,ss).model_dump(mode='json'))
                row[f'stage{stage}'] = measure(lambda:mod.analyze(sm,ss),count)
            row['uncached'] = measure(lambda:current.analyze_uncached(mask, setting), count)
            def cold_call():
                current.clear_geometry_cache()
                return current.analyze(mask, setting)
            row['cold'] = measure(cold_call, count)
            for case, values in settings_cases()[1:3]:
                variant = AnalysisSettings(**values)
                old_variant = OldSettings(**values)
                row[f'baseline-{case}'] = measure(lambda:baseline.analyze(old_mask, old_variant), count)
                current.clear_geometry_cache()
                current.analyze(mask, setting)
                row[f'warm-{case}'] = measure(lambda:current.analyze(mask, variant), count)
            profile_call(lambda:current.analyze_uncached(mask, setting), OUT/f'final-profile-{name}.txt')
        report['cases'].append(row)
        print(name, {k:round(v['median_ms'],3) for k,v in row.items() if isinstance(v,dict) and 'median_ms' in v}, flush=True)
        (OUT/f'{args.phase}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    if args.phase == 'final':
        stats = [s for c in report['cases'] for e in c['equivalence'] for s in [e['cold'], e['warm']]]
        print('Compared numeric fields:', sum(s['numeric_fields'] for s in stats), 'differing:', sum(s['different_numeric_fields'] for s in stats), 'max abs error:', max(s['max_absolute_difference'] for s in stats), flush=True)
if __name__ == '__main__': main()
