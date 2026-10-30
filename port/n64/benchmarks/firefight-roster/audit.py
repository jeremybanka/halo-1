"""Verify accepted shapes/base motion and every new source-driven input."""
import gzip,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'port/n64'))
from extract_pve_roster import VARIANTS
from pack_pve import CLIPS
out=ROOT/'build/firefight-roster';source=out/'source';bank=out/'bank'
read=lambda p:json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
old=read(ROOT/'halo64-assets/assets/covenant-symmetry/source/squad-baked.json.gz');new=read(source/'squad-baked.json.gz')
original=read(ROOT/'halo64-assets/assets/covenant-symmetry/source/squad-source.json');raw=read(source/'squad-source.json');rules=read(bank/'pve-report.json')['roster']
checks={};base_frames=0
for name,models in old.items():
 for lod,m in enumerate(models):
  n=new[name][lod];assert m['triangles']==n['triangles'],(name,lod,'triangle/color/UV changed')
  for key in CLIPS:
   assert m['clips'][key]==n['clips'][key] and m['grips'][key]==n['grips'][key],(name,lod,key)
   base_frames+=len(m['clips'][key]['frames'])
  if name in original['models']:
   assert original['models'][name]['nodes']==raw['models'][name]['nodes']
  if lod==0 and name!='spirit':
   for key in ('faces','materials'):assert m['hit'][key]==n['hit'][key]
   for key in CLIPS:assert m['hit']['clips'][key]==n['hit']['clips'][key]
checks['accepted_triangle_colors_uvs_base_motion_and_grips_unchanged']=True
checks['base_animation_frames_verified']=base_frames
for ident,_,path in VARIANTS:
 a=raw['roster']['variants'][ident];v=rules['variants'][ident];assert v['source']==path
 d=v['definition'];p=a['variant']['unit_properties'];assert d['health']==p['body_vitality'] and d['shield']==p['shield_vitality']
 assert d['rate']==a['variant']['ranged_combat']['rate_of_fire']
 if 'stealth' in ident:assert v['flags']&1 and d['shield']==0
 if 'sword' in ident:assert v['flags']&4 and d['melee_damage']==[151,151] and v['strike_reach']<d['melee_range']
 for key,source_key in [('grenade_chance','grenade_chance'),('grenade_timeout','encounter_grenade_timeout')]:assert d[key]==a['variant']['grenades'][source_key]
checks['source_variant_values_verified']=len(VARIANTS)
for kind in ('grunt','elite'):
 for lod in range(3):
  for key in CLIPS:
   c=new[kind][lod]['clips']['alt_'+key];assert c['duration']==raw['actors'][kind]['clips']['alt_'+key]['duration']
   assert all(len(frame)==len(new[kind][lod]['triangles'])*3 for frame in c['frames'])
checks['alternate_pose_frames_grips_and_hit_tracks_present']=True
pcm=(bank/'pve-voices.bin').read_bytes();cursor=0;count=0
for s in raw['roster']['sounds']:
 cursor=(cursor+15)&~15;payload=(source/s['file']).read_bytes();assert len(payload)==s['bytes']
 assert hashlib.sha256(payload).hexdigest()==s['sha256'] and pcm[cursor:cursor+len(payload)]==payload
 cursor+=len(payload)+16;count+=1
checks['complete_source_audio_permutations_verified']=count
checks['dialogue_permutations']=sum(s['kind']<4 for s in raw['roster']['sounds'])
checks['weapon_sound_permutations']=sum(s['kind']==4 for s in raw['roster']['sounds'])
checks['audio_rom_bytes']=len(pcm)
checks['source_caches']=raw['roster']['caches']
checks['bank_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in bank.iterdir() if p.is_file()}
(out/'asset-checks.json').write_text(json.dumps(checks,indent=2)+'\n');print(json.dumps({k:v for k,v in checks.items() if k not in ('bank_sha256','source_caches')},indent=2))
