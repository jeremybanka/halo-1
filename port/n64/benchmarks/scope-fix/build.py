"""Build the frozen native photo fixture or the playable release."""
import subprocess,sys,os,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=ROOT/'build/scope-fix'
name=sys.argv[1] if len(sys.argv)>1 else 'play'
assert name in ('before','after','play')
OUT.mkdir(parents=True,exist_ok=True)
if name=='before':
 expected=json.loads((Path(__file__).parent/'before-source-sha256.json').read_text())
 for source,sha in expected.items():
  assert hashlib.sha256((ROOT/'port/n64'/source).read_bytes()).hexdigest()==sha,'Restore the preserved baseline in an isolated checkout before rebuilding before: '+source
args=['--firefight','--preset','release'] if name=='play' else ['--pve-squad','--scope-qa']
command=[str(ROOT/'build/n64-python/bin/python'),'port/n64/build.py',*args,'--pve-crunch','--pve-roster','--pve-jackal-shields','--vehicle-distance-lods','--pve-model-bank','build/vehicle-lods/bank','--enemy-vehicle-bank','build/vehicle-lods/bank','--map-bank-override','build/pve/ground/bloodgulch.map64','--sdk','/Users/jem/dojo/n64-2048/.build/libdragon','--tiny3d','/Users/jem/dojo/halo-1/build/n64-sidewinder-throughput/tiny3d-unlit','--output-dir',str(OUT/name)]
with (OUT/(name+'-build.log')).open('w') as log:subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,env={**os.environ,'TMPDIR':'/private/tmp'})
print('Built',name)
