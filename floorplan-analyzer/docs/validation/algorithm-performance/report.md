# Algorithm performance measurement

Timestamp UTC: 2026-09-14T15:04:07.610693+00:00

## Sequential stages (milliseconds: median / nearest-rank p95)

| Fixture | Baseline | Stage1 | Stage2 | Stage3 | Final uncached | Final cold |
|---|---:|---:|---:|---:|---:|---:|
| sample | 3.000 / 3.315 | 2.824 / 3.261 | 2.840 / 3.177 | 2.906 / 2.992 | 2.822 / 2.924 | 4.152 / 6.911 |
| holes-door-gap-demo | 0.431 / 0.456 | 0.424 / 0.434 | 0.435 / 0.456 | 0.439 / 0.485 | 0.432 / 0.444 | 0.653 / 0.695 |
| sample-110-rooms | 86.602 / 94.186 | 75.171 / 81.537 | 76.198 / 86.340 | 40.605 / 46.881 | 41.538 / 47.827 | 61.845 / 62.843 |
| sample-550-rooms | 1627.138 / 1678.503 | 1460.150 / 1503.591 | 1443.395 / 1777.601 | 233.736 / 259.998 | 231.865 / 256.095 | 371.615 / 384.793 |

Stage 1: reuse projected doors. Stage 2: interval scan. Stage 3: STRtree candidates. Final cold: cache preparation included.

## Changed settings (milliseconds: median / p95)

| Fixture | Changed setting | Baseline | Final warm | Median speedup |
|---|---|---:|---:|---:|
| sample | height | 2.888 / 2.948 | 0.840 / 0.910 | 3.44x |
| sample | scale | 2.895 / 3.829 | 0.843 / 0.893 | 3.43x |
| holes-door-gap-demo | height | 0.431 / 0.471 | 0.140 / 0.150 | 3.07x |
| holes-door-gap-demo | scale | 0.428 / 0.442 | 0.140 / 0.150 | 3.07x |
| sample-110-rooms | height | 86.003 / 93.062 | 9.556 / 16.909 | 9.00x |
| sample-110-rooms | scale | 87.725 / 91.897 | 8.985 / 14.581 | 9.76x |
| sample-550-rooms | height | 1631.991 / 1652.379 | 99.503 / 108.990 | 16.40x |
| sample-550-rooms | scale | 1618.235 / 1699.750 | 117.560 / 125.817 | 13.77x |

## Result equivalence

40 complete cold/warm response comparisons; 1,015,292 numeric fields; 0 differing numeric values; max absolute error 0.0; max relative error 0.0.

Includes four fixtures and five settings: default, ceiling 3.1m/door 2.2m, scale 123.4px=2.345m, tolerance 0px, tolerance 2.5px. All list order, vertex coordinates, room/edge/interval IDs, holes, overlap regions, warning strings, integers and nulls are checked. No polygon normalization hides vertex-order differences. Float tolerance is abs=1e-10/rel=1e-12; actual differences are independently recorded and were zero. An additional 12 intermediate-stage default-setting comparisons passed in final.json; stage-equivalence.json contains 60 comparisons across all five settings and three stages, also zero error.

The 22 tests in tests/test_performance_equivalence.py require zero differing numeric fields and passed, including invalid/outside/overlapping holes, self-intersection, duplicate IDs, missing walls, 3-vertex lines and changed metadata. This is tested-input equivalence, not proof for every possible input.

Before the final run, comparing the initial cache implementation found 1,636 floating-point differences (maximum 1.8189894035458565e-11). Its room wall-area calculation summed already-subtracted edge areas, while the baseline subtracts summed door area from summed gross area. The implementation was corrected to preserve operation order. pre-arithmetic-fix.json and stage4-equivalence.json retain those historical pre-fix results; they are not the final result. Final measurement was rerun in full after the correction.

## Scope and interpretation

- Sample and hole/door-gap demo: 30 repetitions each. Synthetic 110/550 rooms: 5 repetitions each; p95 for 5 samples is their maximum, not a stable estimate of population p95.
- Local in-process analysis. Input loading/validation, outward response JSON serialization, HTTP and UI rendering excluded. Full response model construction and internal cache JSON/hash/read/write included. Cold includes cache clear. Warm primes at default settings, then changes heights or scale; baseline is timed with those same changed settings.
- Other agents paused heavy test/build work during final measurement. final.json is authoritative. stages.json was exploratory and overlapped equivalence work, so is excluded from claims.
- Large fixtures translate all sample contours 10/50 times with unique IDs, at 1200px horizontal/800px vertical spacing; holes are translated if present. They are synthetic scaling inputs, not independently collected real plans.
- Small-sample cold calls increased: cache preparation costs more than it saves on first use. Height/scale changes are faster. See exact values in the tables above. Demo cold similarly increased.
- Stage 2 alone has no demonstrated benefit on the small sample/110-room inputs. Their few intervals make overhead visible. The 550-room stage2 change is modest. Do not claim every stage speeds up every input.
- Large-input cold calls and changed-settings calls improved, with ratios shown above. Stage 3 candidate reduction explains most of the large-input gain.
- Baseline cProfile at 550 rooms: 2.299s total, 1.640s cumulative segment projection, 0.445s intersects. Profiling adds overhead: these times are not comparable directly to unprofiled latency.
- Cache is process-local, 8 entries/16MiB/300s. Different contours/tolerance, restart, expiry or eviction require cold computation. Vercel instances do not share this cache.
- Spatially separated synthetic copies favor STRtree. Inputs with heavily overlapping bounding boxes may not gain the same speedup.
- Already-displayed room clicks normally reuse computed results. Analysis timing does not measure click-to-render time, network latency or Vercel cold starts. No computer use/browser automation was performed.

## Reproduce

```sh
cd floorplan-analyzer/backend
.venv/bin/python -m benchmarks.performance --phase final
.venv/bin/python -m pytest -q tests/test_performance_equivalence.py
```

Raw samples, input hashes and implementation hashes: [final.json](final.json). Initial pre-change measurements: [baseline.json](baseline.json). Per-function cProfile reports: baseline-profile-* and final-profile-* in this directory.

```json
{
  "timestamp_utc": "2026-09-14T15:04:07.610693+00:00",
  "app_sha256": {
    "__init__.py": "f0cd3f1de44b134e6f0b63f65f2174f50f4cb3975f13c0bf09746c0d31896520",
    "ai.py": "d1b05864527d5f8115c912ada04764fb283f25f922421cedd9a858be25fb1334",
    "ai_schemas.py": "c7c8f941d09d108d4d57bdbf7b3a8022a90c97d634df597d5aeb5d828e9d788d",
    "analysis_cache.py": "dd474c01a0405d2eb0b550231a130c726ea7ce79f57f431b5036a0e21565c4a7",
    "analyzer.py": "873afd910f0c7fb2fd2fd8c48fcb3901b9b177e2b7608d6883e9e3396920c34b",
    "geometry.py": "0267cfab4bf5bbf6180da02c74f0ff5c120ecf07f92e602ec59d06534d094af0",
    "main.py": "5c097e59fc88c164934c9929a9b2d8150d69985c1490176d39a6c0c951d6e719",
    "schemas.py": "f73a5ff22a83ea8ce9700525fdcc990c025e64f9cc60bb101f8d0098d9d991c9",
    "spatial.py": "297a6e7c35a1fbe80ecfd4d8acc6c1c8614ffd20a5eee7eaff409ece98cad882",
    "topology.py": "0cb11122de6cf7ad8da8352e219e30eb0d2ad74af8fcaf5bae883a3a8cfccc1b"
  },
  "python": "3.9.6 (default, Apr 30 2025, 02:07:17) \n[Clang 17.0.0 (clang-1700.0.13.5)]",
  "platform": "macOS-26.6.2-arm64-arm-64bit",
  "processor": "arm",
  "machine": "arm64",
  "shapely": "2.0.7",
  "geos": "3.11.4",
  "pydantic": "2.13.5",
  "baseline_sha256": {
    "__init__.py": "f0cd3f1de44b134e6f0b63f65f2174f50f4cb3975f13c0bf09746c0d31896520",
    "analyzer.py": "ac194057aeeb48d737ab7fbcb5e576357a830df1af46189ed0de6802b5167954",
    "geometry.py": "d5e098de46a65d29f8f51a806544b16e1a446e39c17ccfd5bf5d2171cfb51ea5",
    "schemas.py": "f73a5ff22a83ea8ce9700525fdcc990c025e64f9cc60bb101f8d0098d9d991c9",
    "topology.py": "0cb11122de6cf7ad8da8352e219e30eb0d2ad74af8fcaf5bae883a3a8cfccc1b"
  }
}
```

## 公開APIの追加検証

2026-09-15、Vercel production READYとトップ・healthのHTTP200を確認。サンプル/穴・扉切れ目デモ各3条件の解析6件すべてHTTP200。凍結した変更前実装のローカル結果と全項目を照合し、数値最大絶対差5.684341886080802e-14（辺長px）、デモは差0。文字列・ID・配列順序は一致。ローカルPython3.9・本番Python3.12の異なる環境での比較であり、微差の原因の分離検証は未実施。上記の同一環境での差0という結果とは区別します。[検証データ](production-check.json)。
