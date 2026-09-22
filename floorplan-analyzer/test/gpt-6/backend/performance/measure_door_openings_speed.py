"""補正導入前の固定コミットと補正実装を同梱サンプルで交互測定する（ファイル書出しなし）。

アプリ直下: backend/.venv/bin/python test/gpt-6/backend/performance/measure_door_openings_speed.py 101
凍結版用の scripts/measure_sample_speed.py は新しい出力契約を比較できないため、
今回の変更直前のコードをメモリ内に読み込み、補正有効時の追加コストを測る。
"""
import json
import pathlib
import statistics
import subprocess
import sys
import time
import types

REFERENCE_COMMIT = '2a89bc9'  # ドア開口部の床の補正を入れる直前のコミット（README「丸める」の言い換え、#101）
APP = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(APP / 'backend'))
from app import analyzer
from app.schemas import AnalysisSettings, MaskFile
from legacy_response import without_openings


def load_previous():
    root = pathlib.Path(subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=APP, text=True).strip())
    package = types.ModuleType('before_door_openings')
    package.__path__ = [str(APP / 'backend/app')]
    sys.modules[package.__name__] = package
    # その他の幾何モジュールは今回変更していない。同じファイルから読み込む。
    for name in ('schemas', 'analysis_cache', 'analyzer'):
        path = (APP / 'backend/app' / (name + '.py')).relative_to(root)
        source = subprocess.check_output(['git', 'show', REFERENCE_COMMIT + ':' + path.as_posix()], cwd=APP, text=True)
        module = types.ModuleType(package.__name__ + '.' + name)
        module.__package__ = package.__name__
        sys.modules[module.__name__] = module
        exec(compile(source, REFERENCE_COMMIT + ':' + str(path), 'exec'), module.__dict__)
        setattr(package, name, module)
    return package


def main():
    before = load_previous()
    data = json.loads((APP / 'sample/sample_mask.json').read_text())
    mask, old_mask = MaskFile.model_validate(data), before.schemas.MaskFile.model_validate(data)
    settings, old_settings = AnalysisSettings(), before.schemas.AnalysisSettings()
    raw = analyzer.analyze(mask, AnalysisSettings(door_opening_depth_m=0))
    assert without_openings(raw.model_dump()) == before.analyzer.analyze(old_mask, old_settings).model_dump()
    print('depth=0: 追加フィールド検証後、補正導入前のコミットと全出力一致')
    reps = int(sys.argv[1]) if len(sys.argv) > 1 else 101
    timings = {'before': [], 'after': []}
    for i in range(reps):
        for key in (('before', 'after') if i % 2 == 0 else ('after', 'before')):
            engine, source, config = ((before.analyzer, old_mask, old_settings) if key == 'before'
                                      else (analyzer, mask, settings))
            engine.clear_geometry_cache()
            start = time.perf_counter_ns()
            engine.analyze(source, config)
            timings[key].append((time.perf_counter_ns() - start) / 1e6)
    medians = {key: statistics.median(values) for key, values in timings.items()}
    ratio = medians['after'] / medians['before']
    print('Python: ' + sys.version.split()[0])
    print(f'cold / 交互 {reps} 回 / 中央値: 作業前 {medians["before"]:.3f} ms → 補正あり {medians["after"]:.3f} ms ({(ratio - 1) * 100:+.2f}%)')
    for room in analyzer.analyze(mask).rooms:
        print(f'{room.name}: {room.floor_area_raw_m2:.9f} / {room.door_opening_adjustment_m2:+.9f} / {room.floor_area_m2:.9f}')
    assert ratio < 1.1, '初回解析の遅延が10%以上'


if __name__ == '__main__':
    main()
