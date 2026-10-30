"""Append CE Shade Spartan poses and Wraith hatch to candidate banks only."""
import json,re,struct
import numpy as np
from pack_enemy_vehicles import ROOT,OUT,BANK,BASE,append_array,F,B
from pack_interactions import matrices
from pack_assets import position

def pack():
 d=json.loads((OUT/'details.json').read_text());raw=json.loads((ROOT/'build/n64/assets/extended-raw.json').read_text());world=json.loads((ROOT/'build/n64/assets/extended-reduced.json').read_text());mapping=json.loads((BASE/'world-mesh-sources.json').read_text());nodes=raw['models']['spartan']['nodes'];inverse=np.linalg.inv(matrices(nodes,nodes))
 motion=bytearray((ROOT/'build/n64/frontend-files/interactions.bin').read_bytes());hitmotion=bytearray((ROOT/'build/n64/frontend-files/player-hits.bin').read_bytes());lines=[];lodrows=[];hitrows=[];seat_meta=[]
 def emit(frames,duration,scale):
  coords=np.rint(np.array([[position(p,(0,0,0)) for p in f] for f in frames])*scale).astype(np.int64);assert coords.min()>=-32768 and coords.max()<=32767
  count=len(frames[0]);stride=(count*6+15)&~15;offset=len(motion);assert offset%16==0
  for f in coords:motion.extend(f.astype('>i2').tobytes());motion.extend(bytes(stride-count*6))
  bounds=B(B(map(F,v)) for v in [coords.min(axis=(0,1))/scale,coords.max(axis=(0,1))/scale])
  return B([offset,stride,count,len(frames),F(duration),bounds])
 # Keep native cyborg collision vertex order exactly, including node boundaries.
 from reclaimer.meta.wrappers.halo1_map import Halo1Map
 import contextlib
 with (BANK/'shade-seat.log').open('w') as log,contextlib.redirect_stdout(log):
  h=Halo1Map();h.load_map(ROOT/'build/n64/assets/b40-decompressed.map');es=h.tag_index.tag_index
  collision=h.get_meta(next(i for i,e in enumerate(es) if e.class_1.enum_name=='model_collision_geometry' and e.path==r'characters\cyborg\cyborg'))
 hitvertices=[]
 for n in collision.nodes.STEPTREE:
  ni=next(i for i,v in enumerate(nodes) if v['name']==n.name)
  for bsp in n.bsps.STEPTREE:hitvertices.extend((ni,np.array([x,y,z,1])) for x,y,z,_ in struct.iter_unpack('<fffi',bsp.vertices.STEPTREE))
 for ci,label in enumerate(['GT-gunner unarmed idle','GT-gunner enter','GT-gunner exit']):
  c=d['clips']['shade_human'][label];frames=c['frames'];frames=[frames[round(i*(len(frames)-1)/3)] for i in range(4)] if ci==0 else frames
  poses=[matrices(f,nodes) for f in frames];row=[]
  for model,sources in [(world['models']['spartan'],mapping['spartan']),(world['spartan_lod'],mapping['spartan_lod'])]:
   corners=[(np.array([*p,1]),ws) for t in model['triangles'] for p,ws in zip(t['p'],t['weights'])]
   out=[[sum(((pose@inverse)[b]@corners[i][0])*w for b,w in corners[i][1])[:3].tolist() for i in sources] for pose in poses]
   row.append(emit(out,c['duration'],128))
  lodrows.append(B(row));offset=len(hitmotion);stride=(len(hitvertices)*6+15)&~15
  for pose in poses:
   pts=np.rint(np.array([position((pose[ni]@p)[:3],(0,0,0)) for ni,p in hitvertices])*1024).astype('>i2');hitmotion.extend(pts.tobytes());hitmotion.extend(bytes(stride-len(hitvertices)*6))
  hitrows.append(B([offset,stride,len(frames),F(c['duration'])]));seat_meta.append(c)
 interaction=(BASE/'interaction_assets.c').read_text();pose_count=len(json.loads((BASE/'interaction-report.json').read_text())['body_clips'])
 interaction=append_array(interaction,'bg_seat_poses',[B(lodrows)])
 # Mounted Shade has no personal weapon; a valid inherited unused hand grip is
 # still required by the shared body preparation code.
 match=re.search(r'bg_seat_grips\[\d+\]=\{(.*?)\};',interaction,re.S);assert match
 first=match[1][:match[1].find('}},')+2];interaction=append_array(interaction,'bg_seat_grips',[first],pose_count+1)
 (BANK/'interaction_assets.c').write_text(interaction);(BANK/'interactions.bin').write_bytes(motion)
 text=(BANK/'combat_data.c').read_text();m=re.search(r'bg_player_hit_clips\[\]=\{(.*?)\};',text,re.S);hit_index=m[1].count('},')
 text=append_array(text,'bg_player_hit_clips',hitrows);text+='\nconst unsigned bg_shade_player_hit_clip='+str(hit_index)+';\n'
 # Original Wraith hatch node2: identical fixed-point matrix for visuals/hits.
 model=json.loads((OUT/'extended-raw.json').read_text())['models']['wraith'];inv=np.linalg.inv(matrices(model['nodes'],model['nodes'])[2]);basis=np.array([[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1]]);hrows=[]
 for label in ['stand opening','stand closing']:
  c=d['clips']['wraith_hatch'][label];frames=[]
  for f in c['frames']:
   mat=basis@matrices(f,model['nodes'])[2]@inv@basis.T
   frames.append(np.rint(np.array([mat[:3,3],mat[:3,0],mat[:3,1],mat[:3,2]])*4096).astype(int).tolist())
  sym='hit_wraith_'+label.split()[1];lines.append('static const int16_t '+sym+'[][4][3]='+str(frames).replace('[','{').replace(']','}')+';');hrows.append(B([sym,len(frames)]))
 text='\n'.join(['#include "combat_geometry.h"',*lines])+'\n'+text;text=append_array(text,'bg_hit_hatches',[B(hrows)],3)
 (BANK/'combat_data.c').write_text(text);(BANK/'player-hits.bin').write_bytes(hitmotion)
 # Replace only the Shade row generated by pack_enemy_vehicles.
 text=(BANK/'interaction_defs.c').read_text();pos=text.rfind(',0}}');assert pos>=0;text=text[:pos]+','+str(pose_count)+'}}'+text[pos+5:]
 (BANK/'interaction_defs.c').write_text(text)
 (BANK/'seat-detail-report.json').write_text(json.dumps({'shade_pose':pose_count,'shade_hit_clip':hit_index,'human_clips':[{'name':n,'duration':c['duration'],'frames':len(c['frames'])} for n,c in zip(['idle','enter','exit'],seat_meta)],'interaction_bytes':len(motion),'hit_bytes':len(hitmotion),'wraith_hatch_frames':20},indent=2))
 print('Shade human pose',pose_count,'hit clip',hit_index,'Wraith hatch appended')
if __name__=='__main__':pack()
