"""Check lazy animation's byte identity and borrow lifetime using actual helpers.

Current generated source banks are linked through a host Tiny3D layout shim.
The renderer's decode, tint, clip selection, attachment math and readiness code
are extracted verbatim. Eager and deferred schedules use independent output
banks. Writeback instrumentation rejects any write after a simulated RSP borrow,
including a redundant same-byte decode. This is not target timing/pixel proof.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from test_render_matrix import compact, function

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/n64/performance-audit/deferred-animation'


def check_source(source, before=None):
    prep=compact(function(source,'prepare_frame'));draw=compact(function(source,'draw_view'))
    assert 'animate_player(' not in prep and 'animate_firstperson(' not in prep
    assert prep.index('body_animation_ready=fp_animation_ready=0;') < prep.index('prepare_view(p);')
    assert 'wanted_lods' in prep and 'wanted_held' in prep
    body_call='if(body_lods[p][j]||(held_masks[p]&(1u<<j)))ensure_player_animation(j);'
    fp_call='ensure_firstperson_animation(p);'
    assert draw.count(body_call)==1 and draw.count(fp_call)==1
    assert draw.index('rspq_flush();') < draw.index(body_call) < draw.index('rspq_block_run(lod?')
    assert draw.index(body_call)<draw.index('if(held_masks[p]&(1u<<j))small_model_instance')
    assert draw.index('if(player->health>0&&player->vehicle<0&&!player->zoom){') < draw.index(fp_call)
    assert draw.index(fp_call)<draw.index('t3d_segment_set(')
    for name,ready in [('ensure_player_animation','body_animation_ready'),('ensure_firstperson_animation','fp_animation_ready')]:
        body=compact(function(source,name))
        assert body.index(f'if({ready}&bit)return;') < body.index('animate_')
        assert 'animation_us+=get_ticks_us()-begin;' in body
    assert 'data_cache_hit_writeback(&held_matrices[slot][p],sizeof(T3DMat4FP));' in compact(function(source,'ensure_player_animation'))
    assert 'object_us+=get_ticks_us()-begin-(animation_us-animation_before);' in draw
    assert 'fp_us+=get_ticks_us()-begin-(animation_us-animation_before);' in draw
    if before:
        old=before.read_text()
        for name in ('animate_mesh','animate_player','tint_team','prepare_view','prepare_player_bounds'):
            assert compact(function(source,name))==compact(function(old,name)),name
        eager=function(old,'prepare_frame')
        start=eager.index('    for(unsigned p=0;p<4;p++){')
        end=eager.index('#ifdef BG_PROFILE\n    animation_us=',start)
        loop=eager[start:end];inner=loop[loop.index('{')+1:loop.rfind('}')]
        inner=inner.replace('if(p>=views)continue;','if(p>=views)return;').replace('animate_player(p);','')
        inner=inner.replace('if(player->vehicle>=0||player->health<=0||player->zoom||p>=views)continue;',
                            'if(player->vehicle>=0||player->health<=0||player->zoom||p>=views)return;')
        assert compact(inner)==compact(function(source,'animate_firstperson'))
        restored=draw.replace(body_call,'').replace(fp_call,'')
        restored=restored.replace('unsignedbefore=triangles,animation_before=animation_us;','unsignedbefore=triangles;')
        restored=restored.replace('-(animation_us-animation_before)','').replace('animation_before=animation_us;','')
        assert restored==compact(function(old,'draw_view')),'Draw command/order or another operation changed'
    print('PASS: eager visibility union; first-use guards; animation precedes each vertex borrow and is attributed once.')


SHIM=r'''
#ifndef TEST_T3D_H
#define TEST_T3D_H
#include <stdint.h>
typedef struct {int16_t posA[3];uint16_t normA;int16_t posB[3];uint16_t normB;
 uint32_t rgbaA,rgbaB;int16_t stA[2],stB[2];} T3DVertPacked;
_Static_assert(sizeof(T3DVertPacked)==32,"packed pair");
typedef struct {float m[4][4];} T3DMat4;
typedef struct {struct {int16_t i[4];uint16_t f[4];} m[4];} T3DMat4FP;
static inline uint32_t*t3d_vertbuffer_get_color(T3DVertPacked*v,unsigned i){return i&1?&v[i/2].rgbaB:&v[i/2].rgbaA;}
static inline int16_t*t3d_vertbuffer_get_pos(T3DVertPacked*v,unsigned i){return i&1?v[i/2].posB:v[i/2].posA;}
static inline int16_t*t3d_vertbuffer_get_uv(T3DVertPacked*v,unsigned i){return i&1?v[i/2].stB:v[i/2].stA;}
#endif
'''
PRELUDE=r'''
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "game.h"
#include "asset_firstperson.h"
#include "render_animation.h"
#include "firstperson_ammo_logic.h"
#include "blam/runtime.h"
#define BG_FRAME_SLOTS 2
#define CachedAddr(x) (x)
#define assertf(x,...) assert(x)
#define T3D_F32_TO_FIXED(x) ((int32_t)((x)*65536.f))
enum { CAPACITY=2048, PAIRS=CAPACITY/2 };
typedef struct {
 _Alignas(16) T3DVertPacked near[2][4][PAIRS],far[2][4][PAIRS],fp[2][4][PAIRS];
 _Alignas(16) T3DMat4FP held[2][4];
 _Alignas(16) T3DVertPacked counter[2][4][4];
 int weapons[2][4];
} output_bank;
static output_bank banks[2],*active;
static T3DVertPacked*armor[2][4],*armor_lod[2][4],*firstperson[2][4];
#define held_matrices active->held
#define firstperson_weapon active->weapons
#define digits active->counter
bg_player bg_players[4];
static unsigned slot,views,body_clips[4],body_animation_ready,fp_animation_ready;
static uint8_t wanted_lods[4];static unsigned wanted_held;
static bool body_throwing[4];static T3DMat4 body_matrices[4];
static float game_time,fired_at[4];
static bg_motion_track motion_tracks[CAPACITY];static unsigned motion_capacity=CAPACITY;
static struct {uint8_t r,g,b,a;} colors[4]={{225,45,38,255},{39,92,215,255},{215,179,44,255},{57,183,69,255}};
static bool borrowed[4][4];static unsigned writebacks,late_calls,consumptions;
static void bind_bank(unsigned id){
 active=&banks[id];
 for(unsigned s=0;s<2;s++)for(unsigned p=0;p<4;p++){
  armor[s][p]=active->near[s][p];armor_lod[s][p]=active->far[s][p];firstperson[s][p]=active->fp[s][p];
 }
}
static void data_cache_hit_writeback(void*ptr,unsigned bytes){
 (void)bytes;writebacks++;
 for(unsigned p=0;p<4;p++){
  if(ptr==armor[slot][p])assert(!borrowed[p][0]);
  else if(ptr==armor_lod[slot][p])assert(!borrowed[p][1]);
  else if(ptr==&held_matrices[slot][p])assert(!borrowed[p][2]);
  else if(ptr==firstperson[slot][p])assert(!borrowed[p][3]);
  else if(ptr==digits[slot][p])assert(!borrowed[p][3]);
 }
}
static uint32_t seed=0xCE064;
static uint32_t rnd(void){seed=seed*1664525u+1013904223u;return seed;}
static float uniform(float a,float b){return a+(b-a)*(float)(rnd()>>8)/16777215.f;}
'''
TEST=r'''
static void consume(unsigned player,unsigned kind){borrowed[player][kind]=true;consumptions++;}
int main(void){
 assert(bg_fp_max_vertices<=CAPACITY);
 memset(banks,0x73,sizeof(banks));
 for(unsigned b=0;b<2;b++)for(unsigned s=0;s<2;s++)for(unsigned p=0;p<4;p++)banks[b].weapons[s][p]=-1;
 unsigned both_lod=0,held_only=0,fp_guard=0,fp_render=0;
 for(unsigned trial=0;trial<2400;trial++){
  slot=trial%2;views=trial%3==0?1:trial%3==1?2:4;game_time=uniform(0,90);
  uint8_t lod[4][4]={{0}},held[4]={0};wanted_held=0;memset(wanted_lods,0,sizeof(wanted_lods));
  for(unsigned p=0;p<4;p++){
   bg_player*q=&bg_players[p];memset(q,0,sizeof(*q));q->weapon=(trial+p)%9;
   q->vehicle=-1;q->health=100;q->anim_time=uniform(-.1f,4);q->heat=uniform(0,1);
   q->ammo=(trial+p)%61;q->reserve=(trial/7+p)%60;
   switch((trial/9+p)%8){case 1:q->reload=1;break;case 2:q->overheated=true;break;
    case 3:q->melee_time=uniform(.01f,.7f);break;case 4:q->vehicle=1;break;
    case 5:q->health=0;break;case 6:q->zoom=1;break;default:break;}
   fired_at[p]=trial%2?game_time-uniform(0,.2f):-100;
   body_clips[p]=(trial+p)%BG_A_COUNT;body_throwing[p]=trial%7==0;q->grenade_cooldown=uniform(.55f,.9f);
   body_matrices[p]=(T3DMat4){{{1,0,0,0},{0,1,0,0},{0,0,1,0},{(float)p*32,4,-12,1}}};
   for(unsigned v=0;v<views;v++)if(p<views){
    lod[v][p]=rnd()%3;held[v]|=(rnd()%3==0)<<p;
   }
  }
  /* Force held-only and both-LOD combinations in addition to random views. */
  if(trial%5==0){for(unsigned v=0;v<views;v++)lod[v][0]=0;held[0]|=1;}
  if(views>1&&trial%5==1){lod[0][0]=1;lod[1][0]=2;}
  for(unsigned v=0;v<views;v++)for(unsigned p=0;p<views;p++){
   if(lod[v][p])wanted_lods[p]|=1u<<(lod[v][p]-1);
   wanted_held|=held[v];
  }
  for(unsigned p=0;p<views;p++){both_lod+=wanted_lods[p]==3;held_only+=wanted_lods[p]==0&&(wanted_held&(1u<<p));}
  banks[1]=banks[0];memset(borrowed,0,sizeof(borrowed));bind_bank(0);
  for(unsigned p=0;p<views;p++){animate_player(p);animate_firstperson(p);}
  bind_bank(1);body_animation_ready=fp_animation_ready=0;
  /* Permuting view order changes first consumer but never the wanted union. */
  unsigned order[4]={0,1,2,3};
  for(unsigned p=views-1;p>0;p--){unsigned other=rnd()%(p+1),tmp=order[p];order[p]=order[other];order[other]=tmp;}
  for(unsigned visit=0;visit<views;visit++){
   unsigned v=order[visit];
   for(unsigned p=0;p<views;p++){
    if(lod[v][p]||(held[v]&(1u<<p)))ensure_player_animation(p);
    if(lod[v][p])consume(p,lod[v][p]-1);
    if(held[v]&(1u<<p))consume(p,2);
    if(body_animation_ready&(1u<<p)){
     unsigned before=writebacks;ensure_player_animation(p);assert(writebacks==before);late_calls++;
    }
   }
   bg_player*q=&bg_players[v];
   if(q->health>0&&q->vehicle<0&&!q->zoom){
    ensure_firstperson_animation(v);consume(v,3);fp_render++;
    unsigned before=writebacks;ensure_firstperson_animation(v);assert(writebacks==before);late_calls++;
   }else fp_guard++;
  }
  assert(!memcmp(&banks[0],&banks[1],sizeof(output_bank)));
  assert(firstperson_weapon[slot][0]==banks[0].weapons[slot][0]);
 }
 assert(both_lod&&held_only&&fp_guard&&fp_render);
 printf("PASS:2400 actual-bank eager/lazy schedules; %u both-LOD, %u held-only, %u FP draws/%u guards; %u borrows and %u post-borrow ensures produce no writes; all vertex/color/UV/padding/fixed-attachment bytes identical.\n",both_lod,held_only,fp_render,fp_guard,consumptions,late_calls);
}
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before',type=Path)
    args=parser.parse_args()
    source=(ROOT/'port/n64/main.c').read_text();check_source(source,args.before)
    OUT.mkdir(parents=True,exist_ok=True);shim=OUT/'include/t3d';shim.mkdir(parents=True,exist_ok=True)
    (shim/'t3d.h').write_text(SHIM)
    sdk=ROOT.parent/'n64-3d-splitscreen/.build/tiny3d/src/t3d'
    header=(sdk/'t3dmath.h').read_text();math=(sdk/'t3dmath.c').read_text()
    c=PRELUDE
    game=(ROOT/'port/n64/game.c').read_text()
    definitions=re.search(r'const bg_weapon_def bg_weapon_defs\[BG_WEAPON_COUNT\]=\{.*?\n\};',game,re.S)
    assert definitions
    c+='\n'+definitions[0]+'\n'
    ammo_source=(ROOT/'port/n64/firstperson_ammo.c').read_text()
    c+='\nvoid bg_fp_ammo_prepare(unsigned slot,unsigned player,unsigned weapon,unsigned clip,unsigned f0,unsigned f1,int fraction,int ammo,int reserve,float reload_elapsed,T3DVertPacked*firstperson_vertices){'+function(ammo_source,'bg_fp_ammo_prepare')+'}\n'
    for src,name,argspec in [
      (header,'t3d_mat4_scale','T3DMat4*mat,float scaleX,float scaleY,float scaleZ'),
      (header,'t3d_mat4_mul','T3DMat4*matRes,const T3DMat4*matA,const T3DMat4*matB'),
      (math,'t3d_mat4_to_fixed_3x4','T3DMat4FP*matOut,const T3DMat4*matIn'),
      (math,'t3d_mat4_from_srt','T3DMat4*mat,const float scale[3],const float quat[4],const float translate[3]'),
      (source,'tint_team','T3DVertPacked*vertices,unsigned count,const uint8_t*masks,unsigned player'),
      (source,'animate_mesh','T3DVertPacked*output,const bg_anim_asset*a,unsigned f0,unsigned f1,int fraction'),
      (source,'animate_player','unsigned p'),(source,'animate_firstperson','unsigned p'),
      (source,'ensure_player_animation','unsigned p'),(source,'ensure_firstperson_animation','unsigned p')]:
        c+=f'\nstatic void {name}({argspec}){{{function(src,name)}}}\n'
    c+=TEST;(OUT/'actual-functions.c').write_text(c)
    cmd=['clang','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
         '-fno-omit-frame-pointer','-fno-strict-aliasing','-I'+str(shim.parent),'-Iport/n64',
         str(OUT/'actual-functions.c'),'build/n64/generated/models_data.c',
         'build/n64/generated/firstperson_data.c','build/n64/generated/firstperson_ammo_data.c',
         'port/n64/blam/runtime.c','-lm','-o',str(OUT/'actual-functions')]
    subprocess.run(cmd,check=True,cwd=ROOT)
    result=subprocess.run([str(OUT/'actual-functions')],check=True,capture_output=True,text=True)
    print(result.stdout,end='');(OUT/'actual-functions.log').write_text(result.stdout)
    inputs=['port/n64/main.c','port/n64/render_animation.h','port/n64/firstperson_ammo.c','port/n64/firstperson_ammo_logic.h',
            'build/n64/generated/models_data.c','build/n64/generated/firstperson_data.c','build/n64/generated/firstperson_ammo_data.c']
    (OUT/'actual-functions-proof.json').write_text(json.dumps({'command':cmd,'output':result.stdout,
        'sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in inputs},
        'scope':'Actual functions and current banks; little-endian host Tiny3D layout shim and exact SDK math; no target timing or pixel claim'},indent=2)+'\n')

if __name__=='__main__':main()
