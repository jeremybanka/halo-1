"""Check quiet VI build isolation without building a ROM.

The CLI tests execute the real build argument handling against temporary dummy
SDK files; subprocess calls are captured, never executed. Optional target
preprocessing verifies the quiet mode's render/audio/presentation helpers are
identical to the paced release, and all legacy configurations remain unchanged.
"""
import argparse
import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_render_matrix import compact, function

ROOT = Path(__file__).resolve().parents[2]


def load_builder():
    spec = importlib.util.spec_from_file_location('n64_builder', ROOT / 'port/n64/build.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class QuietBuild(unittest.TestCase):
    def build(self, flags):
        builder = load_builder()
        with contextlib.redirect_stderr(io.StringIO()):
            args=builder.parse_args(flags)
        sdk,tiny=Path('/dummy/sdk'),Path('/dummy/tiny')
        compiles=[[str(sdk/'bin/mips64-elf-gcc'),*builder.compile_options(args,sdk,tiny,Path('/dummy/out'),Path(name))]
                  for name in ('main.c','scene.c','presentation.c','runtime.c','vehicle_physics.c')]
        return [*compiles,['n64tool','--output',builder.rom_name(args)+'.z64']]

    def test_quiet_unpaced(self):
        calls = self.build(['--vi-benchmark'])
        compiles = [c for c in calls if Path(c[0]).name == 'mips64-elf-gcc']
        self.assertTrue(compiles)
        for c in compiles:
            self.assertIn('-DBG_VI_BENCHMARK', c)
            self.assertIn('-DBG_DEMO', c)
            for forbidden in ('-DBG_PROFILE', '-DBG_BENCHMARK', '-DBG_PACED30', '-DRDPQ_VALIDATE'):
                self.assertNotIn(forbidden, c)
        rom = next(c for c in calls if Path(c[0]).name == 'n64tool')
        self.assertEqual(Path(rom[rom.index('--output') + 1]).name,
                         'halo-blood-gulch-replay-vi-benchmark.z64')

    def test_quiet_paced(self):
        calls = self.build(['--vi-benchmark', '--paced30'])
        compile = next(c for c in calls if Path(c[0]).name == 'mips64-elf-gcc')
        self.assertIn('-DBG_PACED30', compile)
        self.assertNotIn('-DBG_PROFILE', compile)
        rom = next(c for c in calls if Path(c[0]).name == 'n64tool')
        self.assertEqual(Path(rom[rom.index('--output') + 1]).name,
                         'halo-blood-gulch-replay-vi-benchmark-paced30.z64')

    def test_legacy_benchmark(self):
        calls = self.build(['--benchmark', '--paced30'])
        compile = next(c for c in calls if Path(c[0]).name == 'mips64-elf-gcc')
        for flag in ('-DBG_PROFILE', '-DBG_BENCHMARK', '-DBG_DEMO', '-DBG_PACED30'):
            self.assertIn(flag, compile)
        self.assertNotIn('-DBG_VI_BENCHMARK', compile)
        rom = next(c for c in calls if Path(c[0]).name == 'n64tool')
        self.assertEqual(Path(rom[rom.index('--output') + 1]).name,
                         'halo-blood-gulch-replay-benchmark-paced30.z64')

    def test_extra_surfaces_are_explicit(self):
        for buffers in (3, 4, 5):
            calls = self.build(['--vi-benchmark', '--paced30', '--paced30-buffers', str(buffers)])
            compile = next(c for c in calls if Path(c[0]).name == 'mips64-elf-gcc')
            self.assertEqual(f'-DBG_PACED30_BUFFERS={buffers}' in compile, buffers > 3)
            rom = next(c for c in calls if Path(c[0]).name == 'n64tool')
            suffix = f'-buffers{buffers}' if buffers > 3 else ''
            self.assertEqual(Path(rom[rom.index('--output') + 1]).name,
                             'halo-blood-gulch-replay-vi-benchmark-paced30' + suffix + '.z64')
        for buffers in (2, 3, 4, 5, 6):
            with self.subTest(buffers=buffers), self.assertRaises(SystemExit):
                self.build(['--paced30-buffers', str(buffers)])
        for buffers in (2, 6):
            with self.subTest(buffers=buffers), self.assertRaises(SystemExit):
                self.build(['--paced30', '--paced30-buffers', str(buffers)])

    def test_snapshot_ignores_presentation_experiment(self):
        for buffers in (4, 5):
            calls = self.build(['--snapshot-tick', '1148', '--paced30', '--paced30-buffers', str(buffers)])
            compile = next(c for c in calls if Path(c[0]).name == 'mips64-elf-gcc')
            self.assertNotIn('-DBG_PACED30', compile)
            self.assertNotIn(f'-DBG_PACED30_BUFFERS={buffers}', compile)
            rom = next(c for c in calls if Path(c[0]).name == 'n64tool')
            self.assertEqual(Path(rom[rom.index('--output') + 1]).name,
                             'halo-blood-gulch-snapshot-1148.z64')

    def test_quiet_rejects_instrumented_or_different_scenes(self):
        for flags in (['--benchmark'], ['--profile'], ['--validate'], ['--gpu-diagnostic'],
                      ['--showcase', 'banshee'], ['--snapshot-tick', '75']):
            with self.subTest(flags=flags), self.assertRaises(SystemExit) as raised:
                self.build(['--vi-benchmark', *flags])
            self.assertEqual(raised.exception.code, 2)


def check_preprocessed(sdk, tiny, before=None):
    gcc = sdk / 'bin/mips64-elf-gcc'
    common = [str(gcc), '-E', '-P', '-std=gnu17', '-DN64', '-DBG_RSPQ_OVERRIDE',
              '-I' + str(sdk / 'mips64-elf/include'), '-I' + str(tiny / 'src'),
              '-I' + str(ROOT / 'port/n64'), '-I' + str(ROOT / 'build/n64/blam-core')]

    def preprocess(path, flags):
        from runtime_source import RUNTIME_UNITS
        paths=[path.parent/name for name in RUNTIME_UNITS if name.endswith('.c')] if path.name=='main.c' and (path.parent/'scene.c').exists() else [path]
        outputs=[subprocess.run([*common,*['-D'+flag for flag in flags],str(unit)],capture_output=True,text=True,check=True).stdout for unit in paths]
        result=type('Result',(),{'stdout':'\n'.join(outputs)})()
        # Assert diagnostics embed source paths and line numbers. They affect
        # no successful execution and are the sole normalization here.
        import re
        return re.sub(r'"[^"\n]*main(?:-before)?\.c"\s*,\s*\d+\s*,',
                      '"MAIN_SOURCE",0,', result.stdout)

    main = ROOT / 'port/n64/main.c'
    release = preprocess(main, ['BG_DEMO', 'BG_PACED30'])
    quiet = preprocess(main, ['BG_DEMO', 'BG_PACED30', 'BG_VI_BENCHMARK'])
    helpers = ('pump_audio', 'paced_acquire', 'prepare_frame', 'prepare_view', 'draw_view',
               'frame_complete', 'frame_present', 'bg_presentation_mode', 'paced_vi',
               'animate_mesh', 'prepare_vehicle', 'input')
    for name in helpers:
        assert compact(function(release, name)) == compact(function(quiet, name)), name
    for buffers in (3, 4, 5):
        flags = ['BG_DEMO', 'BG_PACED30', f'BG_PACED30_BUFFERS={buffers}']
        rel = preprocess(main, flags)
        measured = preprocess(main, flags + ['BG_VI_BENCHMARK'])
        for name in helpers:
            assert compact(function(rel, name)) == compact(function(measured, name)), (buffers, name)
    for name in ('bg_benchmark_add', 'benchmark_origin', 'completed_cadence', 'completed_tail',
                 'audio_pump_previous', 'audio_pump_max_gap', 'category_triangles',
                 'submitted_vertices', 'profile_frame_summary', 'bg_rspq_get_metrics(&'):
        assert name not in quiet, 'Unexpected full profiler work: ' + name
    for text in ('REPLAY %u FPS', 'PERF views=', 'PHASE camera='):
        assert text not in quiet, 'Live diagnostic output: ' + text
    body = compact(function(quiet, 'main'))
    assert 'if(bg_vi_complete(bg_presentation_meter()))benchmark_results(screen);' in body
    results = compact(function(quiet, 'benchmark_results'))
    assert 'bg_presentation_finish_metrics();' in results
    assert 'bg_cadence_finish(&visible_meter.fresh);' in compact(function(quiet,'bg_presentation_finish_metrics'))
    assert 'benchmark_vi_page(screen);' in results
    assert 'benchmark_page(' not in results and 'benchmark_tail_page(' not in results
    assert 'register_VI_handler(observe_vi);' in compact(function(quiet,'bg_presentation_observer_init'))
    assert 'register_VI_handler(paced_vi);' in compact(function(quiet,'bg_presentation_paced_init'))
    assert body.index('bg_presentation_observer_init();') < body.index('display_init(')
    assert body.index('display_init(') < body.index('bg_presentation_paced_init();')
    if before:
        for flags in ([], ['BG_PACED30'], ['BG_DEMO'],
                      ['BG_DEMO', 'BG_BENCHMARK'], ['BG_DEMO', 'BG_BENCHMARK', 'BG_PACED30']):
            assert compact(preprocess(before, flags)) == compact(preprocess(main, flags)), flags
    print(f'PASS: {len(helpers)} quiet/release helpers identical; no profile instrumentation or live '
          'diagnostic output; VI-only stop/report and handler ordering verified.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preprocess', action='store_true')
    parser.add_argument('--sdk', type=Path, default=ROOT.parent / 'n64-2048/.build/libdragon')
    parser.add_argument('--tiny3d', type=Path, default=ROOT.parent / 'n64-3d-splitscreen/.build/tiny3d')
    parser.add_argument('--before', type=Path)
    args, remaining = parser.parse_known_args()
    if args.preprocess:
        check_preprocessed(args.sdk, args.tiny3d, args.before)
    else:
        unittest.main(argv=[sys.argv[0], *remaining])
