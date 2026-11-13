#!/usr/bin/env python3
"""Build a zoom allocation fixture; run through tools/workspace.py run."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'port/n64'))
from build import parse_args
from build_inputs import enemy_bank


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fixture',choices=('onslaught','gauntlet','crowded','jackals','pressure-frontend','combat-onslaught','combat-gauntlet'),required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--logging',action='store_true',help='Also package a Blood Gulch-only image below the Ares ISViewer limit')
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    if (out/'logging').exists():p.error('Choose a fresh output directory')
    bank=enemy_bank(ROOT/'halo64-assets',out/'enemy-bank',json.loads((ROOT/'halo64-assets/assets/build-inputs/pr18/manifest.json').read_text()))
    (out/'scratch').mkdir(exist_ok=True)
    mode=(['--firefight-qa','3','--telemetry','--rspq-buffer-kib','32'] if a.fixture=='pressure-frontend' else
        ['--profile','--pve-squad','--pve-players','3','--pve-qa','3'])
    flags=['--preset','release',*mode,
        '--pve-model-bank',str(bank),'--pve-crunch','--pve-roster','--pve-jackal-shields',
        '--enemy-vehicle-bank',str(bank),'--vehicle-distance-lods',
        '--game-source',str(HERE/(a.fixture+'.c')),'--output-dir',str(out/'rom')]
    subprocess.run([sys.executable,str(ROOT/'port/n64/build.py'),*flags],cwd=ROOT,
        env={**os.environ,'TMPDIR':str(out/'scratch')},check=True)
    if not a.logging:return
    sdk=parse_args(flags).sdk.resolve()/'bin'
    target=out/'logging';stage=target/'frontend-files';stage.mkdir(parents=True)
    for source in (out/'rom/frontend-files').iterdir():
        if source.is_dir():
            assert source.name=='maps';(stage/source.name).mkdir()
            for m in source.iterdir():
                if m.name.startswith('bloodgulch'):(stage/source.name/m.name).symlink_to(m.resolve())
        else:(stage/source.name).symlink_to(source.resolve())
    stripped=next((out/'rom').glob('*.stripped'));sym=stripped.with_suffix('.sym')
    rom=target/stripped.with_suffix('.z64').name
    for command in [
        [sdk/'mkdfs',target/'frontend.dfs',stage],
        [sdk/'n64tool','--title','HALO 64 ZOOM QA','--toc','--output',rom,
            '--align','256',stripped,'--align','8',sym,'--align','16',target/'frontend.dfs'],
        [sdk/'ed64romconfig','--savetype','none','--regionfree','--controller1','n64',
            '--controller2','n64','--controller3','n64','--controller4','n64',rom],
    ]:subprocess.run(list(map(str,command)),check=True)
    assert rom.stat().st_size<64*1024*1024,'ISViewer logging image must stay below 64 MiB'
    (target/'diagnostic.json').write_text(json.dumps({
        'purpose':'Same executable and Blood Gulch inputs; other map filesystem payloads omitted for ISViewer logging only',
        'fixture':a.fixture,'stripped_sha256':hashlib.sha256(stripped.read_bytes()).hexdigest(),
        'rom':str(rom),'rom_sha256':hashlib.sha256(rom.read_bytes()).hexdigest(),
    },indent=2)+'\n')
    print('Logging ROM:',rom)


if __name__=='__main__':main()
