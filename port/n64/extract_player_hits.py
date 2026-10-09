"""Original cyborg collision surfaces animated on the demake's visual timeline.

Frames live in ROM. Only two endpoints and four live collision poses are kept
in RAM; there is no per-frame allocation or simplified head/torso proxy.
"""
import json,struct
import numpy as np
from pack_fp_ammo import globals_for,rotate,overlay_states

def player_hits(h,campaign,root):
 from reclaimer.animation.animation_decompilation import extract_animation
 raw=json.loads((root/'build/n64/assets/extended-raw.json').read_text())
 reduced=json.loads((root/'build/n64/assets/extended-reduced.json').read_text())
 nodes=raw['models']['spartan']['nodes'];es=h.tag_index.tag_index
 def meta(cache,path,kind):
  es=cache.tag_index.tag_index;i=next(i for i,e in enumerate(es) if e.path==path and e.class_1.enum_name==kind)
  value=cache.get_meta(i)
  if kind=='model_animations':cache.meta_to_tag_data(value,'antr',es[i])
  return value
 collision=meta(h,r'characters\cyborg\cyborg','model_collision_geometry')
 vertices=[];triangles=[];regions=[];groups=[]
 for node in collision.nodes.STEPTREE:
  ni=next(i for i,n in enumerate(nodes) if n['name']==node.name);start=len(triangles)
  for bsp in node.bsps.STEPTREE:
   base=len(vertices);vertices.extend((ni,[x,y,z]) for x,y,z,_ in struct.iter_unpack('<fffi',bsp.vertices.STEPTREE))
   edges=list(struct.iter_unpack('<6i',bsp.edges.STEPTREE))
   for si,(_,first,flags,_,material) in enumerate(struct.iter_unpack('<iiBbh',bsp.surfaces.STEPTREE)):
    if flags&2:continue
    polygon=[];edge=first
    while True:
     a,b,forward,reverse,left,right=edges[edge];polygon.append(base+(a if left==si else b));edge=forward if left==si else reverse
     if edge==first:break
    for j in range(1,len(polygon)-1):
     triangles.append([polygon[0],polygon[j],polygon[j+1]])
     name=collision.materials.STEPTREE[material].name;regions.append(2 if name=='head' else 0 if name=='legs' else 1)
  if len(triangles)>start:groups.append([start,len(triangles)-start])
 bank=bytearray();clips=[]
 def emit(frames,duration):
  stride=(len(vertices)*6+15)&~15;offset=len(bank)
  for frame in frames:
   transforms=globals_for(frame,nodes);points=[]
   for ni,p in vertices:
    r,t=transforms[ni];q=rotate(r,p);q=[q[a]+t[a] for a in range(3)]
    points.append([round(q[0]*1024),round(q[2]*1024),round(-q[1]*1024)])
   assert all(-32768<=v<=32767 for p in points for v in p)
   data=np.array(points,dtype='>i2').tobytes();bank.extend(data);bank.extend(bytes(stride-len(data)))
  clips.append(dict(offset=offset,stride=stride,count=len(frames),duration=duration))
 for name,c in raw['animations'].items():
  count=len(reduced['animations'][name]['frames']);frames=[]
  for i in range(count):
   states=c['frames'][round(i*(len(c['frames'])-1)/max(1,count-1))]
   if c['type']=='overlay':states=overlay_states(raw['animations']['idle']['frames'][0],states,dict(rot=c['rot_flags'],trans=c['trans_flags'],scale=c['scale_flags']))
   frames.append(states)
  emit(frames,c['duration'])
 graph=meta(h,r'characters\cyborg\cyborg','model_animations')
 def clip(i,idle=False):
  a=extract_animation(i,graph,write_jma=False);count=graph.animations.STEPTREE[i].frame_count
  frames=[[{'p':[n.pos_x/100,n.pos_y/100,n.pos_z/100],'q':[n.rot_i,n.rot_j,n.rot_k,n.rot_w]} for n in frame] for frame in a.frames[:count]]
  if idle and count>4:frames=[frames[round(i*(count-1)/3)] for i in range(4)]
  emit(frames,count/30)
 for name in ['stand rifle ready','crouch rifle idle','crouch rifle move-front','stand rifle land-soft','stand rifle land-hard','crouch rifle land-soft','crouch rifle land-hard']:
  clip(next(i for i,a in enumerate(graph.animations.STEPTREE) if a.name==name))
 seen=set()
 for name,path in [('warthog',r'vehicles\warthog\warthog'),('ghost',r'vehicles\ghost\ghost_mp'),('scorpion',r'vehicles\scorpion\scorpion_mp'),('banshee',r'vehicles\banshee\banshee')]:
  v=meta(campaign if name=='banshee' else h,path,'vehicle');seats=list(v.unit_attrs.seats.STEPTREE)
  if name=='warthog':seats=[seats[i] for i in (0,2,1)]
  for seat in seats:
   unit=next(u for u in graph.units.STEPTREE if u.label==seat.label)
   ids=(unit.weapons.STEPTREE[0].animations.STEPTREE[0].animation,unit.animations.STEPTREE[7].animation,unit.animations.STEPTREE[8].animation)
   if ids in seen:continue
   seen.add(ids)
   for i,index in enumerate(ids):clip(index,i==0)
 (root/'build/n64/frontend-files/player-hits.bin').write_bytes(bank)
 def array(v):return str(v).replace('[','{').replace(']','}')
 lines=['const uint16_t bg_player_hit_triangles[][3]='+array(triangles)+';',
 'const uint8_t bg_player_hit_regions[]='+array(regions)+';',
 'const uint16_t bg_player_hit_groups[][2]='+array(groups)+';',
 'const unsigned bg_player_hit_vertex_count='+str(len(vertices))+';',
 'const unsigned bg_player_hit_group_count='+str(len(groups))+';',
 'const bg_hit_clip bg_player_hit_clips[]={']
 for c in clips:lines.append('{'+f'{c["offset"]},{c["stride"]},{c["count"]},{c["duration"]:.9f}f'+'},')
 lines.append('};')
 return lines,dict(vertices=len(vertices),triangles=len(triangles),groups=len(groups),clips=clips,rom_bytes=len(bank),source=r'characters\cyborg\cyborg')
