#include <libdragon.h>
#include <t3d/t3d.h>
#include <math.h>
#include <string.h>
#include "game.h"
#include "asset_models.h"
#include "asset_firstperson.h"
#include "blam/runtime.h"
#include "sound.h"
#include "hud.h"
#include "replay.h"
#ifdef BG_SHOWCASE
#include "showcase.h"
#endif

/* Two fenced geometry slots retain detailed models within base 4 MiB RAM.
 * Display color buffers remain triple buffered; geometry reuse waits on RSP. */
#define BG_FRAME_SLOTS 2
extern T3DVertPacked bg_vertices[];
extern uint16_t bg_textures[][32*32];
static const color_t colors[4]={{225,45,38,255},{39,92,215,255},{215,179,44,255},{57,183,69,255}};
static surface_t textures[32];
static T3DVertPacked *armor[BG_FRAME_SLOTS][4], particles[7][12] __attribute__((aligned(16)));
static T3DVertPacked *firstperson[BG_FRAME_SLOTS][4];
static int firstperson_weapon[BG_FRAME_SLOTS][4];
static T3DVertPacked *armor_lod[BG_FRAME_SLOTS][4];
static rspq_block_t *armor_lod_blocks[BG_FRAME_SLOTS][4];
static rspq_block_t *firstperson_blocks[BG_FRAME_SLOTS][4];
static float fired_at[4]={-100,-100,-100,-100};
static rspq_block_t *world_blocks[512], *player_blocks[BG_FRAME_SLOTS][4], *models[BG_M_COUNT], *particle_blocks[7];
static rspq_block_t *vehicle_lods[4];
static rspq_block_t *vehicle_parts[4][7];
static T3DMat4FP part_matrices[BG_FRAME_SLOTS][BG_MAX_VEHICLES][7];
static float wheel_rotation[BG_MAX_VEHICLES];
static T3DViewport viewports[BG_FRAME_SLOTS][4] __attribute__((aligned(16)));
static T3DMat4FP transforms[BG_FRAME_SLOTS][4], guns[BG_FRAME_SLOTS][4], vehicle_matrices[BG_FRAME_SLOTS][BG_MAX_VEHICLES],
    pickup_matrices[BG_FRAME_SLOTS][BG_MAX_PICKUPS], projectile_matrices[BG_FRAME_SLOTS][BG_MAX_PROJECTILES], explosion_matrices[BG_FRAME_SLOTS][12];
static T3DMat4FP held_matrices[BG_FRAME_SLOTS][4];
static rspq_syncpoint_t fences[BG_FRAME_SLOTS];
static bool pending[BG_FRAME_SLOTS],paused;
static unsigned slot,views=4,triangles,fps,menu_row;
static float game_time;
#ifdef BG_PROFILE
static unsigned sim_us,prep_us,draw_us,wait_us;
#endif
#ifdef RDPQ_VALIDATE
static unsigned validation_errors,validation_warnings;
static char validation_line[192],validation_message[96];
static unsigned validation_length;
static int validation_write(void*cookie,const char*text,int length){
    for(int i=0;i<length;i++){
        if(text[i]=='\n'){
            validation_line[validation_length]=0;
            if(strstr(validation_line,"[RDPQ_VALIDATION]")){
                if(strstr(validation_line,"ERROR:")||strstr(validation_line,"CRASH:"))validation_errors++;
                if(strstr(validation_line,"WARN:"))validation_warnings++;
                if(strstr(validation_line,"ERROR:")||strstr(validation_line,"WARN:"))
                    snprintf(validation_message,sizeof(validation_message),"%.95s",validation_line+18);
            }
            validation_length=0;
        }else if(validation_length+1<sizeof(validation_line))validation_line[validation_length++]=text[i];
    }
    return fwrite(text,1,length,(FILE*)cookie);
}
#endif
static struct {float pos[3],life,radius;} explosions[12];
static unsigned explosion_next;

static unsigned weapon_model(unsigned w){return w==BG_W_FLAMETHROWER?BG_M_FLAMETHROWER:w<8?w:BG_M_AR;}
static void tint_team(T3DVertPacked*vertices,unsigned count,const uint8_t*masks,unsigned player){
    for(unsigned i=0;i<count;i++){
        uint32_t*rgba=t3d_vertbuffer_get_color(vertices,i);
        unsigned r=*rgba>>24,g=(*rgba>>16)&255,b=(*rgba>>8)&255,mask=masks[i];
        r=(r*(65025-mask*(255-colors[player].r))+32512)/65025;
        g=(g*(65025-mask*(255-colors[player].g))+32512)/65025;
        b=(b*(65025-mask*(255-colors[player].b))+32512)/65025;
        *rgba=(r<<24)|(g<<16)|(b<<8)|255;
    }
}
static rspq_block_t *record(T3DVertPacked *verts,unsigned count){
    rspq_block_begin();
    for(unsigned first=0;first<count;first+=60){
        unsigned n=count-first>60?60:count-first;
        t3d_vert_load(verts+first/2,0,(n+1)&~1u);
        for(unsigned j=0;j<n;j+=3)t3d_tri_draw(j,j+1,j+2);
        t3d_tri_sync();
    }
    return rspq_block_end();
}
static void init_scene(void){
    assertf(bg_chunk_count<=512&&bg_material_count<=32,"Asset capacity exceeded");
    data_cache_hit_writeback(bg_vertices,bg_vertex_count*16);
    for(unsigned i=0;i<bg_material_count;i++){
        textures[i]=surface_make(bg_textures[i],FMT_RGBA16,32,32,64);
        data_cache_hit_writeback(bg_textures[i],2048);
    }
    for(unsigned i=0;i<bg_chunk_count;i++)world_blocks[i]=record(bg_vertices+bg_chunks[i].first/2,bg_chunks[i].count);
    for(unsigned m=0;m<BG_M_COUNT;m++){
        const bg_model_asset*a=&bg_model_assets[m];
        data_cache_hit_writeback(a->vertices,((a->vertex_count+1)&~1u)*16);
        models[m]=record(a->vertices,a->vertex_count);
    }
    for(unsigned m=0;m<4;m++){
        const bg_model_asset*a=&bg_vehicle_lods[m];
        data_cache_hit_writeback(a->vertices,((a->vertex_count+1)&~1u)*16);
        vehicle_lods[m]=record(a->vertices,a->vertex_count);
        const bg_vehicle_rig*rig=&bg_vehicle_rigs[m];
        assertf(rig->count<=7,"Vehicle rig capacity");
        for(unsigned j=0;j<rig->count;j++)
            vehicle_parts[m][j]=record(bg_model_assets[BG_M_WARTHOG+m].vertices+rig->parts[j].first/2,rig->parts[j].count);
    }
    const bg_model_asset*spartan=&bg_model_assets[BG_M_SPARTAN];
    unsigned bytes=((spartan->vertex_count+1)/2)*sizeof(T3DVertPacked);
    for(unsigned s=0;s<BG_FRAME_SLOTS;s++)for(unsigned p=0;p<4;p++){
        armor[s][p]=malloc_uncached(bytes);assertf(armor[s][p],"Spartan buffer allocation");
        memcpy(armor[s][p],spartan->vertices,bytes);
        tint_team(armor[s][p],spartan->vertex_count,bg_spartan_team_mask,p);
        player_blocks[s][p]=record(armor[s][p],spartan->vertex_count);
        unsigned lod_bytes=((bg_spartan_lod.vertex_count+1)&~1u)*16;
        armor_lod[s][p]=malloc_uncached(lod_bytes);assertf(armor_lod[s][p],"Spartan LOD allocation");
        memcpy(armor_lod[s][p],bg_spartan_lod.vertices,lod_bytes);
        tint_team(armor_lod[s][p],bg_spartan_lod.vertex_count,bg_spartan_lod_team_mask,p);
        armor_lod_blocks[s][p]=record(armor_lod[s][p],bg_spartan_lod.vertex_count);
        firstperson[s][p]=malloc_uncached(bg_fp_max_vertices*16);
        assertf(firstperson[s][p],"First-person buffer allocation");
        firstperson_weapon[s][p]=-1;
        viewports[s][p]=t3d_viewport_create();
    }
    static const int16_t points[6][3]={{0,32,0},{0,-32,0},{32,0,0},{0,0,32},{-32,0,0},{0,0,-32}};
    static const uint8_t indices[24]={0,2,3,0,3,4,0,4,5,0,5,2,1,3,2,1,4,3,1,5,4,1,2,5};
    const uint32_t hues[7]={0x54d9ffff,0xf15cffff,0xffd38aff,0x818977ff,0x76abffff,0xffbc50ff,0xff9836ff};
    for(unsigned k=0;k<7;k++){
        for(unsigned i=0;i<24;i++){
            memcpy(t3d_vertbuffer_get_pos(particles[k],i),points[indices[i]],6);
            *t3d_vertbuffer_get_color(particles[k],i)=hues[k];
        }
        data_cache_hit_writeback(particles[k],sizeof(particles[k]));particle_blocks[k]=record(particles[k],24);
    }
}
static void fill(int x,int y,int w,int h,color_t color){rdpq_set_mode_fill(color);rdpq_fill_rectangle(x,y,x+w,y+h);}
static void reset_view_state(void){
    for(unsigned p=0;p<4;p++)fired_at[p]=-100;
    memset(explosions,0,sizeof(explosions));memset(wheel_rotation,0,sizeof(wheel_rotation));explosion_next=0;
}
static bool input(bg_input in[4]){
    bool was_paused=paused;
    joypad_poll();
    for(unsigned i=0;i<4;i++){
        joypad_inputs_t stick=joypad_get_inputs(i);joypad_buttons_t held=joypad_get_buttons(i),pressed=joypad_get_buttons_pressed(i);
        float x=stick.stick_x/80.f,y=stick.stick_y/80.f;if(fabsf(x)<.12f)x=0;if(fabsf(y)<.12f)y=0;
        in[i]=(bg_input){.forward=y,.turn=-x,.strafe=held.c_right-held.c_left,.look=held.c_up-held.c_down,
            .jump=bg_players[i].vehicle>=0?held.a:pressed.a,.fire=held.z,.reload=pressed.b,.interact=pressed.b,.switch_weapon=pressed.r,
            .grenade=pressed.l,.secondary_fire=held.l,.switch_grenade=pressed.d_left,.melee=pressed.d_down,.zoom=pressed.d_up,.crouch=held.d_right};
        if(i==0){
            if(pressed.start)paused=!paused;
            if(paused){
                if(pressed.d_down)menu_row=(menu_row+1)%4;
                if(pressed.d_up)menu_row=(menu_row+3)%4;
                if(pressed.a){
                    if(menu_row==0)paused=false;
                    if(menu_row==1){bg_reset();paused=false;game_time=0;reset_view_state();}
                    if(menu_row==2){views=views==4?1:views==1?2:4;bg_set_players(views);}
                }
            }
        }
    }
    if(paused||was_paused)memset(in,0,sizeof(bg_input)*4);
    return paused||was_paused;
}
static bool visible(T3DViewport*vp,const float pos[3],float radius){
    int16_t lo[3],hi[3];for(int i=0;i<3;i++){lo[i]=(pos[i]-radius)*BG_SCALE;hi[i]=(pos[i]+radius)*BG_SCALE;}
    return t3d_frustum_vs_aabb_s16(&vp->viewFrustum,lo,hi);
}
static void instance(unsigned model,T3DMat4FP*matrix){
    t3d_matrix_push(matrix);rspq_block_run(models[model]);t3d_matrix_pop(1);triangles+=bg_model_assets[model].vertex_count/3;
}
static void matrix(T3DMat4FP*out,float scale,float yaw,float pitch,const float pos[3]){
    t3d_mat4fp_from_srt_euler(out,(float[]){scale,scale,scale},(float[]){0,-yaw,-pitch},
        (float[]){pos[0]*BG_SCALE,pos[1]*BG_SCALE,pos[2]*BG_SCALE});
}
static void animate_player(unsigned p){
    bg_player*player=&bg_players[p];unsigned clip;
    float body_yaw=player->yaw,body_pitch=0;
    switch(player->animation){
        case BG_ANIM_WALK:case BG_ANIM_RUN:clip=BG_A_RUN;break;
        case BG_ANIM_FIRE:clip=BG_A_FIRE;break;case BG_ANIM_RELOAD:clip=BG_A_RELOAD;break;
        case BG_ANIM_DIE:clip=BG_A_DEATH;break;case BG_ANIM_JUMP:clip=BG_A_JUMP;break;
        case BG_ANIM_MELEE:clip=BG_A_MELEE;break;case BG_ANIM_DRIVE:clip=BG_A_DRIVE;break;
        default:clip=BG_A_IDLE;break;
    }
    if(player->health>0&&player->vehicle>=0){
        const bg_vehicle*vehicle=&bg_vehicles[player->vehicle];
        if(vehicle->kind==BG_V_WARTHOG){
            clip=player->seat==2?BG_A_PASSENGER:player->seat==1?BG_A_GUNNER:BG_A_DRIVE;
            body_yaw=vehicle->yaw+(player->seat==1?vehicle->turret_yaw:0);
            body_pitch=vehicle->pitch;
        }
    }
    bool throwing=player->health>0&&player->grenade_cooldown>.55f&&player->vehicle<0;
    if(throwing)clip=BG_A_THROW;
    for(unsigned lod=0;lod<2;lod++){
    const bg_anim_asset*a=lod?&bg_spartan_lod_animations[clip]:&bg_animations[clip];
    float phase=throwing?(.9f-player->grenade_cooldown)/.35f:player->anim_time/a->duration;
    bool loop=clip==BG_A_RUN||clip==BG_A_IDLE||clip==BG_A_DRIVE||clip==BG_A_PASSENGER||clip==BG_A_GUNNER;
    if(loop)phase-=floorf(phase);else phase=fminf(phase,.9999f);
    float frame=phase*(a->frames-1);unsigned f0=(unsigned)frame,f1=f0+1<a->frames?f0+1:f0;
    int fraction=(frame-f0)*256;
    T3DVertPacked*output=CachedAddr(lod?armor_lod[slot][p]:armor[slot][p]);
    for(unsigned v=0;v<a->vertices;v++){
        int16_t*dst=t3d_vertbuffer_get_pos(output,v);
        unsigned track=a->indices[v];
        const uint8_t*src0=a->positions+(f0*a->tracks+track)*3,*src1=a->positions+(f1*a->tracks+track)*3;
        for(unsigned c=0;c<3;c++)dst[c]=a->origin[c]+src0[c]+((src1[c]-src0[c])*fraction)/256;
    }
    data_cache_hit_writeback(output,((a->vertices+1)&~1u)*16);
    if(lod==0){
        const bg_attachment_clip*attach=&bg_weapon_attachment[clip];
        const bg_attachment_pose*pose0=&attach->poses[f0],*pose1=&attach->poses[f1];
        float q[4],pos[3],weight=frame-f0;
        blam_quaternions_interpolate_and_normalize(pose0->quat,pose1->quat,weight,q);
        for(unsigned c=0;c<3;c++)pos[c]=(pose0->pos[c]+(pose1->pos[c]-pose0->pos[c])*weight)*BG_SCALE;
        T3DMat4 hand,body,world;float size=player->crouched?.8f:1;
        float model_scale=BG_SCALE/BG_OBJECT_SCALE;
        t3d_mat4_from_srt(&hand,(float[]){model_scale,model_scale,model_scale},q,pos);
        t3d_mat4_from_srt_euler(&body,(float[]){size,size,size},(float[]){0,-body_yaw,-body_pitch},
            (float[]){player->pos[0]*BG_SCALE,player->pos[1]*BG_SCALE,player->pos[2]*BG_SCALE});
        t3d_mat4_mul(&world,&body,&hand);t3d_mat4_to_fixed_3x4(&held_matrices[slot][p],&world);
    }
    }
    matrix(&transforms[slot][p],(player->crouched?.8f:1)*BG_SCALE/BG_MODEL_SCALE,body_yaw,body_pitch,player->pos);
}
static void pivot_rotation(T3DMat4*out,const float pivot[3],float yaw,float pitch){
    t3d_mat4_from_srt_euler(out,(float[]){1,1,1},(float[]){0,-yaw,-pitch},(float[]){0,0,0});
    T3DVec3 p={{pivot[0]*BG_OBJECT_SCALE,pivot[1]*BG_OBJECT_SCALE,pivot[2]*BG_OBJECT_SCALE}},rotated;
    t3d_mat3_mul_vec3(&rotated,out,&p);
    for(unsigned a=0;a<3;a++)out->m[3][a]=p.v[a]-rotated.v[a];
}
static void prepare_vehicle(unsigned i){
    bg_vehicle*v=&bg_vehicles[i];const bg_vehicle_rig*rig=&bg_vehicle_rigs[v->kind];
    float model_scale=BG_SCALE/BG_OBJECT_SCALE;
    T3DMat4 base,yaw;t3d_mat4_from_srt_euler(&base,(float[]){model_scale,model_scale,model_scale},(float[]){0,-v->yaw,-v->pitch},
        (float[]){v->pos[0]*BG_SCALE,v->pos[1]*BG_SCALE,v->pos[2]*BG_SCALE});
    t3d_mat4_to_fixed_3x4(&vehicle_matrices[slot][i],&base);
    pivot_rotation(&yaw,rig->turret_pivot,v->turret_yaw,0);
    for(unsigned j=0;j<rig->count;j++){
        const bg_vehicle_part*part=&rig->parts[j];T3DMat4 local,world;
        if(part->kind==BG_PART_BODY){part_matrices[slot][i][j]=vehicle_matrices[slot][i];continue;}
        if(part->kind==BG_PART_TURRET)local=yaw;
        else if(part->kind==BG_PART_WHEEL)pivot_rotation(&local,part->pivot,0,-wheel_rotation[i]);
        else{
            T3DMat4 pitch;pivot_rotation(&pitch,part->pivot,0,v->turret_pitch-v->pitch);
            t3d_mat4_mul(&local,&yaw,&pitch);
        }
        t3d_mat4_mul(&world,&base,&local);t3d_mat4_to_fixed_3x4(&part_matrices[slot][i][j],&world);
    }
}
static void prepare_frame(void){
    for(unsigned p=0;p<4;p++){
        if(p>=views)continue;
        animate_player(p);
        bg_player*player=&bg_players[p];unsigned w=player->weapon;
        if(player->vehicle>=0||player->health<=0||player->zoom||p>=views)continue;
        const bg_model_asset*m=&bg_fp_models[w];
        T3DVertPacked*output=CachedAddr(firstperson[slot][p]);
        unsigned bytes=((m->vertex_count+1)&~1u)*16;
        if(firstperson_weapon[slot][p]!=(int)w){
            memset((uint8_t*)output+bytes,0,bg_fp_max_vertices*16-bytes);
            memcpy(output,m->vertices,bytes);
            tint_team(output,m->vertex_count,bg_fp_team_masks[w],p);
            /* This frame slot's RSP fence has completed before preparation. */
            if(firstperson_blocks[slot][p])rspq_block_free(firstperson_blocks[slot][p]);
            firstperson_blocks[slot][p]=record(firstperson[slot][p],m->vertex_count);
            firstperson_weapon[slot][p]=w;
        }
        unsigned clip=BG_FP_IDLE;float seconds=game_time;
        if(player->reload>0){clip=BG_FP_RELOAD;seconds=player->anim_time;}
        else if(player->overheated){clip=BG_FP_RELOAD;seconds=(1-player->heat)/.85f*bg_fp_animations[w][clip].duration;}
        else if(player->melee_time>0){clip=BG_FP_MELEE;seconds=.7f-player->melee_time;}
        else if(game_time>=fired_at[p]&&game_time-fired_at[p]<bg_fp_animations[w][BG_FP_FIRE].duration){clip=BG_FP_FIRE;seconds=game_time-fired_at[p];}
        const bg_anim_asset*a=&bg_fp_animations[w][clip];
        float phase=fmaxf(0,seconds/a->duration);
        if(clip==BG_FP_IDLE)phase-=floorf(phase);else phase=fminf(phase,.9999f);
        float frame=phase*(a->frames-1);unsigned f0=frame,f1=f0+1<a->frames?f0+1:f0;int fraction=(frame-f0)*256;
        for(unsigned v=0;v<a->vertices;v++){
            int16_t*dst=t3d_vertbuffer_get_pos(output,v);
            unsigned track=a->indices[v];
            const uint8_t*src0=a->positions+(f0*a->tracks+track)*3,*src1=a->positions+(f1*a->tracks+track)*3;
            for(unsigned c=0;c<3;c++)dst[c]=a->origin[c]+src0[c]+(src1[c]-src0[c])*fraction/256;
        }
        data_cache_hit_writeback(output,bg_fp_max_vertices*16);
    }
    for(unsigned i=0;i<bg_vehicle_count;i++)if(bg_vehicles[i].active)
        prepare_vehicle(i);
    for(unsigned i=0;i<bg_pickup_count;i++){
        if(!bg_pickups[i].active)continue;
        float pos[3];memcpy(pos,bg_pickups[i].pos,sizeof(pos));pos[1]+=.035f*sinf(game_time*2+i);
        matrix(&pickup_matrices[slot][i],BG_SCALE/BG_OBJECT_SCALE,game_time*.5f,0,pos);
    }
    for(unsigned i=0;i<BG_MAX_PROJECTILES;i++){
        bg_projectile*q=bg_projectile_at(i);if(!q||!q->active)continue;
        float scale=q->kind==BG_P_CANNON?.09f:q->kind==BG_P_FLAME?.18f:.045f;
        if(q->kind==BG_P_FRAG||q->kind==BG_P_PLASMA_GRENADE)scale=BG_SCALE/BG_OBJECT_SCALE;
        matrix(&projectile_matrices[slot][i],scale,game_time*4,0,q->pos);
    }
    for(unsigned i=0;i<12;i++)if(explosions[i].life>0)
        matrix(&explosion_matrices[slot][i],explosions[i].radius*(.4f+1-explosions[i].life/.35f),0,0,explosions[i].pos);
    data_cache_hit_writeback(transforms[slot],sizeof(transforms[slot]));data_cache_hit_writeback(vehicle_matrices[slot],sizeof(vehicle_matrices[slot]));
    data_cache_hit_writeback(pickup_matrices[slot],sizeof(pickup_matrices[slot]));data_cache_hit_writeback(projectile_matrices[slot],sizeof(projectile_matrices[slot]));
    data_cache_hit_writeback(explosion_matrices[slot],sizeof(explosion_matrices[slot]));
    data_cache_hit_writeback(part_matrices[slot],sizeof(part_matrices[slot]));
    data_cache_hit_writeback(held_matrices[slot],sizeof(held_matrices[slot]));
}
static void update_effects(float dt){
    if(bg_match_time()<=dt+.00001f)reset_view_state();
    for(unsigned i=0;i<bg_vehicle_count;i++)wheel_rotation[i]=fmodf(wheel_rotation[i]+bg_vehicles[i].speed*dt/.18f,6.2831853f);
    for(unsigned i=0;i<12;i++)explosions[i].life=fmaxf(0,explosions[i].life-dt);
    for(unsigned i=0;i<bg_event_count;i++)if(bg_events[i].kind==BG_EVENT_FIRE&&bg_events[i].player>=0&&bg_events[i].player<4)
        fired_at[bg_events[i].player]=game_time;
    for(unsigned i=0;i<bg_event_count;i++)if(bg_events[i].kind==BG_EVENT_EXPLOSION){
        unsigned j=explosion_next++%12;memcpy(explosions[j].pos,bg_events[i].pos,12);
        explosions[j].life=.35f;explosions[j].radius=bg_events[i].amount*.4f;
    }
}
static void draw_view(unsigned p){
    int w=views==4?160:320,h=views==1?240:120,x=views==4?(p%2)*160:0,y=views==1?0:(views==4?p/2:p)*120;
    bg_player*player=&bg_players[p];float cp=cosf(player->pitch),sy=sinf(player->yaw),cy=cosf(player->yaw);
    float head=player->crouched?.42f:.62f;
    T3DVec3 eye={{player->pos[0]*BG_SCALE,(player->pos[1]+head)*BG_SCALE,player->pos[2]*BG_SCALE}};
    T3DVec3 target={{eye.v[0]+cy*cp,eye.v[1]+sinf(player->pitch),eye.v[2]-sy*cp}};
    if(player->vehicle>=0){
        const bg_vehicle*vehicle=&bg_vehicles[player->vehicle];
        /* A shallow hull-relative boom keeps the complete vehicle in view,
         * including the front seats in a half-height split-screen viewport. */
        float direction[3]={-cy*.992774f,.12f,sy*.992774f};
        float origin[3]={vehicle->pos[0],vehicle->pos[1]+.5f,vehicle->pos[2]};
        float distance=bg_raycast(origin,direction,3.5f)-.15f;if(distance<.3f)distance=.3f;
        for(int i=0;i<3;i++)eye.v[i]=(origin[i]+direction[i]*distance)*BG_SCALE;
        /* Mounted weapons start one unit ahead of the player's aim origin.
         * Follow that pitch-aware trajectory so the reticle tracks the shot. */
        float aim_direction[3]={cy*cp,sinf(player->pitch),-sy*cp};
        float muzzle[3]={player->pos[0],player->pos[1]+(player->crouched?.4f:.62f),player->pos[2]};
        for(unsigned a=0;a<3;a++)muzzle[a]+=aim_direction[a];
        float aim_distance=fmaxf(2.f,bg_raycast(muzzle,aim_direction,150.f));
        for(unsigned a=0;a<3;a++)target.v[a]=(muzzle[a]+aim_direction[a]*aim_distance)*BG_SCALE;
    }else if(player->health<=0){
        /* Pull the death view away from the corpse. If the wall behind it is
         * close, choose a clear shoulder direction before placing the camera. */
        const float directions[3][3]={{-cy*.82f,.572f,sy*.82f},{sy*.82f,.572f,cy*.82f},{-sy*.82f,.572f,-cy*.82f}};
        float origin[3]={player->pos[0],player->pos[1]+.5f,player->pos[2]};
        unsigned direction=0;float distance=bg_raycast(origin,directions[0],2.f)-.1f;
        if(distance<.75f)for(unsigned d=1;d<3;d++){
            float candidate=bg_raycast(origin,directions[d],2.f)-.1f;
            if(candidate>distance){direction=d;distance=candidate;}
        }
        if(distance<.2f)distance=.2f;
        for(unsigned a=0;a<3;a++){eye.v[a]=(origin[a]+directions[direction][a]*distance)*BG_SCALE;target.v[a]=player->pos[a]*BG_SCALE;}
        target.v[1]+=.3f*BG_SCALE;
    }
    T3DViewport*vp=&viewports[slot][p];t3d_viewport_set_area(vp,x,y,w,h);
    float fov=views==2?.72f:1.08f;
    if(player->health>0&&player->zoom)fov/=player->weapon==BG_W_SNIPER?(player->zoom==2?10:2):2;
    t3d_viewport_set_projection(vp,fov,1.4f,6200.f);t3d_viewport_look_at(vp,&eye,&target,&(T3DVec3){{0,1,0}});
    t3d_viewport_attach(vp);rdpq_clear(RGBA32(150,185,216,255));t3d_frame_start();
    rdpq_mode_dithering(DITHER_NONE_NONE);t3d_light_set_ambient((uint8_t[]){255,255,255,255});t3d_light_set_count(0);
    rdpq_mode_tlut(TLUT_NONE);rdpq_mode_combiner(RDPQ_COMBINER_TEX_SHADE);rdpq_mode_persp(true);rdpq_mode_filter(FILTER_BILINEAR);
    t3d_state_set_drawflags(T3D_FLAG_SHADED|T3D_FLAG_DEPTH|T3D_FLAG_TEXTURED|T3D_FLAG_CULL_FRONT);
    unsigned bound=~0u;
    for(unsigned b=0;b<bg_chunk_count;b++){
        const bg_chunk*c=&bg_chunks[b];if(!t3d_frustum_vs_aabb_s16(&vp->viewFrustum,c->bounds,c->bounds+3))continue;
        if(bound!=c->material){
            rdpq_tex_upload(TILE0,&textures[c->material],&(rdpq_texparms_t){.s.repeats=REPEAT_INFINITE,.t.repeats=REPEAT_INFINITE});
            bound=c->material;
        }
        rspq_block_run(world_blocks[b]);triangles+=c->count/3;
    }
    rdpq_mode_combiner(RDPQ_COMBINER_SHADE);t3d_state_set_drawflags(T3D_FLAG_SHADED|T3D_FLAG_DEPTH|T3D_FLAG_CULL_FRONT);
    for(unsigned i=0;i<bg_vehicle_count;i++)if(bg_vehicles[i].active&&visible(vp,bg_vehicles[i].pos,2.5f)){
        bg_vehicle*v=&bg_vehicles[i];float distance=0;
        for(unsigned a=0;a<3;a++){float d=v->pos[a]-eye.v[a]/BG_SCALE;distance+=d*d;}
        if(distance>36&&player->zoom==0){
            t3d_matrix_push(&vehicle_matrices[slot][i]);rspq_block_run(vehicle_lods[v->kind]);t3d_matrix_pop(1);
            triangles+=bg_vehicle_lods[v->kind].vertex_count/3;
        }else{
            const bg_vehicle_rig*rig=&bg_vehicle_rigs[v->kind];
            for(unsigned j=0;j<rig->count;j++){
                t3d_matrix_push(&part_matrices[slot][i][j]);rspq_block_run(vehicle_parts[v->kind][j]);t3d_matrix_pop(1);
                triangles+=rig->parts[j].count/3;
            }
        }
    }
    for(unsigned j=0;j<views;j++){
        bg_player*q=&bg_players[j];
        if((j==p&&player->vehicle<0&&player->health>0)||!visible(vp,q->pos,1)||q->invisibility>0)continue;
        if(q->vehicle>=0&&bg_vehicles[q->vehicle].kind==BG_V_BANSHEE)continue;
        float distance=0;for(unsigned a=0;a<3;a++){float d=q->pos[a]-eye.v[a]/BG_SCALE;distance+=d*d;}
        /* A 160x120 view needs the detailed body only at close range. The
         * authored distant topology preserves its silhouette at small sizes. */
        bool lod=distance>(views==4?4.f:16.f)&&player->zoom==0;
        t3d_matrix_push(&transforms[slot][j]);rspq_block_run(lod?armor_lod_blocks[slot][j]:player_blocks[slot][j]);t3d_matrix_pop(1);
        triangles+=(lod?bg_spartan_lod.vertex_count:bg_model_assets[BG_M_SPARTAN].vertex_count)/3;
        bool personal=q->vehicle<0||q->seat==2||
            (q->seat==1&&bg_vehicles[q->vehicle].kind==BG_V_SCORPION);
        if((distance<=16||player->zoom)&&q->health>0&&personal)
            instance(weapon_model(q->weapon),&held_matrices[slot][j]);
    }
    for(unsigned i=0;i<bg_pickup_count;i++){
        bg_pickup*q=&bg_pickups[i];if(!q->active||!visible(vp,q->pos,.6f))continue;
        if(q->weapon<BG_WEAPON_COUNT)instance(weapon_model(q->weapon),&pickup_matrices[slot][i]);
        else if(q->weapon==BG_PICK_FRAG||q->weapon==BG_PICK_PLASMA)instance(q->weapon==BG_PICK_FRAG?BG_M_FRAG:BG_M_PLASMA_GRENADE,&pickup_matrices[slot][i]);
        else instance(q->weapon==BG_PICK_HEALTH?BG_M_HEALTHPACK:q->weapon==BG_PICK_OVERSHIELD?BG_M_OVERSHIELD:BG_M_CAMOUFLAGE,&pickup_matrices[slot][i]);
    }
    t3d_state_set_drawflags(T3D_FLAG_SHADED|T3D_FLAG_DEPTH);
    for(unsigned i=0;i<BG_MAX_PROJECTILES;i++){
        bg_projectile*q=bg_projectile_at(i);if(!q||!q->active||!visible(vp,q->pos,.2f))continue;
        if(q->kind==BG_P_FRAG||q->kind==BG_P_PLASMA_GRENADE){instance(q->kind==BG_P_FRAG?BG_M_FRAG:BG_M_PLASMA_GRENADE,&projectile_matrices[slot][i]);continue;}
        t3d_matrix_push(&projectile_matrices[slot][i]);rspq_block_run(particle_blocks[q->kind]);t3d_matrix_pop(1);triangles+=8;
    }
    for(unsigned i=0;i<12;i++)if(explosions[i].life>0&&visible(vp,explosions[i].pos,explosions[i].radius)){
        t3d_matrix_push(&explosion_matrices[slot][i]);rspq_block_run(particle_blocks[6]);t3d_matrix_pop(1);triangles+=8;
    }
    if(player->health>0&&player->vehicle<0&&!player->zoom){
        float pos[3]={eye.v[0]/BG_SCALE,eye.v[1]/BG_SCALE+sinf(player->gait)*.007f,eye.v[2]/BG_SCALE};
        matrix(&guns[slot][p],BG_SCALE/BG_FP_SCALE,player->yaw,player->pitch,pos);data_cache_hit_writeback(&guns[slot][p],sizeof(T3DMat4FP));
        t3d_state_set_drawflags(T3D_FLAG_SHADED|T3D_FLAG_CULL_FRONT);rdpq_mode_zbuf(false,false);
        t3d_matrix_push(&guns[slot][p]);rspq_block_run(firstperson_blocks[slot][p]);t3d_matrix_pop(1);triangles+=bg_fp_models[player->weapon].vertex_count/3;
    }
    bg_hud_draw(p,x,y,w,h);
}
static void draw_menu(void){
    fill(48,32,224,176,RGBA32(12,27,56,255));fill(48,32,224,2,RGBA32(114,176,233,255));
    rdpq_set_mode_standard();rdpq_text_print(NULL,1,66,52,"HALO / BLOOD GULCH");
    rdpq_text_print(NULL,1,66,68,"SLAYER");
    const char*items[]={"RESUME","RESTART MATCH","PLAYERS","CONTROLS"};
    for(unsigned i=0;i<4;i++)rdpq_text_printf(NULL,1,66,90+i*16,"%c %s%s",menu_row==i?'>':' ',items[i],i==2?(views==4?" 4":views==2?" 2":" 1"):"");
    rdpq_text_print(NULL,1,58,158,"Z FIRE  A JUMP  B USE/RELOAD");
    rdpq_text_print(NULL,1,58,170,"R WEAPON  L GRENADE  C AIM");
    rdpq_text_print(NULL,1,58,182,"D: UP ZOOM / DOWN MELEE");
    rdpq_text_print(NULL,1,58,194,"LEFT GRENADE / RIGHT CROUCH");
}
static void draw_result(void){
    fill(66,45,188,146,RGBA32(12,27,56,255));fill(66,45,188,2,RGBA32(114,176,233,255));
    rdpq_set_mode_standard();rdpq_text_print(NULL,1,124,64,"GAME OVER");
    rdpq_text_printf(NULL,1,112,80,"PLAYER %d WINS",bg_match_winner()+1);
    for(unsigned p=0;p<views;p++){
        fill(83,90+p*17,5,9,colors[p]);rdpq_set_mode_standard();
        rdpq_text_printf(NULL,1,96,98+p*17,"PLAYER %u       %2d",p+1,bg_players[p].score);
    }
    rdpq_text_print(NULL,1,90,178,"START FOR MATCH OPTIONS");
}
int main(void){
    debug_init_isviewer();debug_init_usblog();
#ifdef BG_BLAM_BSP
    assertf(get_memory_size()>=8*1024*1024,"Original Blam BSP requires an 8 MiB Expansion Pak");
#endif
    display_init(RESOLUTION_320x240,DEPTH_16_BPP,3,GAMMA_NONE,FILTERS_RESAMPLE);
    joypad_init();rdpq_init();
#ifdef RDPQ_VALIDATE
    FILE*original_log=stderr;stderr=funopen(original_log,NULL,validation_write,NULL,NULL);
    assertf(stderr,"Validation log allocation");setvbuf(stderr,NULL,_IONBF,0);
    rdpq_debug_start();
#endif
    t3d_init((T3DInitParams){});
    rdpq_text_register_font(1,rdpq_font_load_builtin(FONT_BUILTIN_DEBUG_VAR));
    surface_t depth=surface_alloc(FMT_RGBA16,320,240);init_scene();bg_hud_init();bg_reset();bg_set_players(views);bg_sound_init();
#ifdef BG_SHOWCASE
    bg_showcase_begin(BG_SHOWCASE);views=bg_showcase_views();
#endif
    heap_stats_t heap;sys_get_heap_stats(&heap);
    debugf("HALO N64 world=%u textures=%u RAM=%d free=%d\n",bg_collision_count,bg_material_count,get_memory_size(),heap.total-heap.used);
    uint64_t previous=get_ticks_us(),fps_time=previous;unsigned frames=0;blam_clock clock;blam_clock_reset(&clock);
    bg_input latch[4]={0};
    while(1){
#ifdef BG_PROFILE
        uint64_t profile_start=get_ticks_us();
#endif
        surface_t*screen;while(!(screen=display_try_get()))bg_sound_pump();
#ifdef BG_PROFILE
        wait_us=get_ticks_us()-profile_start;profile_start=get_ticks_us();
#endif
        uint64_t now=get_ticks_us();float dt=(now-previous)*.000001f;previous=now;
        bg_input in[4]={0};if(input(in))memset(latch,0,sizeof(latch));clock.paused=paused;
        for(unsigned p=0;p<4;p++){
#define EDGE(field) latch[p].field|=in[p].field;in[p].field=latch[p].field
            EDGE(jump);EDGE(reload);EDGE(switch_weapon);EDGE(grenade);EDGE(switch_grenade);EDGE(interact);EDGE(melee);EDGE(zoom);
#undef EDGE
        }
        unsigned ticks=blam_clock_update(&clock,dt);
        for(unsigned t=0;t<ticks;t++){
#ifdef BG_DEMO
            bg_replay_input(in,game_time);views=4;bg_set_players(4);
#endif
#ifdef BG_SHOWCASE
            bg_showcase_input(in,game_time);views=bg_showcase_views();
#endif
            bg_clear_events();bg_tick(in,BLAM_TICK_SECONDS);game_time+=BLAM_TICK_SECONDS;
#ifdef BG_SHOWCASE
            bg_showcase_observe();
#endif
            update_effects(BLAM_TICK_SECONDS);bg_sound_update();
            for(unsigned p=0;p<4;p++){
                if(bg_players[p].vehicle<0)in[p].jump=false;
                in[p].reload=in[p].switch_weapon=in[p].grenade=in[p].switch_grenade=in[p].interact=in[p].melee=in[p].zoom=false;
            }
            memset(latch,0,sizeof(latch));
        }
        bg_sound_pump();
#ifdef BG_PROFILE
        sim_us=get_ticks_us()-profile_start;profile_start=get_ticks_us();
#endif
        if(pending[slot])while(!rspq_syncpoint_check(fences[slot]))bg_sound_pump();
#ifdef BG_PROFILE
        wait_us+=get_ticks_us()-profile_start;profile_start=get_ticks_us();
#endif
        prepare_frame();
#ifdef BG_PROFILE
        prep_us=get_ticks_us()-profile_start;profile_start=get_ticks_us();
#endif
        rdpq_attach(screen,&depth);rdpq_clear_z(ZBUF_MAX);triangles=0;
        for(unsigned p=0;p<views;p++){draw_view(p);bg_sound_pump();}
        rdpq_set_scissor(0,0,320,240);
        if(views>1)fill(0,119,320,2,RGBA32(0,0,0,255));
        if(views==4)fill(159,0,2,240,RGBA32(0,0,0,255));
#ifdef BG_DEMO
        rdpq_set_mode_standard();rdpq_text_printf(NULL,1,116,118,"REPLAY %u FPS",fps);
#endif
#ifdef BG_SHOWCASE
        fill(50,222,220,16,RGBA32(8,19,37,255));rdpq_set_mode_standard();
        rdpq_text_printf(NULL,1,56,233,"SCRIPTED | %s",bg_showcase_title());
        const char*caption=bg_showcase_caption();
        if(caption&&caption[0]){
            fill(50,207,220,14,RGBA32(8,19,37,255));rdpq_set_mode_standard();
            rdpq_text_print(NULL,1,56,218,caption);
        }
#endif
#ifdef BG_PROFILE
        draw_us=get_ticks_us()-profile_start;sys_get_heap_stats(&heap);rdpq_set_mode_standard();
        rdpq_text_printf(NULL,1,2,232,"S%u P%u D%u W%u T%u M%d",sim_us/1000,prep_us/1000,draw_us/1000,wait_us/1000,triangles,(heap.total-heap.used)/1024);
#endif
#ifdef RDPQ_VALIDATE
        rdpq_set_mode_standard();rdpq_text_printf(NULL,1,4,215,"RDP %u ERRORS %u WARNINGS",validation_errors,validation_warnings);
        if(validation_errors||validation_warnings)rdpq_text_print(NULL,1,4,225,validation_message);
#endif
        if(bg_match_finished())draw_result();
        if(paused)draw_menu();
        rdpq_detach_show();fences[slot]=rspq_syncpoint_new();pending[slot]=true;slot=(slot+1)%BG_FRAME_SLOTS;
        frames++;
        if(now-fps_time>=1000000){
            fps=frames*1000000ULL/(now-fps_time);frames=0;fps_time=now;sys_get_heap_stats(&heap);
            debugf("PERF views=%u fps=%u triangles=%u free=%d audio=%d p1=(%.2f %.2f %.2f)\n",views,fps,triangles,heap.total-heap.used,audio_can_write(),
                bg_players[0].pos[0],bg_players[0].pos[1],bg_players[0].pos[2]);
        }
    }
}
