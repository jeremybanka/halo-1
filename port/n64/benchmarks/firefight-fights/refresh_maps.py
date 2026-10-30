"""Reproduce the sole geometry-bank dependency on game.c before recertifying it."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'port/n64'))
import pack_maps
out=ROOT/'build/firefight-fights/maps-check';out.mkdir(parents=True,exist_ok=True)
pack_maps.blood(out)
base=ROOT/'halo64-assets/generated/maps';name='bloodgulch.map64'
assert (out/name).read_bytes()==(base/name).read_bytes(),'Changed packed map bytes'
p=base/'maps-report.json';report=json.loads(p.read_text());old=report['inputs']['port/n64/game.c'];new=hashlib.sha256((ROOT/'port/n64/game.c').read_bytes()).hexdigest()
report['inputs']['port/n64/game.c']=new;p.write_text(json.dumps(report,indent=2)+'\n')
(HERE/'map-revalidation.json').write_text(json.dumps({'old_game_sha256':old,'new_game_sha256':new,'bank_sha256':hashlib.sha256((out/name).read_bytes()).hexdigest(),'byte_identical':True},indent=2)+'\n')
print('Blood Gulch bank reproduced byte-for-byte; map input hash revalidated')
