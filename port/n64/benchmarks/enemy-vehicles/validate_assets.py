"""Check additive banks, canonical hit streaming and retained source bodies."""
import hashlib,json,re,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'port/n64'));sys.path.insert(0,str(ROOT/'port/n64/blam'))
from prepare_vehicle import function
OUT=ROOT/'build/pve-vehicles';BANK=OUT/'bank';BASE=ROOT/'halo64-assets/generated';accepted=ROOT/'halo64-assets/assets/jackal-shields/bank'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def rows(text,name):
 m=re.search(r'\b'+name+r'(?:\[[^\]]*\])+\s*=\s*\{',text);assert m,name
 result=[];depth=0;first=m.end()
 for i in range(first,len(text)):
  c=text[i]
  if c=='{':depth+=1
  elif c=='}':
   if depth==0:
    last=text[first:i].strip()
    if last:result.append(last)
    return result
   depth-=1
  elif c==',' and depth==0:
   result.append(text[first:i].strip());first=i+1
 raise AssertionError(name)
checks=[]
for file,names in {'models_data.c':['bg_model_assets','bg_pickup_lods','bg_vehicle_lods','bg_vehicle_rigs'],'combat_data.c':['bg_vehicle_hit_meshes','bg_damage_profiles','bg_mounted_profiles','bg_player_hit_clips','bg_hit_hatches'],'interaction_defs.c':['bg_seat_counts','bg_seat_definitions'],'interaction_assets.c':['bg_seat_poses','bg_seat_grips']}.items():
 for n in names:
  a=rows((BASE/file).read_text(),n);b=rows((BANK/file).read_text(),n);assert a==b[:len(a)],(file,n);checks.append({'array':n,'unchanged_rows':len(a),'added_rows':len(b)-len(a)})
for name in ['pve_data.c','pve_roster.c','pve_jackal_shield.c']:
 assert (BANK/name).read_bytes()==(accepted/name).read_bytes(),name
motion=(BANK/'pve-motion.bin').read_bytes();assert motion.startswith((accepted/'pve-motion.bin').read_bytes())
hit=(BANK/'enemy_pilot_hits.c').read_text();hits=[]
for name,data in re.findall(r'static const uint16_t (enemy_pilot_\w+_hit)\[\]=\{([^}]*)\}',hit):
 offset=int(re.search(r'#define '+name+r' \(\(const uint16_t\*\)\(uintptr_t\)(\d+)\)',hit)[1]);values=[int(v) for v in data.split(',')];packed=struct.pack('>'+str(len(values))+'H',*values)
 assert motion[offset:offset+len(packed)]==packed;hits.append({'clip':name,'coordinates':len(values),'rom_offset':offset,'bytes':len(packed)})
assert len(hits)==12
source=json.loads((BANK/'ai-source-manifest.json').read_text())
for row in source['functions']:assert hashlib.sha256(function((ROOT/row['path']).read_text(),row['name']).encode()).hexdigest()==row['function_sha256']
report={'additive_tables':checks,'existing_covenant_geometry_unchanged':True,'existing_covenant_motion_prefix_unchanged':True,'native_host_hit_streams_exact':hits,'original_functions_verified':len(source['functions']),'bank_files':{p.name:sha(p) for p in sorted(BANK.iterdir()) if p.is_file()}}
(OUT/'asset-validation.json').write_text(json.dumps(report,indent=2));print('PASS additive banks, unchanged existing meshes/motion, 12 exact hit streams,',len(source['functions']),'retained source functions')
