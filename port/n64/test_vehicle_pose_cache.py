import re
"""Compare actual cached vehicle preparation against its unchanged miss path.

The host harness links real game/replay sources and extracts current rig tables
and SDK matrix math. Separate output banks prevent the reference from filling a
missing cached slot. Host libm replaces N64 trig; all fixed16.16 coefficients and
active part/union bounds are compared exactly. This is not a target speed test.
"""
from pathlib import Path
import sys,re,subprocess,json,hashlib
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'build/n64/performance-audit/vehicle-pose-cache'
OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'port/n64'))
from test_render_matrix import function
from test_vehicle_culling import declaration
main=(ROOT/'port/n64/main.c').read_text();assets=(ROOT/'port/n64/asset_models.h').read_text();bank=(ROOT/'build/n64/generated/models_data.c').read_text()
sdk=ROOT.parent/'n64-3d-splitscreen/.build/tiny3d/src/t3d'
header=(sdk/'t3dmath.h').read_text();math=(sdk/'t3dmath.c').read_text()
pre=r'''
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "game.h"
#include "replay.h"
#include "blam/runtime.h"
#include "render_bounds.h"
#include "render_pose_cache.h"
#define BG_OBJECT_SCALE 1024.f
#define BG_FRAME_SLOTS 2
#define fm_cosf cosf
#define fm_sinf sinf
typedef struct {float v[3];} T3DVec3;
typedef struct {float m[4][4];} T3DMat4;
/* Compare integer16.16 coefficients before host-endian serialization. */
typedef struct {int32_t c[4][3];uint32_t reserved[4];} T3DMat4FP;
static void t3d_mat4_to_fixed_3x4(T3DMat4FP*out,const T3DMat4*in){
 for(unsigned c=0;c<4;c++)for(unsigned r=0;r<3;r++)out->c[c][r]=(int32_t)(in->m[c][r]*65536.f);
}
static unsigned slot;
static float wheel_rotation[BG_MAX_VEHICLES];
static bg_vehicle_pose_cache vehicle_pose_cache[BG_MAX_VEHICLES];
typedef struct {
 T3DMat4FP vehicle[BG_FRAME_SLOTS][BG_MAX_VEHICLES];
 T3DMat4FP parts[BG_FRAME_SLOTS][BG_MAX_VEHICLES][7];
 bg_cull_bounds bounds[BG_MAX_VEHICLES],part_bounds[BG_MAX_VEHICLES][7];
} outputs;
static outputs all_outputs[2],*state;
#define vehicle_matrices state->vehicle
#define part_matrices state->parts
#define vehicle_bounds state->bounds
#define vehicle_part_bounds state->part_bounds
'''
# Cached and uncached paths use the same current full rigid-body pose.
c=pre+assets[assets.index('enum { BG_PART_BODY'):assets.index('extern const bg_vehicle_rig')]
for name in ('parts_warthog','parts_ghost','parts_scorpion','parts_banshee','bg_vehicle_rigs','bg_vehicle_lod_bounds'):
 c+='\n'+declaration(bank,name)
c+='\nconst bg_bounds bg_vehicle_micro_gate_bounds[4]='+declaration((ROOT/'build/n64/generated/micro_data.c').read_text(),'bg_vehicle_micro_gate_bounds').split('=',1)[1]
c+='\n'+declaration((ROOT/'build/n64/generated/vehicle_visuals_data.c').read_text(),'bg_covenant_wreck_bounds')
interaction=(ROOT/'port/n64/asset_interaction.h').read_text()
c+='\n'+interaction[interaction.index('typedef struct {'):interaction.index('extern const bg_rom_pose')]
c+='\n'+re.search(r'const bg_rom_pose bg_hatch_poses[^;]+;', (ROOT/'build/n64/generated/interaction_assets.c').read_text()).group()
c+=r'''
static void t3d_mat4_identity(T3DMat4*m){memset(m,0,sizeof(*m));for(unsigned a=0;a<4;a++)m->m[a][a]=1;}
static void bg_interaction_points(int16_t(*out)[3],const bg_rom_pose*p,float seconds){
 static FILE*f;if(!f){f=fopen("build/n64/frontend-files/interactions.bin","rb");assert(f);}
 float frame=fminf(fmaxf(seconds/p->duration,0),1)*(p->frames-1);
 unsigned f0=frame,f1=f0+1<p->frames?f0+1:f0;int fraction=(frame-f0)*256;
 int16_t points[2][4][3];assert(p->vertices==4);
 for(unsigned sample=0;sample<2;sample++){
  assert(!fseek(f,p->offset+p->stride*(sample?f1:f0),SEEK_SET));
  for(unsigned i=0;i<4;i++)for(unsigned a=0;a<3;a++){int hi=fgetc(f),lo=fgetc(f);assert(hi>=0&&lo>=0);points[sample][i][a]=(int16_t)((hi<<8)|lo);}
 }
 for(unsigned i=0;i<4;i++)for(unsigned a=0;a<3;a++){int x=points[0][i][a],y=points[1][i][a];out[i][a]=x+(y-x)*fraction/256;}
}
'''

for source,result,name,args in (
 (math,'void','t3d_mat4_from_srt_euler','T3DMat4*mat,const float scale[3],const float rot[3],const float translate[3]'),
 (header,'void','t3d_mat4_mul','T3DMat4*matRes,const T3DMat4*matA,const T3DMat4*matB'),
 (header,'void','t3d_mat3_mul_vec3','T3DVec3*vecOut,const T3DMat4*mat,const T3DVec3*vec'),
 (main,'void','pivot_rotation','T3DMat4*out,const float pivot[3],float yaw,float pitch'),
 (main,'void','compute_vehicle_pose','unsigned i'),
 (main,'void','prepare_vehicle','unsigned i')):
 c+=f'\nstatic {result} {name}({args}){{{function(source,name)}}}\n'
c+=r'''
typedef struct {uint32_t words[BG_VEHICLE_POSE_WORDS];} pose_key;
static unsigned hits,misses,copies,reuses,checked;
static uint64_t copy_bytes;
static pose_key key_for(unsigned i){
 pose_key k;bg_vehicle_pose_key(k.words,&bg_vehicles[i],&wheel_rotation[i]);return k;
}
static void cached_prepare(unsigned i){
 bg_vehicle_pose_cache*p=&vehicle_pose_cache[i];pose_key k=key_for(i);unsigned count=bg_vehicle_rigs[bg_vehicles[i].kind].count;
 if(p->valid&&!memcmp(k.words,p->key,sizeof(k))){
  hits++;
  if(!(p->slot_mask&(1u<<slot))){copies++;copy_bytes+=(count+1)*sizeof(T3DMat4FP);}
  else reuses++;
 }else misses++;
 prepare_vehicle(i);
}
static void compare(unsigned i){
 state=&all_outputs[0];cached_prepare(i);state=&all_outputs[1];compute_vehicle_pose(i);
 unsigned count=bg_vehicle_rigs[bg_vehicles[i].kind].count;
 assert(!memcmp(&all_outputs[0].vehicle[slot][i],&all_outputs[1].vehicle[slot][i],sizeof(T3DMat4FP)));
 assert(!memcmp(all_outputs[0].parts[slot][i],all_outputs[1].parts[slot][i],count*sizeof(T3DMat4FP)));
 assert(!memcmp(&all_outputs[0].bounds[i],&all_outputs[1].bounds[i],sizeof(bg_cull_bounds)));
 assert(!memcmp(all_outputs[0].part_bounds[i],all_outputs[1].part_bounds[i],count*sizeof(bg_cull_bounds)));
 checked++;
}
static void reset_stats(void){hits=misses=copies=reuses=0;copy_bytes=0;}
static void report(const char*name){printf("%s {\"hits\":%u,\"misses\":%u,\"hit_fraction\":%.6f,\"copies\":%u,\"already_valid_slot\":%u,\"copied_bytes\":%llu}\n",name,hits,misses,(double)hits/(hits+misses),copies,reuses,(unsigned long long)copy_bytes);}
static uint32_t seed=0xCE064;
static uint32_t rnd(void){seed=seed*1664525u+1013904223u;return seed;}
static float uniform(float lo,float hi){return lo+(hi-lo)*(float)(rnd()>>8)/16777215.f;}
int main(void){
 for(unsigned frequency=1;frequency<=2;frequency++){
  memset(vehicle_pose_cache,0,sizeof(vehicle_pose_cache));memset(wheel_rotation,0,sizeof(wheel_rotation));reset_stats();
  bg_reset();bg_set_players(4);float time=0;
  for(unsigned tick=0;tick<2250;tick++){
   bg_input in[4];bg_replay_input(in,time);bg_clear_events();bg_tick(in,BLAM_TICK_SECONDS);time+=BLAM_TICK_SECONDS;
   if(bg_match_time()<=BLAM_TICK_SECONDS+.00001f)memset(wheel_rotation,0,sizeof(wheel_rotation));
   for(unsigned i=0;i<bg_vehicle_count;i++)wheel_rotation[i]=fmodf(wheel_rotation[i]+bg_vehicles[i].speed*BLAM_TICK_SECONDS/.18f,6.2831853f);
   for(unsigned redraw=0;redraw<frequency;redraw++){
    slot=(tick*frequency+redraw)%2;
    for(unsigned i=0;i<bg_vehicle_count;i++)if(bg_vehicles[i].active)compare(i);
   }
   if(tick==1079)report(frequency==1?"combat30":"combat60");
  }
  report(frequency==1?"replay30":"replay60");
 }
 reset_stats();
 for(unsigned trial=0;trial<12000;trial++){
  unsigned i=rnd()%BG_MAX_VEHICLES;slot=trial%2;bg_vehicle*v=&bg_vehicles[i];
  if(trial%7==0){bg_reset();memset(wheel_rotation,0,sizeof(wheel_rotation));}
  if(trial%3==0){
   v->kind=rnd()%4;for(unsigned a=0;a<3;a++)v->pos[a]=uniform(-80,80);
   v->physics_valid=(trial%2)==0;
   float angle=uniform(-3,3);v->forward[0]=1;v->forward[1]=v->forward[2]=0;v->up[0]=0;v->up[1]=cosf(angle);v->up[2]=sinf(angle);
   v->hatch=uniform(0,1);v->hatch_closing=(trial%4)==0;v->steering=uniform(-.5,.5);for(unsigned a=0;a<8;a++)v->suspension[a]=uniform(-.3,-.1);
   v->yaw=uniform(-4,4);v->pitch=uniform(-4,4);v->turret_yaw=uniform(-4,4);v->turret_pitch=uniform(-4,4);wheel_rotation[i]=uniform(-100000,100000);
  }
  v->active=trial%13!=0; /* Include dead/live transitions with the same pose. */
  compare(i);slot^=1;compare(i);compare(i);slot^=1;compare(i);
 }
 report("varied");
 bg_vehicles[0].active=true;pose_key live=key_for(0);bg_vehicles[0].active=false;pose_key dead=key_for(0);assert(memcmp(&live,&dead,sizeof(live)));
 /* Float comparison would equate these; exact bit keys must not. */
 bg_vehicles[0].yaw=0.f;pose_key plus=key_for(0);bg_vehicles[0].yaw=-0.f;pose_key minus=key_for(0);assert(memcmp(&plus,&minus,sizeof(plus)));
 printf("PASS: %u exact cached/uncached matrix and bounds comparisons; independent output banks; signed-zero keys.\n",checked);
}
'''
(OUT/'probe.c').write_text(c)
cmd=['clang','-std=c17','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer','-Wno-multichar','-Wno-unused-function','-Wno-unused-parameter','-Wno-unused-variable','-Wno-incompatible-pointer-types','-Ibuild/n64/blam-vehicle','-fno-strict-aliasing','-fwrapv','-Iport/n64','-Ibuild/n64/blam-core',str(OUT/'probe.c'),'port/n64/game.c','build/n64/generated/interaction_defs.c','port/n64/replay.c','port/n64/blam/runtime.c','port/n64/blam/core.c','port/n64/blam/vehicle_physics.c','build/n64/generated/vehicle_data.c','build/n64/generated/collision_data.c','-lm','-o',str(OUT/'probe')]
subprocess.run(cmd,check=True)
p=subprocess.run([str(OUT/'probe')],capture_output=True,text=True);print(p.stdout+p.stderr);(OUT/'probe.log').write_text(p.stdout+p.stderr);assert p.returncode==0
results={}
for line in p.stdout.splitlines():
 if ' {' in line:
  name,value=line.split(' ',1);results[name]=json.loads(value)
paths=['port/n64/render_pose_cache.h','port/n64/main.c','port/n64/game.c','port/n64/replay.c','build/n64/generated/models_data.c']
results['source_sha256']={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
results['scope']='Actual75s fixed30Hz portable replay at30/60 rendered frames/s, plus varied reset/inactive/reactivated/kind/pose cases. Host SDK math uses libm trig, both paths share exact source computation. No target timing claimed.'
(OUT/'results.json').write_text(json.dumps(results,indent=2)+'\n')
