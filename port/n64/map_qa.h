#ifndef BG_MAP_QA_H
#define BG_MAP_QA_H
#include "map.h"
#include "terrain.h"
#include "pickup_rules.h"
/* Camera selection is diagnostic only; all positions are authored starts. */
static unsigned model_qa_page=BG_MAP_QA;
static const char *const model_qa_labels[]={"MAP: SOURCE STARTS","MAP: ROUTE VIEWS","MAP: LOWER ROUTES","MAP: ONE PLAYER"};
static bool model_qa_firstperson(void){return true;}
static void model_qa_camera(unsigned p,T3DVec3*eye,T3DVec3*target){(void)p;(void)eye;(void)target;}
static void model_qa_stage(uint64_t now){
    (void)now;static bool ready;if(ready)return;ready=true;
    bg_set_players(BG_MAP_QA==3?1:4);bg_reset();(*qa.views)=bg_player_count();bg_scene_reset();
    unsigned starts[128],count=0;
    for(unsigned i=0;i<bg_spawn_count;i++)if(bg_slayer_spawns[i])starts[count++]=i;
    assertf(count>=4,"Map inspection starts");
    if(BG_MAP_QA==1||BG_MAP_QA==2)
        for(unsigned i=1;i<count;i++){
            unsigned id=starts[i],j=i;
            while(j&&((BG_MAP_QA==1)?bg_spawns[starts[j-1]].pos[1]<bg_spawns[id].pos[1]:bg_spawns[starts[j-1]].pos[1]>bg_spawns[id].pos[1])){starts[j]=starts[j-1];j--;}
            starts[j]=id;
        }
    for(unsigned p=0;p<4;p++){
        bg_player*q=&bg_players[p];const bg_spawn*s=&bg_spawns[starts[(BG_MAP_QA==0?p*count/4:p)%count]];
        if(bg_map_id()==BG_MAP_BATTLE_CREEK&&(BG_MAP_QA==1||BG_MAP_QA==3)){
            /* Owned-cache Slayer starts in the courtyard and beside the river. */
            const unsigned courtyard[]={62,63,66,25};
            assertf(courtyard[p]<bg_spawn_count&&bg_slayer_spawns[courtyard[p]],"Battle Creek inspection start");
            s=&bg_spawns[courtyard[p]];
        }
        memcpy(q->pos,s->pos,12);q->pos[1]=bg_floor(q->pos[0],q->pos[2],q->pos[1]+.5f)+.015f;
        q->yaw=s->yaw;q->pitch=-.06f;q->invisibility=1;q->camo_opacity=0;
        /* Battle Creek's cliff starts face rock. Keep the authored camera
         * positions, but look toward the arena for useful inspection views. */
        if(bg_map_id()==BG_MAP_BATTLE_CREEK){
            float center_x=0,center_z=0;
            for(unsigned i=0;i<count;i++){
                center_x+=bg_spawns[starts[i]].pos[0];
                center_z+=bg_spawns[starts[i]].pos[2];
            }
            q->yaw=-atan2f(center_z/count-q->pos[2],center_x/count-q->pos[0]);
        }
        memcpy(q->last_pos,q->pos,12);q->animation=BG_ANIM_IDLE;q->anim_time=0;
    }
}
#endif
