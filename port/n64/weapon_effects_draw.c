#include <libdragon.h>
#include <t3d/t3d.h>
#include <math.h>
#include <string.h>
#include "weapon_effects.h"
#include "weapon_effects_draw.h"
#include "vehicle_visuals.h"
#include "shield_assets.h"
#define FX_QUADS 32
#define FX_SCALE 256.f
/* Separate storage per fenced slot and camera: drawing the next split must
 * never overwrite vertices or matrices still borrowed by the RSP. */
static T3DVertPacked vertices[2][4][FX_QUADS*2] __attribute__((aligned(16)));
static T3DMat4FP matrices[2][4];
static surface_t textures[18];
static float fp_markers[4][2][3],eye_pos[3],right[3],up[3];
static unsigned frame_slot,view,used,bound,limit;
static float pixel_width;
void bg_fx_draw_init(void){
    assertf(bg_fx_texture_count+7<=18,"Effect texture table capacity");
    for(unsigned i=0;i<bg_fx_texture_count;i++)textures[i]=surface_make_linear((void*)bg_fx_textures[i],FMT_RGBA32,16,16);
    for(unsigned i=0;i<5;i++)textures[bg_fx_texture_count+i]=surface_make_linear((void*)bg_vehicle_fx_textures[i],FMT_RGBA32,16,16);
    for(unsigned i=0;i<2;i++)textures[bg_fx_texture_count+5+i]=surface_make_linear((void*)bg_shield_textures[i],FMT_RGBA32,16,16);
}
void bg_fx_pose(unsigned player,unsigned weapon,unsigned clip,unsigned f0,unsigned f1,int fraction){
    const int16_t (*a)[3]=bg_fx_marker_poses[bg_fx_marker_offsets[weapon][clip]+f0];
    const int16_t (*b)[3]=bg_fx_marker_poses[bg_fx_marker_offsets[weapon][clip]+f1];
    for(unsigned m=0;m<2;m++)for(unsigned k=0;k<3;k++)fp_markers[player][m][k]=(a[m][k]+(b[m][k]-a[m][k])*(fraction/256.f))/4096.f;
}
void bg_fx_draw_begin(unsigned slot,unsigned p,const T3DViewport*vp,const T3DVec3*eye){
    frame_slot=slot;view=p;used=0;bound=~0u;limit=FX_QUADS;
    pixel_width=1.f/(vp->size[1]*fabsf(vp->matProj.m[1][1]));
    for(unsigned a=0;a<3;a++){eye_pos[a]=eye->v[a]/BG_SCALE;right[a]=vp->matCamera.m[a][0];up[a]=vp->matCamera.m[a][1];}
    t3d_mat4fp_from_srt_euler(&matrices[slot][p],(float[]){BG_SCALE/FX_SCALE,BG_SCALE/FX_SCALE,BG_SCALE/FX_SCALE},(float[]){0,0,0},eye->v);
    data_cache_hit_writeback(&matrices[slot][p],sizeof(T3DMat4FP));
}
static void mode(void){
    rdpq_sync_pipe();
    t3d_state_set_drawflags(T3D_FLAG_SHADED|T3D_FLAG_TEXTURED|T3D_FLAG_DEPTH);
    rdpq_mode_combiner(RDPQ_COMBINER_TEX_SHADE);rdpq_mode_blender(RDPQ_BLENDER_MULTIPLY);
    rdpq_mode_zbuf(true,false);rdpq_mode_persp(true);rdpq_mode_filter(FILTER_BILINEAR);
    t3d_matrix_set(&matrices[frame_slot][view],true);bound=~0u;
}
static void restore(void){
    rdpq_sync_pipe();
    rdpq_mode_blender(0);rdpq_mode_zbuf(true,true);rdpq_mode_combiner(RDPQ_COMBINER_SHADE);
    t3d_state_set_drawflags(T3D_FLAG_SHADED|T3D_FLAG_DEPTH|T3D_FLAG_CULL_BACK);
}
static bool quad(float points[4][3],unsigned texture,uint32_t color){
    if(used>=limit)return false;
    T3DVertPacked*v=&vertices[frame_slot][view][used*2];
    for(unsigned i=0;i<4;i++)for(unsigned a=0;a<3;a++){
        float value=(points[i][a]-eye_pos[a])*FX_SCALE;
        if(!isfinite(value)||fabsf(value)>32760)return false;
        t3d_vertbuffer_get_pos(v,i)[a]=lrintf(value);
    }
    for(unsigned i=0;i<4;i++){
        *t3d_vertbuffer_get_color(v,i)=color;
        int16_t*uv=t3d_vertbuffer_get_uv(v,i);uv[0]=(i==1||i==2)?15*32:0;uv[1]=i>=2?15*32:0;
    }
    data_cache_hit_writeback(v,2*sizeof(*v));
    if(bound!=texture){rdpq_sync_pipe();rdpq_sync_tile();rdpq_sync_load();rdpq_tex_upload(TILE0,&textures[texture],NULL);bound=texture;}
    t3d_vert_load(v,0,4);t3d_tri_draw(0,1,2);t3d_tri_draw(0,2,3);t3d_tri_sync();used++;return true;
}
static void sprite(const float center[3],float rx,float ry,unsigned texture,uint32_t color,float angle){
    float c=cosf(angle),s=sinf(angle),points[4][3];
    for(unsigned i=0;i<4;i++)for(unsigned a=0;a<3;a++){
        float x=(i==1||i==2)?rx:-rx,y=i>=2?-ry:ry;
        points[i][a]=center[a]+right[a]*(x*c-y*s)+up[a]*(x*s+y*c);
    }
    quad(points,texture,color);
}
static uint32_t tint(const uint8_t c[3],float alpha){return (uint32_t)c[0]<<24|(uint32_t)c[1]<<16|(uint32_t)c[2]<<8|(unsigned)(fmaxf(0,fminf(1,alpha))*255);}
static void transform(float out[3],const T3DMat4FP*matrix,const float point[3],float units){
    for(unsigned a=0;a<3;a++){
        out[a]=t3d_mat4fp_get_float(matrix,3,a);
        for(unsigned b=0;b<3;b++)out[a]+=t3d_mat4fp_get_float(matrix,b,a)*point[b]*units;
        out[a]/=BG_SCALE;
    }
}
unsigned bg_fx_draw_weapon(unsigned player,const T3DMat4FP*matrix,float units,bool firstperson,float time){
    float flash=bg_fx_flash(player),charge=bg_fx_charge(player);if(flash<=0&&charge<=0)return 0;
    unsigned before=used,w=bg_players[player].weapon;const bg_fx_definition*d=&bg_fx_definitions[w];
    float points[2][3];
    for(unsigned m=0;m<2;m++)transform(points[m],matrix,firstperson?fp_markers[player][m]:bg_fx_world_markers[w][m],units);
    mode();if(!firstperson)limit=FX_QUADS-4;
    if(flash>0){
        unsigned marker=w==BG_W_PLASMA_RIFLE?(bg_fx_shots[player].sequence&1):0;
        float radius=d->radius*(.65f+.35f*flash),alpha=fminf(1,flash*3);
        if(bg_fx_shots[player].charged){radius*=1.6f;alpha=1;}
        sprite(points[marker],radius,radius,d->texture,tint(d->color,alpha),bg_fx_shots[player].sequence*2.4f);
    }
    if(charge>0){
        float pulse=.94f+.06f*sinf(time*33+player),r=(.015f+.12f*charge)*pulse;
        /* Original overcharge corona with a tapering rising lobe. The base
         * follows the animated secondary marker, never a fixed HUD coordinate. */
        uint8_t green[3]={105,255,42},core[3]={215,255,145};
        sprite(points[1],r,r*1.15f,bg_fx_glow_texture,tint(green,.45f+.45f*charge),time*1.7f);
        float tip[3];for(unsigned a=0;a<3;a++)tip[a]=points[1][a]+up[a]*r*.85f;
        sprite(tip,r*.44f,r*1.25f,bg_fx_charge_texture,tint(green,.55f*charge),sinf(time*13)*.15f);
        sprite(points[1],r*.34f,r*.5f,bg_fx_charge_texture,tint(core,.8f),0);
    }
    limit=FX_QUADS;restore();return (used-before)*2;
}
unsigned bg_fx_draw_blasts(void){
    unsigned before=used,order[BG_FX_BLASTS],count=0;float keys[BG_FX_BLASTS];
    /* Keep transparent overdraw bounded even when twelve blasts coexist.
     * Nearby/new bursts get priority; every visible stage uses <=4 quads. */
    for(unsigned i=0;i<BG_FX_BLASTS;i++){
        const bg_fx_blast*b=&bg_fx_blasts[i];
        if(b->age>=bg_fx_blast_definitions[b->kind].life)continue;
        float d2=0;for(unsigned a=0;a<3;a++){float d=b->origin[a]-eye_pos[a];d2+=d*d;}
        if(d2>60*60)continue;
        float key=d2*(b->age<.18f?.5f:1.f);unsigned j=count++;
        while(j&&keys[j-1]>key){keys[j]=keys[j-1];order[j]=order[j-1];j--;}
        keys[j]=key;order[j]=i;
    }
    if(!count)return 0;
    mode();limit=before+12<FX_QUADS-4?before+12:FX_QUADS-4;
    for(unsigned n=0;n<count&&used<limit;n++){
        const bg_fx_blast*b=&bg_fx_blasts[order[n]];const bg_fx_blast_definition*d=&bg_fx_blast_definitions[b->kind];
        float t=b->age,phase=t/d->life,size=b->radius;bool energy=b->kind!=BG_EXPLOSION_NORMAL;
        unsigned firetex=energy?bg_fx_energy_texture:bg_fx_texture_count+BG_VFX_FIRE;
        unsigned smoketex=energy?bg_fx_energy_texture:bg_fx_texture_count+BG_VFX_SMOKE;
        float fire=fmaxf(0,1-t/d->fire_life),smoke=fminf(1,t/.25f)*(1-phase);
        float center[3]={b->origin[0],b->origin[1]+size*.15f,b->origin[2]};
        /* Source fire -> widening, rising smoke. Two lobes replace 10–35
         * emitted particles, with deterministic motion and no gameplay RNG. */
        if(t<d->fire_life){
            float r=size*(.28f+.55f*fminf(1,t/.18f));
            sprite(center,r,r,firetex,tint(d->colors[0],fminf(1,fire*2)*d->alpha[0]),t*3);
            if(t<.13f)sprite(center,r*.8f,r*.8f,bg_fx_glow_texture,tint((uint8_t[]){242,247,224},1-t/.13f),0);
            else {
                float lobe[3];for(unsigned a=0;a<3;a++)lobe[a]=center[a]+right[a]*r*.45f;
                lobe[1]+=r*.3f;
                sprite(lobe,r*.65f,r*.8f,firetex,tint(d->colors[0],fire*.8f),-t*4+1);
            }
        }
        if(t>.10f){
            unsigned lobes=keys[n]>25*25?1:2;
            for(unsigned j=0;j<lobes;j++){
                float r=size*(.28f+phase*.65f),point[3];
                for(unsigned a=0;a<3;a++)point[a]=center[a]+right[a]*(j?1:-1)*size*(.16f+phase*.24f);
                point[1]+=size*(t*.45f+j*.15f);point[0]+=t*.12f;
                sprite(point,r,r*(energy?1.25f:1.f),smoketex,tint(d->colors[1],smoke*d->alpha[1]),j+t*.5f);
            }
        }
    }
    limit=FX_QUADS;restore();return (used-before)*2;
}

unsigned bg_fx_draw_trails(float time){
    (void)time;unsigned before=used;bool drawing=false;
    for(unsigned t=0;t<BG_FX_TRAILS;t++){
        const bg_fx_trail*trail=&bg_fx_trails[t];if(!trail->active)continue;
        if(!drawing){mode();drawing=true;}
        float phase=trail->age/BG_FX_TRAIL_LIFE,width=.0125f+.03125f*phase;
        uint8_t color[3];for(unsigned a=0;a<3;a++)color[a]=trail->age<.15f?(uint8_t[]){242,217,151}[a]:196;
        /* Four camera-facing ribbon segments approximate the original warm
         * streak -> widening gray smoke -> fade, along the actual hitscan. */
        for(unsigned s=0;s<4;s++){
            float a[3],b[3],side[3],axis[3],toward[3],points[4][3];
            for(unsigned k=0;k<3;k++){
                a[k]=trail->muzzle[k]+(trail->end[k]-trail->muzzle[k])*(s/4.f);
                b[k]=trail->muzzle[k]+(trail->end[k]-trail->muzzle[k])*((s+1)/4.f);
                axis[k]=b[k]-a[k];toward[k]=eye_pos[k]-(a[k]+b[k])*.5f;
            }
            a[1]+=phase*.08f;b[1]+=phase*.08f;
            side[0]=axis[1]*toward[2]-axis[2]*toward[1];side[1]=axis[2]*toward[0]-axis[0]*toward[2];side[2]=axis[0]*toward[1]-axis[1]*toward[0];
            float length=sqrtf(side[0]*side[0]+side[1]*side[1]+side[2]*side[2]);
            /* Preserve a one-pixel ribbon footprint in a 160x120 split. */
            float radius=fmaxf(width,fminf(.18f,pixel_width*sqrtf(toward[0]*toward[0]+toward[1]*toward[1]+toward[2]*toward[2])));
            for(unsigned k=0;k<3;k++){
                side[k]=length>1e-6f?side[k]*radius/length:right[k]*radius;
                points[0][k]=a[k]-side[k];points[1][k]=b[k]-side[k];points[2][k]=b[k]+side[k];points[3][k]=a[k]+side[k];
            }
            quad(points,bg_fx_trail_texture,tint(color,(1-phase)*.85f));
        }
    }
    if(drawing)restore();
    return (used-before)*2;
}
unsigned bg_fx_draw_vehicle_destruction(void){
    unsigned before=used;bool drawing=false;limit=FX_QUADS-4;/* Reserve first-person feedback. */
    for(unsigned i=0;i<4&&used<limit;i++){
        const bg_fx_vehicle_burst*b=&bg_fx_vehicle_bursts[i];float t=b->age;
        if(t>=8||b->vehicle<0||b->vehicle>=(int)bg_vehicle_count)continue;
        const bg_vehicle*v=&bg_vehicles[b->vehicle];if(v->active||v->wreck_time<=0)continue;
        float distance=0;for(unsigned a=0;a<3;a++){float d=v->pos[a]-eye_pos[a];distance+=d*d;}
        if(distance>60*60)continue;
        if(!drawing){mode();drawing=true;}
        float size=b->kind==BG_V_SCORPION?1.4f:b->kind==BG_V_GHOST?.8f:1.f;
        unsigned base=bg_fx_texture_count;float center[3];memcpy(center,b->origin,sizeof(center));center[1]+=.3f;
        /* The source shared Covenant death effect uses warm fire, gray smoke,
         * blue metal panels and sustained flame/sparks (not a green orb). */
        if(t<1.1f){
            float radius=size*(.6f+1.5f*t),alpha=fminf(1,(1.1f-t)*2);
            sprite(center,radius,radius,base+BG_VFX_FIRE,tint((uint8_t[]){255,221,140},alpha),t*3);
            for(unsigned j=0;j<2;j++){
                float lobe[3]={center[0]+(j?1:-1)*radius*.45f,center[1]+radius*.4f,center[2]+(j?-.3f:.3f)*radius};
                sprite(lobe,radius*.65f,radius*.75f,base+BG_VFX_FIRE,tint((uint8_t[]){255,181,104},alpha*.85f),t*-4+j);
            }
            if(t<.2f)sprite(center,size*1.2f,size*1.2f,bg_fx_glow_texture,tint((uint8_t[]){255,249,220},1-t/.2f),0);
        }
        if(t<1.65f){
            for(unsigned j=0;j<3;j++){
                float angle=j*2.094395f+i*.7f,point[3]={center[0]+cosf(angle)*t*2.5f,center[1]+t*(2.4f+j*.4f)-2.5f*t*t,center[2]+sinf(angle)*t*2.5f};
                float r=.11f*size;bool alien=b->kind==BG_V_GHOST||b->kind==BG_V_BANSHEE;
                sprite(point,r,r*.7f,base+BG_VFX_PANEL,tint(alien?(uint8_t[]){66,80,112}:(uint8_t[]){90,80,61},fminf(1,(1.65f-t)*3)),t*(j%2?-8:11));
            }
        }
        memcpy(center,v->pos,sizeof(center));center[1]+=.25f;
        if(t<3){
            float pulse=.85f+.15f*sinf(t*21+i),r=size*(.3f+.1f*pulse);
            sprite(center,r,r*1.7f,base+BG_VFX_FLAME,tint((uint8_t[]){255,207,130},fminf(1,3-t)),sinf(t*7)*.1f);
            float spark[3]={center[0]+.2f*sinf(t*8),center[1]+fmodf(t*2,1.1f),center[2]};
            sprite(spark,.045f,.17f,base+BG_VFX_SPARK,tint((uint8_t[]){255,226,167},fminf(1,3-t)),.2f);
        }
        /* Two analytically advected puffs replace dozens of source particles. */
        for(unsigned j=0;j<2;j++){
            float phase=fmodf(t+j*1.2f,2.4f),alpha=fminf(1,phase*4)*(1-phase/2.4f)*fminf(1,8-t)*.65f;
            float point[3]={center[0]+phase*.15f,center[1]+phase*.8f,center[2]+j*.18f};
            float r=size*(.3f+phase*.28f);
            sprite(point,r,r,base+BG_VFX_SMOKE,tint((uint8_t[]){67,65,63},alpha),phase*.3f+j);
        }
    }
    limit=FX_QUADS;if(drawing)restore();
    return (used-before)*2;
}

unsigned bg_fx_draw_shield_breaks(unsigned viewer){
    (void)viewer;unsigned before=used;bool drawing=false;limit=FX_QUADS-4;
    /* Sharing the existing 32-quad budget bounds every viewport's work.
     * Two short depletion clouds, then four outward falling gold sparks. */
    for(unsigned p=0;p<bg_player_count();p++){
        const bg_player*q=&bg_players[p];
        if(q->shield_break<=0)continue;
#ifndef BG_SHIELD_QA
        if(p==viewer&&!bg_player_third_person(q))continue;
#endif
        float age=2.25f-q->shield_break;
        float center[3]={q->shield_break_pos[0],q->shield_break_pos[1]+.4f,q->shield_break_pos[2]};
        if(!drawing){mode();drawing=true;}
        uint8_t gold[3]={255,213,85};
        if(age<.3f)for(unsigned k=0;k<2;k++){
            float toward[3],length=0;for(unsigned a=0;a<3;a++){toward[a]=eye_pos[a]-center[a];length+=toward[a]*toward[a];}
            length=sqrtf(length);float at[3];
            /* Billboards sit on the near side of the shield envelope; keeping
             * their centers inside the opaque torso would hide the flash. */
            for(unsigned a=0;a<3;a++)at[a]=center[a]+toward[a]*(.18f/fmaxf(.01f,length))+right[a]*(k?.12f:-.12f);
            at[1]+=k*.18f;
            float r=.3f*(1+age*5);
            sprite(at,r,r,bg_fx_texture_count+5,tint(gold,fminf(1,(.3f-age)*5)),p+k*1.7f);
        }
        for(unsigned k=0;k<4;k++){
            float angle=k*1.5707963f+p,at[3]={center[0]+cosf(angle)*(.18f+age*.25f),center[1]+.15f+age*.22f-age*age*.17f,center[2]+sinf(angle)*(.18f+age*.25f)};
            sprite(at,.024f,.07f,bg_fx_texture_count+6,tint(gold,fminf(1,q->shield_break)),angle+age);
        }
    }
    limit=FX_QUADS;if(drawing)restore();
    return (used-before)*2;
}
