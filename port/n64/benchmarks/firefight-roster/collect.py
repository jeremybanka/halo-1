"""Keep changed encounter populations separate from the matched runtime control."""
import hashlib,importlib.util,json,re,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent;out=ROOT/'build/firefight-roster'
spec=importlib.util.spec_from_file_location('crunch',HERE.parent/'covenant-crunch/collect.py');prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cases={};provenance={}
for kind in ('baseline','candidate','roster','ordinary'):
 for n in range(1,5):
  name=f'{kind}-perf-{n}';log=out/(name+'-native.log')
  if not log.exists() or log.read_text().count('PERF views=')!=45:continue
  text=log.read_text();assert not any(s in text.lower() for s in ('assertion failed','assertf','rdpq error','rdpq warning'))
  r=prior.summarize(log);r['voice_events']=len(re.findall(r'^COVENANT_VOICE ',text,re.M));cases[name]=r
  manifest=next((out/name).glob('*.build.json'));m=json.loads(manifest.read_text());rom=next((out/name).glob('*.z64'))
  assert m['options']['pve_players']==n and m['options']['pve_qa']=={'baseline':4,'candidate':4,'roster':7,'ordinary':3}[kind]
  provenance[name]={'rom_sha256':sha(rom),'rom_bytes':rom.stat().st_size,'log_sha256':sha(log),'manifest_sha256':sha(manifest),'manifest':m}
  shutil.copyfile(log,HERE/log.name)
  scope=r['living_players_and_landed_enemies'];print(name,scope,'voices',r['voice_events'])
result={'schema':1,'scope':'Ares v148, NTSC 320x240, 8 MiB, audio enabled; uncapped diagnostic, 45 observations minus 5 warmup. Live CPU, not serialized GPU timing.','comparisons':{'baseline_vs_candidate':'Same original cap-sized fixture; new runtime/pose layout/dialogue enabled. Sampled live states need not match after timing shifts.','roster':'Same staging/caps/input schedule; new variant mix replaces the original composition. Not a matched enemy-workload speedup comparison.','ordinary':'Normal opening waves; includes delivery and recovery. Forty retained samples do not cover the full set.'},'cases':cases}
(out/'results.json').write_text(json.dumps(result,indent=2)+'\n');(HERE/'results.json').write_text(json.dumps(result,indent=2)+'\n')
(out/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n');(HERE/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
