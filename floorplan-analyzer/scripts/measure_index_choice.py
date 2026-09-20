#!/usr/bin/env python3
"""同梱 JSON だけを使い、線分の候補検索を「外接長方形の走査」と「STRtree」で入れ替えて解析時間を比べる。

    backend/.venv/bin/python scripts/measure_index_choice.py [回数] [出力 JSON]

索引の切り替え（線分 64 本以上で STRtree）が同梱データの規模で妥当かを確かめるためのもの。
2 つの方式で出力が完全に一致することを確かめてから、交互に計測する。
"""
import json, math, pathlib, statistics, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from shapely.geometry import LineString          # noqa: E402
from shapely.strtree import STRtree              # noqa: E402
from app import analyzer, spatial                # noqa: E402
from app.schemas import MaskFile, AnalysisSettings  # noqa: E402

REPS = int(sys.argv[1]) if len(sys.argv) > 1 else 101
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else None
mask = MaskFile.model_validate(json.loads((ROOT / "sample" / "sample_mask.json").read_bytes()))
settings = AnalysisSettings()
original_init = spatial.SegmentIndex.__init__


def force(use_tree):
    def init(self, segments):
        self.segments = segments
        self.tree = STRtree([LineString(s) for _, s in segments]) if use_tree and segments else None
        self.bounds = [(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))
                       for _, (a, b) in segments] if self.tree is None else []
    spatial.SegmentIndex.__init__ = init


def run():
    start = time.perf_counter()
    result = analyzer.analyze_uncached(mask, settings)
    return (time.perf_counter() - start) * 1000, result


outputs = {}
for name, use_tree in (("scan", False), ("tree", True)):
    force(use_tree)
    outputs[name] = run()[1].model_dump_json()
if outputs["scan"] != outputs["tree"]:
    sys.exit("NG: 2 つの方式で出力が一致しない")

times = {"scan": [], "tree": []}
for i in range(REPS + 5):
    for name, use_tree in (("scan", False), ("tree", True)) if i % 2 == 0 else (("tree", True), ("scan", False)):
        force(use_tree)
        elapsed, _ = run()
        if i >= 5:                      # 最初の 5 回は慣らし
            times[name].append(elapsed)
spatial.SegmentIndex.__init__ = original_init

walls = sum(1 for c in mask.contours if c.label_id == 2)
doors = sum(1 for c in mask.contours if c.label_id == 3)
stats = {k: {"median_ms": statistics.median(v), "p95_ms": sorted(v)[math.ceil(len(v) * 0.95) - 1]}  # p95 は最近順位法
         for k, v in times.items()}
print(f"同梱 sample_mask.json（壁 {walls} 本・ドア {doors} 本）/ 交互 {REPS} 回 / キャッシュ無効の直接計算 / 出力は 2 方式で完全一致")
print(f"  外接長方形の走査（現行はこちら）: 中央値 {stats['scan']['median_ms']:.3f} ms / p95 {stats['scan']['p95_ms']:.3f} ms")
print(f"  STRtree を強制                  : 中央値 {stats['tree']['median_ms']:.3f} ms / p95 {stats['tree']['p95_ms']:.3f} ms")
if OUT:
    OUT.write_text(json.dumps({"input": "sample/sample_mask.json", "walls": walls, "doors": doors, "reps": REPS,
                               "python": sys.version.split()[0], "stats": stats, "raw_ms": times},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"結果を書き出しました: {OUT}")
