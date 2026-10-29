"""Assemble the corrected three-tier visual bank, retaining the Spirit verbatim."""
import sys,gzip,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'port/n64'))
from pack_crunch import palette
from pack_pve import pack
p=ROOT/'build/covenant-symmetry';data=json.loads(gzip.decompress((p/'reduced-baked.json.gz').read_bytes()));old=json.loads(gzip.decompress((ROOT/'halo64-assets/assets/covenant-crunch/source/squad-baked.json.gz').read_bytes()))
report={name:palette(models[2]) for name,models in data.items()};data['spirit']=old['spirit'];(p/'source').mkdir(exist_ok=True)
(p/'source/squad-source.json').write_bytes((p/'reduced-source.json').read_bytes());(p/'source/squad-baked.json.gz').write_bytes(gzip.compress(json.dumps(data,separators=(',',':')).encode(),mtime=0));(p/'palettes.json').write_text(json.dumps(report,indent=2)+'\n')
pack(p/'source',p/'bank',model_candidate=True,visual_only=True)
