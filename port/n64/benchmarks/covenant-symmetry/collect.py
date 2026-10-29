"""Paired crowded 1–4 player results, original runtime and source behaviors."""
import importlib.util,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent;out=ROOT/'build/covenant-symmetry'
spec=importlib.util.spec_from_file_location('prior',HERE.parent/'covenant-crunch/collect.py');prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cases={};provenance={}
for n in range(1,5):
 manifests=[]
 for v in ['baseline','candidate']:
  name=f'{v}-perf-{n}';log=out/(name+'-native.log');result=prior.summarize(log);assert result['observations']==45
  assert not any(x in log.read_text().lower() for x in ('assertion failed','assertf','rdpq warning','rdpq error'))
  cases[name]=result;manifest=next((out/name).glob('*.build.json'));m=json.loads(manifest.read_text());manifests.append(m)
  assert m['options']['pve_crunch'] and not m['options']['pve_crunch_baseline'] and m['options']['pve_qa']==4
  provenance[name]={'log_sha256':sha(log),'rom_sha256':sha(next((out/name).glob('*.z64'))),'manifest_sha256':sha(manifest),'manifest':m}
 a,b=manifests;oa,ob=dict(a['options']),dict(b['options'])
 for d in (oa,ob):
  for k in ['output_dir','pve_model_bank']:d.pop(k)
 ia,ib=prior.prior.inputs(a),prior.prior.inputs(b)
 changed={k for k in ia.keys()|ib.keys() if ia.get(k)!=ib.get(k)}
 expected={'build/n64/generated/models_data.c','halo64-assets/assets/covenant-crunch/bank/pve_data.c','build/covenant-symmetry/bank/pve_data.c'}
 assert oa==ob and changed==expected,(n,'unexpected runtime/data difference',changed)
 print(n,cases[f'baseline-perf-{n}']['living_players_and_landed_enemies'],cases[f'candidate-perf-{n}']['living_players_and_landed_enemies'])
(out/'results.json').write_text(json.dumps({'cases':cases,'fixture':'Crowded live matched QA4; 45 observations, first five excluded; living-player/landed-enemy scope'},indent=2)+'\n')
(out/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
