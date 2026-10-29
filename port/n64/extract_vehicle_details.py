"""Reproducible owned-cache supplement: firing variants and seat/hatch clips."""
import contextlib,json,struct
from extract_enemy_vehicles import ROOT,OUT

def extract():
 from reclaimer.meta.wrappers.halo1_map import Halo1Map
 from reclaimer.animation.animation_decompilation import extract_animation
 from extract_extended import tag_values
 with (OUT/'details.log').open('w') as log,contextlib.redirect_stdout(log):
  h=Halo1Map();h.load_map(ROOT/'build/n64/assets/b40-decompressed.map');es=h.tag_index.tag_index
  def tag(path,kind):
   i=next(i for i,e in enumerate(es) if e.path==path and e.class_1.enum_name==kind)
   return h.get_meta(i,disable_tag_cleaning=True),i
  pilots={}
  for name,path in [('ghost',r'vehicles\ghost\ghost pilot'),('banshee',r'vehicles\banshee\banshee pilot'),('wraith',r'vehicles\wraith\wraith pilot'),('shade',r'vehicles\c gun turret\c gun turret gunner')]:
   v,i=tag(path,'actor_variant');pilots[name]={'path':path,'variant':tag_values(v)}
  actor,i=tag(r'characters\elite\elite minor\elite minor','actor')
  # Native cache stores derived fields in HEK padding. CE struct moving+32.
  offset=h.map_pointer_converter.v_ptr_to_f_ptr(es[i].meta_offset)+128+32
  h.map_data.seek(offset);begin=struct.unpack('<f',h.map_data.read(4))[0]
  data={'pilots':pilots,'begin_angle_cosine':begin,'begin_angle_cache_offset':offset,'clips':{}}
  for key,path,prefixes in [('shade_human',r'characters\cyborg\cyborg',('GT-gunner',)),('wraith_hatch',r'vehicles\wraith\wraith',('stand opening','stand closing','stand fixed aim-still'))]:
   graph,i=tag(path,'model_animations');h.meta_to_tag_data(graph,'antr',es[i]);clips={}
   for i,a in enumerate(graph.animations.STEPTREE):
    if not a.name.startswith(prefixes):continue
    c=extract_animation(i,graph,write_jma=False)
    clips[a.name]={'duration':a.frame_count/30,'frames':[[{'p':[n.pos_x/100,n.pos_y/100,n.pos_z/100],'q':[n.rot_i,n.rot_j,n.rot_k,n.rot_w]} for n in f] for f in c.frames[:a.frame_count]]}
   data['clips'][key]=clips
  (OUT/'pilots.json').write_text(json.dumps(pilots))
  (OUT/'details.json').write_text(json.dumps(data))
 print('Vehicle variants and seat/hatch source clips extracted',begin)
if __name__=='__main__':extract()
