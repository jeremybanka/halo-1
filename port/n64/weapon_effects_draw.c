#include <libdragon.h>
#include <t3d/t3d.h>
#include <math.h>
#include <string.h>
#include "weapon_effects.h"
#include "weapon_effects_draw.h"
#define FX_QUADS 32
#define FX_SCALE 256.f
/* Separate storage per fenced slot and camera: drawing the next split must
 * never overwrite vertices or matrices still borrowed by the RSP. */
static T3DVertPacked vertices[2][4][FX_QUADS*2] __attribute__((aligned(16)));
static T3DMat4FP matrices[2][4];
static surface_t textures[16];
static float fp_markers[4][2][3],eye_pos[3],right[3],up[3];
static unsigned frame_slot,view,used,bound;
static float pixel_width;
void bg_fx_draw_init(void){
    assertf(bg_fx_texture_count<=16,"Effect texture table capacity");
    for(unsigned i=0;i<bg_fx_texture_count;i++)textures[i]=surface_make_linear((void*)bg_fx_textures[i],FMT_RGBA32,16,16);
}
void bg_fx_pose(unsigned player,unsigned weapon,unsigned clip,unsigned f0,unsigned f1,int fraction){
    const int16_t (*a)[3]=bg_fx_marker_poses[bg_fx_marker_offsets[weapon][clip]+f0];
    const int16_t (*b)[3]=bg_fx_marker_poses[bg_fx_marker_offsets[weapon][clip]+f1];
    for(unsigned m=0;m<2;m++)for(unsigned k=0;k<3;k++)fp_markers[player][m][k]=(a[m][k]+(b[m][k]-a[m][k])*(fraction/256.f))/4096.f;
}
void bg_fx_draw_begin(unsigned slot,unsigned p,const T3DViewport*vp,const T3DVec3*eye){
    frame_slot=slot;view=p;used=0;bound=~0u;
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
    if(used==FX_QUADS)return false;
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
    mode();
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
    restore();return (used-before)*2;
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
