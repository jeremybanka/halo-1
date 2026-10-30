"""Build/capture identical routes with the pre-symmetry and corrected banks.

Build baseline before applying center_warthog.py to the private world bank.
The candidate uses that corrected bank. All simulation sources stay shared.
"""
import argparse,concurrent.futures,subprocess,sys,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
p=argparse.ArgumentParser();p.add_argument('action',choices=['build','capture']);p.add_argument('version',choices=['baseline','candidate']);p.add_argument('--photos-only',action='store_true');a=p.parse_args()
out=ROOT/'build/covenant-symmetry';version=a.version
bank=ROOT/('halo64-assets/assets/covenant-crunch/bank' if version=='baseline' else 'build/covenant-symmetry/bank')
cases=[('photo-'+version,['--pve-players','4','--pve-model-qa'])]
if not a.photos_only:cases += [(version+'-perf-'+str(n),['--pve-players',str(n),'--pve-qa','4','--profile','--collision-profile','--pve-prep-profile']) for n in range(1,5)]
def build(c):
 name,flags=c
 cmd=[sys.executable,str(ROOT/'port/n64/build.py'),'--pve-squad',*flags,'--pve-crunch','--pve-model-bank',str(bank),'--map-bank-override',str(ROOT/'build/pve/ground/bloodgulch.map64'),'--sdk','/Users/jem/dojo/n64-2048/.build/libdragon','--tiny3d','/Users/jem/dojo/halo-1/build/n64-sidewinder-throughput/tiny3d-unlit','--output-dir',str(out/name)]
 with (out/(name+'-build.log')).open('w') as f:r=subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
 print(name,r.returncode,flush=True);return r.returncode
if a.action=='build':
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(build,cases))
 if any(codes):raise SystemExit(1)
else:
 settings=out/'ares.bml'
 if not settings.exists():shutil.copyfile(ROOT/'build/covenant-crunch/checks-ares.bml',settings)
 for name,_ in cases:
  photo=name.startswith('photo');rom=next((out/name).glob('*.z64'));log=out/(name+'-native.log')
  count=71 if photo else 45;token='FF_PHOTO_END' if photo else 'PERF views='
  if log.exists() and log.read_text().count(token)==count:print('KEEP',name,flush=True);continue
  print('CAPTURE',name,flush=True)
  runner='covenant-models' if photo else 'firefight-performance'
  subprocess.run([sys.executable,str(ROOT/'port/n64/benchmarks'/runner/'capture.py'),str(rom),str(settings),str(log),'--frames' if photo else '--observations',str(count)],check=True)
