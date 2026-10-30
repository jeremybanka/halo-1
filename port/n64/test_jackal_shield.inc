/* Real hit meshes, damage rules and recharge clock; no renderer substitutes. */
#include "jackal_shield_flash.h"
static void jackal_shield_acceptance(void){
    for(unsigned rank=0;rank<2;rank++){
        bg_ff_start(1);bg_ff.phase=BG_FF_RECOVER;bg_ff.timer=9999;bg_pve_count=0;
        float pos[3]={4,bg_floor(4,0,12)+.015f,0};pve_spawn_actor(0,BG_PVE_JACKAL,BG_W_PLASMA_PISTOL,0,pos,0);
        if(rank)bg_pve_set_variant(0,PVE_R_JACKAL_MAJOR);
        bg_player*p=&bg_players[4];bg_pve_actor*a=&bg_pve_actors[0];a->clip=PVE_IDLE;a->time=bg_pve_hits[BG_PVE_JACKAL].clips[PVE_IDLE].duration*.35f;
        float maximum=p->shield,health=p->health,shield_ray[3]={0},gap_ray[3]={0},gap_score=1e9f;unsigned blocked=0,gaps=0;int shield_region=0,gap_region=0;
        for(unsigned y=1;y<44;y++)for(int z=-30;z<=30;z++){
            float o[3]={pos[0]+2,pos[1]+y*.02f,pos[2]+z*.02f},d[3]={-1,0,0};int up=-1,down=-1;
            p->shield=maximum;float u=bg_pve_hit_ray(4,o,d,4,&up);
            p->shield=0;float v=bg_pve_hit_ray(4,o,d,4,&down);
            if(u<4&&bg_pve_hits[BG_PVE_JACKAL].rules[(up>>8)-1].material==16){blocked++;shield_region=up;memcpy(shield_ray,o,12);}
            else if(u<4&&u==v&&up==down){gaps++;float score=(y*.02f-.45f)*(y*.02f-.45f)+(z*.02f)*(z*.02f);if(score<gap_score){gap_score=score;gap_region=up;memcpy(gap_ray,o,12);}}
        }
        assert(blocked>50&&gaps>10&&shield_region&&gap_region);p->shield=maximum;
        bg_jackal_flash visual={0};assert(bg_jackal_flash_step(&visual,a->generation,p->shield,0,0)==0);
        damage_player_region(4,0,7,false,false,BG_D_PLASMA_PISTOL,false,false,1,shield_region);
        assert(bg_jackal_flash_step(&visual,a->generation,p->shield,p->hurt,1)==1);
        assert(p->health==health&&p->shield<maximum);float reduced=p->shield;
        damage_player_region(4,0,2,false,false,BG_D_PISTOL,false,false,1,gap_region);
        assert(bg_jackal_flash_step(&visual,a->generation,p->shield,p->hurt,5)==.8f); /* body hit cannot restart flash */
        assert(p->shield==reduced&&p->health<health);health=p->health;
        damage_player_region(4,0,1,false,false,BG_D_OVERCHARGE,false,false,1,shield_region);
        assert(p->shield==0&&p->health==health&&p->shield_delay==pve_definition(0)->shield_delay);
        bg_players[0].health=0;a->aware=false;a->target=-1;a->decision_time=9999;
        for(unsigned t=0;t<447;t++)bg_pve_tick(1.f/30);assert(p->shield==0);
        for(unsigned t=0;t<6;t++)bg_pve_tick(1.f/30);assert(p->shield==maximum);
        assert(bg_jackal_flash_step(&visual,a->generation,p->shield,p->hurt,458)==0);
        pve_killed(4,-1);for(unsigned t=0;t<480;t++)bg_pve_tick(1.f/30);assert(p->shield==0&&p->health==0);
        printf("JACKAL_SHIELD rank=%u blocked_rays=%u exposed_body_rays=%u shield_origin=%.6f,%.6f,%.6f gap_origin=%.6f,%.6f,%.6f direction=-1,0,0\n",rank,blocked,gaps,shield_ray[0],shield_ray[1],shield_ray[2],gap_ray[0],gap_ray[1],gap_ray[2]);
    }
    puts("PASS Minor/Major shield interception, exposed-body hits, EMP depletion, source 15-second restore and no corpse recharge");
}
