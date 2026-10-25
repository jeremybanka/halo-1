"""Refresh only the private map bank when generated renderer tables are identical."""
import hashlib,json,subprocess
from pathlib import Path
from sidewinder_budget import OUT
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def repack():
 visibility=(OUT/'visibility-data.c').read_bytes();bank=OUT/'candidate-maps/sidewinder.map64';sidecar=OUT/'visibility.json'
 for name in ('native-four','native-one','native-census','native-target','native-photo','native-validation'):
  directory=OUT/name;manifest_path=next(directory.glob('*.build.json'));m=json.loads(manifest_path.read_text());assert (directory/'visibility-data.c').read_bytes()==visibility,'Recompilation required for changed renderer tables'
  rom=Path(m['rom']['path']);old=sha(rom);target=directory/'frontend-files/maps/sidewinder.map64';target.write_bytes(bank.read_bytes());sdk=Path(m['options']['sdk']);
  subprocess.run([str(sdk/'bin/mkdfs'),str(directory/'frontend.dfs'),str(directory/'frontend-files')],check=True,stdout=subprocess.DEVNULL)
  subprocess.run([str(sdk/'bin/n64tool'),'--title','HALO 64','--toc','--output',str(rom),'--align','256',str(rom.with_suffix('.stripped')),'--align','8',str(rom.with_suffix('.sym')),'--align','16',str(directory/'frontend.dfs')],check=True,stdout=subprocess.DEVNULL)
  subprocess.run([str(sdk/'bin/ed64romconfig'),'--savetype','none','--regionfree','--controller1','n64','--controller2','n64','--controller3','n64','--controller4','n64',str(rom)],check=True,stdout=subprocess.DEVNULL)
  m['post_build_bank_repack']=dict(previous_rom_sha256=old,new_rom_sha256=sha(rom),bank_sha256=sha(bank),generated_visibility_data_identical=True,method='Unchanged compiled program and renderer tables; map bank replaced in private DFS, then n64tool and ROM header configuration rerun.')
  m['rom'].update(sha256=sha(rom),bytes=rom.stat().st_size);m['render_bank_experiment']['sha256']=sha(bank)
  m['world_pvs_experiment']['sidecar_sha256']=sha(sidecar);m['world_pvs_experiment']['map_sha256']=sha(bank)
  if 'maps' in m and 'maps' in m['maps'] and 'sidewinder' in m['maps']['maps']:m['maps']['maps']['sidewinder']['sha256']=sha(bank)
  manifest_path.write_text(json.dumps(m,indent=2)+'\n');print(name,sha(rom),flush=True)
if __name__=='__main__':repack()
