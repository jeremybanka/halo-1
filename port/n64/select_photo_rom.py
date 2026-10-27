"""Repack only a one-byte photo selector; preserve compiled code and map bank."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

def select(directory,index):
    manifest_path=next(directory.glob('*.build.json'));manifest=json.loads(manifest_path.read_text())
    rom=Path(manifest['rom']['path']);sdk=Path(manifest['options']['sdk']).resolve()
    (directory/'frontend-files/photo-index.bin').write_bytes(bytes([index]))
    subprocess.run([str(sdk/'bin/mkdfs'),str(directory/'frontend.dfs'),str(directory/'frontend-files')],check=True,stdout=subprocess.DEVNULL)
    subprocess.run([str(sdk/'bin/n64tool'),'--title','HALO 64','--toc','--output',str(rom),
        '--align','256',str(rom.with_suffix('.stripped')),'--align','8',str(rom.with_suffix('.sym')),
        '--align','16',str(directory/'frontend.dfs')],check=True,stdout=subprocess.DEVNULL)
    subprocess.run([str(sdk/'bin/ed64romconfig'),'--savetype','none','--regionfree',
        '--controller1','n64','--controller2','n64','--controller3','n64','--controller4','n64',str(rom)],check=True,stdout=subprocess.DEVNULL)
    record={'photo':index,'rom_sha256':hashlib.sha256(rom.read_bytes()).hexdigest(),'rom_path':str(rom),'compiled_source_sha256':manifest['sources'][str(directory/'main.c')],
        'selector':index,'render_bank_experiment':manifest['render_bank_experiment']}
    (directory/f'photo-{index:02}.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('index',type=int,choices=range(24));a=p.parse_args();select(a.directory.resolve(),a.index)
