#include "combat_geometry.h"
#include "blam/vehicle_physics.h"
#include <math.h>
#include "terrain.h"
#include "movement.h"
#include <assert.h>
#include <string.h>
#if defined(N64) && defined(BG_PROFILE)
#include <libdragon.h>
uint32_t bg_geometry_profile[4];
#define PROFILE_BEGIN uint32_t profile_start=get_ticks_us()
#define PROFILE_END(i) (bg_geometry_profile[i]+=get_ticks_us()-profile_start)
#else
#define PROFILE_BEGIN
#define PROFILE_END(i) ((void)0)
#endif
static float dot3(const float*a,const float*b){return a[0]*b[0]+a[1]*b[1]+a[2]*b[2];}
static void cross3(const float*a,const float*b,float*out){out[0]=a[1]*b[2]-a[2]*b[1];out[1]=a[2]*b[0]-a[0]*b[2];out[2]=a[0]*b[1]-a[1]*b[0];}
/* One compact cache per articulated model. Static hulls use the ROM tree;
 * only changed rigid parts and their BVH ancestors are refitted. */
typedef struct {
    bg_hit_mesh mesh;int16_t (*vertices)[3];bg_hit_node *nodes;uint8_t *moving;
    int kind;float yaw,pitch,hatch;bool closing,valid,initialized;
} hit_pose_cache;
static int16_t hit_hog_vertices[340][3],hit_tank_vertices[209][3],hit_banshee_vertices[158][3];
static bg_hit_node hit_hog_nodes[255],hit_tank_nodes[127],hit_banshee_nodes[127];
static uint8_t hit_hog_moving[255],hit_tank_moving[127],hit_banshee_moving[127];
static hit_pose_cache pose_cache[3]={
 {.vertices=hit_hog_vertices,.nodes=hit_hog_nodes,.moving=hit_hog_moving},
 {.vertices=hit_tank_vertices,.nodes=hit_tank_nodes,.moving=hit_tank_moving},
 {.vertices=hit_banshee_vertices,.nodes=hit_banshee_nodes,.moving=hit_banshee_moving}};
static void rotate_pivot(float p[3],const float pivot[3],float yaw,float pitch){
    float x=p[0]-pivot[0],y=p[1]-pivot[1],z=p[2]-pivot[2];
    float c=cosf(pitch),s=sinf(pitch),rx=c*x-s*y; y=s*x+c*y;x=rx;
    c=cosf(yaw);s=sinf(yaw);p[0]=pivot[0]+c*x+s*z;p[1]=pivot[1]+y;p[2]=pivot[2]-s*x+c*z;
}
const bg_hit_mesh *bg_vehicle_collision_pose_impl(const bg_vehicle*v){
    const bg_hit_mesh*source=&bg_vehicle_hit_meshes[v->kind];
    bool hatch=v->active&&(v->kind==BG_V_SCORPION||v->kind==BG_V_BANSHEE);
    float pitch=v->turret_pitch-v->pitch;
    if(v->kind==BG_V_GHOST||(!hatch&&v->turret_yaw==0&&pitch==0))return source;
    hit_pose_cache*c=&pose_cache[v->kind==BG_V_WARTHOG?0:v->kind==BG_V_SCORPION?1:2];
    if(c->valid&&c->yaw==v->turret_yaw&&c->pitch==pitch&&c->hatch==(hatch?v->hatch:-1)&&c->closing==v->hatch_closing)return &c->mesh;
    unsigned changed=0;
    if(!c->valid||c->yaw!=v->turret_yaw)changed|=(1u<<2)|(1u<<3);
    if(!c->valid||c->pitch!=pitch)changed|=1u<<3;
    if(!c->valid||c->hatch!=(hatch?v->hatch:-1)||c->closing!=v->hatch_closing)changed|=1u<<4;
    if(!c->initialized){
        static const unsigned capacities[4][2]={{340,255},{0,0},{209,127},{158,127}};
        assert(source->vertex_count<=capacities[v->kind][0]&&source->node_count<=capacities[v->kind][1]);
        c->mesh=*source;c->mesh.vertices=c->vertices;c->mesh.nodes=c->nodes;
        memcpy(c->vertices,source->vertices,source->vertex_count*sizeof(c->vertices[0]));
        memcpy(c->nodes,source->nodes,source->node_count*sizeof(bg_hit_node));
        for(int i=source->node_count-1;i>=0;i--){const bg_hit_node*n=&source->nodes[i];unsigned moving=0;
            if(n->count){for(unsigned t=n->first;t<n->first+n->count;t++)for(unsigned j=0;j<3;j++){
                unsigned kind=source->parts[source->groups[source->triangles[t][j]]].kind;if(kind>=2)moving|=1u<<kind;
            }}else moving=c->moving[n->first]|c->moving[n->right];
            c->moving[i]=moving;
        }
        c->initialized=true;
    }
    c->kind=v->kind;c->yaw=v->turret_yaw;c->pitch=pitch;c->hatch=hatch?v->hatch:-1;c->closing=v->hatch_closing;c->valid=true;
    float matrix[4][3]={{0},{1,0,0},{0,1,0},{0,0,1}};
    if(hatch){
        const bg_hit_hatch*h=&bg_hit_hatches[v->kind==BG_V_BANSHEE][v->hatch_closing];
        float frame=fminf(h->count-1,fmaxf(0,v->hatch*(h->count-1)));unsigned a=frame,b=a+1<h->count?a+1:a;float weight=frame-a;
        for(unsigned j=0;j<4;j++)for(unsigned k=0;k<3;k++)matrix[j][k]=(h->frames[a][j][k]+weight*(h->frames[b][j][k]-h->frames[a][j][k]))/4096.f;
    }
    float transforms[8][4][3];assert(source->part_count<=8);
    for(unsigned j=0;j<source->part_count;j++){
        const bg_hit_part*part=&source->parts[j];if(!(changed&(1u<<part->kind)))continue;float(*m)[3]=transforms[j];
        for(unsigned axis=0;axis<4;axis++){
            float point[3]={0};if(axis)point[axis-1]=1;
            if(part->kind==3)rotate_pivot(point,part->pivot,0,pitch);
            if(part->kind==2||part->kind==3)rotate_pivot(point,source->parts[source->turret_part].pivot,v->turret_yaw,0);
            for(unsigned k=0;k<3;k++)m[axis][k]=point[k];
        }
        for(unsigned axis=1;axis<4;axis++)for(unsigned k=0;k<3;k++)m[axis][k]-=m[0][k];
        if(part->kind==4&&hatch)memcpy(m,matrix,sizeof(matrix));
    }
    for(unsigned i=0;i<source->vertex_count;i++){
        if(!(changed&(1u<<source->parts[source->groups[i]].kind)))continue;
        float(*m)[3]=transforms[source->groups[i]];const int16_t*p=source->vertices[i];
        for(unsigned a=0;a<3;a++)c->vertices[i][a]=(int16_t)lrintf(m[0][a]*1024+m[1][a]*p[0]+m[2][a]*p[1]+m[3][a]*p[2]);
    }
    for(int i=source->node_count-1;i>=0;i--){
        if(!(c->moving[i]&changed))continue;
        bg_hit_node*n=&c->nodes[i];
        for(unsigned a=0;a<3;a++){
            int lo=32767,hi=-32768;
            if(n->count){for(unsigned t=n->first;t<n->first+n->count;t++)for(unsigned j=0;j<3;j++){
                int value=c->vertices[source->triangles[t][j]][a];if(value<lo)lo=value;if(value>hi)hi=value;
            }}else{lo=c->nodes[n->first].bounds[a];if(c->nodes[n->right].bounds[a]<lo)lo=c->nodes[n->right].bounds[a];
                hi=c->nodes[n->first].bounds[a+3];if(c->nodes[n->right].bounds[a+3]>hi)hi=c->nodes[n->right].bounds[a+3];}
            n->bounds[a]=lo;n->bounds[a+3]=hi;
        }
    }
    memcpy(c->mesh.bounds,c->nodes[0].bounds,sizeof(c->mesh.bounds));return &c->mesh;
}
const bg_hit_mesh* bg_vehicle_collision_pose(const bg_vehicle*v){PROFILE_BEGIN;const bg_hit_mesh* result=bg_vehicle_collision_pose_impl(v);PROFILE_END(1);return result;}

static float vehicle_sweep_radius(const bg_vehicle*v){
    static float radii[4];if(radii[v->kind]>0)return radii[v->kind];
    const bg_hit_mesh*m=&bg_vehicle_hit_meshes[v->kind];float radius=0;
    const float*yaw=m->parts[m->turret_part].pivot;
    /* Bound each rigid part around its actual joint. A whole-hull bound at
     * every joint grossly enlarges the broad phase and forces needless refits. */
    for(unsigned i=0;i<m->vertex_count;i++){
        const bg_hit_part*part=&m->parts[m->groups[i]];float point[3],delta[3];
        for(unsigned a=0;a<3;a++)point[a]=m->vertices[i][a]/1024.f;
        float reach=sqrtf(dot3(point,point));
        if(part->kind==2){for(unsigned a=0;a<3;a++)delta[a]=point[a]-yaw[a];reach=sqrtf(dot3(yaw,yaw))+sqrtf(dot3(delta,delta));}
        if(part->kind==3){float between[3];for(unsigned a=0;a<3;a++){delta[a]=point[a]-part->pivot[a];between[a]=part->pivot[a]-yaw[a];}
            reach=sqrtf(dot3(yaw,yaw))+sqrtf(dot3(between,between))+sqrtf(dot3(delta,delta));}
        if(part->kind==4)for(unsigned c=0;c<2;c++){
            const bg_hit_hatch*h=&bg_hit_hatches[v->kind==BG_V_BANSHEE][c];
            for(unsigned f=0;f<h->count;f++){
                for(unsigned a=0;a<3;a++)delta[a]=(h->frames[f][0][a]+h->frames[f][1][a]*point[0]+h->frames[f][2][a]*point[1]+h->frames[f][3][a]*point[2])/4096.f;
                reach=fmaxf(reach,sqrtf(dot3(delta,delta)));
            }
        }
        radius=fmaxf(radius,reach);
    }
    return radii[v->kind]=radius+.003f;
}
float bg_vehicle_hit_ray_material_impl(const bg_vehicle*v,const float origin[3],const float direction[3],float distance,unsigned *material){
    float o[3],d[3],offset[3];
    for(unsigned a=0;a<3;a++)offset[a]=origin[a]-v->pos[a];
    /* Most queries are nowhere near this hull. Reject in world space before
     * transforming the ray or traversing its authored collision geometry. */
    float radius=vehicle_sweep_radius(v);
    float along=fminf(distance,fmaxf(0,-dot3(offset,direction))),closest[3];
    for(unsigned a=0;a<3;a++)closest[a]=offset[a]+along*direction[a];
    if(dot3(closest,closest)>radius*radius)return distance;
    const bg_hit_mesh*m=bg_vehicle_collision_pose(v);
    float basis[3][3];
    if(v->physics_valid){
        for(unsigned a=0;a<3;a++){basis[0][a]=v->forward[a];basis[1][a]=v->up[a];}
        cross3(basis[0],basis[1],basis[2]);
    }else for(unsigned axis=0;axis<3;axis++){
        float unit[3]={0};unit[axis]=1;bg_vehicle_transform(v,unit,basis[axis]);
        for(unsigned a=0;a<3;a++)basis[axis][a]-=v->pos[a];
    }
    float inverse[3];bool parallel[3];
    for(unsigned axis=0;axis<3;axis++){
        o[axis]=dot3(offset,basis[axis]);d[axis]=dot3(direction,basis[axis]);
        parallel[axis]=fabsf(d[axis])<1e-8f;inverse[axis]=parallel[axis]?0:1/d[axis];
    }
    uint16_t stack[16]={0};unsigned pending=1;
    while(pending){
      const bg_hit_node*node=&m->nodes[stack[--pending]];
      float lo=0,hi=distance;bool overlap=true;
      for(unsigned a=0;a<3;a++){
        float lower=node->bounds[a]/1024.f,upper=node->bounds[a+3]/1024.f;
        if(parallel[a]){if(o[a]<lower||o[a]>upper){overlap=false;break;}}
        else{float x=(lower-o[a])*inverse[a],y=(upper-o[a])*inverse[a];lo=fmaxf(lo,fminf(x,y));hi=fminf(hi,fmaxf(x,y));if(lo>hi){overlap=false;break;}}
      }
      if(!overlap)continue;
      if(!node->count){assert(pending+2<=16);stack[pending++]=node->right;stack[pending++]=node->first;continue;}
      for(unsigned i=node->first;i<node->first+node->count;i++){
        const int16_t*a=m->vertices[m->triangles[i][0]],*b=m->vertices[m->triangles[i][1]],*c=m->vertices[m->triangles[i][2]];
        float e1[3],e2[3],tvec[3],p[3],q[3];
        for(unsigned k=0;k<3;k++){e1[k]=(b[k]-a[k])/1024.f;e2[k]=(c[k]-a[k])/1024.f;tvec[k]=o[k]-a[k]/1024.f;}
        cross3(d,e2,p);float det=dot3(e1,p);if(fabsf(det)<1e-8f)continue;
        float inverse=1/det,u=dot3(tvec,p)*inverse;if(u<0||u>1)continue;
        cross3(tvec,e1,q);float w=dot3(d,q)*inverse;if(w<0||u+w>1)continue;
        float t=dot3(e2,q)*inverse;if(t>=0&&t<distance){distance=t;if(material)*material=m->materials[i];}
      }
    }return distance;
}
float bg_vehicle_hit_ray_material(const bg_vehicle*v,const float origin[3],const float direction[3],float distance,unsigned *material){PROFILE_BEGIN;float result=bg_vehicle_hit_ray_material_impl(v,origin,direction,distance,material);PROFILE_END(0);return result;}


/* Bounded narrow phase shared by splatters and exit clearance. Broadly reject
 * using the authored hull bounds before touching its triangles. */
static bool vehicle_player_contact_impl(const bg_vehicle*v,const bg_player*p,bg_player*resolve){
    float r=bg_movement.radius,h=bg_body_height(p),d2=0;
    for(unsigned a=0;a<3;a++){
        float d=p->pos[a]+(a==1?h*.5f:0)-v->pos[a];d2+=d*d;
    }
    float reach=vehicle_sweep_radius(v)+h*.5f+r;if(d2>reach*reach)return false;
    const bg_hit_mesh*m=bg_vehicle_collision_pose(v);
    float basis[3][3];
    if(v->physics_valid){
        memcpy(basis[0],v->forward,12);memcpy(basis[1],v->up,12);cross3(basis[0],basis[1],basis[2]);
    }else for(unsigned axis=0;axis<3;axis++){
        float unit[3]={0};unit[axis]=1;bg_vehicle_transform(v,unit,basis[axis]);
        for(unsigned a=0;a<3;a++)basis[axis][a]-=v->pos[a];
    }
    bool contact=false;
    float bounds[6],delta[3];for(unsigned a=0;a<3;a++)delta[a]=p->pos[a]-v->pos[a];
    for(unsigned axis=0;axis<3;axis++){
        float base=dot3(delta,basis[axis]),lo=base+r*basis[axis][1],hi=base+(h-r)*basis[axis][1];
        bounds[axis]=fminf(lo,hi)-r;bounds[axis+3]=fmaxf(lo,hi)+r;
    }
    uint16_t stack[16]={0};unsigned pending=1;
    while(pending){
        const bg_hit_node*node=&m->nodes[stack[--pending]];bool overlap=true;
        for(unsigned a=0;a<3;a++)if(bounds[a]>node->bounds[a+3]/1024.f||bounds[a+3]<node->bounds[a]/1024.f){overlap=false;break;}
        if(!overlap)continue;
        if(!node->count){assert(pending+2<=16);stack[pending++]=node->right;stack[pending++]=node->first;continue;}
        for(unsigned t=node->first;t<node->first+node->count;t++){
            float points[3][3];bg_triangle tri={{points[0],points[1],points[2]}};
            for(unsigned j=0;j<3;j++){
                const int16_t*local=m->vertices[m->triangles[t][j]];
                for(unsigned a=0;a<3;a++)points[j][a]=v->pos[a]+(basis[0][a]*local[0]+basis[1][a]*local[1]+basis[2][a]*local[2])/1024.f;
            }
            float a[3],b[3],d2=bg_capsule_triangle(p->pos,h,r,&tri,a,b);
            if(!resolve){if(d2<r*r)return true;continue;}
            const float skin=.015f;
            if(d2>(r+skin+.001f)*(r+skin+.001f)||d2<1e-12f)continue;
            float distance=sqrtf(d2),normal[3];for(unsigned k=0;k<3;k++)normal[k]=(a[k]-b[k])/distance;
            if(distance<r+skin)for(unsigned k=0;k<3;k++)resolve->pos[k]+=normal[k]*(r+skin-distance);
            float inward=dot3(resolve->velocity,normal);
            if(inward<0)for(unsigned k=0;k<3;k++)resolve->velocity[k]-=normal[k]*inward;
            if(normal[1]>=bg_movement.slope[0]&&inward<=.01f){resolve->grounded=true;memcpy(resolve->ground_normal,normal,12);}
            contact=true;
        }
    }
    return contact;
}
static bool vehicle_player_contact(const bg_vehicle*v,const bg_player*p,bg_player*resolve){PROFILE_BEGIN;bool result=vehicle_player_contact_impl(v,p,resolve);PROFILE_END(2);return result;}

bool bg_vehicle_contacts_player(const bg_vehicle*v,const bg_player*p){return vehicle_player_contact(v,p,NULL);}
bool bg_vehicle_resolve_player(const bg_vehicle*v,bg_player*p){return vehicle_player_contact(v,p,p);}

float bg_vehicle_hit_ray(const bg_vehicle*v,const float origin[3],const float direction[3],float distance){return bg_vehicle_hit_ray_material(v,origin,direction,distance,NULL);}

#ifdef N64
#include <libdragon.h>
#else
#include <stdio.h>
#endif
#define PLAYER_HIT_VERTICES 160
#define PLAYER_HIT_GROUPS 16
typedef struct {bool valid;unsigned clip,blend_clip;float phase,blend_phase,weight;int16_t points[PLAYER_HIT_VERTICES][3];int16_t bounds[PLAYER_HIT_GROUPS][6];} player_hit_pose;
static player_hit_pose player_poses[BG_PLAYERS];
static uint8_t hit_frames[2*PLAYER_HIT_VERTICES*6] __attribute__((aligned(16)));
static void player_hit_read(uint32_t offset,unsigned bytes){
    assert(bytes<=sizeof(hit_frames));
    static uint32_t previous_offset=UINT32_MAX;static unsigned previous_bytes;
    if(offset==previous_offset&&bytes==previous_bytes)return;
    previous_offset=offset;previous_bytes=bytes;
#ifdef N64
    static uint32_t rom,size;
    if(!rom){rom=dfs_rom_addr("player-hits.bin");size=dfs_rom_size("player-hits.bin");assert(rom&&size);}
    assert(offset+bytes<=size);data_cache_hit_invalidate(hit_frames,bytes);dma_read(hit_frames,rom+offset,bytes);
#else
    static FILE*f;if(!f)f=fopen("build/n64/frontend-files/player-hits.bin","rb");assert(f);
    assert(!fseek(f,offset,SEEK_SET));assert(fread(hit_frames,1,bytes,f)==bytes);
#endif
}
static int hit_short(const uint8_t*p){return (int16_t)((unsigned)p[0]*256+p[1]);}
static float clip_phase(unsigned clip,float seconds,bool loop){float phase=fmaxf(0,seconds/bg_player_hit_clips[clip].duration);return loop?phase-floorf(phase):fminf(phase,1);}
static void sample_player_hits(int16_t out[][3],unsigned clip,float phase,float weight){
    const bg_hit_clip*c=&bg_player_hit_clips[clip];float frame=phase*(c->count-1);unsigned f0=frame,f1=f0+1<c->count?f0+1:f0;
    player_hit_read(c->offset+c->stride*f0,c->stride*(f1==f0?1:2));int fraction=(frame-f0)*256,blend=weight*256;
    for(unsigned i=0;i<bg_player_hit_vertex_count;i++)for(unsigned a=0;a<3;a++){
        unsigned at=(i*3+a)*2;int lo=hit_short(hit_frames+at),hi=hit_short(hit_frames+(f1==f0?0:c->stride)+at),value=lo+((hi-lo)*fraction)/256;
        if(blend==256)out[i][a]=value;else out[i][a]+=((value-out[i][a])*blend)/256;
    }
}
static const player_hit_pose*player_pose(unsigned index){
    const bg_player*p=&bg_players[index];const bg_seat_definition*seat=bg_player_seat(p);
    unsigned clip=0;bool loop=false;float seconds=p->anim_time,weight=0,second=0;unsigned blend_clip=0;
    switch(p->animation){case BG_ANIM_WALK:case BG_ANIM_RUN:clip=1;break;case BG_ANIM_FIRE:clip=2;break;case BG_ANIM_RELOAD:clip=3;break;case BG_ANIM_DIE:clip=4;break;case BG_ANIM_JUMP:clip=5;break;case BG_ANIM_MELEE:clip=6;break;case BG_ANIM_DRIVE:clip=8;break;default:break;}
    loop=clip==0||clip==1||clip>=8;
    if(p->grenade_cooldown>.55f&&p->vehicle<0){clip=7;seconds=(.9f-p->grenade_cooldown)/.35f*bg_player_hit_clips[7].duration;loop=false;}
    if(seat){clip=18+seat->pose*3+p->seat_state;loop=p->seat_state==BG_SEAT_STABLE;}
    else if(p->weapon_ready>0){clip=11;seconds=(1-p->weapon_ready/bg_ready_times[p->weapon])*bg_player_hit_clips[11].duration;loop=false;}
    else if(p->health>0&&p->melee_time<=0&&p->reload<=0&&p->flash<=0&&p->grenade_cooldown<=.55f){
        if(p->landing_time>0){blend_clip=14+(p->hard_landing?1:0)+(p->crouch_amount>.5f?2:0);second=clip_phase(blend_clip,p->landing_duration-p->landing_time,false);weight=1;}
        else if(p->grounded&&p->crouch_amount>0){blend_clip=12+(hypotf(p->velocity[0],p->velocity[2])>.15f);second=clip_phase(blend_clip,p->anim_time,true);weight=p->crouch_amount;}
    }
    float phase=clip_phase(clip,seconds,loop);player_hit_pose*c=&player_poses[index];
    if(c->valid&&c->clip==clip&&c->phase==phase&&c->blend_clip==blend_clip&&c->blend_phase==second&&c->weight==weight)return c;
    assert(bg_player_hit_vertex_count<=PLAYER_HIT_VERTICES&&bg_player_hit_group_count<=PLAYER_HIT_GROUPS);
    sample_player_hits(c->points,clip,phase,1);if(weight>0)sample_player_hits(c->points,blend_clip,second,weight);
    for(unsigned g=0;g<bg_player_hit_group_count;g++)for(unsigned a=0;a<3;a++){
        int lo=32767,hi=-32768;unsigned first=bg_player_hit_groups[g][0],count=bg_player_hit_groups[g][1];
        for(unsigned t=first;t<first+count;t++)for(unsigned j=0;j<3;j++){int value=c->points[bg_player_hit_triangles[t][j]][a];if(value<lo)lo=value;if(value>hi)hi=value;}
        c->bounds[g][a]=lo;c->bounds[g][a+3]=hi;
    }
    c->valid=true;c->clip=clip;c->phase=phase;c->blend_clip=blend_clip;c->blend_phase=second;c->weight=weight;return c;
}
float bg_player_hit_ray_impl(unsigned index,const float origin[3],const float direction[3],float distance,int *region){
    const bg_player*p=&bg_players[index];float offset[3];for(unsigned a=0;a<3;a++)offset[a]=origin[a]-p->pos[a];
    float along=fminf(distance,fmaxf(0,-dot3(offset,direction))),closest[3];for(unsigned a=0;a<3;a++)closest[a]=offset[a]+direction[a]*along;
    if(dot3(closest,closest)>4)return distance;
    const player_hit_pose*pose=player_pose(index);const bg_seat_definition*seat=bg_player_seat(p);
    float basis[3][3]={{cosf(p->yaw),0,-sinf(p->yaw)},{0,1,0},{sinf(p->yaw),0,cosf(p->yaw)}};
    if(seat){const bg_vehicle*v=&bg_vehicles[p->vehicle];float relative=seat->yaw+(v->kind==BG_V_WARTHOG&&p->seat==1?v->turret_yaw:0),c=cosf(relative),s=sinf(relative),hull[3][3];
        for(unsigned j=0;j<3;j++){float unit[3]={0};unit[j]=1;bg_vehicle_transform(v,unit,hull[j]);for(unsigned a=0;a<3;a++)hull[j][a]-=v->pos[a];}
        for(unsigned a=0;a<3;a++){basis[0][a]=hull[0][a]*c-hull[2][a]*s;basis[1][a]=hull[1][a];basis[2][a]=hull[0][a]*s+hull[2][a]*c;
            if(p->seat_blend>0)offset[a]-=p->seat_offset[a]*(p->seat_blend/(6.f/30));}
    }
    float o[3],d[3],inverse[3];bool parallel[3];
    for(unsigned a=0;a<3;a++){o[a]=dot3(offset,basis[a]);d[a]=dot3(direction,basis[a]);}
    if(pose->weight==0){float scale=bg_body_height(p)/bg_movement.height[0];o[1]/=scale;d[1]/=scale;}
    for(unsigned a=0;a<3;a++){parallel[a]=fabsf(d[a])<1e-8f;inverse[a]=parallel[a]?0:1/d[a];}
    for(unsigned g=0;g<bg_player_hit_group_count;g++){
        float lo=0,hi=distance;bool overlap=true;
        for(unsigned a=0;a<3;a++){float lower=pose->bounds[g][a]/1024.f,upper=pose->bounds[g][a+3]/1024.f;
            if(parallel[a]){if(o[a]<lower||o[a]>upper){overlap=false;break;}}
            else {float x=(lower-o[a])*inverse[a],y=(upper-o[a])*inverse[a];lo=fmaxf(lo,fminf(x,y));hi=fminf(hi,fmaxf(x,y));if(lo>hi){overlap=false;break;}}}
        if(!overlap)continue;
        unsigned first=bg_player_hit_groups[g][0],count=bg_player_hit_groups[g][1];
        for(unsigned t=first;t<first+count;t++){
            const int16_t*a=pose->points[bg_player_hit_triangles[t][0]],*b=pose->points[bg_player_hit_triangles[t][1]],*c=pose->points[bg_player_hit_triangles[t][2]];
            float e1[3],e2[3],delta[3],cross[3],q[3];for(unsigned k=0;k<3;k++){e1[k]=(b[k]-a[k])/1024.f;e2[k]=(c[k]-a[k])/1024.f;delta[k]=o[k]-a[k]/1024.f;}
            cross3(d,e2,cross);float det=dot3(e1,cross);if(fabsf(det)<1e-8f)continue;
            float inv=1/det,u=dot3(delta,cross)*inv;if(u<0||u>1)continue;cross3(delta,e1,q);float w=dot3(d,q)*inv;if(w<0||u+w>1)continue;
            float hit=dot3(e2,q)*inv;if(hit>=0&&hit<distance){distance=hit;*region=bg_player_hit_regions[t];}
        }
    }return distance;
}
float bg_player_hit_ray(unsigned index,const float origin[3],const float direction[3],float distance,int *region){PROFILE_BEGIN;float result=bg_player_hit_ray_impl(index,origin,direction,distance,region);PROFILE_END(3);return result;}
