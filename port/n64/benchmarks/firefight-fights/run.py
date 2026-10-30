"""Build the playable fights and exercise the actual shell in native Ares."""
import argparse,subprocess,hashlib,json,shutil,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=ROOT/'build/firefight-fights';HERE=Path(__file__).resolve().parent
PYTHON=ROOT/'build/n64-python/bin/python'
BASE=[str(PYTHON),'port/n64/build.py','--firefight','--pve-crunch','--pve-roster','--pve-jackal-shields','--vehicle-distance-lods','--pve-model-bank','build/vehicle-lods/bank','--enemy-vehicle-bank','build/vehicle-lods/bank','--map-bank-override','build/pve/ground/bloodgulch.map64','--sdk','/Users/jem/dojo/n64-2048/.build/libdragon','--tiny3d','/Users/jem/dojo/halo-1/build/n64-sidewinder-throughput/tiny3d-unlit']
p=argparse.ArgumentParser();p.add_argument('action',choices=['build','capture']);p.add_argument('cases',nargs='*');a=p.parse_args();OUT.mkdir(exist_ok=True,parents=True)
for name in a.cases or (['menu-4','play'] if a.action=='build' else ['menu-4']):
 if a.action=='build':
  args=['--preset','release'] if name=='play' else ['--firefight-qa',name.split('-')[1]]
  with (OUT/(name+'-build.log')).open('w') as log:subprocess.run(BASE+args+['--output-dir',str(OUT/name)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
  m=json.loads(next((OUT/name).glob('*.build.json')).read_text());assert hashlib.sha256(Path(m['rom']['path']).read_bytes()).hexdigest()==m['rom']['sha256']
  (OUT/name/'frontend.dfs').unlink(missing_ok=True)
  for folder in ('objects','frontend-files'):shutil.rmtree(OUT/name/folder,ignore_errors=True)
  for file in (OUT/name).glob('*.stripped'):file.unlink()
  print('Built',name,flush=True)
 else:
  assert name!='play';m=json.loads(next((OUT/name).glob('*.build.json')).read_text());logpath=OUT/(name+'-native.log')
  with logpath.open('w') as log:
   proc=subprocess.Popen(['/Applications/ares.app/Contents/MacOS/ares','--settings-file',str(ROOT/'build/pve-vehicles/ares.bml'),'--no-file-prompt',m['rom']['path']],stdout=log,stderr=subprocess.STDOUT)
   start=time.monotonic();passed=False
   try:
    while proc.poll() is None and time.monotonic()-start<300:
     time.sleep(.5);text=logpath.read_text(errors='replace')
     if 'FIREFIGHT_QA PASS' in text:passed=True;break
     if 'assertion failed' in text.lower() or 'assertf' in text.lower():break
   finally:
    proc.terminate()
    try:proc.wait(timeout=5)
    except subprocess.TimeoutExpired:proc.kill();proc.wait()
  assert passed,logpath
  print('Native menu/launch/restart/quit/PvP PASS',name,flush=True)
