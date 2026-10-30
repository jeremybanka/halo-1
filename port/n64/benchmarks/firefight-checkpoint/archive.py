"""Complete and verify the requested private appraisal archives; no Git mutation."""
import gzip,hashlib,json,re,shutil
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote,urlsplit
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).parent
BANK=ROOT/'halo64-assets';ASSETS=BANK/'assets';DEST=ASSETS/'firefight-checkpoint'
WEB=ROOT.parents[2]/'build'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def copy(a,b):
 b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a,b)
def json_write(p,value):p.write_text(json.dumps(value,indent=2)+'\n')
def clean_page(p):
 s=p.read_text();s=re.sub(r'<a\b[^>]*href=["\'][^"\']+\.z64["\'][^>]*>.*?</a>\s*(?:·\s*)?','',s,flags=re.S)
 p.write_text(s)
class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[]
 def handle_starttag(self,tag,attrs):
  for name,value in attrs:
   if name in ('src','href') and value:self.links.append(value)
def check_links(page):
 parser=Links();parser.feed(page.read_text());count=0
 for name in parser.links:
  url=urlsplit(name)
  if url.scheme or url.netloc or not url.path:continue
  p=page.parent/unquote(url.path);assert p.is_file(),(page,name);count+=1
 return count
# The existing large archives are immutable evidence, apart from removing the
# unavailable ROM link in the simulation viewer during publication packaging.
for folder,file,key in [('vehicle-lods','SHA256.json',None),('vehicle-simulation','manifest.json','files')]:
 p=ASSETS/folder/file;data=json.loads(p.read_text());files=data[key] if key else data
 for name,want in files.items():assert sha(p.parent/name)==want,(folder,name)
# Add the missing selectable-fight gallery and its original capture/manifests.
fights=ASSETS/'firefight-fights';fights.mkdir(exist_ok=True)
for p in (WEB/'n64-firefight-fights').iterdir():
 if p.is_file() and p.suffix!='.z64':copy(p,fights/p.name)
for name in ('menu-4-native.log','menu-4-build.log','play-build.log','summercart-build.json'):
 copy(ROOT/'build/firefight-fights'/name,fights/name)
for case in ('menu-4','play'):
 for p in (ROOT/'build/firefight-fights'/case).glob('*.build.json'):copy(p,fights/(case+'-build.json'))
for p in (ROOT/'port/n64/benchmarks/firefight-fights').iterdir():
 if p.is_file():copy(p,fights/'public-evidence'/p.name)
for n,want in json.loads((fights/'native.json').read_text())['photos_sha256'].items():assert sha(fights/(n+'.png'))==want
assert sha(fights/'menu-4-native.log')==json.loads((fights/'native.json').read_text())['raw_log_sha256']
# Preserve the already-reviewed M64 page with all its native frames/diffs.
m64=ASSETS/'m64-polish'
for p in (WEB/'n64-m64-polish').iterdir():
 if p.is_file() and p.suffix!='.z64':copy(p,m64/p.name)
for p in (ROOT/'port/n64/benchmarks/m64-polish').iterdir():
 if p.is_file():copy(p,m64/'public-evidence'/p.name)
# Include the rejected fixed-near experiment, explicitly separate from passing evidence.
rejected=ASSETS/'scope-fix/rejected-fixed-near';rejected.mkdir(exist_ok=True)
for p in (ROOT/'build/scope-fix/fixed-near-experiment').glob('photo-*.png'):copy(p,rejected/p.name)
for p in (ROOT/'build/scope-fix/fixed-near-experiment').glob('*.build.json'):copy(p,rejected/p.name)
for name in ('fixed-near-native.log','fixed-near-build.log'):copy(ROOT/'build/scope-fix'/name,rejected/name)
(rejected/'README.md').write_text('Rejected experiment: always using near=4 fixed the foreground but regressed distant depth precision. These photos are not the final adaptive implementation.\n')
for folder in ('vehicle-simulation','m64-polish','scope-fix','firefight-fights'):
 for p in (ASSETS/folder).rglob('*.html'):clean_page(p)
# Update only changed packaging hashes in the existing simulation archive.
p=ASSETS/'vehicle-simulation/manifest.json';data=json.loads(p.read_text())
for name in data['files']:data['files'][name]=sha(p.parent/name)
json_write(p,data)
DEST.mkdir(exist_ok=True);(DEST/'inputs').mkdir(exist_ok=True)
inputs={}
for case in ('after','play'):
 p=next((ROOT/'build/scope-fix'/case).glob('*.build.json'));m=json.loads(p.read_text());copy(p,DEST/(case+'-build.json'));inputs[case]={}
 for group in ('sources','headers','included_data','generated_adapters'):
  inputs[case][group]=m[group]
  for name,want in m[group].items():
   source=ROOT/name;assert sha(source)==want,(case,name)
   target=DEST/'inputs'/(want+'.gz')
   if not target.exists():target.write_bytes(gzip.compress(source.read_bytes(),mtime=0))
   assert hashlib.sha256(gzip.decompress(target.read_bytes())).hexdigest()==want
json_write(DEST/'compiler-inputs.json',inputs)
for p in HERE.iterdir():
 if p.is_file() and p.name!='archive-check.json':copy(p,DEST/'public-evidence'/p.name)
copy(ROOT/'port/n64/FIREFIGHT_CHECKPOINT.md',DEST/'FIREFIGHT_CHECKPOINT.md')
copy(ROOT/'build/firefight-checkpoint/verify.log',DEST/'verify.log')
(DEST/'comparison.html').write_text('''<!doctype html><meta charset="utf-8"><title>Firefight checkpoint — 2026-10-30</title><style>body{font:18px/1.6 system-ui;max-width:900px;margin:40px auto;background:#101c29;color:#e6f0fa}a{color:#8cd6ff}</style><h1>Firefight checkpoint</h1><p>Native comparisons, difference filters, captured benchmarks and their original provenance. ROMs remain local. Historical captures retain the build they actually measured.</p><ul><li><a href="../vehicle-lods/evidence/comparison.html">Wraith and Shade distance LODs</a></li><li><a href="../vehicle-simulation/viewer/comparison.html">Shared clearance and Wraith firing queries</a></li><li><a href="../firefight-fights/comparison.html">Onslaught and Gauntlet</a></li><li><a href="../m64-polish/comparison.html">M64 controls, P3 layout and damage feedback</a></li><li><a href="../scope-fix/comparison.html">Final terrain and scope fixes</a></li></ul><p><a href="FIREFIGHT_CHECKPOINT.md">Checkpoint report</a> · <a href="public-evidence/verified-builds.json">Verified current build hashes</a></p>''')
folders=['vehicle-lods','vehicle-simulation','firefight-fights','m64-polish','scope-fix','firefight-checkpoint'];files={};link_count=0
for folder in folders:
 for p in (ASSETS/folder).rglob('*'):
  if not p.is_file():continue
  assert not p.is_symlink(),p
  assert p.suffix not in ('.z64','.map','.map64','.pyc') and '__pycache__' not in p.parts,p
  if p==DEST/'manifest.json':continue
  if p.suffix=='.html':link_count+=check_links(p)
  files[str(p.relative_to(BANK))]={'sha256':sha(p),'bytes':p.stat().st_size}
json_write(DEST/'manifest.json',{'description':'Published appraisal archives and exact current compiler inputs; no ROMs or raw map caches.','files':files})
for name,record in files.items():assert sha(BANK/name)==record['sha256']
report={'private_payloads':len(files),'private_payload_bytes':sum(r['bytes'] for r in files.values()),'verified_static_gallery_links':link_count,'private_manifest_sha256':sha(DEST/'manifest.json'),'private_folders':['assets/'+p for p in folders],'public_source_only':True}
json_write(HERE/'archive-check.json',report)
# This list is deliberately restricted to the six reviewed archive directories;
# Git's global *.log ignore must not discard their requested native evidence.
(ROOT/'build/firefight-checkpoint/private-paths').write_bytes(b''.join(str(ASSETS/folder).encode()+b'\0' for folder in folders))
print(json.dumps(report,indent=2))
