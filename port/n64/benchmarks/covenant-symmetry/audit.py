"""Exact authored symmetry and source animation/hit invariants."""
import sys,json,gzip,collections,copy,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'port/n64'))
from symmetrize_pve import bone_pairs
from center_warthog import center_fixture
p=ROOT/'build/covenant-symmetry';raw=json.loads((p/'source/squad-source.json').read_text());before=json.loads(gzip.decompress((ROOT/'halo64-assets/assets/covenant-crunch/source/squad-baked.json.gz').read_bytes()));after=json.loads(gzip.decompress((p/'source/squad-baked.json.gz').read_bytes()));meta=json.loads((p/'reduced-source.report.json').read_text());checks={}
oldraw=json.loads((ROOT/'halo64-assets/assets/covenant-crunch/reduced-source.json').read_text())
assert raw['actors']==oldraw['actors'] and raw['spirit']==oldraw['spirit']
def canon(face):return min(tuple(face[i:]+face[:i]) for i in range(3))
for name in ['grunt','elite','jackal','hunter']:
 m=raw['models'][name];assert m['nodes']==oldraw['models'][name]['nodes'];pairs=bone_pairs(m['nodes']);rows=[]
 for lod,key in enumerate(m['n64_lods']):
  g=m['source_geometry_lods'][key];protected=meta[name][lod]['protected_equipment_triangles'];count=len(g['faces'])-protected
  def corner(fi,j,mirror=False):
   vi=g['faces'][fi][j];pt=list(g['vertices'][vi]);skin=g['skin_weights'][vi]
   if mirror:pt[1]*=-1;skin=[(pairs[b],w) for b,w in skin]
   return (*[round(x,7) for x in pt],tuple((b,round(w,7)) for b,w in sorted(skin)),tuple(g['corner_colors'][fi][j]),g['corner_tints'][fi][j])
  original=collections.Counter((g['materials'][i],canon([corner(i,j) for j in range(3)])) for i in range(count))
  reflected=collections.Counter((g['materials'][i],canon([corner(i,j,True) for j in reversed(range(3))])) for i in range(count))
  assert original==reflected,(name,lod,'symmetry')
  assert all(abs(sum(w for _,w in skin)-1)<1e-7 for skin in g['skin_weights'])
  b,c=before[name][lod],after[name][lod]
  assert b['grips']==c['grips'] and b['hit']==c['hit'],(name,lod,'source hit/grip')
  for key in b['clips']:
   x,y=b['clips'][key],c['clips'][key]
   assert x['duration']==y['duration'] and x['tag_name']==y['tag_name'] and len(x['frames'])==len(y['frames'])
   assert np.isfinite(np.asarray(y['frames'])).all()
  rows.append({'lod':lod,'mirrored_faces':count,'preserved_hunter_joined_shell_faces':protected,'mirrored_weights_colors_winding':True,'original_hit_grips_clip_timings':True})
 checks[name]=rows
assert before['spirit']==after['spirit'];checks['spirit_unchanged']=True
# Repacking changes exactly four visual corners per Warthog tier. Nothing else.
b=json.loads((p/'world-before/model-preview.json').read_text());c=json.loads((ROOT/'halo64-assets/generated/model-preview.json').read_text());assert b.keys()==c.keys()
for name in b:
 if name not in ('warthog','warthog_lod'):assert b[name]==c[name],name
 else:
  assert all(b[name][k]==c[name][k] for k in b[name] if k!='positions')
  changed=[(u,v) for u,v in zip(b[name]['positions'],c[name]['positions']) if u!=v];assert len(changed)==6
  assert all(u[:2]==v[:2] for u,v in changed)
assert (p/'world-before/micro_data.c').read_bytes()==(ROOT/'halo64-assets/generated/micro_data.c').read_bytes()
checks['warthog']={'near_far_changed_corners':6,'unchanged_triangles_colors_indices':True,'other_world_models_identical':True,'micro_identical_fixture_already_omitted':True}
(p/'asset-checks.json').write_text(json.dumps(checks,indent=2)+'\n');print(json.dumps(checks,indent=2))
