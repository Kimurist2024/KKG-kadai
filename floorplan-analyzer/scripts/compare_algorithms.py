#!/usr/bin/env python3
"""Compare exact profiles; exit 1 when any output differs from default."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.experiments import compare
from app.schemas import AnalysisSettings, MaskFile
from app.strategies import PROFILES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", type=Path,
                        help="repeat for multiple inputs (default: bundled sample)")
    parser.add_argument("--profiles", default=",".join(PROFILES))
    parser.add_argument("--reps", type=int, default=101)
    parser.add_argument("--json", type=Path, dest="output")
    args = parser.parse_args()
    if args.reps < 1:
        parser.error("--reps must be positive")
    names = [name.strip() for name in args.profiles.split(",")]
    report = dict(python=sys.version.split()[0], reps=args.reps, warmups=5, alternate=True, inputs=[])
    matched = True
    for source in args.input or [ROOT / "sample/sample_mask.json"]:
        try:
            mask = MaskFile.model_validate_json(source.read_bytes())
            rows = compare(mask, AnalysisSettings(), names, args.reps)
        except (ValueError, KeyError, OSError) as exc:
            parser.error(str(exc))
        report["inputs"].append(dict(input=str(source), results=rows))
        print(f"\n入力: {source}")
        print("| profile | 中央値 ms | p95 ms | default との出力一致 | 差があったフィールド |")
        print("|---|---:|---:|---|---|")
        for name, row in rows.items():
            equal = row["matches_default"]
            matched &= equal
            diff = row["difference"]
            detail = "—" if diff is None else (
                f"{diff['path']}: {diff['expected']!r} → {diff['actual']!r}")
            detail = detail.replace("|", "\\|").replace("\n", " ")
            print(f"| {name} | {row['median_ms']:.3f} | {row['p95_ms']:.3f} | "
                  f"{'一致' if equal else '不一致'} | {detail} |")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n結果を書き出しました: {args.output}")
    return 0 if matched else 1


if __name__ == "__main__":
    sys.exit(main())
