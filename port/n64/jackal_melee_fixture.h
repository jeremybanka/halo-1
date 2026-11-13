/* Call after including game.c: exercise the production 25-ray melee selector. */
#ifndef BG_JACKAL_MELEE_FIXTURE_H
#define BG_JACKAL_MELEE_FIXTURE_H
static void jackal_melee_case(unsigned rank,unsigned mode,unsigned rotation){
    bg_ff_start(3);bg_ff.phase=BG_FF_RECOVER;bg_ff.timer=9999;bg_pve_count=0;bg_vehicle_count=0;
    float pos[3]={4,bg_floor(4,0,12)+.015f,0},yaw=rotation*1.57079632679f;
    pve_spawn_actor(0,BG_PVE_JACKAL,BG_W_PLASMA_PISTOL,0,pos,yaw);
#ifdef BG_PVE_ROSTER
    if(rank)bg_pve_set_variant(0,PVE_R_JACKAL_MAJOR);
#else
    (void)rank;
#endif
    bg_player*jackal=&bg_players[4],*human=&bg_players[0];bg_pve_actor*a=&bg_pve_actors[0];
    a->clip=PVE_IDLE;a->time=bg_pve_hits[BG_PVE_JACKAL].clips[PVE_IDLE].duration*.35f;
    float health=jackal->health,shield=jackal->shield;
    /* Five shield-face origins, then depleted shield, exposed body and back. */
    float x=mode==7?-.65f:.65f,y=mode>=6?.44f:.56f,z=mode<5?.08f+(mode-2.f)*.02f:-.04f;
    if(mode==6)z=-.20f;
    if(mode==5){jackal->shield=0;z=.08f;}
    float co=cosf(yaw),si=sinf(yaw);
    human->pos[0]=pos[0]+co*x+si*z;human->pos[2]=pos[2]-si*x+co*z;
    human->pos[1]=pos[1]+y-bg_eye_height(human);human->yaw=yaw+(mode==7?0:3.14159265359f);human->pitch=0;
    human->airborne_time=0;memset(human->velocity,0,sizeof(human->velocity));
    melee_impact(0);
    if(mode<5)assert(jackal->health==health&&jackal->shield<shield);
    else if(mode==5)assert(jackal->health<health&&jackal->shield==0);
    else if(mode==6)assert(jackal->health<health&&jackal->shield==shield);
    else assert(jackal->health==0);
}
#endif
