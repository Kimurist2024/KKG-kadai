"""Compare against an immutable, separately extracted app directory.

python -m benchmarks.exact_speed --reference /path/to/backend/app --output report.json
"""
import argparse
import copy
import importlib.util
import json
import platform
import random
import statistics
import sys
import time
from pathlib import Path

from app import analyzer, schemas
from benchmarks.performance import fixtures, settings_cases


def exact(a, b):
    """No tolerance: compare types, sequence order and every float bit pattern."""
    assert type(a) is type(b), (type(a), type(b))
    if isinstance(a, dict):
        assert a.keys() == b.keys()
        return sum(exact(a[k], b[k]) for k in a)
    if isinstance(a, list):
        assert len(a) == len(b)
        return sum(exact(x, y) for x, y in zip(a, b))
    if isinstance(a, float):
        assert a.hex() == b.hex(), (a, b)
        return 1
    assert a == b, (a, b)
    return 0


def measure(fn):
    fn()
    values = []
    for _ in range(9):
        started = time.perf_counter_ns()
        fn()
        values.append((time.perf_counter_ns() - started) / 1e6)
    return {"median_ms": statistics.median(values), "raw_ms": values}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("speed_reference", args.reference / "__init__.py",
                                                submodule_search_locations=[str(args.reference)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    from speed_reference import analyzer as old, schemas as old_schemas
    report = {"python": sys.version, "platform": platform.platform(),
              "scope": "In-process analyze, excluding input validation, HTTP and response serialization",
              "reference_commit": "e25dadf", "cases": []}
    rng = random.Random(20260917)
    sample_data = next(fixtures())[1]
    random_checked = 0
    for _ in range(30):
        data = copy.deepcopy(sample_data)
        for contour in data["contours"]:
            for vertex in contour["vertices"]:
                vertex["x"] += rng.uniform(-0.05, 0.05)
                vertex["y"] += rng.uniform(-0.05, 0.05)
        before = old_schemas.MaskFile.model_validate(data)
        after = schemas.MaskFile.model_validate(data)
        old.clear_geometry_cache()
        analyzer.clear_geometry_cache()
        for _ in range(2):
            random_checked += exact(old.analyze(before).model_dump(mode="json"),
                                    analyzer.analyze(after).model_dump(mode="json"))
    report["randomized_cases"] = 30
    report["randomized_float_values_exact"] = random_checked
    for name, data in fixtures():
        before = old_schemas.MaskFile.model_validate(data)
        after = schemas.MaskFile.model_validate(data)
        checked = 0
        cases = settings_cases()
        if name == "sample":
            cases += [("regularized", {"geometry_mode": "regularized_shared", "boundary_reference": "centerline"})]
        for _, values in cases:
            old_settings = old_schemas.AnalysisSettings(**values)
            settings = schemas.AnalysisSettings(**values)
            old.clear_geometry_cache()
            analyzer.clear_geometry_cache()
            for _ in range(2):
                expected = old.analyze(before, old_settings).model_dump(mode="json")
                actual = analyzer.analyze(after, settings).model_dump(mode="json")
                checked += exact(expected, actual)
        row = {"fixture": name, "float_values_exact": checked}
        for mode in ("cold", "warm", "uncached"):
            def run(mod, mask):
                if mode == "cold":
                    mod.clear_geometry_cache()
                return (mod.analyze_uncached if mode == "uncached" else mod.analyze)(mask)
            old.clear_geometry_cache()
            analyzer.clear_geometry_cache()
            a = measure(lambda: run(old, before))
            b = measure(lambda: run(analyzer, after))
            row[mode] = {"before": a, "after": b, "speedup": a["median_ms"] / b["median_ms"]}
        report["cases"].append(row)
        print(name, {m: round(row[m]["speedup"], 3) for m in ("cold", "warm", "uncached")}, flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
