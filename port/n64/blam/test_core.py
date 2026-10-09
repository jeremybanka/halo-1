#!/usr/bin/env python3
"""Run original Blam core/BSP host sanitizers and link an N64 core test ELF.

This does not build or boot a ROM. A successful target link is not an emulator
execution result; the game ROM's own validation remains a separate step.
"""
import argparse
import os
from pathlib import Path
import subprocess
from prepare_core import prepare
from prepare_collision import prepare as prepare_collision

ROOT=Path(__file__).resolve().parents[3]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sdk',type=Path,default=os.environ.get('N64_INST',ROOT.parent/'n64-2048/.build/libdragon'))
    a=p.parse_args();sdk=a.sdk.resolve();out=ROOT/'build/n64/blam-core'
    prepare(out);prepare_collision(out)
    def run(command):subprocess.run([str(x) for x in command],cwd=ROOT,check=True)
    common=['-std=c17','-O1','-g','-Wall','-Wextra','-Werror','-fno-strict-aliasing','-fwrapv','-ffp-contract=off','-I'+str(out)]
    for module in ('core','collision'):
        flags=['-Wno-multichar','-Wno-unused-function'] if module=='core' else []
        exe=out/('test_'+module)
        run(['cc',*common,*flags,'-fsanitize=address,undefined',f'port/n64/blam/{module}.c',f'port/n64/blam/test_{module}.c','-lm','-o',exe])
        run([exe])
        for source in (f'{module}.c',f'test_{module}.c'):
            run([sdk/'bin/mips64-elf-gcc','-march=vr4300','-mtune=vr4300','-mabi=o64','-EB',
                 *common,*flags,'-ffunction-sections','-fdata-sections','-I'+str(sdk/'mips64-elf/include'),
                 '-c','port/n64/blam/'+source,'-o',out/(Path(source).stem+'.o')])
        elf=out/('test_'+module+'.elf')
        run([sdk/'bin/mips64-elf-g++','-o',elf,out/(module+'.o'),out/('test_'+module+'.o'),'-mabi=o64',
             '-Wl,-L'+str(sdk/'mips64-elf/lib'),'-Wl,-ldragon','-Wl,-lc','-Wl,-lm','-Wl,-ldragonsys',
             '-Wl,-Tn64.ld','-Wl,--gc-sections','-Wl,--wrap,__do_global_ctors'])
        missing=subprocess.check_output([str(sdk/'bin/mips64-elf-nm'),'-u',str(elf)],text=True).strip()
        if missing:raise RuntimeError('Unresolved N64 test symbols: '+missing)
        run([sdk/'bin/mips64-elf-size',elf])
    print('PASS: host sanitizers, original target structure sizes, and fully resolved N64 test ELFs (not booted)')


if __name__=='__main__':main()
