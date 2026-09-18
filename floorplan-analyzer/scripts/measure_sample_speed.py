"""同梱の sample/sample_mask.json だけを対象に、変更前の凍結実装（backend/benchmarks/baseline、2026-09-14 時点）と
現行実装（backend/app）の解析時間を交互に計測する。

使い方（アプリ直下から）:
  backend/.venv/bin/python scripts/measure_sample_speed.py [反復回数=101] [結果 JSON の出力先]

計測するもの（ミリ秒、中央値 / p95）:
  - 初回解析 (cold):          幾何キャッシュを空にしてから既定条件で解析
  - 設定変更後の再解析 (warm): 既定条件で解析した直後に、天井高 3.1m・ドア高 2.2m で再解析（現行はキャッシュを再利用）
  - キャッシュ無効の直接計算:  現行の analyze_uncached（変更前にキャッシュは無いので cold と同じ値を並べる）
先に、既定条件・設定変更の両方で summary と rooms が変更前後で一致することを確認する。
"""
import json, math, pathlib, statistics, sys, time

APP = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP / "backend"))

from app import analyzer as cur                                   # noqa: E402
from app.schemas import MaskFile, AnalysisSettings                # noqa: E402
from benchmarks.baseline import analyzer as old                   # noqa: E402
from benchmarks.baseline.schemas import MaskFile as OldMask, AnalysisSettings as OldSettings  # noqa: E402

REPS = int(sys.argv[1]) if len(sys.argv) > 1 else 101
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else None
ALT = dict(ceiling_height_m=3.1, door_height_m=2.2)

data = json.loads((APP / "sample/sample_mask.json").read_text(encoding="utf-8"))
mask, omask = MaskFile.model_validate(data), OldMask.model_validate(data)
base, obase = AnalysisSettings(), OldSettings()
salt, osalt = AnalysisSettings(**ALT), OldSettings(**ALT)


def stats(xs):
    xs = sorted(xs)
    return dict(median_ms=statistics.median(xs), p95_ms=xs[math.ceil(0.95 * len(xs)) - 1], min_ms=xs[0])


def timed(fn):
    t = time.perf_counter_ns()
    fn()
    return (time.perf_counter_ns() - t) / 1e6


def cold_cur():
    cur.clear_geometry_cache()
    return cur.analyze(mask, base)


for a, b in ((cur.analyze(mask, base), old.analyze(omask, obase)), (cur.analyze(mask, salt), old.analyze(omask, osalt))):
    da, db = a.model_dump(mode="json"), b.model_dump(mode="json")
    assert da["summary"] == db["summary"] and da["rooms"] == db["rooms"], "変更前後で結果が一致しません"
print("結果一致: summary / rooms が変更前後で完全一致（既定条件・設定変更）")

res = {k: [] for k in ("cold_old", "cold_cur", "warm_old", "warm_cur", "uncached_cur")}
for i in range(REPS):
    for who in (("old", "cur") if i % 2 == 0 else ("cur", "old")):
        if who == "old":
            res["cold_old"].append(timed(lambda: old.analyze(omask, obase)))
            res["warm_old"].append(timed(lambda: old.analyze(omask, osalt)))
        else:
            res["cold_cur"].append(timed(cold_cur))
            res["warm_cur"].append(timed(lambda: cur.analyze(mask, salt)))
            res["uncached_cur"].append(timed(lambda: cur.analyze_uncached(mask, base)))

S = {k: stats(v) for k, v in res.items()}
rows = [
    ("初回解析 (cold)", "cold_old", "cold_cur"),
    ("設定変更後の再解析 (warm)", "warm_old", "warm_cur"),
    ("キャッシュ無効の直接計算", "cold_old", "uncached_cur"),
]
print(f"同梱 sample_mask.json / 交互 {REPS} 回 / ミリ秒（中央値 / p95）")
for label, o, c in rows:
    so, sc = S[o], S[c]
    print(f"  {label:<26} 変更前 {so['median_ms']:.3f} / {so['p95_ms']:.3f}  →  現行 {sc['median_ms']:.3f} / {sc['p95_ms']:.3f}   倍率 {so['median_ms'] / sc['median_ms']:.2f}x")
if OUT:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(dict(
        input="sample/sample_mask.json", reference="backend/benchmarks/baseline (2026-09-14 時点の凍結コピー)",
        reps=REPS, alt_settings=ALT, python=sys.version.split()[0],
        stats=S, speedup={label: S[o]["median_ms"] / S[c]["median_ms"] for label, o, c in rows},
        raw_ms=res,
    ), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"結果を書き出しました: {OUT}")
