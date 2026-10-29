"""Native model inspection, menu lifecycle and controller-playable candidate."""
import concurrent.futures,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];out=ROOT/'build/covenant-crunch'
cases=[('photo-before',['--pve-squad','--pve-players','4','--pve-model-qa','--pve-crunch-baseline']),('photo-after',['--pve-squad','--pve-players','4','--pve-model-qa']),('frontend-4',['--firefight-qa','4','--pve-players','4','--validate']),('playable',['--firefight','--preset','release'])]
def build(c):
 name,flags=c
 cmd=[sys.executable,str(ROOT/'port/n64/build.py'),*flags,'--pve-crunch','--pve-model-bank',str(out/'bank'),'--map-bank-override',str(ROOT/'build/pve/ground/bloodgulch.map64'),'--sdk','/Users/jem/dojo/n64-2048/.build/libdragon','--tiny3d','/Users/jem/dojo/halo-1/build/n64-sidewinder-throughput/tiny3d-unlit','--output-dir',str(out/name)]
 with (out/(name+'-build.log')).open('w') as f:r=subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
 print(name,r.returncode,flush=True);return r.returncode
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(build,cases))
if any(codes):raise SystemExit(1)
