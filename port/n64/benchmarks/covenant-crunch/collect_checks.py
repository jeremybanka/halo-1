"""Archive check provenance and publish only non-image native records."""
import argparse,hashlib,json,re,shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('capture',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output;out.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
records={}
for name in ('photo-before','photo-after','frontend-4','playable'):
 rom=next((a.capture/name).glob('*.z64'));manifest=next((a.capture/name).glob('*.build.json'));m=json.loads(manifest.read_text());log=a.capture/(name+'-native.log')
 records[name]={'rom_sha256':sha(rom),'rom_bytes':rom.stat().st_size,'manifest_sha256':sha(manifest),'manifest':m}
 if log.exists():
  records[name]['log_sha256']=sha(log)
  if name=='frontend-4':assert 'FIREFIGHT_QA PASS players=4' in log.read_text();shutil.copyfile(log,out/log.name)
for log in sorted((a.capture/'checks').glob('*-native.log')):
 name=log.name.removesuffix('-native.log');rom=next((a.capture/'checks'/name).glob('*.z64'));manifest=next((a.capture/'checks'/name).glob('*.build.json'));m=json.loads(manifest.read_text());text=log.read_text()
 assert text.count('FF_PHOTO_END')==17
 assert not any(x in text.lower() for x in ('assertion failed','assertf','rdpq error','rdpq warning'))
 records[name]={'rom_sha256':sha(rom),'rom_bytes':rom.stat().st_size,'log_sha256':sha(log),'manifest_sha256':sha(manifest),'manifest':m}
 (out/(name+'-census.log')).write_text(''.join(l for l in text.splitlines(keepends=True) if not l.startswith('FF_PIX ')))
assert len(records)==14,len(records)
for name in ('pixel-checks.json','unchanged-services.json','iteration.json','memory.json','asset-checks.json','silhouette-audit.json','silhouette-summary.json','host-lod.log','host-bank.log','host-preparation.log','host-firefight.log','deferred-test.log','configs-test.log'):
 shutil.copyfile(a.capture/name,out/name)
shutil.copyfile(a.capture/'checks/photos/results.json',out/'census.json')
(out/'checks-provenance.json').write_text(json.dumps({'settings_sha256':sha(a.capture/'checks-ares.bml'),'cases':records},indent=2)+'\n')
print('Archived 14 check/playable manifests and ten redacted native census logs')
