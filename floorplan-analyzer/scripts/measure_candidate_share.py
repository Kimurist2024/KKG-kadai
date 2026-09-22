#!/usr/bin/env python3
"""同梱 JSON だけを使い、解析時間のうち線分の候補検索（索引の構築と辺ごとの問い合わせ）が占める割合を測る。

    backend/.venv/bin/python scripts/measure_candidate_share.py [回数] [出力 JSON]

索引の方式を替えて短くできる時間の上限を知るためのもの。候補検索の時間は
SegmentIndex の構築・near・near_many の所要時間を足し合わせて求め、解析全体は
キャッシュ無効の直接計算（analyze_uncached）の所要時間。同じ回で両方を測る。
"""
import json, pathlib, statistics, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app import analyzer, spatial                    # noqa: E402
from app.schemas import MaskFile, AnalysisSettings  # noqa: E402

REPS = int(sys.argv[1]) if len(sys.argv) > 1 else 101
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else None
mask = MaskFile.model_validate(json.loads((ROOT / "sample" / "sample_mask.json").read_bytes()))
settings = AnalysisSettings()
spent = {"ms": 0.0}


def timed(func):
    def wrapper(*args, **kwargs):
        start = time.perf_counter_ns()
        try:
            return func(*args, **kwargs)
        finally:
            spent["ms"] += (time.perf_counter_ns() - start) / 1e6
    return wrapper


for name in ("__init__", "near", "near_many"):
    setattr(spatial.SegmentIndex, name, timed(getattr(spatial.SegmentIndex, name)))

total_ms, search_ms = [], []
for _ in range(REPS):
    spent["ms"] = 0.0
    start = time.perf_counter_ns()
    analyzer.analyze_uncached(mask, settings)
    total_ms.append((time.perf_counter_ns() - start) / 1e6)
    search_ms.append(spent["ms"])

total, search = statistics.median(total_ms), statistics.median(search_ms)
share = search / total * 100
print(f"同梱 sample_mask.json / {REPS} 回 / キャッシュ無効の直接計算")
print(f"  解析全体 中央値 {total:.3f} ms、候補検索（索引の構築＋問い合わせ）中央値 {search:.3f} ms、割合 {share:.1f}%")
if OUT:
    OUT.write_text(json.dumps({"input": "sample/sample_mask.json", "reps": REPS, "python": sys.version.split()[0],
                               "median_total_ms": total, "median_search_ms": search, "share_percent": share,
                               "raw_ms": {"total": total_ms, "search": search_ms}}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"結果を書き出しました: {OUT}")
