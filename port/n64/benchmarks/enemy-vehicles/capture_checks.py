"""Serial bounded native captures. Each helper owns and closes only its Ares."""
import argparse,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=ROOT/'build/pve-vehicles';PY=ROOT/'build/n64-python/bin/python'
p=argparse.ArgumentParser();p.add_argument('--players',type=int,nargs='*',default=[1,2,3,4]);p.add_argument('--fixtures',type=int,nargs='*',default=[8,9]);p.add_argument('--photo',action='store_true');a=p.parse_args()
for fixture in a.fixtures:
 for players in a.players:
  name=f'final-{fixture}-{players}';rom=next((OUT/name).glob('*.z64'))
  subprocess.run([str(PY),'port/n64/benchmarks/firefight-performance/capture.py',str(rom),str(OUT/'ares.bml'),str(OUT/(name+'-native.log')),'--observations','45'],cwd=ROOT,check=True)
  print('Captured',name,flush=True)
if a.photo:
 rom=next((OUT/'final-photo').glob('*.z64'))
 subprocess.run([str(PY),'port/n64/benchmarks/covenant-models/capture.py',str(rom),str(OUT/'ares.bml'),str(OUT/'final-photos-native.log'),'--frames','42'],cwd=ROOT,check=True)
