"""Local private evidence archive only; no commit, push or ROM redistribution."""
import gzip,hashlib,json,shutil
from pathlib import Path
from run import ROOT,HERE,OUT,CASES
DEST=ROOT/'halo64-assets/assets/vehicle-simulation';VIEW=ROOT.parents[2]/'build/n64-vehicle-simulation'
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
 DEST.mkdir(parents=True,exist_ok=True);(DEST/'blobs').mkdir(exist_ok=True);inputs={}
 for name in CASES:
  manifest=next((OUT/name).glob('*.build.json'));m=json.loads(manifest.read_text());dest=DEST/'manifests'/manifest.parent.name;dest.mkdir(parents=True,exist_ok=True);shutil.copyfile(manifest,dest/manifest.name)
  paths={}
  for group in ('sources','headers','included_data','generated_adapters'):paths.update(m[group])
  if m['vehicle_cost_audit']:paths.update(m['vehicle_cost_audit']['sources'])
  for path,want in paths.items():
   source=ROOT/path;data=source.read_bytes();assert sha(data)==want,path
   blob=DEST/'blobs'/(want+'.gz')
   if not blob.exists():blob.write_bytes(gzip.compress(data,mtime=0))
   inputs[path]=want
  log=OUT/(name+'-native.log')
  if log.exists():
   dest=DEST/'logs';dest.mkdir(exist_ok=True);(dest/(name+'.log.gz')).write_bytes(gzip.compress(log.read_bytes(),mtime=0))
 for source,name in ((HERE,'public-evidence'),(VIEW,'viewer')):
  dest=DEST/name
  for p in source.rglob('*'):
   if not p.is_file() or '__pycache__' in p.parts or p.suffix=='.z64':continue
   target=dest/p.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
 # Retain rejected traversal evidence and the uncontrolled live hash trial.
 exploratory=OUT.parent
 for folder in ('before-8-4','after-8-4','diagnostic-live','reference','earlier-final-4p'):
  source=exploratory/folder
  for p in source.rglob('*'):
   if not p.is_file() or p.suffix not in ('.c','.h','.inc','.json','.log'):continue
   target=DEST/'exploratory'/folder/p.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True)
   target.with_suffix(target.suffix+'.gz').write_bytes(gzip.compress(p.read_bytes(),mtime=0))
 for name in ('before-8-4-native.log','after-8-4-native.log','storage-reclamation.json','source-cache/provenance.json'):
  p=exploratory/name
  target=DEST/'exploratory'/name;target.parent.mkdir(parents=True,exist_ok=True);target.with_suffix(target.suffix+'.gz').write_bytes(gzip.compress(p.read_bytes(),mtime=0))
 shutil.copyfile(ROOT/'port/n64/VEHICLE_SIMULATION.md',DEST/'VEHICLE_SIMULATION.md')
 (DEST/'compiler-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
 files={str(p.relative_to(DEST)):sha(p.read_bytes()) for p in DEST.rglob('*') if p.is_file() and p.name!='manifest.json'}
 (DEST/'manifest.json').write_text(json.dumps({'description':'Local appraisal: vehicle simulation exact query reuse. No ROM/map cache packaged.','files':files},indent=2)+'\n')
 for name,want in files.items():assert sha((DEST/name).read_bytes())==want
 print('Verified',len(files),'private local payloads',DEST)
if __name__=='__main__':main()
