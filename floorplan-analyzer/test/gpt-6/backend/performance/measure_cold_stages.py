"""Interleaved before/after measurements; reference is a copied backend/app directory.

Run from app root with backend/.venv/bin/python and --reference /path/to/copy.
Input validation and equality checks are outside the timed region.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import statistics
import struct
import sys
import time
from pydantic import BaseModel

APP = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(APP / 'backend'))
from app import analyzer, schemas
from benchmarks.performance import fixtures


def exact(a, b):
    assert type(a) is type(b)
    if isinstance(a, dict):
        assert list(a) == list(b)
        for key in a:
            exact(a[key], b[key])
    elif isinstance(a, list):
        assert len(a) == len(b)
        for x, y in zip(a, b):
            exact(x, y)
    elif isinstance(a, float):
        assert struct.pack('!d', a) == struct.pack('!d', b)
    else:
        assert a == b


def exact_fields_set(a, b):
    if isinstance(a, BaseModel):
        assert isinstance(b, BaseModel)
        assert a.model_fields_set == b.model_fields_set
        for key in a.__dict__:
            exact_fields_set(getattr(a, key), getattr(b, key))
    elif isinstance(a, list):
        assert len(a) == len(b)
        for x, y in zip(a, b):
            exact_fields_set(x, y)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reps', type=int, default=101)
    parser.add_argument('--large-reps', type=int, default=21)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('cold_reference', args.reference / '__init__.py',
                                                submodule_search_locations=[str(args.reference)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    from cold_reference import analyzer as before, schemas as old_schemas
    report = {'python': sys.version, 'reference': str(args.reference), 'cases': []}
    for name, data in fixtures():
        if name == 'holes-door-gap-demo':
            continue
        masks = [old_schemas.MaskFile.model_validate(data), schemas.MaskFile.model_validate(data)]
        modules = [before, analyzer]
        settings = [old_schemas.AnalysisSettings(), schemas.AnalysisSettings()]
        alt = [old_schemas.AnalysisSettings(ceiling_height_m=3.1, door_height_m=2.2),
               schemas.AnalysisSettings(ceiling_height_m=3.1, door_height_m=2.2)]
        row = {'fixture': name}
        for mode in ('cold', 'warm', 'uncached'):
            def run(i):
                if mode == 'cold':
                    modules[i].clear_geometry_cache()
                fn = modules[i].analyze_uncached if mode == 'uncached' else modules[i].analyze
                return fn(masks[i], alt[i] if mode == 'warm' else settings[i])
            for i in (0, 1):
                modules[i].clear_geometry_cache()
                modules[i].analyze(masks[i], settings[i])
            expected, actual = run(0), run(1)
            exact_fields_set(expected, actual)
            for options in ({}, {'exclude_unset': True}, {'exclude_defaults': True}, {'exclude_none': True}):
                exact(expected.model_dump(mode='json', **options), actual.model_dump(mode='json', **options))
                assert expected.model_dump_json(**options) == actual.model_dump_json(**options)
            samples = [[], []]
            for iteration in range(args.reps if name == 'sample' else args.large_reps):
                for i in ((0, 1) if iteration % 2 == 0 else (1, 0)):
                    start = time.perf_counter_ns()
                    run(i)
                    samples[i].append((time.perf_counter_ns() - start) / 1e6)
            row[mode] = [{'median_ms': statistics.median(xs), 'raw_ms': xs} for xs in samples]
        report['cases'].append(row)
        print(name, ' / '.join('%s %.3f -> %.3f' % (mode, row[mode][0]['median_ms'], row[mode][1]['median_ms'])
                              for mode in ('cold', 'warm', 'uncached')), 'ms; exact', flush=True)
    args.output.write_text(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
