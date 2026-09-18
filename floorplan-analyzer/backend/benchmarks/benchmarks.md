# Algorithm performance regression benchmark

Run from `backend/`:

```sh
.venv/bin/python -m benchmarks.performance --phase baseline
.venv/bin/python -m benchmarks.performance --phase final
.venv/bin/python -m pytest -q tests/test_performance_equivalence.py
```

`baseline/` is a frozen copy of the application immediately before the requested
optimization on 2026-09-14. Do not update it to match the implementation under
test. It deliberately retains its own Pydantic schemas and relative imports.
`stages/stage1`, `stage2`, `stage3` preserve intermediate implementations.
They are development-only modules, never imported by `app/`.

Results are written to `docs/validation/algorithm-performance/`. Raw millisecond
samples, nearest-rank p95, median, runtime versions, and baseline file hashes are
included. Run performance measurement without concurrent builds/tests/other
benchmarks. `final.json` is the authoritative same-run comparison of baseline,
intermediate stages and final implementation. Initial `baseline.json` is retained
as historical pre-change measurement; `stages.json` was an exploratory run and
had concurrent equivalence work, so is not used for speedup claims.

Input parsing/Pydantic input validation, HTTP and response JSON serialization are
excluded. Creating the full response model inside `analyze` is included. No warm
cache key bypass is used: cache lookup costs are timed. Cold includes cache clear
and full call. Warm scale/height calls start from geometry primed at default
settings. Baseline/stages are uncached. These are local measurements, not a
measurement of Vercel or end-user click latency.

Fixtures: the shipped 11-room sample, existing handmade hole/door-gap demo, and
10/50 translated copies of all sample contours (110/550 rooms). Copies receive
unique contour IDs and are spaced 1200px horizontally/800px vertically; holes
are also translated if present. Copies retain source area/perimeter metadata.
Repeated room names exercise suffix and warning order stability. These are
synthetic scaling workloads, not 110/550 independently collected floor plans.

Comparison checks every output field recursively, including order of polygon
vertices, rooms, intervals, IDs and warnings. Strings/integers/types match exactly.
Floats are compared at `abs_tol=1e-10`, `rel_tol=1e-12`, with actual maximum
absolute/relative errors and number of bitwise-different values recorded, so a
nonzero tolerated difference is never presented as exact equality.
