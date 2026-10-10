#!/usr/bin/env python3
"""Retain original CE vehicle/rigid-body/math functions; audit every adaptation.

No drive/contact/integration equations are substituted. Presentation and world
services are implemented at the explicit boundary in vehicle_physics.c.
"""
from pathlib import Path
import argparse,hashlib,json,re
from prepare_collision import function as source_function
def function(source,name):
    source=re.sub(r"(?m)^((?:static )?(?:void|boolean|real|short|long))\n(?=\w)",r"\1 ",source)
    return source_function(source,name)
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'build/n64/blam-vehicle'
def section(path,start,end):
 s=(ROOT/path).read_text();return s[s.index(start):s.index(end,s.index(start))]
def structure(path,name):
 s=(ROOT/path).read_text();a=s.index('struct '+name+'\n{');b=s.index('\n};',a)+3;return s[a:b]
def adapt(s):
 s=re.sub(r'\bunsigned long\b','uint32_t',s);s=re.sub(r'\blong\b','int32_t',s)
 s=s.replace('LONG_MAX','INT32_MAX').replace('LONG_MIN','INT32_MIN')
 s=s.replace('__inline ', 'static inline ')
 return s

def prepare():
 OUT.mkdir(parents=True,exist_ok=True)
 mh=(ROOT/'source/math/real_math.h').read_text()
 types=mh[mh.index('union real_euler_angles2d\n'):mh.index('/* ---------- prototypes/REAL_MATH.C */')]
 (OUT/'vehicle_math_types.h').write_text(types)
 chunks=[];type_inputs={"source/math/real_math.h": hashlib.sha256(mh.encode()).hexdigest()}
 for path,names in {
 'source/physics/physics_definitions.h':['mass_point_definition','physics_definition'],
 'source/physics/physics.c':['powered_mass_point_definition'],
 'source/physics/physics_variables.h':['physics_variable_speed_parameters'],
 'source/physics/friction_datum.h':['friction_datum'],
 'source/physics/powered_mass_point_datum.h':['powered_mass_point_datum'],
 'source/physics/mass_point_datum.h':['mass_point_datum'],
 'source/physics/physics.h':['physics_instance'],
 'source/units/vehicles.c':['vehicle_definition','physics_mass_point_definition'],
 'source/units/vehicle_datum.h':['_vehicle_datum','vehicle_datum'],
 'source/physics/collision_features.h':['collision_feature','collision_sphere','collision_cylinder','collision_prism','collision_feature_list','collision_plane'],
 }.items():
  type_inputs[path]=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
  for name in names:
   text=structure(path,name)
   if name=='vehicle_definition':text=text.replace('byte unused338[8];','real slide_acceleration, slide_deceleration; /* native 0x338 / 0x33c */')
   chunks.append(text)
 # Types with source names retain field semantics; engine object/tag ownership
 # is provided by the adapter rather than allocating the entire engine tree.
 (OUT/'vehicle_types.h').write_text(adapt('\n'.join(chunks)))
 selected={
 'source/physics/physics.c':['pin_fraction','physics_instance_new','compute_ground_plane','friction_evaluate','physics_compute_new','physics_compute_vehicle_collision','rotate_vectors3d_by_angular_velocity','physics_update_new','physics_update'],
 'source/physics/physics_variables.c':['physics_variable_speed_update','physics_variable_speed_update_seek','physics_variable_position_update_seek','physics_variable_position_update','physics_variable_position_get_seek_direction'],
 'source/units/vehicles.c':['vehicle_accelerate','compute_acceleration','update_alien_fighter_physics_new','update_human_tank_physics','update_human_jeep_physics','update_alien_scout_physics','vehicle_cross_product3d_target','compute_airborne_ticks','slowly_stop_vehicle','vehicle_is_flipped'],
 'source/physics/collision_features.c':['collision_features_new','collision_features_from_point','collision_features_from_line','collision_features_from_polygon','collision_features_from_vertex','collision_features_from_edge','collision_features_from_surface','collision_features_test_point','collision_sphere_test_point','collision_cylinder_test_point','collision_prism_test_point'],
 'source/physics/collision_bsp.c':['collision_surface_polygon','collision_surface_test_point'],
 'source/physics/bsp3d.h':['bsp3d_get_plane_from_designator'],
 'source/math/real_math.h':['distance_squared3d'],
 }
 funcs={};records=[]
 for path,names in selected.items():
  source=(ROOT/path).read_text()
  for name in names:
   s=function(source,name);changes=[]
   if name=='physics_update':
    before='''\tif (physics->radius > 0.0f)
\t{
\t\tphysics_update_old(
\t\t\tobject_index,
\t\t\tpowered_mass_points,
\t\t\tmass_points,
\t\t\tmagic_force,
\t\t\tmagic_torque);
\t\treturn;
\t}'''
    assert before in s;s=s.replace(before,'\tassert(physics->radius <= 0.0f);')
    changes.append('All four exported retail tags select the new solver; fail rather than substitute unsupported legacy tags')
   if name=='compute_ground_plane':
    s=s.replace('struct collision_feature_list features;', 'struct collision_feature_list *features = &vehicle_workspace->features;').replace('&features','features')
    changes.append('Single-threaded non-recursive scratch uses match-only workspace instead of N64 stack')
   if name=='physics_compute_vehicle_collision':
    (OUT/'vehicle_pair_reference.c').write_text(adapt(s.replace(name,name+'_reference')))
    before='\tshort mass_point0_index;'
    after=before+'''
 real_point3d points1[22];
 assert(instance1->physics->mass_points.count<=22);
 for(int j=0;j<instance1->physics->mass_points.count;j++){
  const struct mass_point_definition*m=TAG_BLOCK_GET_ELEMENT(&instance1->physics->mass_points,j,struct mass_point_definition);
  matrix4x3_transform_point(&instance1->world_matrix,&m->position,&points1[j]);
 }
'''
    assert before in s;s=s.replace(before,after)
    before='matrix4x3_transform_point(&instance1->world_matrix, &mass_point1->position, &point1);'
    assert before in s;s=s.replace(before,'point1 = points1[mass_point1_index];')
    before='\t\t\tdistance = normalize3d(&direction);'
    assert before in s;s=s.replace(before,'''            /* Conservative rejection only; overlapping pairs keep original math/order. */
            if(fabsf(direction.i)>radius+.0001f || fabsf(direction.j)>radius+.0001f || fabsf(direction.k)>radius+.0001f)continue;
'''+before)
    changes.append('Hoist invariant second-body contact transforms; reject separated contact AABBs with conservative 0.0001 margin before unchanged normalization/force accumulation; unadapted oracle emitted for differential tests')
   funcs[name]=adapt(s);records.append(dict(source=path,name=name,source_sha256=hashlib.sha256(source.encode()).hexdigest(),function_sha256=hashlib.sha256(function(source,name).encode()).hexdigest(),adaptations=changes+['Xbox 32-bit long made explicit; MSVC inline spelling']))
 # Retain the complete original control/pre-physics portion of vehicle_update.
 # Engine parenting, presentation, damage, sound and animation are separate
 # demake services, not fake implementations of these physics equations.
 vs=(ROOT/'source/units/vehicles.c').read_text();full=function(vs,'vehicle_update')
 start=full.index('\tSET_FLAG(vehicle->vehicle.flags, 2,');end=full.index('\n\tmatch_assert("c:\\\\halo\\\\SOURCE\\\\units\\\\vehicles.c", 308,',start)
 control='static void vehicle_control_update(int32_t vehicle_index){\nstruct vehicle_datum *vehicle=vehicle_datum_get(vehicle_index);\nstruct vehicle_definition *definition=vehicle_specific_definition_get(vehicle->definition_index);\nreal steering_angle,torque;\n'+full[start:end]+'\nvehicle_steering[vehicle_index]=steering_angle;\n}\n'
 funcs['vehicle_control_update']=adapt(control)
 records.append(dict(source='source/units/vehicles.c',name='vehicle_update control blocks',source_sha256=hashlib.sha256(vs.encode()).hexdigest(),adaptations=['Retain contiguous control blocks; adapter dispatches supported vehicle types and gameplay/presentation services separately']))
 # Damage kick arithmetic comes from the original aftermath block; callers
 # supply the exported effect/object values instead of the engine tag registry.
 ds=(ROOT/'source/objects/damage.c').read_text();damage=function(ds,'object_damage_aftermath')
 da=damage.index('\t\treal_vector3d direction = damage->direction;');db=damage.index('\n\t\tswitch (object->object.type)',da)
 body=damage[da:db].replace('damage->direction','*input').replace('damage_effect->damage.instantaneous_acceleration','instantaneous').replace('object_definition->object.acceleration_scale','object_scale')
 funcs['vehicle_damage_acceleration']='static void vehicle_damage_acceleration(const real_vector3d*input,real instantaneous,real object_scale,real_vector3d*result){\n'+body+'\n*result=acceleration;\n}\n'
 records.append(dict(source='source/objects/damage.c',name='object_damage_aftermath acceleration block',source_sha256=hashlib.sha256(ds.encode()).hexdigest(),adaptations=['Tag and damage-record field reads passed as arguments; original upward bias, normalization and tick conversion retained']))
 # Recursively retain required math implementations, including their arithmetic
 # order, normalization thresholds, matrix convention and quaternion handling.
 math_sources=[('source/math/real_math.h',mh)]+[(p,(ROOT/p).read_text()) for p in ['source/math/real_math.c','source/math/matrix_math.c']]
 seen=set(funcs);queue=list(funcs.values())
 while queue:
  text=queue.pop()
  for name in re.findall(r'\b(\w+)\s*\(',text):
   if name in seen or name.startswith(('match_assert','assert_valid','valid_real')):continue
   seen.add(name)
   for path,source in math_sources:
    try:s=function(source,name)
    except RuntimeError:continue
    # Assembly SSE branches do not belong to the N64 arithmetic path.
    if '__asm' in s:raise RuntimeError('Unexpected inline assembly in '+name)
    funcs[name]=adapt(s);queue.append(s)
    records.append(dict(source=path,name=name,source_sha256=hashlib.sha256(source.encode()).hexdigest(),function_sha256=hashlib.sha256(s.encode()).hexdigest(),adaptations=['Xbox widths / inline spelling']))
    break
 prototypes=[]
 for name,s in funcs.items():prototypes.append(s[:s.index('{')].strip()+';')
 table=section('source/math/real_math.c','short const global_projection3d_mappings[3][2][2] =','/* ---------- public code */')
 # The table is the only global from that section needed here.
 table=table[:table.index(';')+1]
 table+='\n'+section('source/math/matrix_math.c','static short data_0030790c[7]', 'void matrix4x3_rotation_from_axis_and_angle(')
 table+='\n'+section('source/physics/physics.c','#define PHYSICS_POINT_FROM_LINE3D','/* ---------- structures */')
 output='/* Generated original implementations. See vehicle-source-manifest.json. */\n'+table+'\n'+'\n'.join(prototypes)+'\n'+'\n'.join(funcs.values())
 (OUT/'vehicle_original.c').write_text(output)
 # Keep the release implementation byte-for-byte unchanged. Diagnostics
 # time complete original bodies via wrappers; their arithmetic is untouched.
 measured={
  'compute_ground_plane':('BG_VP_GROUND','object_index, mass_point, mass_point_definition',False),
  'collision_features_test_point':('BG_VP_FEATURE_TEST','features, point, collision',True),
  'physics_compute_vehicle_collision':('BG_VP_PAIRS','instance0, instance1',True),
 }
 profile=output;wrappers=[]
 for name,(bucket,args,returns) in measured.items():
  original=funcs[name];signature=original[:original.index('{')].strip()
  renamed=original.replace(name+'(',name+'_measured(',1)
  assert renamed!=original
  profile=profile.replace(original,renamed,1)
  call=name+'_measured('+args+')'
  body=('boolean result='+call+';' if returns else call+';')
  wrappers.append(signature+'{ BG_VP_BEGIN; '+body+' BG_VP_END('+bucket+'); '+('return result;' if returns else '')+' }')
 (OUT/'vehicle_profile.c').write_text(profile+'\n'+'\n'.join(wrappers)+'\n')
 for record in records:
  if record['name'] in funcs:record['generated_sha256']=hashlib.sha256(funcs[record['name']].encode()).hexdigest()
 (OUT/'vehicle-source-manifest.json').write_text(json.dumps(records,indent=2)+'\n')
 provenance=dict(structure_sources=type_inputs,generated_files={name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in ['vehicle_original.c','vehicle_types.h','vehicle_math_types.h']},
  boundary_files={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['port/n64/blam/prepare_vehicle.py','port/n64/blam/vehicle_private.h','port/n64/blam/vehicle_physics.c']},
  adaptations=['Minimal object/unit/tag records retain only solver-facing fields; no native whole-object ABI claim',
   'Vehicle definition slide fields named explicitly at original offsets 0x338/0x33c',
   'Lossless int16 collision-edge indices; original float32 planes and positions',
   'BVH candidate enumeration; original feature construction/tests and polygon containment',
   'Bounded pool of demake vehicle handles replaces object partition queries',
   'Blood Gulch has no water; no AI drivers; presentation remains the demake layer',
   'Vehicle explosion selection and biped damage remain demake gameplay services'])
 (OUT/'vehicle-boundary-manifest.json').write_text(json.dumps(provenance,indent=2)+'\n')
 print('Retained',len(funcs),'functions/blocks')
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--output',type=Path,default=OUT)
 OUT=parser.parse_args().output
 prepare()
