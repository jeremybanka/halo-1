"""Extract owned CE vehicle art, native AI/physics metadata and seat animations.

No map payload is copied into the candidate/archive. Original caches remain local.
"""
import contextlib,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/pve-vehicles/source'
PATHS={'wraith':r'vehicles\wraith\wraith','shade':r'vehicles\c gun turret\c gun turret'}
def extract():
 import extract_extended as ex
 from reclaimer.meta.wrappers.halo1_map import Halo1Map
 from reclaimer.animation.animation_decompilation import extract_animation
 OUT.mkdir(parents=True,exist_ok=True)
 def cache(path,unused):
  h=Halo1Map();h.load_map(ROOT/'build/n64/assets'/(path.stem+'-decompressed.map'));return h
 # The extractor hashes its input paths, so stage only links to the owned caches.
 maps=OUT/'maps';maps.mkdir(exist_ok=True)
 for name in ('bloodgulch','b40'):
  p=maps/(name+'.map')
  if not p.exists():p.symlink_to(ROOT/'build/n64/assets'/(name+'-decompressed.map'))
 ex.MODEL_PATHS=PATHS;ex.open_cache=cache
 (OUT/'extended-raw.json').write_text(json.dumps({'models':{},'sources':{}}))
 ex.extract(OUT,maps,models_only=True,include_source_lods=True,campaign_name='b40')
 with (OUT/'metadata.log').open('w') as log,contextlib.redirect_stdout(log):
  h=cache(maps/'b40.map',OUT);entries=h.tag_index.tag_index
  def meta(path,kind):
   ix=next(i for i,e in enumerate(entries) if e.path==path and e.class_1.enum_name==kind)
   return h.get_meta(ix,disable_tag_cleaning=True),ix
  data={}
  for name,path in {'ghost':r'vehicles\ghost\ghost','banshee':r'vehicles\banshee\banshee',**PATHS}.items():
   v,ix=meta(path,'vehicle');data[name]=ex.tag_values(v)
   for field in ('physics','collision_model'):
    data[name][field]=ex.tag_values(h.get_meta(getattr(v.obje_attrs,field).id,disable_tag_cleaning=True))
  graph,ix=meta(r'characters\elite\elite','model_animations');h.meta_to_tag_data(graph,'antr',entries[ix])
  clips={}
  for i,a in enumerate(graph.animations.STEPTREE):
   if not a.name.startswith(('G-driver','B-driver','GT-gunner','wraith-driver')):continue
   c=extract_animation(i,graph,write_jma=False)
   clips[a.name]={'duration':a.frame_count/30,'frames':[[{'p':[n.pos_x/100,n.pos_y/100,n.pos_z/100],'q':[n.rot_i,n.rot_j,n.rot_k,n.rot_w]} for n in f] for f in c.frames[:a.frame_count]]}
  data['elite_clips']=clips
  # Preserve complete tag attributes to make native AI values auditable.
  (OUT/'metadata.json').write_text(json.dumps(data,separators=(',',':')))
 from extract_vehicle_details import extract as extract_details
 extract_details()
 raw=json.loads((OUT/'extended-raw.json').read_text())
 print(json.dumps({k:{'nodes':[n['name'] for n in v['nodes']],'lods':v['source_lods']} for k,v in raw['models'].items()},indent=2))
if __name__=='__main__':extract()
