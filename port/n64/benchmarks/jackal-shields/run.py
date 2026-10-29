"""Matched native shield appraisal; each capture owns only its Ares process."""
import argparse,concurrent.futures,subprocess,sys,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=ROOT/'build/jackal-shields'
p=argparse.ArgumentParser();p.add_argument('action',choices=['build','capture']);p.add_argument('version',choices=['before','after']);p.add_argument('suite',choices=['photos','roster-photos','control','roster','ordinary','play','perf']);a=p.parse_args()
OUT.mkdir(exist_ok=True);settings=OUT/'ares.bml'
if not settings.exists():shutil.copyfile(ROOT/'build/firefight-roster/ares.bml',settings)
def cases(suite):
    name=a.version+'-'+suite
    if suite in ('photos','roster-photos'):return [(name,['--pve-squad','--pve-players','4','--jackal-shield-qa' if suite=='photos' else '--pve-model-qa'],72 if suite=='photos' else 46)]
    if suite=='play':return [(name,['--firefight','--preset','release'],0)]
    if suite=='perf':return sum((cases(s) for s in ('control','roster','ordinary')),[])
    return [(name+'-'+str(n),['--pve-squad','--pve-players',str(n),'--pve-qa',str({'control':4,'roster':7,'ordinary':3}[suite]),'--profile','--collision-profile','--pve-prep-profile'],0) for n in range(1,5)]
def build(case):
    name,flags,_=case;bank=ROOT/('build/jackal-shields/bank' if a.version=='after' else 'halo64-assets/assets/firefight-roster/bank')
    cmd=[sys.executable,'port/n64/build.py',*flags,'--pve-crunch','--pve-roster','--pve-model-bank',str(bank),'--map-bank-override',str(ROOT/'build/pve/ground/bloodgulch.map64'),'--sdk','/Users/jem/dojo/n64-2048/.build/libdragon','--tiny3d','/Users/jem/dojo/halo-1/build/n64-sidewinder-throughput/tiny3d-unlit','--output-dir',str(OUT/name)]
    if a.version=='after':cmd+=['--pve-jackal-shields']
    with (OUT/(name+'-build.log')).open('w') as f:r=subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
    print(name,r.returncode,flush=True);return r.returncode
if a.action=='build':
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(build,cases(a.suite)))
    raise SystemExit(any(codes))
else:
    for name,_,photos in cases(a.suite):
        if (OUT/'stop-captures').exists():raise SystemExit('Capture stop requested between owned emulator runs')
        runner='covenant-models' if photos else 'firefight-performance';rom=next((OUT/name).glob('*.z64'))
        subprocess.run([sys.executable,str(ROOT/'port/n64/benchmarks'/runner/'capture.py'),str(rom),str(settings),str(OUT/(name+'-native.log')),'--frames' if photos else '--observations',str(photos or 45)],check=True)
