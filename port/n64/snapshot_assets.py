#!/usr/bin/env python3
"""Record the tracked private Halo64 payloads for backup/restore verification."""
import hashlib
import json
from pathlib import Path
import subprocess
import argparse

ROOT=Path(__file__).resolve().parents[2]
BANK=ROOT/'halo64-assets'

def main(output=None):
    paths=subprocess.check_output(['git','-C',str(BANK),'ls-files','-z']).decode().split('\0')
    files=[]
    for name in sorted(paths):
        if not name or name in ('bank-manifest.json','README.md','.gitignore'):
            continue
        p=BANK/name
        if not p.is_file() or p.is_symlink():
            raise RuntimeError('Missing or linked private payload: '+name)
        files.append(dict(path=name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    commit=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
    target=Path(output) if output else BANK/'bank-manifest.json'
    target.write_text(json.dumps(dict(source_commit=commit,files=files,total_bytes=sum(f['bytes'] for f in files)),indent=2)+'\n')
    print('Recorded',len(files),'private payload files')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,help='Stage the manifest in a guarded fresh output before promotion');args=parser.parse_args();main(args.output)
