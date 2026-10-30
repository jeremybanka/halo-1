"""Fresh reference/candidate native matrix, matched photos and frozen graphics checks."""
import argparse,subprocess,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent;OUT=ROOT/'build/vehicle-lods'
PYTHON=ROOT/'build/n64-python/bin/python'
BASE=[str(PYTHON),'port/n64/build.py','--pve-crunch','--pve-roster','--pve-jackal-shields',
      '--map-bank-override','build/pve/ground/bloodgulch.map64','--sdk','/Users/jem/dojo/n64-2048/.build/libdragon',
      '--tiny3d','/Users/jem/dojo/halo-1/build/n64-sidewinder-throughput/tiny3d-unlit']
CASES={}
for variant in ('before','after'):
    for fixture in (8,9):
        for players in (1,2,3,4):
            CASES[f'{variant}-{fixture}-{players}']=['--pve-squad','--pve-players',str(players),'--pve-qa',str(fixture),'--profile','--collision-profile','--pve-prep-profile']
    CASES[variant+'-photos']=['--pve-squad','--pve-players','4','--vehicle-lod-qa']
    for tick in (1,60,180):
        CASES[f'{variant}-route-{tick}']=['--pve-squad','--pve-players','4','--pve-qa','8','--profile','--collision-profile','--vehicle-cost-audit','--pve-photo-tick',str(tick)]
    CASES[variant+'-timing']=[*CASES[variant+'-route-60'],'--gpu-diagnostic']
CASES['after-play']=['--firefight','--preset','release']

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['build','capture']);p.add_argument('cases',nargs='*');a=p.parse_args()
    for name in a.cases or [n for n in CASES if a.action=='build' or not n.endswith('play')]:
        assert name in CASES,name
        if a.action=='build':
            after=name.startswith('after');bank='build/vehicle-lods/bank' if after else 'build/pve-vehicles/bank'
            cmd=BASE+['--pve-model-bank',bank,'--enemy-vehicle-bank',bank]+(['--vehicle-distance-lods'] if after else [])+CASES[name]+['--output-dir',str(OUT/name)]
            with (OUT/(name+'-build.log')).open('w') as log:subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
            manifest=json.loads(next((OUT/name).glob('*.build.json')).read_text())
            assert hashlib.sha256(Path(manifest['rom']['path']).read_bytes()).hexdigest()==manifest['rom']['sha256']
            # The finished ROM already contains this regenerable filesystem image.
            (OUT/name/'frontend.dfs').unlink(missing_ok=True)
            print('Built',name,flush=True)
        else:
            assert not name.endswith('play')
            photos=name.endswith('photos');frozen=photos or '-route-' in name or name.endswith('timing')
            script=HERE.parent/('covenant-models' if frozen else 'firefight-performance')/'capture.py'
            flags=['--frames','36' if photos else '9'] if frozen else ['--observations','45']
            subprocess.run([str(PYTHON),str(script),str(next((OUT/name).glob('*.z64'))),str(ROOT/'build/pve-vehicles/ares.bml'),str(OUT/(name+'-native.log')),*flags],cwd=ROOT,check=True)
if __name__=='__main__':main()
