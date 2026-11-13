"""Reproduce game.c's map-pack output before updating its dependency digest.

Only writes proposed metadata into --output. Apply it to the asset bank after
review, then commit that private revision and the public submodule pin together.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'port/n64'))
import pack_maps

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    bank=ROOT/'halo64-assets';base=bank/'generated/maps';report=json.loads((base/'maps-report.json').read_text())
    for name,expected in report['files'].items():assert sha(base/name)==expected,name
    pack_maps.blood(out)
    assert (out/'bloodgulch.map64').read_bytes()==(base/'bloodgulch.map64').read_bytes()
    old=report['inputs']['port/n64/game.c'];new=sha(ROOT/'port/n64/game.c')
    report['inputs']['port/n64/game.c']=new
    proposed=out/'maps-report.json';proposed.write_text(json.dumps(report,indent=2)+'\n')
    manifest=json.loads((bank/'bank-manifest.json').read_text())
    row=next(r for r in manifest['files'] if r['path']=='generated/maps/maps-report.json')
    row.update(bytes=proposed.stat().st_size,sha256=sha(proposed))
    (out/'bank-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    result={'old_game_sha256':old,'new_game_sha256':new,'bloodgulch_sha256':sha(out/'bloodgulch.map64'),
        'bloodgulch_reproduced_byte_identically':True,'all_existing_map_payloads_verified':len(report['files']),
        'scope':'blood() is the only map packer that reads game.c; it reads the teleporter initializer. arena() does not read game.c.',
        'proposed_maps_report_sha256':sha(proposed)}
    (out/'revalidation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
