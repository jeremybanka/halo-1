#!/usr/bin/env python3
"""Build the standalone N64 demake with an installed libdragon/Tiny3D SDK."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk', type=Path, default=os.environ.get('N64_INST', ROOT.parent/'n64-2048/.build/libdragon'))
    parser.add_argument('--tiny3d', type=Path, default=os.environ.get('TINY3D_DIR', ROOT.parent/'n64-3d-splitscreen/.build/tiny3d'))
    parser.add_argument('--validate', action='store_true')
    parser.add_argument('--profile', action='store_true', help='Show N64 frame timing and memory counters')
    parser.add_argument('--demo', action='store_true', help='Build a separately labeled deterministic replay ROM')
    args = parser.parse_args()
    sdk, tiny = args.sdk.resolve(), args.tiny3d.resolve()
    out = ROOT/'build/n64'
    out.mkdir(parents=True, exist_ok=True)
    if not (out/'generated/render_data.c').exists():
        parser.error('Generate local assets first; see port/n64/README.md')
    if not (sdk/'bin/mips64-elf-gcc').exists() or not (tiny/'build/libt3d.a').exists():
        parser.error('Supply --sdk and --tiny3d paths to installed libdragon and built Tiny3D')

    def run(command):
        subprocess.run([str(x) for x in command], check=True, cwd=ROOT,
                       env={**os.environ, 'N64_INST': str(sdk)})

    objects = []
    sources = ['main.c', 'game.c', 'hud.c', 'sound.c', 'replay.c', 'blam/runtime.c']
    generated = ['render_data.c', 'collision_data.c', 'models_data.c', 'audio_data.c', 'hud_data.c', 'firstperson_data.c']
    for source in [*(ROOT/'port/n64'/name for name in sources), *(out/'generated'/name for name in generated)]:
        obj = out/(source.stem+'.o')
        objects.append(obj)
        run([sdk/'bin/mips64-elf-gcc', '-c', source, '-o', obj,
             '-march=vr4300', '-mtune=vr4300', '-mabi=o64', '-O2', '-g', '-std=gnu17',
             '-falign-functions=32', '-ffunction-sections', '-fdata-sections',
             '-ffast-math', '-ftrapping-math', '-fno-associative-math', '-DN64',
             '-Wall', '-Wextra', '-Werror', '-ftrivial-auto-var-init=pattern',
             '-I'+str(sdk/'mips64-elf/include'), '-I'+str(tiny/'src'), '-I'+str(ROOT/'port/n64'),
             *(['-DRDPQ_VALIDATE'] if args.validate else []),
             *(['-DBG_DEMO'] if args.demo else []),
             *(['-DBG_PROFILE'] if args.profile else []),
             *(['-fno-fast-math', '-ffp-contract=off'] if source.name == 'runtime.c' else [])])
    elf = out/('halo-blood-gulch-replay.elf' if args.demo else 'halo-blood-gulch.elf')
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
