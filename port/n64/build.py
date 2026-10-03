#!/usr/bin/env python3
"""Build the standalone N64 demake with an installed libdragon/Tiny3D SDK."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SHOWCASES = ['banshee', 'frag-double-kill', 'warthog-passenger', 'shotgun-kill',
             'needler-supercombine', 'needler-homing']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk', type=Path, default=os.environ.get('N64_INST', ROOT.parent/'n64-2048/.build/libdragon'))
    parser.add_argument('--tiny3d', type=Path, default=os.environ.get('TINY3D_DIR', ROOT.parent/'n64-3d-splitscreen/.build/tiny3d'))
    parser.add_argument('--validate', action='store_true')
    parser.add_argument('--profile', action='store_true', help='Show N64 frame timing and memory counters')
    parser.add_argument('--benchmark', action='store_true', help='Measure one four-player replay without live debug overlays, then show frame statistics')
    parser.add_argument('--vi-benchmark', action='store_true', help='Quiet four-player replay measuring actual VI presentation only; no CPU/RDP profiling or live debug overlays')
    parser.add_argument('--gpu-diagnostic', action='store_true', help='Serialize RSP/RDP before the HUD to diagnose queue backpressure; not a release FPS measurement')
    parser.add_argument('--guard-band4', action='store_true', help='Test Tiny3D guard-band 4 for four-player viewports; projection and scissor are unchanged')
    parser.add_argument('--paced30', action='store_true', help='Experimental four-view two-retrace FIFO presentation with a two-frame prefill; NTSC/MPAL only, ignored by frozen snapshots')
    parser.add_argument('--paced30-buffers', type=int, choices=[3, 4, 5], help='Display surfaces for --paced30 (default 3); 4/5 are opt-in acquisition/latency experiments with the same two-frame prefill')
    parser.add_argument('--rspq-buffer-kib', type=int, choices=[0, 2, 4, 8, 16, 32], default=16, help='KiB per local low-priority queue buffer (default 16); 2 is the baseline, 0 uses the installed SDK without its source checkout')
    parser.add_argument('--libdragon-source', type=Path, help='Matching libdragon source checkout for the local queue override; defaults to SDK sibling libdragon-src')
    parser.add_argument('--blam-bsp', action='store_true', help='Use original Blam BSP collision; requires an 8 MiB Expansion Pak')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--demo', action='store_true', help='Build a separately labeled deterministic replay ROM')
    mode.add_argument('--showcase', choices=SHOWCASES, help='Build a focused gameplay recording scenario')
    mode.add_argument('--snapshot-tick', type=int, help='QA only: fast-forward exactly N fixed replay ticks, then redraw the frozen four-player scene without overlays')
    args = parser.parse_args()
    if args.paced30_buffers is not None and not args.paced30:
        parser.error('--paced30-buffers requires --paced30')
    args.paced30_buffers = args.paced30_buffers or 3
    if args.snapshot_tick is not None:
        args.paced30 = False
        args.paced30_buffers = 3
        if not 0 <= args.snapshot_tick <= 0xffffffff:
            parser.error('--snapshot-tick must be an unsigned 32-bit tick count')
        if args.benchmark or args.vi_benchmark or args.profile or args.validate or args.gpu_diagnostic:
            parser.error('--snapshot-tick is an overlay-free pixel fixture; benchmark/profile/validation diagnostics must use separate builds')
    if args.gpu_diagnostic and not args.benchmark:
        parser.error('--gpu-diagnostic requires --benchmark')
    if args.vi_benchmark:
        if args.benchmark or args.profile or args.validate or args.gpu_diagnostic or args.showcase:
            parser.error('--vi-benchmark is a quiet four-player replay and cannot combine with benchmark/profile/validation/diagnostic/showcase modes')
        args.demo = True
    if args.benchmark:
        if args.showcase or args.validate:
            parser.error('--benchmark is a four-player replay measurement and cannot combine with --showcase or --validate')
        args.demo = True
    sdk, tiny = args.sdk.resolve(), args.tiny3d.resolve()
    out = ROOT/'build/n64'
    out.mkdir(parents=True, exist_ok=True)
    if not all((out/'generated'/name).exists() for name in ('render_data.c','micro_data.c')):
        parser.error('Generate local assets, including the micro bank, first; see port/n64/README.md and port/n64/MICRO_LODS.md')
    micro_report = out/'generated/micro-report.json'
    if not micro_report.exists():
        parser.error('Missing micro asset provenance; run port/n64/pack_micro_lods.py')
    report = json.loads(micro_report.read_text())
    for name, key in [('models_data.c', 'baseline_c_sha256'),
                      ('model-preview.json', 'baseline_preview_sha256'),
                      ('micro_data.c', 'generated_c_sha256')]:
        if hashlib.sha256((out/'generated'/name).read_bytes()).hexdigest() != report.get(key):
            parser.error('Stale micro bank after model changes; regenerate and pack micro LODs (port/n64/MICRO_LODS.md)')
    ammo_report = out/'generated/firstperson-ammo-report.json'
    if not ammo_report.exists():
        parser.error('Generate the on-weapon ammo displays first: extract_fp_ammo.py, then pack_fp_ammo.py')
    ammo = json.loads(ammo_report.read_text())
    fp_sha = next((value for name, value in ammo.get('inputs', {}).items()
                   if Path(name).name == 'firstperson_data.c'), None)
    for name, expected in [('firstperson_data.c', fp_sha),
                           ('firstperson_ammo_data.c', ammo.get('generated_sha256'))]:
        path = out/'generated'/name
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            parser.error('Stale on-weapon ammo bank; run port/n64/pack_fp_ammo.py after packing first-person models')
    if not (sdk/'bin/mips64-elf-gcc').exists() or not (tiny/'build/libt3d.a').exists():
        parser.error('Supply --sdk and --tiny3d paths to installed libdragon and built Tiny3D')

    def run(command):
        subprocess.run([str(x) for x in command], check=True, cwd=ROOT,
                       env={**os.environ, 'N64_INST': str(sdk)})

    objects = []
    run([sys.executable, ROOT/'port/n64/blam/prepare_core.py'])
    sources = ['main.c', 'game.c', 'hud.c', 'firstperson_ammo.c', 'sound.c', 'sound_mix.c', 'replay.c', 'blam/runtime.c', 'blam/core.c']
    sdk_extra_sources = []
    if args.rspq_buffer_kib:
        sdk_source = (args.libdragon_source or sdk.parent/'libdragon-src').resolve()
        run([sys.executable, ROOT/'port/n64/prepare_rspq.py', '--source', sdk_source,
             '--sdk', sdk, '--output', out/'rspq-override', '--buffer-kib', args.rspq_buffer_kib])
        sdk_extra_sources.append(out/'rspq-override/rspq_override.c')
    if args.showcase:
        sources.append('showcase.c')
    generated = ['render_data.c', 'collision_data.c', 'models_data.c', 'audio_data.c', 'hud_data.c', 'firstperson_data.c', 'firstperson_ammo_data.c', 'micro_data.c']
    if args.blam_bsp:
        if not (out/'generated/blam_collision_data.c').exists():
            parser.error('Export the original BSP first: port/n64/blam/tags/export_collision.py')
        run([sys.executable, ROOT/'port/n64/blam/prepare_collision.py'])
        sources.append('blam/collision.c')
        generated.append('blam_collision_data.c')
    for source in [*(ROOT/'port/n64'/name for name in sources), *(out/'generated'/name for name in generated), *sdk_extra_sources]:
        obj = out/(source.stem+'.o')
        objects.append(obj)
        run([sdk/'bin/mips64-elf-gcc', '-c', source, '-o', obj,
             '-march=vr4300', '-mtune=vr4300', '-mabi=o64', '-O2', '-g', '-std=gnu17',
             '-falign-functions=32', '-ffunction-sections', '-fdata-sections',
             '-ffast-math', '-ftrapping-math', '-fno-associative-math', '-DN64',
             '-Wall', '-Wextra', '-Werror',
             *(['-ftrivial-auto-var-init=pattern'] if args.validate else []),
             '-I'+str(sdk/'mips64-elf/include'), '-I'+str(tiny/'src'), '-I'+str(ROOT/'port/n64'),
             '-I'+str(out/'blam-core'),
             *(['-I'+str(sdk_source/'src'), '-I'+str(sdk_source/'src/rspq'),
                '-ftrivial-auto-var-init=pattern', '-Wno-unused-parameter',
                '-Wno-override-init', '-Wno-sign-compare'] if source.name == 'rspq_override.c' else []),
             *(['-DRDPQ_VALIDATE'] if args.validate else []),
             *(['-DBG_DEMO'] if args.demo else []),
             *(['-DBG_SHOWCASE='+str(SHOWCASES.index(args.showcase))] if args.showcase else []),
             *(['-DBG_SNAPSHOT_TICK='+str(args.snapshot_tick)+'u'] if args.snapshot_tick is not None else []),
             *(['-DBG_PROFILE'] if args.profile or args.benchmark else []),
             *(['-DBG_RSPQ_OVERRIDE'] if args.rspq_buffer_kib else []),
             *(['-DBG_BENCHMARK'] if args.benchmark else []),
             *(['-DBG_VI_BENCHMARK'] if args.vi_benchmark else []),
             *(['-DBG_GPU_DIAGNOSTIC'] if args.gpu_diagnostic else []),
             *(['-DBG_GUARDBAND4'] if args.guard_band4 else []),
             *(['-DBG_PACED30'] if args.paced30 else []),
             *([f'-DBG_PACED30_BUFFERS={args.paced30_buffers}'] if args.paced30_buffers > 3 else []),
             *(['-DBG_BLAM_BSP'] if args.blam_bsp else []),
             *(['-fno-fast-math', '-ffp-contract=off'] if source.name == 'runtime.c' else []),
             *(['-fno-fast-math', '-ffp-contract=off', '-fno-strict-aliasing'] if source.name == 'collision.c' else []),
             *(['-Wno-multichar', '-Wno-unused-function', '-fno-strict-aliasing', '-fwrapv'] if source.name == 'core.c' else [])])
    name = 'halo-blood-gulch-showcase-'+args.showcase if args.showcase else 'halo-blood-gulch-replay' if args.demo else 'halo-blood-gulch'
    if args.snapshot_tick is not None:
        name += '-snapshot-'+str(args.snapshot_tick)
    if args.blam_bsp:
        name += '-blam-bsp'
    if args.vi_benchmark:
        name += '-vi-benchmark'
    elif args.benchmark:
        name += '-benchmark'
        if args.gpu_diagnostic:
            name += '-gpu-diagnostic'
    elif args.validate:
        name += '-validation'
    elif args.profile:
        name += '-profile'
    if args.guard_band4:
        name += '-guard4'
    if args.paced30:
        name += '-paced30'
        if args.paced30_buffers > 3:
            name += f'-buffers{args.paced30_buffers}'
    if args.rspq_buffer_kib != 16:
        name += f'-rspq{args.rspq_buffer_kib}k' if args.rspq_buffer_kib else '-rspq-stock'
    elf = out/(name+'.elf')
    run([sdk/'bin/mips64-elf-g++', '-o', elf, *objects, tiny/'build/libt3d.a', '-lc', '-mabi=o64',
         '-Wl,-g', '-Wl,-L'+str(sdk/'mips64-elf/lib'), '-Wl,-ldragon', '-Wl,-lm', '-Wl,-ldragonsys',
         '-Wl,-Tn64.ld', '-Wl,--gc-sections', '-Wl,--wrap,__do_global_ctors', '-Wl,-Map='+str(elf.with_suffix('.map'))])
    run([sdk/'bin/mips64-elf-size', elf])
    sym = elf.with_suffix('.sym')
    run([sdk/'bin/n64sym', elf, sym])
    stripped = elf.with_suffix('.stripped')
    shutil.copy2(elf, stripped)
    run([sdk/'bin/mips64-elf-strip', '-s', stripped])
    run([sdk/'bin/n64elfcompress', '-o', out, '-c', '1', stripped])
    rom = elf.with_suffix('.z64')
    run([sdk/'bin/n64tool', '--title', 'HALO BLOOD GULCH', '--toc', '--output', rom,
         '--align', '256', stripped, '--align', '8', sym])
    run([sdk/'bin/ed64romconfig', '--savetype', 'none', '--regionfree',
         '--controller1', 'n64', '--controller2', 'n64', '--controller3', 'n64', '--controller4', 'n64', rom])
    print(f'Built {rom} ({rom.stat().st_size:,} bytes)')


if __name__ == '__main__':
    main()
