"""Exercise the actual deferred-animation readiness/fence boundaries.

Animation callbacks are spies that enforce the renderer's borrowed-buffer
contract. Source arithmetic is checked by test_scene_equivalence; ROM poses and
skins by test_interaction_assets. This harness owns only lifetime/order checks.
"""
from pathlib import Path
import subprocess
import tempfile
from runtime_source import read_runtime
from test_render_matrix import compact,function

ROOT=Path(__file__).resolve().parents[2]
source=read_runtime(ROOT/'port/n64/main.c')
prep=compact(function(source,'prepare_frame'));draw=compact(function(source,'draw_view'))
assert 'animate_player(' not in prep and 'animate_firstperson(' not in prep
assert prep.index('body_animation_ready=fp_animation_ready=0;')<prep.index('prepare_view(p);')
assert draw.count('if(body_lods[p][j]||(held_masks[p]&(1u<<j)))ensure_player_animation(j);')==1
assert draw.count('ensure_firstperson_animation(p);')==1
assert draw.index('ensure_firstperson_animation(p);')<draw.index('t3d_segment_set(')
C=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef struct {unsigned stamp;} T3DMat4FP;
static T3DMat4FP held_matrices[2][4];
static unsigned slot,wanted_held,body_animation_ready,fp_animation_ready;
static uint8_t wanted_lods[4];
static unsigned body_calls[4],fp_calls[4],writebacks[4];
static bool borrowed[4][4],retired[2];
#ifdef BG_PROFILE
static unsigned animation_us;
static uint64_t get_ticks_us(void){static uint64_t time;return ++time;}
#endif
static void animate_player(unsigned p){
 assert(retired[slot]);body_calls[p]++;
 for(unsigned lod=0;lod<2;lod++)if(wanted_lods[p]&(1u<<lod))assert(!borrowed[p][lod]);
 if(wanted_held&(1u<<p)){assert(!borrowed[p][2]);held_matrices[slot][p].stamp++;}
}
static void animate_firstperson(unsigned p){assert(retired[slot]&&!borrowed[p][3]);fp_calls[p]++;}
static void data_cache_hit_writeback(void*pointer,unsigned bytes){
 assert(bytes==sizeof(T3DMat4FP));
 for(unsigned p=0;p<4;p++)if(pointer==&held_matrices[slot][p]){assert(!borrowed[p][2]);writebacks[p]++;return;}
 assert(false);
}
'''
for name in ('ensure_player_animation','ensure_firstperson_animation'):
    C+='static void '+name+'(unsigned p){'+function(source,name)+'}\n'
C+=r'''
static uint32_t seed=0xce064;
static unsigned random_u(void){seed=1664525u*seed+1013904223u;return seed;}
int main(void){
 unsigned consumed=0;
 for(unsigned frame=0;frame<10000;frame++){
  slot=frame%2;retired[slot]=true; /* same completed slot fence as production */
  memset(borrowed,0,sizeof(borrowed));memset(body_calls,0,sizeof(body_calls));
  memset(fp_calls,0,sizeof(fp_calls));memset(writebacks,0,sizeof(writebacks));
  memset(wanted_lods,0,sizeof(wanted_lods));wanted_held=0;
  body_animation_ready=fp_animation_ready=0;
  unsigned views=1+frame%4;uint8_t lod[4][4]={{0}},held[4]={0};bool firstperson[4]={0};
  for(unsigned view=0;view<views;view++){
   firstperson[view]=random_u()%3!=0;
   for(unsigned p=0;p<views;p++){
    lod[view][p]=random_u()%3;held[view]|=(random_u()%3==0)<<p;
    if(lod[view][p])wanted_lods[p]|=1u<<(lod[view][p]-1);
   }
   wanted_held|=held[view];
  }
  /* Reorder views to exercise each possible first consumer. */
  unsigned order[4]={0,1,2,3};
  for(unsigned p=views-1;p>0;p--){unsigned j=random_u()%(p+1),old=order[p];order[p]=order[j];order[j]=old;}
  for(unsigned i=0;i<views;i++){
   unsigned view=order[i];
   for(unsigned p=0;p<views;p++){
    if(lod[view][p]||(held[view]&(1u<<p)))ensure_player_animation(p);
    if(lod[view][p]){borrowed[p][lod[view][p]-1]=true;consumed++;}
    if(held[view]&(1u<<p)){borrowed[p][2]=true;consumed++;}
   }
   if(firstperson[view]){
    ensure_firstperson_animation(view);borrowed[view][3]=true;consumed++;
    ensure_firstperson_animation(view); /* Must not write after first borrow. */
   }
  }
  for(unsigned p=0;p<views;p++){
   assert(body_calls[p]==(unsigned)(wanted_lods[p]||(wanted_held&(1u<<p))));
   assert(fp_calls[p]==firstperson[p]);assert(writebacks[p]==!!(wanted_held&(1u<<p)));
  }
  retired[slot]=false;
 }
 printf("PASS: 10,000 fenced frames, 1-4 shuffled views; %u consumers; exactly one animation per needed buffer, no writes after borrowing.\n",consumed);
}
'''
with tempfile.TemporaryDirectory(prefix='halo-animation-lifetimes-') as directory:
    test=Path(directory)/'test.c';test.write_text(C)
    for mode in ([],['-DBG_PROFILE']):
        binary=Path(directory)/('profile' if mode else 'release')
        subprocess.run(['clang','-std=c17','-O2','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',*mode,str(test),'-o',str(binary)],check=True)
        subprocess.run([str(binary)],check=True)
