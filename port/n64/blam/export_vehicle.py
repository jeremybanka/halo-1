#!/usr/bin/env python3
"""Export native 30 Hz vehicle physics tags and undecimated collision topology.

Only the world broad phase is replaced by a BVH. Original face/edge/vertex
features and material responses are retained; no render LOD is used for physics.
"""
import argparse,contextlib,hashlib,json,math,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'build/n64/generated'
ROM_FILES=ROOT/'build/n64/frontend-files'
sys.path.insert(0,str(Path(__file__).parent/'tags'))
from audit import CacheGraph
from export_collision import decode,check,polygons,number,row

def scalar(v):return number(float(v))
def vec(v):return '{.n={'+','.join(scalar(x) for x in v)+'}}'
def fields(o,names):return ','.join('.'+n+'='+scalar(getattr(o,n)) for n in names)
def export():
 OUT.mkdir(parents=True,exist_ok=True)
 with (OUT/'vehicle-export.log').open('w') as log,contextlib.redirect_stdout(log):
  g=CacheGraph(ROOT/'build/n64/assets');data,_=decode(ROOT/'build/n64/assets/bloodgulch-decompressed.map')
 check(data);lines=['/* Native cache values; no HEK unit conversion. Do not commit. */','#include "blam/vehicle_private.h"']
 keys=[k for k in g.root_ids() if g.entry(k).class_1.enum_name=='vehicle'];keys.sort(key=lambda k:next(i for i,n in enumerate(['warthog','ghost','scorpion','banshee']) if n in g.entry(k).path))
 pdefs=[];vdefs=[];susp=[];bounds=[];seat_times=[];accel_scales=[];report=[]
 for kind,k in enumerate(keys):
  vehicle=g.meta(k);v=vehicle.vehi_attrs;p=g.meta((k[0],vehicle.obje_attrs.physics.id&65535));assert p.radius<=0 and p.mass_points.size<=22 and p.powered_mass_points.size<=2
  lines+=[f'static const struct mass_point_definition mass_{kind}[]={{']
  for m in p.mass_points.STEPTREE:
   lines+=['{.name='+json.dumps(m.name)+',.powered_mass_point_index='+str(m.powered_mass_point)+',.model_node_index='+str(m.model_node)+',.flags='+str(m.flags.data)+','+fields(m,['relative_mass','mass','relative_density','density','friction_parallel_scale','friction_perpendicular_scale','radius'])+',.position='+vec(m.position)+',.forward='+vec(m.forward)+',.up='+vec(m.up)+',.friction_type='+str(m.friction_type.data)+'},']
  lines+=['};',f'static const struct powered_mass_point_definition power_{kind}[]={{']
  for m in p.powered_mass_points.STEPTREE:lines+=['{.name='+json.dumps(m.name)+',.flags='+str(m.flags.data)+','+fields(m,['antigrav_strength','antigrav_offset','antigrav_height','antigrav_damp_fraction','antigrav_normal_k1','antigrav_normal_k0'])+'},']
  lines+=['};',f'static const real_matrix3x3 inertia_{kind}[]={{']
  for m in p.inertia_matrices.STEPTREE:lines+=['{.n={'+','.join('{'+','.join(scalar(x) for x in r)+'}' for r in m)+'}},']
  lines+=['};']
  pdefs+=['{'+fields(p,['radius','mass','density','gravity_scale','ground_friction','ground_depth','ground_damp_fraction','ground_normal_k1','ground_normal_k0','water_friction','water_depth','water_density','air_friction','xx_moment','yy_moment','zz_moment'])+',.moment='+scalar(p.moment_scale)+',.center_of_mass='+vec(p.center_of_mass)+f',.inertial_matrix={{2,inertia_{kind},0}},.powered_mass_points={{{p.powered_mass_points.size},power_{kind},0}},.mass_points={{{p.mass_points.size},mass_{kind},0}}'+'}']
  offsets=['maximum_forward_speed','maximum_reverse_speed','speed_acceleration','speed_deceleration','maximum_left_turn','maximum_right_turn','wheel_circumference','turn_rate','blur_speed']
  targets=['unknown2f8','unknown2fc','unknown300','unknown304','unknown308','unknown30c','wheel_circumference','unknown314','unknown318']
  # Native Banshee fixed-gun-pitch is stored in radians at 0x364.
  vdefs+=['{.unit={.object={.physics={'+str(kind)+'}}},.flags='+str(v.flags.data)+',.vehicle_type='+str(v.type.data)+','+','.join('.'+b+'='+scalar(getattr(v,a)) for a,b in zip(offsets,targets))+',.unknown330='+scalar(v.maximum_left_slide)+',.unknown334='+scalar(v.maximum_right_slide)+',.slide_acceleration='+scalar(v.slide_acceleration)+',.slide_deceleration='+scalar(v.slide_deceleration)+',.unknown340='+scalar(v.minimum_flipping_angular_velocity)+',.unknown344='+scalar(v.maximum_flipping_angular_velocity)+',.unknown364='+scalar(v.fixed_gun_pitch)+'}']
  accel_scales.append(scalar(vehicle.obje_attrs.acceleration_scale))
  ps=list(vehicle.unit_attrs.powered_seats.STEPTREE)
  seat_times.append('{'+','.join('{'+scalar(x.driver_powerup_time)+','+scalar(x.driver_powerdown_time)+'}' for x in ps)+(',' if ps else '')+','.join('{1,1}' for _ in range(2-len(ps)))+'}')
  a=g.meta((k[0],vehicle.obje_attrs.animation_graph.id&65535));ss=list(a.vehicles.STEPTREE[0].suspension_animations.STEPTREE) if a.vehicles.size else []
  assert len(ss)<=8
  susp.append('{'+','.join(str(s.mass_point_index) for s in ss)+(',' if ss else '')+','.join('-1' for _ in range(8-len(ss)))+'}')
  bounds.append('{'+','.join('{'+scalar(s.full_extension_ground_depth)+','+scalar(s.full_compression_ground_depth)+'}' for s in ss)+(',' if ss else '')+','.join('{0,0}' for _ in range(8-len(ss)))+'}')
  report.append(dict(path=g.entry(k).path,cache=k[0],mass_points=p.mass_points.size,powered=p.powered_mass_points.size,mass=p.mass,radius=p.radius))
 lines+=['const struct physics_definition bg_vehicle_physics_defs[4]={'+',\n'.join(pdefs)+'};','const struct vehicle_definition bg_vehicle_drive_defs[4]={'+',\n'.join(vdefs)+'};','const int8_t bg_vehicle_suspension_points[4][8]={'+','.join(susp)+'};','const float bg_vehicle_suspension_bounds[4][8][2]={'+','.join(bounds)+'};']
 lines+=['const float bg_vehicle_acceleration_scale[4]={'+','.join(accel_scales)+'};']
 lines+=['const float bg_vehicle_seat_times[4][2][2]={'+','.join(seat_times)+'};']
 assert all(len(data[n])<8192 for n in ['surfaces','edges','vertices'])
 cache=g.caches['bloodgulch'];entries=cache.tag_index.tag_index
 damage_paths=[None,r'weapons\needler\detonation damage',r'weapons\rocket launcher\explosion',r'weapons\frag grenade\explosion',r'weapons\plasma grenade\explosion',r'vehicles\scorpion\shell explosion',r'weapons\flamethrower\explosion']
 kicks=[]
 for path in damage_paths:
  if path is None:kicks.append('{0,0}');continue
  damage=g.meta(('bloodgulch',next(i for i,e in enumerate(entries) if e.class_1.enum_name=='damage_effect' and e.path==path))).damage
  kicks.append('{'+scalar(damage.instantaneous_acceleration)+','+str(damage.flags.data)+'}')
 lines+=['const struct vehicle_damage_kick bg_vehicle_damage_kicks[7]={'+','.join(kicks)+'};']
 bsp=cache.get_meta(next(i for i,e in enumerate(entries) if e.class_1.enum_name=='scenario_structure_bsp'),disable_tag_cleaning=True)
 mats=g.meta(('bloodgulch',next(i for i,e in enumerate(entries) if e.class_1.enum_name=='globals'))).materials.STEPTREE
 assert len(mats)<=33
 lines+=['const struct material_definition bg_vehicle_materials[33]={']
 names=['ground_friction_scale','ground_friction_normal_k1_scale','ground_friction_normal_k0_scale','ground_depth_scale','ground_damp_fraction_scale']
 lines+=['{'+','.join(scalar(getattr(m,n)) for n in names)+'},' for m in mats];lines+=['};']
 lines+=['const float bg_vehicle_floor='+scalar(bsp.vehicle_floor)+',bg_vehicle_ceiling='+scalar(bsp.vehicle_ceiling)+';']
 # Resolve collision material indices to global physics materials once.
 materials=[(int(m.unknown)>>16)&65535 for m in bsp.collision_materials.STEPTREE]
 for i,s in enumerate(data['surfaces']):
  material=materials[s[-1]] if s[-1]>=0 else -1;assert -1<=material<33
  data['surfaces'][i]=(*s[:-1],material)
 geometry_start=len(lines)
 for name,ctype in [('planes','real_plane3d'),('surfaces','struct collision_surface'),('edges','struct collision_edge'),('vertices','struct collision_vertex')]:
  lines += [f'static const {ctype} vehicle_{name}[]={{']+[row(name,r)+',' for r in data[name]]+['};']
 lines+=['#define BLOCK(n) {sizeof(vehicle_##n)/sizeof(vehicle_##n[0]),vehicle_##n,0}','struct collision_bsp bg_vehicle_bsp={{{0,0,0},BLOCK(planes)},BLOCK(surfaces),BLOCK(edges),BLOCK(vertices)};','#undef BLOCK']
 # A balanced surface BVH keeps broad-phase work logarithmic without storing
 # Xbox BSP ownership/connectivity arrays. All leaves reference original faces.
 bounds=[]
 for poly in polygons(data):
  points=[data['vertices'][j][:3] for j in poly]
  box=[math.floor(min(p[a] for p in points)*64) for a in range(3)]+[math.ceil(max(p[a] for p in points)*64) for a in range(3)]
  assert all(-32768<=v<=32767 for v in box);bounds.append(box)
 indices=[];tree=[];max_depth=0
 def build(ids,depth=0):
  nonlocal max_depth
  max_depth=max(max_depth,depth)
  box=[min(bounds[i][a] for i in ids) for a in range(3)]+[max(bounds[i][a+3] for i in ids) for a in range(3)]
  index=len(tree);tree.append(None)
  if len(ids)<=8:
   first=len(indices);indices.extend(ids);tree[index]=(box,first,len(ids))
  else:
   axis=max(range(3),key=lambda a:max(bounds[i][a]+bounds[i][a+3] for i in ids)-min(bounds[i][a]+bounds[i][a+3] for i in ids))
   ids.sort(key=lambda i:bounds[i][axis]+bounds[i][axis+3]);middle=len(ids)//2
   assert build(ids[:middle],depth+1)==index+1
   right=build(ids[middle:],depth+1);tree[index]=(box,right,0)
  return index
 build(list(range(len(bounds))));assert max_depth<31 and len(tree)<32768
 lines+=['static const int16_t vehicle_surface_bounds[][6]={'+','.join('{'+','.join(map(str,b))+'}' for b in bounds)+'};']
 lines+=['static const struct vehicle_bvh_node vehicle_bvh[]={'+','.join('{{'+','.join(map(str,b))+'},'+str(first)+','+str(count)+'}' for b,first,count in tree)+'};','static const uint16_t vehicle_surface_indices[]={'+','.join(map(str,indices))+'};']
 # The same lossless bank is resident only during matches on N64. The front
 # end reuses its heap space; host tests keep typed C arrays as an endian oracle.
 lines+=['const struct vehicle_bvh_node *bg_vehicle_bvh=vehicle_bvh;',
  'const uint16_t *bg_vehicle_surface_indices=vehicle_surface_indices;',
  'const int16_t (*bg_vehicle_surface_bounds)[6]=vehicle_surface_bounds;']
 blob=bytearray();layout=[]
 blocks=[(data['planes'],'4f'),(data['surfaces'],'2iBBh'),(data['edges'],'6h'),(data['vertices'],'3fi'),
  ([(*b,first,count) for b,first,count in tree],'6h2H'),(bounds,'6h'),([(i,) for i in indices],'H')]
 for values,fmt in blocks:
  assert len(blob)%4==0
  layout.append((len(blob),len(values)))
  for value in values:
   packed=struct.pack('>'+fmt,*value)
   assert tuple(struct.unpack('>'+fmt,packed))==tuple(value)
   blob.extend(packed)
 bank=ROM_FILES/'vehicle-world.bin';bank.parent.mkdir(parents=True,exist_ok=True);bank.write_bytes(blob)
 lines=lines[:geometry_start]+['#ifndef N64']+lines[geometry_start:]+['#else',
  'struct collision_bsp bg_vehicle_bsp;',
  'const struct vehicle_bvh_node *bg_vehicle_bvh;',
  'const uint16_t *bg_vehicle_surface_indices;',
  'const int16_t (*bg_vehicle_surface_bounds)[6];','#endif',
  'const unsigned bg_vehicle_world_bytes='+str(len(blob))+';',
  'const unsigned bg_vehicle_world_layout[7][2]={'+','.join('{'+str(o)+','+str(n)+'}' for o,n in layout)+'};']
 out=OUT/'vehicle_data.c';out.write_text('\n'.join(lines)+'\n')
 record=dict(world_bank_bytes=len(blob),world_bank_sha256=hashlib.sha256(blob).hexdigest(),vehicles=report,bvh_nodes=len(tree),bvh_depth=max_depth,surface_count=len(indices),source_maps=g.sources,files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'port/n64/blam/vehicle_private.h',out]})
 (OUT/'vehicle-report.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record['vehicles'],indent=2))
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--output',type=Path,default=OUT)
 parser.add_argument('--rom-files',type=Path,default=ROM_FILES)
 args=parser.parse_args();OUT=args.output;ROM_FILES=args.rom_files
 export()
