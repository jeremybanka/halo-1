#ifndef BG_WIZARD_QA_H
#define BG_WIZARD_QA_H
/* Frozen source-spawn/architecture inspection through production rendering. */
static unsigned model_qa_page=BG_WIZARD_QA;
static const char *const model_qa_labels[]={"WIZARD: SOURCE STARTS","WIZARD: UPPER ROUTES","WIZARD: TELEPORTERS","WIZARD: ONE PLAYER"};
static bool model_qa_firstperson(void){return true;}
static void model_qa_camera(unsigned p,T3DVec3*eye,T3DVec3*target){(void)p;(void)eye;(void)target;}
static void model_qa_stage(uint64_t now){
    (void)now;static bool ready;if(ready)return;ready=true;
    bg_set_players(BG_WIZARD_QA==3?1:4);bg_reset();(*qa.views)=bg_player_count();bg_scene_reset();
    for(unsigned p=0;p<4;p++){
        bg_player*q=&bg_players[p];q->invisibility=1;q->camo_opacity=0;
        if(BG_WIZARD_QA==1||BG_WIZARD_QA==3){
            q->pos[0]=p%2?7:-7;q->pos[2]=p/2?-5:5;
            q->pos[1]=bg_floor(q->pos[0],q->pos[2],-1)+.015f;
            q->yaw=atan2f(q->pos[2],-q->pos[0]);q->pitch=-.08f;
        }else if(BG_WIZARD_QA==2){
            const bg_teleporter*t=&bg_teleporters[p];
            q->pos[0]=t->source[0]*.75f;q->pos[2]=t->source[2]*.75f;
            q->pos[1]=bg_floor(q->pos[0],q->pos[2],t->source[1]+.5f)+.015f;
            q->yaw=-atan2f(t->source[2]-q->pos[2],t->source[0]-q->pos[0]);q->pitch=0;
        }
        memcpy(q->last_pos,q->pos,12);q->animation=BG_ANIM_IDLE;q->anim_time=0;
    }
}
#endif
