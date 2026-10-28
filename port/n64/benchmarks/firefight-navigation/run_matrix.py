#!/usr/bin/env python3
"""Build/capture paired ordinary and crowded 1-4P fixtures, without editing assets."""
import argparse,concurrent.futures,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
p=argparse.ArgumentParser();p.add_argument('action',choices=['build','capture']);p.add_argument('--baseline-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--settings',type=Path);p.add_argument('--versions',nargs='+',choices=['baseline','candidate'],default=['baseline','candidate']);p.add_argument('--kinds',nargs='+',choices=['opening','perf'],default=['opening','perf']);p.add_argument('--players',nargs='+',type=int,choices=range(1,5),default=list(range(1,5)));p.add_argument('--resume',action='store_true',help='Keep complete captures already in the output directory; use only with unchanged ROMs');p.add_argument('--sdk',type=Path,default=Path('/Users/jem/dojo/n64-2048/.build/libdragon'));p.add_argument('--tiny3d',type=Path,default=Path('/Users/jem/dojo/halo-1/build/n64-sidewinder-throughput/tiny3d-unlit'));a=p.parse_args();a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=True)
specs=[(version,kind,n) for kind in a.kinds for n in a.players for version in a.versions]
def name(s):return '-'.join(map(str,s))
def build(s):
    version,kind,n=s;root=a.baseline_root.resolve() if version=='baseline' else ROOT
    build_out=root/'build/navigation-matrix'/name(s) if version=='baseline' else a.output/name(s)
    command=[str(ROOT/'build/n64-python/bin/python'),str(root/'port/n64/build.py'),'--pve-squad','--pve-players',str(n),'--pve-qa','3' if kind=='opening' else '4','--profile','--output-dir',str(build_out),'--sdk',str(a.sdk),'--tiny3d',str(a.tiny3d),'--map-bank-override',str(ROOT/'build/pve/ground/bloodgulch.map64')]
    with (a.output/(name(s)+'-build.log')).open('w') as log:r=subprocess.run(command,cwd=root,stdout=log,stderr=subprocess.STDOUT)
    if r.returncode==0 and version=='baseline':
        dest=a.output/name(s);dest.mkdir(exist_ok=True)
        for source in [*build_out.glob('*.z64'),*build_out.glob('*.build.json')]:
            link=dest/source.name
            if link.is_symlink():link.unlink()
            link.symlink_to(source.resolve())
    print('BUILD',name(s),r.returncode,flush=True);return r.returncode
if a.action=='build':
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(build,specs))
    if any(results):raise SystemExit(1)
else:
    if not a.settings:p.error('--settings required for capture')
    settings=a.output/'ares.bml'
    if settings.resolve()!=a.settings.resolve():shutil.copyfile(a.settings,settings)
    for s in specs:
        rom=next((a.output/name(s)).glob('*.z64'));log=a.output/(name(s)+'-native.log')
        observations=75 if s[1]=='opening' else 45
        if a.resume and log.exists() and log.read_text().count('PERF views=')==observations:
            print('KEEP',name(s),flush=True);continue
        print('CAPTURE',name(s),flush=True)
        subprocess.run([sys.executable,str(ROOT/'port/n64/benchmarks/firefight-performance/capture.py'),str(rom),str(settings),str(log),'--observations',str(observations)],check=True)
