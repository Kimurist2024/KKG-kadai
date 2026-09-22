#!/usr/bin/env python3
"""同梱 JSON だけを使い、線分の候補検索を「外接長方形の走査」と「STRtree」で入れ替えて解析時間を比べる。

    backend/.venv/bin/python scripts/measure_index_choice.py [回数] [出力 JSON]

索引の切り替え（線分 64 本以上で STRtree）が同梱データの規模で妥当かを確かめるためのもの。
2 つの方式で出力が完全に一致することを確かめてから、交互に計測する。
"""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.experiments import compare                # noqa: E402
from app.schemas import MaskFile, AnalysisSettings  # noqa: E402

REPS = int(sys.argv[1]) if len(sys.argv) > 1 else 101
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else None
mask = MaskFile.model_validate(json.loads((ROOT / "sample" / "sample_mask.json").read_bytes()))
results = compare(mask, AnalysisSettings(), ["scan_only", "tree_only"], REPS)
if not all(row["matches_default"] for row in results.values()):
    sys.exit("NG: 2 つの方式で出力が一致しない: " + repr(results))
times = {name: results[profile]["raw_ms"]
         for name, profile in (("scan", "scan_only"), ("tree", "tree_only"))}

walls = sum(1 for c in mask.contours if c.label_id == 2)
doors = sum(1 for c in mask.contours if c.label_id == 3)
stats = {name: {key: results[profile][key] for key in ("median_ms", "p95_ms")}
         for name, profile in (("scan", "scan_only"), ("tree", "tree_only"))}
print(f"同梱 sample_mask.json（壁 {walls} 本・ドア {doors} 本）/ 交互 {REPS} 回 / キャッシュ無効の直接計算 / 出力は 2 方式で完全一致")
print(f"  外接長方形の走査（現行はこちら）: 中央値 {stats['scan']['median_ms']:.3f} ms / p95 {stats['scan']['p95_ms']:.3f} ms")
print(f"  STRtree を強制                  : 中央値 {stats['tree']['median_ms']:.3f} ms / p95 {stats['tree']['p95_ms']:.3f} ms")
if OUT:
    OUT.write_text(json.dumps({"input": "sample/sample_mask.json", "walls": walls, "doors": doors, "reps": REPS,
                               "python": sys.version.split()[0], "stats": stats, "raw_ms": times},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"結果を書き出しました: {OUT}")
