# Measurement artifacts

- `report.md`: final measurement and interpretation.
- `final.json`: authoritative post-fix same-run comparison, all raw repetitions and source/input hashes.
- `baseline.json`: initial pre-change measurement, retained as history.
- `stage-equivalence.json`: intermediate stages 1-3, 60 complete-response comparisons.
- `pre-arithmetic-fix.json`: historical measurement before correcting cached room-area arithmetic order; not final.
- `stage4-equivalence.json`: historical pre-arithmetic-fix cache comparisons; not final.
- `stages.json`: exploratory timing overlapping comparison work; not used for performance claims.
- `baseline-profile-*.txt`, `final-profile-*.txt`: cumulative cProfile reports. Profiling adds overhead.

All measurements use local CLI calls. No browser or native-app computer use.
