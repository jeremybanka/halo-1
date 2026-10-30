"""Fresh matched baseline/candidate matrix; diagnostics and photos stay separate."""
import argparse,subprocess,json,hashlib,shutil,gzip
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent;OUT=ROOT/'build/vehicle-simulation/final'
PYTHON=ROOT/'build/n64-python/bin/python'
BASE=[str(PYTHON),'port/n64/build.py','--pve-crunch','--pve-roster','--pve-jackal-shields','--vehicle-distance-lods',
 '--pve-model-bank','build/vehicle-lods/bank','--enemy-vehicle-bank','build/vehicle-lods/bank',
 '--map-bank-override','build/pve/ground/bloodgulch.map64','--sdk','/Users/jem/dojo/n64-2048/.build/libdragon',
 '--tiny3d','/Users/jem/dojo/halo-1/build/n64-sidewinder-throughput/tiny3d-unlit']
CASES={}
for variant in ('before','after'):
 for fixture in (8,9):
  for players in (1,2,3,4):CASES[f'{variant}-{fixture}-{players}']=['--pve-squad','--pve-players',str(players),'--pve-qa',str(fixture),'--profile','--collision-profile','--pve-prep-profile','--vehicle-cost-audit']
 CASES[variant+'-verify']=[*CASES[variant+'-8-4'],'--vehicle-query-verify','--pve-photo-tick','1200']
 for tick in (60,180):CASES[f'{variant}-photo-{tick}']=[*CASES[variant+'-8-4'],'--pve-photo-tick',str(tick)]
CASES['after-play']=['--firefight','--preset','release']
def rom_path(name):
 return Path(json.loads(next((OUT/name).glob('*.build.json')).read_text())['rom']['path'])
def rom_bytes(path):return path.read_bytes() if path.exists() else gzip.decompress(path.with_suffix(path.suffix+'.gz').read_bytes())
def compress_rom(path):
 data=path.read_bytes();packed=path.with_suffix(path.suffix+'.gz');packed.write_bytes(gzip.compress(data,compresslevel=1,mtime=0))
 assert gzip.decompress(packed.read_bytes())==data;path.unlink()
def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['build','capture']);p.add_argument('cases',nargs='*');a=p.parse_args()
 OUT.mkdir(parents=True,exist_ok=True)
 for name in a.cases or [n for n in CASES if a.action=='build' or not n.endswith('play')]:
  assert name in CASES
  if a.action=='build':
   cmd=BASE+(['--vehicle-query-baseline'] if name.startswith('before') else [])+CASES[name]+['--output-dir',str(OUT/name)]
   with (OUT/(name+'-build.log')).open('w') as log:subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
   manifest=json.loads(next((OUT/name).glob('*.build.json')).read_text());rom=Path(manifest['rom']['path'])
   assert hashlib.sha256(rom.read_bytes()).hexdigest()==manifest['rom']['sha256']
   # Only redundant, regenerable files beside verified complete ROMs. Retain
   # compiler inputs, generated sources, manifests, logs and the ROM itself.
   (OUT/name/'frontend.dfs').unlink(missing_ok=True)
   for folder in ('objects','frontend-files'):shutil.rmtree(OUT/name/folder,ignore_errors=True)
   for stripped in (OUT/name).glob('*.stripped'):stripped.unlink()
   if not name.endswith('play'):compress_rom(rom)
   print('Built',name,flush=True)
  else:
   assert not name.endswith('play');photo='-photo-' in name or name.endswith('verify')
   script=HERE.parent/('covenant-models' if photo else 'firefight-performance')/'capture.py'
   flags=['--frames','9'] if photo else ['--observations','45']
   rom=rom_path(name);restored=not rom.exists()
   if restored:rom.write_bytes(rom_bytes(rom))
   subprocess.run([str(PYTHON),str(script),str(rom),str(ROOT/'build/pve-vehicles/ares.bml'),str(OUT/(name+'-native.log')),*flags],cwd=ROOT,check=True)
   if restored:rom.unlink()
if __name__=='__main__':main()
