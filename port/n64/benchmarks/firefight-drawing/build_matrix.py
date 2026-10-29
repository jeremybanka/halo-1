#!/usr/bin/env python3
"""Build fixed-tick four-camera drawing diagnostics against the existing fixtures."""
from pathlib import Path
import concurrent.futures,subprocess,sys
ROOT=Path(__file__).resolve().parents[4]
out=ROOT/'build/firefight-draw-audit';out.mkdir(exist_ok=True)
cases=[('crowded-1',4,1),('crowded-60',4,60),('crowded-180',4,180),('crowded-360',4,360),('opening-360',3,360),('delivery-60',5,60),('delivery-300',5,300),('opening-900',3,900)]
if len(sys.argv)>1:cases=[c for c in cases if c[0] in sys.argv[1:]]
def run(case):
 name,qa,tick=case
 cmd=[sys.executable,str(ROOT/'port/n64/build.py'),'--pve-squad','--pve-players','4','--pve-qa',str(qa),'--pve-photo-tick',str(tick),'--pve-draw-audit','--profile','--pve-model-bank',str(ROOT/'halo64-assets/assets/covenant-model-appraisal/bank'),'--map-bank-override',str(ROOT/'build/pve/ground/bloodgulch.map64'),'--sdk','/Users/jem/dojo/n64-2048/.build/libdragon','--tiny3d','/Users/jem/dojo/halo-1/build/n64-sidewinder-throughput/tiny3d-unlit','--output-dir',str(out/name)]
 with (out/(name+'-build.log')).open('w') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
 print(name,r.returncode,flush=True);return r.returncode
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(run,cases))
if any(codes):raise SystemExit(1)
