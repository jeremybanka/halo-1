"""Build matched native visual/census, graphics and lifecycle controls."""
import concurrent.futures,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];out=ROOT/'build/covenant-crunch'
cases=[(f'{version}-{name}',version,qa,tick,False) for version in ('baseline','candidate') for name,qa,tick in [('crowded-1',4,1),('crowded-60',4,60),('crowded-180',4,180),('delivery-300',5,300)]]
cases += [(version+'-timing',version,4,60,True) for version in ('baseline','candidate')]
if len(sys.argv)>1:cases=[c for c in cases if c[0] in sys.argv[1:]]
def build(c):
 name,version,qa,tick,gpu=c
 cmd=[sys.executable,str(ROOT/'port/n64/build.py'),'--pve-squad','--pve-players','4','--pve-qa',str(qa),'--pve-photo-tick',str(tick),'--pve-draw-audit','--profile','--pve-crunch','--pve-model-bank',str(out/'bank'),'--map-bank-override',str(ROOT/'build/pve/ground/bloodgulch.map64'),'--sdk','/Users/jem/dojo/n64-2048/.build/libdragon','--tiny3d','/Users/jem/dojo/halo-1/build/n64-sidewinder-throughput/tiny3d-unlit','--output-dir',str(out/'checks'/name)]
 if version=='baseline':cmd+=['--pve-crunch-baseline']
 if gpu:cmd+=['--gpu-diagnostic','--collision-profile']
 (out/'checks').mkdir(exist_ok=True)
 with (out/'checks'/(name+'-build.log')).open('w') as f:r=subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
 print(name,r.returncode,flush=True);return r.returncode
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(build,cases))
if any(codes):raise SystemExit(1)
