"""Check vehicle world registration on every map and live Sidewinder contacts."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HARNESS = r'''
#include "blam/runtime.h"
int main(void){
 unsigned checked=0;
 const unsigned maps[]={9,1,0,2,3,4,5,6,7,8,10,11,12};
 for(unsigned at=0;at<13;at++){
  unsigned id=maps[at];
  assert(bg_map_load(id));bg_set_players(4);bg_reset();
  if(!bg_vehicle_count)bg_add_vehicle(BG_V_WARTHOG,bg_players[0].pos,bg_players[0].yaw);
  bg_vehicle_physics_prepare();
  for(unsigned i=0;i<bg_vehicle_count;i++){
   const bg_vehicle*v=&bg_vehicles[i];const float*o=bg_map_origin();
   struct physics_instance instance;physics_instance_new(&instance,i);
   const float expected[3]={v->pos[0]+o[0],-v->pos[2]+o[1],v->pos[1]+o[2]};
   for(unsigned a=0;a<3;a++){
    if(fabsf(instance.world_matrix.position.n[a]-expected[a])>.00003f){
     fprintf(stderr,"map %u vehicle %u axis %u root %.9g source %.9g\n",id,i,a,
      instance.world_matrix.position.n[a],expected[a]);return 3;
    }
   }
   checked++;
  }
  bg_map_unload();
 }
 assert(bg_map_load(BG_MAP_SIDEWINDER));bg_set_players(4);bg_reset();bg_vehicle_physics_prepare();
 assert(bg_vehicle_count==8);
 bool contacted[8]={0};unsigned pose_steps=0;
 for(unsigned tick=0;tick<300;tick++)
  for(unsigned i=0;i<bg_vehicle_count;i++){
   bg_vehicle_physics_step(i,NULL);
   const bg_vehicle*v=&bg_vehicles[i];const float*o=bg_map_origin();
   struct physics_instance instance;physics_instance_new(&instance,i);
   const float expected[3]={v->pos[0]+o[0],-v->pos[2]+o[1],v->pos[1]+o[2]};
   for(unsigned a=0;a<3;a++)assert(fabsf(instance.world_matrix.position.n[a]-expected[a])<.00003f);
   for(int j=0;j<instance.physics->mass_points.count&&!contacted[i];j++){
    const struct mass_point_definition*m=TAG_BLOCK_GET_ELEMENT(&instance.physics->mass_points,j,struct mass_point_definition);
    struct mass_point_datum point={0};matrix4x3_transform_point(&instance.world_matrix,&m->position,&point.position);
    compute_ground_plane(i,&point,m);contacted[i]|=point.ground_material_type!=NONE;
   }
   pose_steps++;
  }
 unsigned rest=0,contacts=0,below=0;
 for(unsigned i=0;i<bg_vehicle_count;i++){
  const bg_vehicle*v=&bg_vehicles[i];float floor=bg_floor(v->pos[0],v->pos[2],v->pos[1]+2);
  fprintf(stderr,"Sidewinder vehicle %u pos %.6f %.6f %.6f home %.6f %.6f %.6f floor %.6f speed %.6f\n",
   i,v->pos[0],v->pos[1],v->pos[2],v->home[0],v->home[1],v->home[2],floor,v->speed);
  contacts+=contacted[i];below+=v->pos[1]<=bg_map_void_height();
  assert(floor>-999&&v->pos[1]>bg_map_void_height()&&fabsf(v->pos[1]-floor)<1.5f);
  rest+=TEST_FLAG(native[i].object.flags,_object_at_rest_bit)!=0;
  printf("Sidewinder vehicle %u kind %u floor gap %.6f speed %.6f resting %d\n",
   i,v->kind,v->pos[1]-floor,v->speed,TEST_FLAG(native[i].object.flags,_object_at_rest_bit)!=0);
 }
 bg_map_unload();
 assert(contacts==8&&rest==8&&below==0);
 printf("PASS: %u map-registered native poses and %u Sidewinder step poses; all eight vehicles encounter source ground (%u resting, %u below void after free simulation)\n",checked,pose_steps,rest,below);
}
'''


def run(out, reference=None):
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    solver = out / 'solver'
    for name in ('prepare_vehicle.py','export_vehicle.py'):
        args = [sys.executable,str(ROOT/'port/n64/blam'/name),'--output',str(solver)]
        if name == 'export_vehicle.py':args += ['--rom-files',str(solver)]
        subprocess.run(args,cwd=ROOT,check=True)
    original = (ROOT/'port/n64/blam/vehicle_physics.c').read_text()
    source = out/'origin.c'
    shared = ['map.c','game.c','combat_geometry.c','terrain.c','movement.c','blam/runtime.c','blam/core.c']
    banks = ['combat_data.c','movement_data.c','interaction_defs.c']
    flags = ['-std=c17','-O2','-g','-fsanitize=address,undefined','-ffp-contract=off',
             '-fno-strict-aliasing','-fwrapv','-Wno-multichar','-Wno-unused-function',
             '-Wno-incompatible-pointer-types','-DBG_STREAM_MAPS','-DBG_BODY_CANDIDATES',
             '-Iport/n64','-Iport/n64/blam','-Ibuild/n64/blam-core','-I'+str(solver)]
    environment = {**os.environ,'BG_MAP_DIRECTORY':str(ROOT/'halo64-assets/generated/maps')}
    for label,math in [('strict',['-fno-fast-math']),
                       ('target',['-ffast-math','-ftrapping-math','-fno-associative-math'])]:
        source.write_text(original+HARNESS)
        binary = out/label
        command = ['clang',*flags,*math,str(source),
                   *(str(ROOT/'port/n64'/p) for p in shared),
                   *(str(ROOT/'build/n64/generated'/p) for p in banks),
                   str(ROOT/'halo64-assets/generated/maps/common_data.c'),str(solver/'vehicle_data.c'),
                   '-lm','-o',str(binary)]
        subprocess.run(command,cwd=ROOT,check=True)
        subprocess.run([str(binary)],cwd=ROOT,env=environment,check=True)
        if reference and label=='strict':
            checkpoint=subprocess.check_output(['git','show',reference+':port/n64/blam/vehicle_physics.c'],cwd=ROOT,text=True)
            source.write_text(checkpoint+HARNESS)
            control=out/'checkpoint';command[-1]=str(control)
            subprocess.run(command,cwd=ROOT,check=True)
            result=subprocess.run([str(control)],cwd=ROOT,env=environment,capture_output=True,text=True)
            (out/'checkpoint-failure.txt').write_text(result.stdout+result.stderr)
            assert result.returncode==3,result
            print('PASS: checkpoint fails the source-coordinate registration check')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'build/n64-expansion-research/vehicle-origin')
    parser.add_argument('--reference',help='Optional checkpoint that must fail the source-coordinate check')
    args=parser.parse_args();run(args.output_dir,args.reference)
