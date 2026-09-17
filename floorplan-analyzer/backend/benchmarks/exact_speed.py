"""Compare against an immutable, separately extracted app directory.

python -m benchmarks.exact_speed --reference /path/to/backend/app --output report.json
"""
import argparse
import copy
import importlib.util
import hashlib
import json
import math
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


def measure_pair(before, after):
    before()
    after()
    values = [[], []]
    for repetition in range(9):
        for index in ((0, 1) if repetition % 2 == 0 else (1, 0)):
            started = time.perf_counter_ns()
            (before, after)[index]()
            values[index].append((time.perf_counter_ns() - started) / 1e6)
    return [{"median_ms": statistics.median(v), "raw_ms": v} for v in values]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference-commit", default="e25dadf")
    parser.add_argument("--include-dense", action="store_true")
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("speed_reference", args.reference / "__init__.py",
                                                submodule_search_locations=[str(args.reference)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    from speed_reference import analyzer as old, schemas as old_schemas
    report = {"python": sys.version, "platform": platform.platform(),
              "scope": "In-process analyze, excluding input validation, HTTP and response serialization",
              "reference_commit": args.reference_commit, "cases": [],
              "method": "9 interleaved runs, alternating before/after order; one warmup each",
              "geometry_sha256": hashlib.sha256((Path(analyzer.__file__).parent / "geometry.py").read_bytes()).hexdigest()}
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
    inputs = list(fixtures())
    if args.include_dense:
        data = copy.deepcopy(sample_data)
        room = copy.deepcopy(next(c for c in data["contours"] if not c.get("isLine")))
        room["vertices"] = [{"x": 500 + 400 * math.cos(i * math.tau / 1024),
                             "y": 500 + 400 * math.sin(i * math.tau / 1024)} for i in range(1024)]
        data.update(contours=[room], image_width=1000, image_height=1000, image_data=None)
        inputs.append(("synthetic-circle-1024-no-walls", data))
        data = copy.deepcopy(data)
        corners = [(100, 100), (900, 100), (900, 900), (100, 900)]
        data["contours"][0]["vertices"] = [
            {"x": a[0] + (b[0] - a[0]) * j / 256, "y": a[1] + (b[1] - a[1]) * j / 256}
            for a, b in zip(corners, corners[1:] + corners[:1]) for j in range(256)]
        wall = next(c for c in sample_data["contours"] if c.get("isLine") and c["label_id"] == 2)
        for i, (a, b) in enumerate(zip(corners, corners[1:] + corners[:1])):
            segment = copy.deepcopy(wall)
            segment.update(id=10000 + i, vertices=[{"x": a[0], "y": a[1]}, {"x": b[0], "y": b[1]}])
            data["contours"].append(segment)
        inputs.append(("synthetic-square-1024-with-walls", data))
    for name, data in inputs:
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
            a, b = measure_pair(lambda: run(old, before), lambda: run(analyzer, after))
            row[mode] = {"before": a, "after": b, "speedup": a["median_ms"] / b["median_ms"]}
        report["cases"].append(row)
        print(name, {m: round(row[m]["speedup"], 3) for m in ("cold", "warm", "uncached")}, flush=True)
    if args.include_dense:
        from app import geometry
        from speed_reference import geometry as old_geometry
        intervals = [(float(i), i + 1.5, {i}) for i in range(1000)]
        a = [geometry.Interval(*iv) for iv in intervals]
        b = [old_geometry.Interval(*iv) for iv in intervals]
        def dump(result):
            return [[float(iv.start), float(iv.end), sorted(iv.ids)] for iv in result]
        exact(dump(old_geometry.clip_intervals(b, b)), dump(geometry.clip_intervals(a, a)))
        before, after = measure_pair(lambda: old_geometry.clip_intervals(b, b), lambda: geometry.clip_intervals(a, a))
        report["interval_microbenchmark"] = {"scope": "1000 overlapping intervals per side; not whole analysis",
                                             "before": before, "after": after,
                                             "speedup": before["median_ms"] / after["median_ms"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
