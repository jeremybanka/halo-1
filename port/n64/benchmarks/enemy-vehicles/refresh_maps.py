"""Revalidate game.c's sole map-pack input by reproducing its complete bank."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'port/n64'))
import pack_maps
out=ROOT/'build/pve-vehicles/maps-check';out.mkdir(exist_ok=True)
pack_maps.blood(out)
base=ROOT/'halo64-assets/generated/maps';name='bloodgulch.map64'
assert (out/name).read_bytes()==(base/name).read_bytes(),'Gameplay source changed packed map bytes'
# arena() never reads game.c; blood() consumes only the teleporter initializer.
p=base/'maps-report.json';r=json.loads(p.read_text());old=r['inputs']['port/n64/game.c'];new=hashlib.sha256((ROOT/'port/n64/game.c').read_bytes()).hexdigest()
r['inputs']['port/n64/game.c']=new;p.write_text(json.dumps(r,indent=2)+'\n')
(out/'revalidation.json').write_text(json.dumps({'old_game_sha256':old,'new_game_sha256':new,'bank_sha256':hashlib.sha256((out/name).read_bytes()).hexdigest(),'byte_identical':True},indent=2))
print('Blood Gulch bank reproduced byte-for-byte; map input hash revalidated')
