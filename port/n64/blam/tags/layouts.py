#!/usr/bin/env python3
"""Cross-compile native Blam tag layouts; read constants without executing MIPS."""
import argparse,json,struct,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
FIELDS={
 'obje_attrs':('struct _object_definition',{'runtime_flags':4}),
 'function':('struct object_function_definition',{
  'runtime_reciprocal_bounds_range':4,'runtime_reciprocal_sawtooth_count':4,
  'runtime_reciprocal_step_count':4,'runtime_one_over_period':4}),
 'unit_attrs':('struct _unit_definition',{'runtime_soft_ping_minimum_interrupt_ticks':2,'runtime_hard_ping_minimum_interrupt_ticks':2}),
 'bipd_attrs':('struct _biped_definition',{
  'runtime_cosine_stationary_turning_threshold':4,'runtime_crouch_transition_velocity':4,
  'runtime_minimum_normal_k':4,'runtime_downhill_k0':4,'runtime_downhill_k1':4,
  'runtime_uphill_k0':4,'runtime_uphill_k1':4,'runtime_pelvis_node_index':2,'runtime_head_node_index':2}),
 'trigger':('struct weapon_trigger_definition',{
  'runtime_illumination_recovery_time':4,'runtime_ejection_port_recovery_time':4,
  'runtime_rate_of_fire_acceleration_time':4,'runtime_rate_of_fire_deceleration_time':4,
  'runtime_error_acceleration_time':4,'runtime_error_deceleration_time':4}),
}
SIZES=('void *','long','struct tag_block','struct tag_reference','struct tag_data',
       'struct object_definition','struct unit_definition','struct biped_definition',
       'struct weapon_definition','struct unit_seat','struct weapon_magazine_definition',
       'struct weapon_trigger_definition')
UNBOUND={
 'model':('struct model',('markers','nodes','regions','geometries','shaders')),
 'model_node':('struct model_node',('default_translation','default_rotation','runtime_default_inverse_matrix')),
 'animation_graph':('struct animation_graph',('unit_seats','first_person_weapon_animations','nodes','animations')),
 'animation':('struct animation',('runtime_parent_animation_index','runtime_normalized_weight','frame_info',
                               'nodes_with_translation_flags','nodes_with_rotation_flags','nodes_with_scale_flags',
                               'compressed_data_offset','default_data','data')),
 'collision_model':('struct collision_model',('resistance','pathfinding_box','pathfinding_spheres','nodes')),
 'damage_resistance':('struct damage_resistance',('maximum_body_vitality','maximum_shield_vitality',
                          'runtime_shield_recharge_velocity','materials','regions','modifiers')),
}


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=ROOT/'build/n64/blam-tags')
 a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 probe=ROOT/'build/n64/blam-probe/objects.log'
 if not probe.exists():p.error('Run port/n64/blam/probe_engine.py first to create the cross-compiler declaration environment.')
 command=json.loads(probe.read_text().splitlines()[1]);command=command[:command.index('-c')]
 source=a.output/'layout_probe.c';obj=a.output/'layout_probe.o';binary=a.output/'layout_probe.bin'
 expressions=[f'sizeof({s})' for s in SIZES]
 for _,(ctype,fields) in FIELDS.items():expressions.extend(f'offsetof({ctype},{name})' for name in fields)
 for _,(ctype,fields) in UNBOUND.items():
  expressions.append(f'sizeof({ctype})')
  for name in fields:expressions.extend((f'offsetof({ctype},{name})',f'sizeof((({ctype}*)0)->{name})'))
 source.write_text('#include "cseries.h"\n#include "object_definitions.h"\n#include "unit_definitions.h"\n#include "biped_definitions.h"\n#include "weapon_definitions.h"\n'
                   '#include "model_definitions.h"\n#include "model_animation_definitions.h"\n#include "collision_model_definitions.h"\n'
                   'const unsigned int tag_layout[] __attribute__((section(".tag_layout")))={\n'+',\n'.join(expressions)+'\n};\n')
 subprocess.run([*command,'-EB','-c',str(source),'-o',str(obj)],cwd=ROOT,check=True)
 objcopy=Path(command[0]).with_name('mips64-elf-objcopy')
 subprocess.run([str(objcopy),'-O','binary','--only-section=.tag_layout',str(obj),str(binary)],check=True)
 values=iter(struct.unpack('>'+str(len(expressions))+'I',binary.read_bytes()[:len(expressions)*4]))
 sizes={name:next(values) for name in SIZES};runtime={}
 for block,(ctype,fields) in FIELDS.items():
  runtime[block]={'ctype':ctype,'fields':{name:{'offset':next(values),'bytes':width} for name,width in fields.items()}}
 unbound={}
 for name,(ctype,fields) in UNBOUND.items():
  unbound[name]={'ctype':ctype,'bytes':next(values),'fields':{field:{'offset':next(values),'bytes':next(values)} for field in fields}}
 assert sizes['void *']==4 and sizes['long']==4
 assert sizes['struct tag_block']==12 and sizes['struct tag_reference']==16 and sizes['struct tag_data']==20
 report={'target':'VR4300 O64 big-endian','sizes':sizes,'runtime_fields':runtime,
         'unbound_native_fields':unbound}
 (a.output/'layouts.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
