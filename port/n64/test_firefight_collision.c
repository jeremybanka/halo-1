#include <stdio.h>
#include <stdlib.h>
#include "game.c"
#include "collision_reference_hits.inc"
extern float reference_bg_move_capsule(bg_player*,float);
extern bool reference_bg_terrain_clearance(const bg_player*);
extern bool reference_bg_can_stand(const bg_player*);
extern void reference_bg_terrain_reset(void);
static uint32_t rng=1234567;
static float random01(void){rng=rng*1664525u+1013904223u;return (rng>>8)*(1.f/16777216);}
static void cache_isolation(void){
    assert(bg_map_load(9));bg_terrain_reset();
    for(unsigned i=0;i<BG_UNITS;i++){
        bg_players[i]=(bg_player){.pos={i*.03f,.1f,4}};
        if(i>=4){const bg_pve_definition*d=&bg_pve_definitions[(i-4)%4];bg_players[i].pve_radius=d->radius;bg_players[i].pve_height=d->height;}
        bg_terrain_clearance(&bg_players[i]);
    }
    for(unsigned n=0;n<128;n++){
        bg_player probe={.pos={n*.17f,2,10}};bg_terrain_clearance(&probe);
    }
    unsigned misses=bg_collision_profile.terrain_misses;
    for(unsigned tick=0;tick<30;tick++)for(unsigned i=0;i<BG_UNITS;i++)bg_terrain_clearance(&bg_players[i]);
    assert(bg_collision_profile.terrain_misses==misses);
    puts("PASS all 16 actor entries survive scratch-probe churn: zero grid rebuilds in 480 warm queries");
}
static void overflow(void){
    assert(bg_map_load(9));
    const bg_triangle*old_triangles=bg_collision;const uint8_t*old_flags=bg_collision_flags;
    const bg_cell*old_grid=bg_grid;const uint16_t*old_ids=bg_grid_indices;
    const float*old_origin=bg_grid_origin,*old_size=bg_grid_size;unsigned old_count=bg_collision_count;
    float corners[3][3]={{-4,0,-4},{4,0,-4},{0,0,4}},origin[2]={-50,-50},size[2]={100,100};
    bg_triangle triangles[600];uint8_t flags[600];uint16_t ids[600];bg_cell grid[BG_GRID*BG_GRID]={{0,600}};
    for(unsigned t=0;t<600;t++){for(unsigned v=0;v<3;v++)triangles[t].p[v]=corners[v];flags[t]=BG_SURFACE_FLOOR;ids[t]=t;}
    bg_collision=triangles;bg_collision_flags=flags;bg_collision_count=600;bg_grid=grid;bg_grid_indices=ids;bg_grid_origin=origin;bg_grid_size=size;
    bg_terrain_reset();reference_bg_terrain_reset();
    bg_player initial={.pos={0,.015f,0},.velocity={1,-1,0},.vehicle=-1};bg_players[0]=initial;
    float a=bg_move_capsule(&bg_players[0],1.f/30);bg_player result=bg_players[0];bg_players[0]=initial;
    float b=reference_bg_move_capsule(&bg_players[0],1.f/30);
    assert(a==b&&!memcmp(&result,&bg_players[0],sizeof(result)));
    assert(bg_collision_profile.terrain_actor_overflows&&bg_collision_profile.terrain_overflows);
    bg_collision=old_triangles;bg_collision_flags=old_flags;bg_collision_count=old_count;bg_grid=old_grid;bg_grid_indices=old_ids;bg_grid_origin=old_origin;bg_grid_size=old_size;
    bg_terrain_reset();reference_bg_terrain_reset();puts("PASS actor-list and contact-list overflow: exact full-scan fallback");
}
static void movement(void){
    unsigned checks=0;
    for(unsigned map=0;map<13;map++){
        assert(bg_map_load(map));bg_pve_stop();bg_terrain_reset();reference_bg_terrain_reset();
        bg_player states[BG_UNITS]={0};
        for(unsigned i=0;i<BG_UNITS;i++){
            bg_player*p=&states[i];memcpy(p->pos,bg_spawns[(i*7)%bg_spawn_count].pos,12);
            p->pos[1]+=.1f;p->health=100;p->vehicle=-1;
            if(i>=4){const bg_pve_definition*d=&bg_pve_definitions[(i-4)%4];p->pve_radius=d->radius;p->pve_height=d->height;}
        }
        for(unsigned tick=0;tick<180;tick++)for(unsigned i=0;i<BG_UNITS;i++){
            bg_player*p=&bg_players[i];*p=states[i];
            p->crouch_amount=i<4?((tick/30)%2):0;
            p->velocity[0]=sinf(i+tick*.03f)*1.4f;p->velocity[2]=cosf(i+tick*.03f)*1.4f;
            p->velocity[1]-=bg_movement.gravity/30;
            if(tick==60)p->velocity[1]=3;
            if(tick==120){memcpy(p->pos,bg_spawns[(i*7+1)%bg_spawn_count].pos,12);p->pos[1]+=.1f;}
            bg_player initial=*p;float a=bg_move_capsule(p,1.f/30);bg_player actual=*p;
            *p=initial;float b=reference_bg_move_capsule(p,1.f/30);
            if(a!=b||memcmp(&actual,p,sizeof(*p))){
                fprintf(stderr,"Movement mismatch map %u tick %u unit %u\n",map,tick,i);abort();
            }
            states[i]=actual;checks++;
            /* Reused stack address, alternating species/postures, cannot evict
             * persistent actors or retain an incompatible capsule envelope. */
            bg_player probe=initial;probe.pos[0]+=.12f;
            assert(bg_terrain_clearance(&probe)==reference_bg_terrain_clearance(&probe));
            if(i<4)assert(bg_can_stand(&probe)==reference_bg_can_stand(&probe));
        }
        printf("PASS map %u: 16 interleaved actor movement trajectories and scratch probes\n",map);
    }
    printf("PASS %u bit-identical movement steps: position/velocity/support/impact, crouch/jump/teleport and scratch probes\n",checks);
}
static void hit_check(unsigned unit,const float*o,const float*d,float length,unsigned*checks,unsigned*hits){
    unsigned i=unit-4;int a=-99,b=-99;
    float x=bg_pve_hit_ray(unit,o,d,length,&a),y=reference_bg_pve_hit_ray(unit,o,d,length,&b);
    if(x!=y||a!=b||(x<length&&memcmp(pve_hit_normals[i],reference_pve_hit_normals[i],12))){
        fprintf(stderr,"Hit mismatch species %u clip %u time %.9g x %.9g y %.9g material %d/%d\n",bg_pve_actors[i].kind,bg_pve_actors[i].clip,bg_pve_actors[i].time,x,y,a,b);abort();
    }
    (*checks)++;*hits+=x<length;
}
static void rays(void){
    assert(bg_map_load(9));bg_pve_count=12;unsigned checks=0,hits=0;
    unsigned poses=4;
#ifdef BG_PVE_ROSTER
    poses+=2; /* Fuel-rod Grunt and sword Elite collision tracks. */
#endif
    for(unsigned pose=0;pose<poses;pose++)for(unsigned clip=0;clip<12;clip++)for(unsigned phase=0;phase<17;phase++){
        unsigned kind=pose<4?pose:pose-4;
        const bg_pve_animation*c=&bg_pve_hits[kind].clips[clip];
#ifdef BG_PVE_ROSTER
        if(pose>=4)c=&bg_pve_alt_hit_clips[kind][clip];
#endif
        unsigned slot=phase%12,unit=4+slot;bg_player*p=&bg_players[unit];bg_pve_actor*a=&bg_pve_actors[slot];
        *p=(bg_player){.pos={1.25f,.7f,-2.5f},.health=100,.shield=phase%2?0:100,.yaw=(phase%4)*.37f};
        *a=(bg_pve_actor){.occupied=true,.kind=kind,.clip=clip,.time=c->duration*phase/16,.generation=1+phase+pose*17+clip*102};
#ifdef BG_PVE_ROSTER
        if(pose>=4)a->armament=kind==0?PVE_ARM_FUEL:PVE_ARM_SWORD;
#endif
        for(unsigned ray=0;ray<640;ray++){
            float o[3],d[3];
            for(unsigned k=0;k<3;k++){o[k]=p->pos[k]+(random01()-.5f)*4;d[k]=random01()-.5f;}
            o[1]+=.5f;
            if(ray%4==0){d[0]=ray%3==0;d[1]=ray%3==1;d[2]=ray%3==2;}
            else if(ray%4==1){for(unsigned k=0;k<3;k++)d[k]=p->pos[k]+(k==1?.4f:0)-o[k];normalize(d);}
            else normalize(d);
            hit_check(unit,o,d,ray%5==0?.1f:5,&checks,&hits);
        }
        /* Shoot through authored vertices: grazing faces and nearest-hit ties
         * must preserve the old material and reflection normal. */
        for(unsigned v=0;v<c->vertices;v+=3){
            float co=cosf(p->yaw),si=sinf(p->yaw);
            const int16_t*q=reference_pve_hit_pose[slot][v];
            float point[3]={p->pos[0]+(co*q[0]+si*q[2])/128.f,p->pos[1]+q[1]/128.f,p->pos[2]+(-si*q[0]+co*q[2])/128.f};
            for(unsigned axis=0;axis<3;axis++){float o[3],d[3]={0};memcpy(o,point,12);o[axis]-=2;d[axis]=1;hit_check(unit,o,d,4,&checks,&hits);}
        }
    }
    assert(hits>10000);printf("PASS %u exact ray distances/materials/normals (%u hits), all species/clips, shield states and recycled slots\n",checks,hits);
    printf("COUNTERS terrain hits %u misses %u; narrow triangles %u / %u eligible before bounds\n",bg_collision_profile.terrain_hits,bg_collision_profile.terrain_misses,bg_collision_profile.hit_triangles,bg_collision_profile.hit_available);
}
int main(void){movement();overflow();cache_isolation();rays();return 0;}
