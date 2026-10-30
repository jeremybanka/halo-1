"""Isolated diagnostic builds and bounded, serial native captures."""
import argparse,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
OUT=ROOT/'build/vehicle-costs';PYTHON=ROOT/'build/n64-python/bin/python'
BASE=[str(PYTHON),'port/n64/build.py','--pve-squad','--pve-crunch','--pve-roster','--pve-jackal-shields',
      '--pve-model-bank','build/pve-vehicles/bank','--enemy-vehicle-bank','build/pve-vehicles/bank',
      '--map-bank-override','build/pve/ground/bloodgulch.map64','--profile','--collision-profile','--pve-prep-profile',
      '--vehicle-cost-audit','--sdk','/Users/jem/dojo/n64-2048/.build/libdragon',
      '--tiny3d','/Users/jem/dojo/halo-1/build/n64-sidewinder-throughput/tiny3d-unlit']
CASES={f'live-{f}-{p}':['--pve-qa',str(f),'--pve-players',str(p)] for f in (8,9) for p in (1,4)}
CASES['live-shot-8-4']=CASES['live-8-4']
for tick in (1,60,180):CASES[f'photo-{tick}']=['--pve-qa','8','--pve-players','4','--pve-photo-tick',str(tick)]
CASES['timing-60']=CASES['photo-60']+['--gpu-diagnostic']
CASES['empty-60']=CASES['timing-60']+['--gpu-empty-scissor']

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['build','capture']);p.add_argument('cases',nargs='*');a=p.parse_args()
    OUT.mkdir(exist_ok=True)
    for name in a.cases or CASES:
        assert name in CASES,name
        if a.action=='build':
            with (OUT/(name+'-build.log')).open('w') as log:
                subprocess.run(BASE+CASES[name]+['--output-dir',str(OUT/name)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
            print('Built',name,flush=True)
        else:
            photo=not name.startswith('live-');script=HERE.parent/('covenant-models' if photo else 'firefight-performance')/'capture.py'
            subprocess.run([str(PYTHON),str(script),str(next((OUT/name).glob('*.z64'))),str(ROOT/'build/pve-vehicles/ares.bml'),
                            str(OUT/(name+'-native.log')),*(['--frames','9'] if photo else ['--observations','45'])],cwd=ROOT,check=True)
if __name__=='__main__':main()
