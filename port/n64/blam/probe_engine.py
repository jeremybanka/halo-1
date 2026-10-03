#!/usr/bin/env python3
"""Probe unmodified Blam translation units with the actual N64 cross compiler.

This diagnoses an engine port; it is not an N64 build of the whole engine.
Logs and object files live in ignored build/n64/blam-probe.
"""
import argparse
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
SOURCES = [
    'source/math/random_math.c',
    'source/game/game_time.c',
    'source/memory/data.c',
    'source/models/model_animations.c',
    'source/objects/objects.c',
    'source/rasterizer/rasterizer.c',
    'source/sound/sound_dsound_xbox.c',
]

ENTRIES = ['seed_random', 'game_time_update', 'data_new', 'animation_get_node_orientations',
           'objects_update', 'rasterizer_frame_begin', 'platform_sound_dsound']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk', type=Path, default=os.environ.get('N64_INST', ROOT.parent/'n64-2048/.build/libdragon'))
    args = parser.parse_args()
    sdk = args.sdk.resolve()
    compiler = sdk/'bin/mips64-elf-gcc'
    out = ROOT/'build/n64/blam-probe'
    out.mkdir(parents=True, exist_ok=True)
    game = json.loads((ROOT/'port/linux/port.json').read_text())['game']
    # Case-insensitive macOS makes Linux's StdDef.h -> stddef.h alias recurse.
    # Copy only the portable declaration shims; use the N64 C runtime itself.
    compat = out/'include'
    compat.mkdir(exist_ok=True)
    (compat/'StdDef.h').write_text('#include_next <stddef.h>\n')
    for name in ['excpt.h', 'halo_port_limits.h', 'halo_port_capacity.h', 'halo_ui_pointer.h']:
        shutil.copy2(ROOT/'port/linux/include'/name, compat/name)
    semantics = out/'semantics.h'
    subprocess.run([sys.executable, 'tools/linux_msvc_semantics.py', '--output', str(semantics),
                    '--tags', 'source'], cwd=ROOT, check=True)
    base = [str(compiler), '-march=vr4300', '-mtune=vr4300', '-mabi=o64', '-EB',
            '-O2', '-ffunction-sections', '-fdata-sections', '-std=gnu89', '-fshort-wchar', '-fcommon', '-fno-strict-aliasing',
            '-fwrapv', '-fms-extensions', '-ffp-contract=off', '-D__STRICT_ANSI__',
            '-DDEBUG', '-Dxbox', '-DM_PI=3.14159265358979323846', '-fmax-errors=8',
            '-D__stdcall=', '-D__cdecl=', '-D__fastcall=', '-D__export=',
            '-D__declspec(x)=', '-D__int64=long long',
            '-D__int32=int', '-D__int16=short', '-D__int8=char', '-D__forceinline=inline', '-D_inline=inline',
            '-include', str(compat/'halo_port_limits.h'), '-include', str(semantics),
            '-I'+str(compat), '-I'+str(sdk/'mips64-elf/include'), '-Iport/include',
            '-Iport/include/xdk', *('-I'+x for x in game['include_dirs'])]
    results = []
    for source, entry in zip(SOURCES, ENTRIES):
        command = [*base, '-c', source, '-o', str(out/(Path(source).stem+'.o'))]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        log = out/(Path(source).stem+'.log')
        log.write_text('COMMAND (JSON argv)\n'+json.dumps(command)+'\n\n'+result.stdout+result.stderr)
        first = next((x for x in result.stderr.splitlines() if 'error:' in x), '')
        undefined = []
        if result.returncode == 0:
            retained = out/(Path(source).stem+'-retained.o')
            subprocess.run([str(sdk/'bin/mips64-elf-ld'), '-r', '--gc-sections', '-u', entry,
                            str(out/(Path(source).stem+'.o')), '-o', str(retained)], check=True)
            nm = subprocess.check_output([str(sdk/'bin/mips64-elf-nm'), '-u', str(retained)], text=True)
            undefined = [line.split()[-1] for line in nm.splitlines() if line.strip()]
            relocations = subprocess.check_output([str(sdk/'bin/mips64-elf-readelf'), '-rW',
                                                   str(retained)], text=True)
            referenced = {line.split()[4] for line in relocations.splitlines()
                          if 'R_MIPS_' in line and len(line.split()) >= 5}
            undefined = [name for name in undefined if name in referenced]
        results.append({'source': source, 'entry': entry, 'success': result.returncode == 0,
                        'first_error': first, 'undefined_symbols': undefined, 'log': str(log.relative_to(ROOT))})
    report = {
        'compiler': subprocess.check_output([str(compiler),'--version'], text=True).splitlines()[0],
        'target': 'vr4300, o64, big-endian, 32-bit pointers and long',
        'scope': 'Representative sources, existing XDK/limits declarations plus StdDef/MSVC spelling adapters; no source patched.',
        'results': results,
        'memory_constants': {
            'native_game_state_bytes': 0xFC0000+0x40000,
            'tag_cache_bytes': 0x1600000,
            'texture_cache_bytes': 0x1600000,
            'sound_cache_bytes': 0x400000,
            'sum_bytes': 0x1000000+0x1600000*2+0x400000,
            'n64_expansion_ram_bytes': 8*1024*1024,
        },
    }
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
