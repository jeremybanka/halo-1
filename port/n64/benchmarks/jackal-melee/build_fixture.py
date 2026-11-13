"""Build a real-game melee regression; invoke through the workspace run guard."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'port/n64'))
from build_inputs import enemy_bank

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--bank',type=Path)
    p.add_argument('--before',help='Use game.c from this Git revision with the same acceptance fixture')
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    bank=a.bank.resolve() if a.bank else enemy_bank(ROOT/'halo64-assets',out/'enemy-bank',
        json.loads((ROOT/'halo64-assets/assets/build-inputs/pr18/manifest.json').read_text()))
    game=HERE/'game.c'
    if a.before:
        (out/'game-before.c').write_bytes(subprocess.check_output(['git','show',a.before+':port/n64/game.c'],cwd=ROOT))
        game=out/'fixture.c'
        game.write_text((HERE/'game.c').read_text().replace('../../game.c','game-before.c').replace('../../jackal_melee_fixture.h','jackal_melee_fixture.h'))
    flags=['--preset','release','--profile','--pve-squad','--pve-players','3','--pve-qa','3',
        '--pve-model-bank',str(bank),'--pve-crunch','--pve-roster','--pve-jackal-shields',
        '--enemy-vehicle-bank',str(bank),'--vehicle-distance-lods',
        '--game-source',str(game),'--output-dir',str(out/'rom')]
    (out/'recipe.json').write_text(json.dumps({'before':a.before,'command':[sys.executable,'port/n64/build.py',*flags]},indent=2)+'\n')
    subprocess.run([sys.executable,str(ROOT/'port/n64/build.py'),*flags],cwd=ROOT,check=True)

if __name__=='__main__':main()
