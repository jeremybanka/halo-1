"""Isolated matched native builds/captures; owns only its Ares subprocess."""
import argparse,concurrent.futures,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
p=argparse.ArgumentParser();p.add_argument('action',choices=['build','capture']);p.add_argument('version',choices=['baseline','candidate','roster','ordinary','photos','play']);a=p.parse_args()
out=ROOT/'build/firefight-roster';out.mkdir(exist_ok=True);version=a.version
cases=[(f'{version}-perf-{n}',['--pve-squad','--pve-players',str(n),'--pve-qa',str({'baseline':4,'candidate':4,'roster':7,'ordinary':3}.get(version,4)),'--profile','--collision-profile','--pve-prep-profile']) for n in range(1,5)]
if version=='photos':cases=[('photos',['--pve-squad','--pve-players','4','--pve-model-qa'])]
if version=='play':cases=[('play',['--firefight','--preset','release'])]
def build(case):
 name,flags=case
 bank=ROOT/('halo64-assets/assets/covenant-symmetry/bank' if version=='baseline' else 'build/firefight-roster/bank')
 cmd=[sys.executable,'port/n64/build.py',*flags,'--pve-crunch','--pve-model-bank',str(bank),'--map-bank-override',str(ROOT/'build/pve/ground/bloodgulch.map64'),'--sdk','/Users/jem/dojo/n64-2048/.build/libdragon','--tiny3d','/Users/jem/dojo/halo-1/build/n64-sidewinder-throughput/tiny3d-unlit','--output-dir',str(out/name)]
 if version!='baseline':cmd+=['--pve-roster']
 with (out/(name+'-build.log')).open('w') as f:r=subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
 print(name,r.returncode,flush=True);return r.returncode
if a.action=='build':
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(build,cases))
 raise SystemExit(any(codes))
else:
 for name,_ in cases:
  rom=next((out/name).glob('*.z64'));log=out/(name+'-native.log');photo=version=='photos'
  runner='covenant-models' if photo else 'firefight-performance'
  subprocess.run([sys.executable,str(ROOT/'port/n64/benchmarks'/runner/'capture.py'),str(rom),str(out/'ares.bml'),str(log),'--frames' if photo else '--observations','46' if photo else '45'],check=True)
