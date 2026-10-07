#include "hud.h"
#include "asset_hud.h"
#include "game.h"
#include <libdragon.h>
#include <math.h>

/* Xbox bitmaps retain their silhouette, glyphs and weapon-specific reticles.
 * Rendering scales the original art to the N64 viewport, without new borders
 * or player labels across the view. Font1 is used only for status messages. */
static surface_t images[BG_H_COUNT];
static surface_t scope_images[BG_SCOPE_COUNT];
/* The source digits use a one-bit alpha silhouette. An IA4 atlas preserves
 * that silhouette in 800 bytes and lets every HUD number share one upload. */
static uint8_t digit_pixels[16*100/2] __attribute__((aligned(16)));
static surface_t digit_atlas;
typedef struct { unsigned value; int places; float x,y,scale; bool warning; } hud_number;
static hud_number numbers[8];
static unsigned number_count;
static int current_combiner,current_filter;
/* Static sprite geometry/texture uploads do not depend on health, ammo or
 * tint. Replaying these RDP blocks avoids repeating the large-sprite tiler
 * on the CPU in every viewport. Blocks live for the whole match session. */
typedef struct { unsigned id; float x,y,scale; rspq_block_t *block; } hud_blit;
static hud_blit blits[192];
static unsigned blit_count;
/* Slot+1 links keep zero-initialized empty lists and the original append order.
 * Match coordinates only against this image's entries, not every HUD sprite.
 * The recorded blocks and their lifetime remain unchanged. */
static uint16_t blit_heads[BG_H_COUNT],blit_next[192];
enum { HUD_EXIT, HUD_PICKUP, HUD_ENTER, HUD_RELOAD, HUD_OVERHEAT,
       HUD_RESPAWN_0, HUD_RESPAWN_1, HUD_RESPAWN_2, HUD_RESPAWN_3,
       HUD_XBOX_EXIT, HUD_XBOX_PICKUP, HUD_XBOX_ENTER, HUD_FLIP, HUD_XBOX_FLIP, HUD_STATUS_COUNT };
static const char *const status_strings[HUD_STATUS_COUNT]={
    "B EXIT","B PICK UP","B ENTER","Reloading","Overheated",
    "Respawn in 0","Respawn in 1","Respawn in 2","Respawn in 3",
    "C-LEFT EXIT","C-LEFT PICK UP","C-LEFT ENTER","B FLIP","C-LEFT FLIP"};
/* These labels have fixed font, width and alignment. Lay them out once instead
 * of allocating and formatting the same paragraph in each player view. */
static rdpq_paragraph_t *status_layouts[2][HUD_STATUS_COUNT];
static const color_t blue = {105,166,236,255};
static const color_t bright = {149,207,255,255};
static const color_t red = {248,63,58,255};
static const color_t muted = {41,70,106,255};
static const unsigned reticles[BG_WEAPON_COUNT] = {
    BG_H_RETICLE_AR, BG_H_RETICLE_PISTOL, BG_H_RETICLE_PLASMA_PISTOL,
    BG_H_RETICLE_PLASMA_RIFLE, BG_H_RETICLE_NEEDLER, BG_H_RETICLE_SHOTGUN,
    BG_H_RETICLE_SNIPER, BG_H_RETICLE_ROCKET, BG_H_RETICLE_AR
};
static const unsigned magazines[BG_WEAPON_COUNT] = {
    BG_H_AMMO_AR, BG_H_AMMO_PISTOL, BG_H_AMMO_AR, BG_H_AMMO_AR,
    BG_H_AMMO_NEEDLER, BG_H_AMMO_SHOTGUN, BG_H_AMMO_SNIPER,
    BG_H_AMMO_ROCKET, BG_H_AMMO_AR
};
static const int vehicle_reticles[BG_VEHICLE_COUNT] = {
    BG_H_RETICLE_WARTHOG, BG_H_RETICLE_GHOST, BG_H_RETICLE_SCORPION, BG_H_RETICLE_BANSHEE
};

static int control_status(int status,bg_control_style style) {
    if(style==BG_CONTROLS_XBOX&&status>=HUD_EXIT&&status<=HUD_ENTER)
        return HUD_XBOX_EXIT+status-HUD_EXIT;
    if(style==BG_CONTROLS_XBOX&&status==HUD_FLIP)return HUD_XBOX_FLIP;
    return status;
}

static void set_combiner(int kind) {
    if (current_combiner==kind) return;
    rdpq_mode_combiner(kind==0?RDPQ_COMBINER_TEX_FLAT:kind==1?
        RDPQ_COMBINER1((0,0,0,PRIM),(TEX0,0,PRIM,0)):RDPQ_COMBINER_FLAT);
    current_combiner=kind;
}

static void set_filter(bool point) {
    if (current_filter==(int)point) return;
    rdpq_mode_filter(point?FILTER_POINT:FILTER_BILINEAR);
    current_filter=point;
}

static void mode(color_t tint) {
    set_filter(false);
    /* The asset pack already applies the Xbox tag's colors. Normal sprites
     * pass through unmodified; depleted meters dim them, warning states use
     * their original alpha silhouette with a red/overcharge color. */
    bool normal=(tint.r==blue.r && tint.g==blue.g) || (tint.r==bright.r && tint.g==bright.g);
    bool dim=tint.r==muted.r && tint.g==muted.g;
    if (normal) tint=RGBA32(255,255,255,tint.a);
    else if (dim) tint=RGBA32(70,70,70,tint.a);
    set_combiner(normal || dim ? 0:1);
    rdpq_set_prim_color(tint);
}

static void blit_picture(unsigned id,float x,float y,float scale) {
    const bg_hud_image *im=&bg_hud_images[id];
    x+=im->x*scale;y+=im->y*scale;
    /* Moving radar blips are deliberately uncached: their positions can fill
     * an unbounded number of entries. Full caches fall back to ordinary blits. */
    if (id!=BG_H_BLIP) {
        uint16_t *link=&blit_heads[id];
        while (*link) {
            unsigned i=*link-1;
            const hud_blit *b=&blits[i];
            if(b->x==x&&b->y==y&&b->scale==scale) {
                rspq_block_run(b->block);return;
            }
            link=&blit_next[i];
        }
        if(blit_count<sizeof(blits)/sizeof(blits[0])) {
            unsigned i=blit_count++;
            hud_blit *b=&blits[i];
            *b=(hud_blit){.id=id,.x=x,.y=y,.scale=scale};
            rspq_block_begin();
            rdpq_tex_blit(&images[id],x,y,&(rdpq_blitparms_t){
                .scale_x=scale,.scale_y=scale,.filtering=true});
            b->block=rspq_block_end();
            blit_next[i]=0;*link=i+1;
            rspq_block_run(b->block);return;
        }
    }
    rdpq_tex_blit(&images[id],x,y,&(rdpq_blitparms_t){
        .scale_x=scale,.scale_y=scale,.filtering=true});
}

static void picture(unsigned id, float x, float y, float scale, color_t tint) {
    if (bg_hud_images[id].w<=1 || bg_hud_images[id].h<=1) return;
    mode(tint);blit_picture(id,x,y,scale);
}

static void meter(unsigned id, float x, float y, float scale, float amount, color_t tint) {
    amount=fminf(fmaxf(amount,0.f),1.f);
    picture(id,x,y,scale,muted);
    if (amount<=0.f) return;
    const bg_hud_image *im=&bg_hud_images[id];
    int width=(int)ceilf(im->w*amount)-im->x;
    if(width<=0)return;
    mode(tint);
    if(width>=im->tex_w) { blit_picture(id,x,y,scale);return; }
    rdpq_tex_blit(&images[id],x+im->x*scale,y+im->y*scale,&(rdpq_blitparms_t){
        .width=width,.scale_x=scale,.scale_y=scale,.filtering=true});
}

static void number(unsigned value, int places, float x, float y, float scale, color_t tint) {
    /* The Xbox18x12 digit cell has only an11x10 ink region. Scaling all its
     * transparent padding down made the four-player digits about4px high.
     * Preserve the original glyph but keep its ink at least6.5px high and
     * sample sharply, with a one-pixel navy shadow for sky/terrain contrast. */
    if (number_count<sizeof(numbers)/sizeof(numbers[0]))
        numbers[number_count++]=(hud_number){value,places,x,y,fmaxf(scale*1.6f,.65f),tint.r==red.r};
}

static void draw_numbers(void) {
    set_filter(true);set_combiner(1);
    rdpq_tex_upload(TILE0,&digit_atlas,NULL);
    /* All shadows, then all foregrounds: only one texture load per viewport,
     * and two color changes for a HUD without warning digits. */
    for (int shadow=1;shadow>=0;shadow--) {
        int last_color=-1;
        for (unsigned n=0;n<number_count;n++) {
            const hud_number *num=&numbers[n];
            int color=shadow?2:num->warning;
            if (color!=last_color) {
                rdpq_set_prim_color(shadow?RGBA32(3,10,25,200):
                    num->warning?red:RGBA32(137,209,255,255));
                last_color=color;
            }
            unsigned divisor=1;
            for (int i=1;i<num->places;i++) divisor*=10;
            float gx=num->x;
            for (int i=0;i<num->places;i++) {
                unsigned digit=(num->value/divisor)%10;
                float px=roundf(gx)+shadow,py=roundf(num->y)+shadow;
                rdpq_texture_rectangle_scaled(TILE0,px,py,px+11*num->scale,py+10*num->scale,
                    0,digit*10,11,digit*10+10);
                gx+=12*num->scale;divisor/=10;
            }
        }
    }
}

static void pixel(int x,int y,int w,int h,color_t c) {
    set_combiner(2);rdpq_set_prim_color(c);
    rdpq_fill_rectangle(x,y,x+w,y+h);
}

static void radar(unsigned p, int x, int y, float scale) {
    float size=bg_hud_images[BG_H_MOTION_BG].w*scale;
    /* cyborg_mp tag colors: background0x28061428, foreground0xa06986a0.
     * The circle's texture is solid white; its original low opacity and dark
     * color belong to the HUD tag, not the bitmap's one-bit alpha channel. */
    picture(BG_H_MOTION_BG,x,y,scale,RGBA32(6,20,40,40));
    picture(BG_H_MOTION_FG,x,y,scale,RGBA32(blue.r,blue.g,blue.b,160));
    float cx=x+size*.5f,cy=y+size*.5f,radius=size*.41f;
    bg_player *viewer=&bg_players[p];
    const float range=8.333333f; /* Xbox motion sensor25m; Halo world unit=3m. */
    float sn=sinf(viewer->yaw),cs=cosf(viewer->yaw);
    for (unsigned j=0;j<bg_player_count();j++) {
        bg_player *other=&bg_players[j];
        if (j==p || other->health<=0 || other->crouched) continue;
        float speed=other->velocity[0]*other->velocity[0]+other->velocity[2]*other->velocity[2];
        if (speed<.01f && other->flash<=0.f && other->vehicle<0) continue;
        float dx=other->pos[0]-viewer->pos[0],dz=other->pos[2]-viewer->pos[2];
        if (dx*dx+dz*dz>range*range) continue;
        int bx=(int)roundf(cx+(dx*sn+dz*cs)*radius/range);
        int by=(int)roundf(cy-(dx*cs-dz*sn)*radius/range);
        picture(BG_H_BLIP,bx-2,by-2,.125f,red);
    }
    pixel((int)cx,(int)cy-1,1,3,bright);
    pixel((int)cx-1,(int)cy+1,3,1,bright);
}

static float distance_squared(const float a[3],const float b[3]) {
    float x=a[0]-b[0],y=a[1]-b[1],z=a[2]-b[2];
    return x*x+y*y+z*z;
}

static int interaction(const bg_player *p) {
    if (p->interact_cooldown>0) return -1;
    if (p->vehicle>=0) return HUD_EXIT;
    /* Match game.c interaction ranges and pickup priority, so the prompt
     * names an action that pressing B can actually perform. */
    for (unsigned i=0;i<bg_pickup_count;i++)
        if (bg_pickups[i].active&&distance_squared(p->pos,bg_pickups[i].pos)<.85f*.85f)
            return HUD_PICKUP;
    for (unsigned i=0;i<bg_vehicle_count;i++) {
        const bg_vehicle *v=&bg_vehicles[i];
        if (!v->active||distance_squared(p->pos,v->pos)>=4.f) continue;
        if(v->physics_valid&&v->up[1]<.2f)return HUD_FLIP;
        int seats=v->kind==BG_V_WARTHOG||v->kind==BG_V_SCORPION?3:1;
        for (int s=0;s<seats;s++) if (v->occupants[s]<0) return HUD_ENTER;
    }
    return -1;
}

static bool scoped(const bg_player *p) {
    return p->health>0&&p->vehicle<0&&p->zoom>0&&
        (p->weapon==BG_W_PISTOL||p->weapon==BG_W_SNIPER);
}

static void scope_mask(const bg_player *p,int x,int y,int width,int height,float cx,float cy) {
    unsigned id=p->weapon==BG_W_PISTOL?BG_SCOPE_PISTOL:BG_SCOPE_SNIPER;
    /* Original AY8 mask: zero leaves the scope clear, the outer field is
     * half intensity and the border is full intensity. N64 uses that channel
     * as darkening opacity; Xbox convolution and night vision are not used. */
    float left=cx-width*.5f,top=cy-height*.5f;
    /* Moving the source mask with its aim center exposes a narrow outer
     * strip. Extend its constant source edge alpha, without darkening the
     * interior twice. Source mask corners are 132 (pistol), 128 (sniper). */
    color_t edge=RGBA32(0,0,0,bg_scope_images[id].pixels[0]);
    if(top>y)pixel(x,y,width,top-y,edge);
    if(top+height<y+height)pixel(x,top+height,width,y-top,edge);
    float inner_top=fmaxf(y,top),inner_bottom=fminf(y+height,top+height);
    if(left>x)pixel(x,inner_top,left-x,inner_bottom-inner_top,edge);
    if(left+width<x+width)pixel(left+width,inner_top,x-left,inner_bottom-inner_top,edge);
    mode(RGBA32(0,0,0,255));
    rdpq_tex_blit(&scope_images[id],left,top,&(rdpq_blitparms_t){
        .scale_x=(float)width/bg_scope_images[id].w,
        .scale_y=(float)height/bg_scope_images[id].h,.filtering=true});
}

static void scope_marks(const bg_player *p,float cx,float cy,int height) {
    bool split=height<240;
    if (p->weapon==BG_W_SNIPER) {
        /* cyborg multiplayer weapon HUD offsets, centered as hud_draw_bitmap
         * does. The bitmap size is exempt from multiplayer half scaling; its
         * offset is not. Source artwork was reduced by two in the packer. */
        static const int offsets[5][2]={{-101,18},{115,18},{-33,0},{33,0},{0,42}};
        float size=split?1.f:2.f,offset=split?.25f:.5f;
        mode(RGBA32(0,0,0,120));
        for (unsigned i=0;i<5;i++) {
            unsigned id=BG_SCOPE_TICK_0+i;
            const bg_scope_image *im=&bg_scope_images[id];
            rdpq_tex_blit(&scope_images[id],cx+offsets[i][0]*offset-im->w*size*.5f,
                cy+offsets[i][1]*offset-im->h*size*.5f,
                &(rdpq_blitparms_t){.scale_x=size,.scale_y=size,.filtering=true});
        }
    }
    unsigned id=p->weapon==BG_W_SNIPER&&p->zoom==2?BG_H_ZOOM_10X:BG_H_ZOOM_2X;
    const bg_hud_image *im=&bg_hud_images[id];
    float ox=p->weapon==BG_W_PISTOL?(split?33.5f:52.5f):(split?23.75f:75.f);
    float oy=p->weapon==BG_W_PISTOL?(split?33.5f:52.5f):(split?15.f:52.f);
    picture(id,cx+ox-im->w*.25f,cy+oy-im->h*.25f,.5f,bright);
}

void bg_hud_init(void) {
    for (unsigned i=0;i<BG_H_COUNT;i++) {
        const bg_hud_image *im=&bg_hud_images[i];
        images[i]=surface_make((void *)im->pixels,FMT_RGBA16,im->tex_w,im->tex_h,im->tex_w*2);
        data_cache_hit_writeback((void *)im->pixels,im->tex_w*im->tex_h*2);
    }
    for (unsigned i=0;i<BG_SCOPE_COUNT;i++) {
        const bg_scope_image *im=&bg_scope_images[i];
        scope_images[i]=surface_make((void *)im->pixels,FMT_I8,im->w,im->h,im->stride);
        data_cache_hit_writeback((void *)im->pixels,im->stride*im->h);
    }
    for (unsigned d=0;d<10;d++) {
        const bg_hud_image *im=&bg_hud_images[BG_H_DIGIT_0+d];
        for (unsigned y=0;y<10;y++) for (unsigned x=0;x<11;x++) {
            unsigned pixel=(d*10+y)*16+x;
            if (im->pixels[(y+1)*im->w+x+4]&1)
                digit_pixels[pixel/2]|=x&1?0x0f:0xf0;
        }
    }
    digit_atlas=surface_make(digit_pixels,FMT_IA4,16,100,8);
    data_cache_hit_writeback(digit_pixels,sizeof(digit_pixels));
    rdpq_font_t *font=(rdpq_font_t *)rdpq_text_get_font(1);
    rdpq_font_style(font,7,&(rdpq_fontstyle_t){.color=bright});
    rdpq_font_style(font,8,&(rdpq_fontstyle_t){.color=red});
    for(unsigned split=0;split<2;split++)for(unsigned i=0;i<HUD_STATUS_COUNT;i++) {
        const rdpq_textparms_t text={.style_id=7,.width=split?150:302,.align=ALIGN_CENTER};
        int length=(int)strlen(status_strings[i]);
        status_layouts[split][i]=rdpq_paragraph_build(&text,1,status_strings[i],&length);
    }
}

void bg_hud_draw(unsigned index,int x,int y,int width,int height,bg_control_style style) {
    const bg_player *p=&bg_players[index];
    float scale=width<200?.45f:.5f;
    int margin=width<200?5:9;
    unsigned weapon=(unsigned)p->weapon<BG_WEAPON_COUNT?(unsigned)p->weapon:BG_W_AR;
    const bg_vehicle *vehicle=p->vehicle>=0&&(unsigned)p->vehicle<bg_vehicle_count?
        &bg_vehicles[p->vehicle]:NULL;
    bool personal=!vehicle || p->seat==2 || (p->seat==1&&vehicle->kind==BG_V_SCORPION);
    float aim_x,aim_y;
    unsigned views=height>=240?1:width<200?4:2;
    bg_hud_aim_point(views,index,x,y,width,height,&aim_x,&aim_y);
    number_count=0;current_combiner=current_filter=-1;
    rdpq_mode_begin();
    rdpq_set_mode_standard();
    rdpq_mode_zbuf(false,false);rdpq_mode_persp(false);rdpq_mode_tlut(TLUT_NONE);
    rdpq_mode_blender(RDPQ_BLENDER_MULTIPLY);
    rdpq_mode_end();
    rdpq_set_scissor(x,y,x+width,y+height);
    if (scoped(p)) scope_mask(p,x,y,width,height,aim_x,aim_y);

    /* Shields and segmented health retain the sloped Xbox backgrounds. */
    /* cyborg_mp tag anchors: background(-7,1), meter(0,0), health(29,11). */
    float shield_x=x+width-margin-bg_hud_images[BG_H_SHIELD_METER].w*scale;
    float shield_y=y+margin;
    picture(BG_H_SHIELD_BG,shield_x-7*scale,shield_y+scale,scale,blue);
    color_t shield=p->shield<=0?red:p->shield>100?RGBA32(248,221,104,255):bright;
    meter(BG_H_SHIELD_METER,shield_x,shield_y,scale,p->shield/100.f,shield);
    meter(BG_H_HEALTH_METER,shield_x+29*scale,shield_y+11*scale,scale,
        p->health/100.f,p->health<=33?red:p->health<=67?RGBA32(255,217,65,255):bright);

    /* Original slanted digits, with ink sized for the N64 display. */
    if (personal) {
    float ammo_x=x+margin,ammo_y=y+margin;
    picture(BG_H_AMMO_BG,ammo_x,ammo_y,scale,blue);
    unsigned ammo=(unsigned)(p->ammo<0?0:p->ammo);
    number(ammo,3,ammo_x+3*scale,ammo_y+2*scale,scale,p->overheated?red:bright);
    float ammo_meter_y=ammo_y+17*scale+3;
    const bg_weapon_def *def=&bg_weapon_defs[weapon];
    float fraction=def->energy?1.f-p->heat:(float)p->ammo/fmaxf(def->magazine,1);
    meter(magazines[weapon],ammo_x,ammo_meter_y,scale,fraction,p->overheated?red:blue);
    if (!def->energy) number((unsigned)(p->reserve<0?0:p->reserve),3,ammo_x,ammo_meter_y+bg_hud_images[magazines[weapon]].h*scale+2,scale*.8f,blue);
    /* The frag/plasma outlines are the original grenade-HUD sprites. */
    float grenade_x=ammo_x+59*scale,grenade_y=ammo_y+2*scale;
    picture(BG_H_GRENADE_FRAG,grenade_x,grenade_y,scale,p->grenade_kind==0?bright:muted);
    number((unsigned)p->grenades[0],1,grenade_x+13*scale,grenade_y,scale,blue);
    grenade_x+=31*scale;
    picture(BG_H_GRENADE_PLASMA,grenade_x,grenade_y,scale,p->grenade_kind==1?bright:muted);
    number((unsigned)p->grenades[1],1,grenade_x+17*scale,grenade_y,scale,blue);
    }

    if (p->health>0) {
        if (scoped(p)) scope_marks(p,aim_x,aim_y,height);
        float reticle_scale=scale;
        int id=reticles[weapon];
        if (!personal) id=vehicle->kind==BG_V_WARTHOG&&p->seat==0?-1:
            vehicle_reticles[vehicle->kind];
        if (id>=0) {
            const bg_hud_image *reticle=&bg_hud_images[id];
            picture(id,aim_x-reticle->w*reticle_scale*.5f,
                aim_y-reticle->h*reticle_scale*.5f,reticle_scale,bright);
        }
        if (!p->zoom) radar(index,x+margin,y+height-margin-bg_hud_images[BG_H_MOTION_BG].h*scale,scale);
    }

    /* Compact multiplayer score: Xbox blue tally in the lower-right corner. */
    int score=p->score;
    float score_x=x+width-margin-36*scale,score_y=y+height-margin-12*scale;
    if (score<0) pixel(score_x-4,score_y+3,3,1,blue);
    number((unsigned)(score<0?-score:score),2,score_x,score_y,scale,bright);
    draw_numbers();
    rdpq_set_mode_standard();
    int status=-1,status_y=y+height-8;
    if (p->health<=0) {
        int seconds=(int)ceilf(p->respawn);
        if(seconds>=0&&seconds<=3)status=HUD_RESPAWN_0+seconds;
        else {
            const rdpq_textparms_t text={.style_id=7,.width=width-2*margin,.align=ALIGN_CENTER};
            rdpq_text_printf(&text,1,x+margin,y+height/2+12,"Respawn in %d",seconds);
        }
        status_y=y+height/2+12;
    } else if (personal&&p->reload>0) {
        status=HUD_RELOAD;
    } else if (personal&&p->overheated) {
        status=HUD_OVERHEAT;
    } else {
        status=interaction(p);
    }
    status=control_status(status,style);
    if(status>=0)rdpq_paragraph_render(status_layouts[width<200][status],x+margin,status_y);
    rdpq_set_mode_standard();
}
