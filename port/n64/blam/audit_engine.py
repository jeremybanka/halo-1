#!/usr/bin/env python3
"""Compile the real engine tree for VR4300 and inspect a retained engine link.

This is an architectural audit, not a ROM build. It never supplies fake game
implementations to satisfy undefined symbols. All output remains in build/.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]


def boundaries(symbols,sdk):
    """Classify dependencies without supplying fake definitions for them."""
    common=set(re.findall(r'(?m)^HALO_COMMON\((\w+),',(ROOT/'port/linux/src/halo_linker_common.c').read_text()))
    libraries=[sdk/'mips64-elf/lib/libc.a',sdk/'mips64-elf/lib/libm.a',
               Path(subprocess.check_output([str(sdk/'bin/mips64-elf-gcc'),'-mabi=o64','-print-libgcc-file-name'],text=True).strip())]
    supplied=set()
    for library in libraries:
        output=subprocess.check_output([str(sdk/'bin/mips64-elf-nm'),'-g','--defined-only',str(library)],text=True,stderr=subprocess.DEVNULL)
        supplied.update(line.split()[-1] for line in output.splitlines() if len(line.split())>=3)
    groups={}
    for symbol in symbols:
        name=symbol['name']
        if name in common:kind='reconstructed_common_storage'
        elif name.startswith(('D3D','blur_shader','pixel_shader','regular_shader')):kind='xbox_graphics'
        elif name.startswith(('DirectSound','IDirectSound')):kind='xbox_audio'
        elif name.startswith(('Bink','RADSetMemory')):kind='bink_video'
        elif name.startswith(('network_distributed_','network_objects_','network_damage_','distributed_player_','p2p_')):kind='native_port_network_hooks'
        elif name.startswith(('render_interpolation_','halo_','hud_hires_','pal_tags_','text_hires_')):kind='native_port_presentation_hooks'
        elif name in supplied:kind='sdk_library_symbol_available_abi_not_proven'
        elif name.startswith(('X','WSA','__WSA')) or name in {'accept','bind','closesocket','connect','getpeername','getsockname','getsockopt','ioctlsocket','listen','recv','recvfrom','select','send','sendto','setsockopt','socket'}:kind='xbox_devices_network_saves'
        else:kind='os_crt_or_remaining_engine_boundary'
        groups.setdefault(kind,[]).append(name)
    return {name:{'count':len(values),'symbols':values} for name,values in sorted(groups.items())}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk',type=Path,default=os.environ.get('N64_INST',ROOT.parent/'n64-2048/.build/libdragon'))
    parser.add_argument('--jobs',type=int,default=2)
    parser.add_argument('--output',type=Path,default=ROOT/'build/n64/blam-engine-audit')
    parser.add_argument('--root',action='append',help='Retained original entrypoint; repeat to replace the default game roots')
    args=parser.parse_args();sdk=args.sdk.resolve();out=args.output.resolve()
    out.mkdir(parents=True,exist_ok=True);compat=out/'include';compat.mkdir(exist_ok=True)
    (compat/'StdDef.h').write_text('#include_next <stddef.h>\n')
    for name in ('excpt.h','halo_port_limits.h','halo_port_capacity.h','halo_ui_pointer.h'):
        shutil.copy2(ROOT/'port/linux/include'/name,compat/name)
    semantics=compat/'semantics.h'
    subprocess.run([sys.executable,'tools/linux_msvc_semantics.py','--output',str(semantics),
                    '--tags','source','--inlines','source','--inlines','port/include/xdk','--all-inlines'],cwd=ROOT,check=True)
    # GCC rejects weak linkage on genuinely static inline functions. Unlike
    # the public MSVC COMDAT definitions, these never need coalescing.
    static_names=set()
    for path in (ROOT/'source').rglob('*'):
        if path.suffix in ('.c','.h'):
            static_names.update(re.findall(r'\bstatic\s+(?:__inline|inline|__forceinline)\s+[^;{}()]*?\b(\w+)\s*\([^;{}]*\)\s*\{',path.read_text(errors='replace')))
    semantics.write_text('\n'.join(line for line in semantics.read_text().splitlines()
                                  if not (line.startswith('#pragma weak ') and line.split()[-1] in static_names))+'\n')
    prefix=compat/'audit_prefix.h'
    prefix.write_text('''#include <wchar.h>
#include "halo_ui_pointer.h"
wchar_t *halo_xbox_wcstok(wchar_t *text,const wchar_t *delimiters);
#define wcstok(text,delimiters) halo_xbox_wcstok(text,delimiters)
#define rasterizer_debug_drawing_begin(opaque,...) (rasterizer_debug_drawing_begin)(opaque)
''')
    manifest=json.loads((ROOT/'port/linux/port.json').read_text());game=manifest['game']
    excluded=set(game['exclude'])
    sources=[p for p in sorted((ROOT/'source').rglob('*.c')) if str(p.relative_to(ROOT)) not in excluded]
    base=[str(sdk/'bin/mips64-elf-gcc'),'-march=vr4300','-mtune=vr4300','-mabi=o64','-EB',
          '-O2','-ffunction-sections','-fdata-sections','-std=gnu89','-fshort-wchar','-fcommon',
          '-fno-strict-aliasing','-fwrapv','-fms-extensions','-ffp-contract=off',
          '-D__STRICT_ANSI__','-DDEBUG','-Dxbox','-DM_PI=3.14159265358979323846','-fmax-errors=8',
          '-D__stdcall=','-D__cdecl=','-D__fastcall=','-D__export=','-D__declspec(x)=',
          '-D__int64=long long','-D__int32=int','-D__int16=short','-D__int8=char',
          '-D__forceinline=inline','-D_inline=inline',
          '-DDECLSPEC_SELECTANY=__attribute__((weak))','-DFD_SETSIZE=256','-DCW_DEFAULT=0x9001f',
          '-D__try=if(1)','-D__except(x)=else if(0)','-DO_BINARY=0','-D_stat=stat','-D_fstat=fstat',
          '-include',str(compat/'halo_port_limits.h'),'-include',str(semantics),'-include',str(prefix),
          '-I'+str(compat),'-I'+str(sdk/'mips64-elf/include'),'-Iport/include','-Iport/include/xdk',
          *('-I'+p for p in game['include_dirs'])]
    def compile_one(source):
        relative=source.relative_to(ROOT);obj=out/'objects'/relative.with_suffix('.o')
        obj.parent.mkdir(parents=True,exist_ok=True)
        compile_path=relative
        if relative.as_posix()=='source/memory/byte_swapping.c':
            compile_path=out/'byte_swapping.c'
            # GCC does not accept MSVC's ui64 literal suffix. Values unchanged.
            compile_path.write_text(re.sub(r'(0x[0-9a-fA-F]+)ui64',r'\1ULL',source.read_text()))
        command=[*base,'-c',str(compile_path),'-o',str(obj)]
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
        log=obj.with_suffix('.log');log.write_text(json.dumps(command)+'\n'+result.stdout+result.stderr)
        errors=[line for line in result.stderr.splitlines() if 'error:' in line or 'Error:' in line]
        return {'source':str(relative),'object':str(obj),'success':result.returncode==0,
                'errors':errors,'log':str(log.relative_to(ROOT))}
    results=[]
    with ThreadPoolExecutor(max_workers=max(1,args.jobs)) as executor:
        jobs=[executor.submit(compile_one,p) for p in sources]
        for future in as_completed(jobs):
            results.append(future.result())
            if len(results)%50==0:print(f'Compiled {len(results)}/{len(sources)} sources; {sum(r["success"] for r in results)} passed',flush=True)
    results.sort(key=lambda r:r['source'])
    objects=[r['object'] for r in results if r['success']]
    archive=out/'libblam-audit.a'
    if archive.exists():archive.unlink()
    subprocess.run([str(sdk/'bin/mips64-elf-ar'),'rcs',str(archive),*objects],check=True)
    roots=args.root or ['game_initialize','game_initialize_for_new_map','game_tick','game_frame']
    retained=out/'engine-retained.o'
    command=[str(sdk/'bin/mips64-elf-ld'),'-r','--gc-sections',*(x for root in roots for x in ('-u',root)),
             str(archive),'-o',str(retained)]
    link=subprocess.run(command,capture_output=True,text=True)
    (out/'link.log').write_text(json.dumps(command)+'\n'+link.stdout+link.stderr)
    undefined=[]
    size=None
    if link.returncode==0:
        nm=subprocess.check_output([str(sdk/'bin/mips64-elf-nm'),'-u',str(retained)],text=True)
        relocation=subprocess.check_output([str(sdk/'bin/mips64-elf-readelf'),'-rW',str(retained)],text=True)
        referenced={line.split()[4] for line in relocation.splitlines() if 'R_MIPS_' in line and len(line.split())>=5}
        undefined=[{'name':line.split()[-1],'binding':line.split()[0]} for line in nm.splitlines()
                   if line.strip() and line.split()[-1] in referenced]
        values=subprocess.check_output([str(sdk/'bin/mips64-elf-size'),str(retained)],text=True).splitlines()[1].split()
        size=dict(zip(('text','data','bss'),map(int,values[:3])))
    report={'target':'VR4300/O64 big-endian','source_count':len(sources),'compiled_count':len(objects),
            'scope':'Original engine C sources, existing native capacity declarations, MSVC declaration adapters and ui64 literal spelling conversion; no platform implementations or stubs',
            'roots':roots,'partial_link_success':link.returncode==0,'undefined_referenced_symbols':undefined,
            'retained_bytes':size,'boundaries':boundaries(undefined,sdk),
            'results':results}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='results'},indent=2))


if __name__=='__main__':main()
