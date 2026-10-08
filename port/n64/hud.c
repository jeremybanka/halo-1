#include "hud.h"
#include "asset_hud.h"
#include "game.h"
#include <libdragon.h>
#include <math.h>

/* Original motion sensor and scopes; native pixel art for compact counters
 * and meters. The immutable IA4 bank is uploaded once per player view. */
static surface_t images[BG_H_COUNT];
static surface_t scope_images[BG_SCOPE_COUNT];
#include "hud_pixels.h"
#include "hud_buttons.h"
static surface_t pixel_atlas;
static surface_t button_atlas;
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
    "B EXIT","B PICK UP","B ENTER","RELOADING","OVERHEATED",
    "RESPAWN IN 0","RESPAWN IN 1","RESPAWN IN 2","RESPAWN IN 3",
    "C-LEFT EXIT","C-LEFT PICK UP","C-LEFT ENTER","B FLIP","C-LEFT FLIP"};
static const color_t blue = {105,166,236,255};
static const color_t bright = {149,207,255,255};
static const color_t red = {248,63,58,255};
static const color_t muted = {41,70,106,255};
static const unsigned reticles[BG_WEAPON_COUNT] = {
    BG_H_RETICLE_AR, BG_H_RETICLE_PISTOL, BG_H_RETICLE_PLASMA_PISTOL,
    BG_H_RETICLE_PLASMA_RIFLE, BG_H_RETICLE_NEEDLER, BG_H_RETICLE_SHOTGUN,
    BG_H_RETICLE_SNIPER, BG_H_RETICLE_ROCKET, BG_H_RETICLE_AR
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

static void pixel(int x,int y,int w,int h,color_t c) {
    set_combiner(2);rdpq_set_prim_color(c);
    rdpq_fill_rectangle(x,y,x+w,y+h);
}

/* This bank stays resident through all counters, bars and labels in a view. */
static const color_t hud_cyan={100,220,255,255};
static const color_t hud_dim={25,62,77,255};
static const color_t hud_shadow={3,13,22,235};
static const color_t hud_backing={3,13,22,150};
static void hud_sprite(int u,int v,int w,int h,int x,int y,color_t color){
    if(w<=0||h<=0)return;
    set_combiner(1);rdpq_set_prim_color(color);
    rdpq_texture_rectangle(TILE0,x,y,x+w,y+h,u,v);
}
static void hud_reticle(unsigned id,int cx,int cy){
    unsigned q=id>=BG_H_RETICLE_WARTHOG?8+id-BG_H_RETICLE_WARTHOG:id-BG_H_RETICLE_AR;
    unsigned lower=q==2?12:q==11?13:q==9?14:q;
    set_combiner(1);rdpq_set_prim_color(hud_cyan);
    /* Even 24px footprint puts its geometric center exactly on the original
     * integer aim anchor. Each quadrant maps 12 texels to 12 screen pixels.
     * Explicit negative UV steps mirror texels without flipped-rectangle
     * endpoint adjustments or fractional scaling of a cropped Xbox bitmap. */
    for(unsigned bottom=0;bottom<2;bottom++){
        unsigned tile=bottom?lower:q;
        int u=(tile%5)*12,v=80+(tile/5)*12;
        bool flip_y=bottom&&lower==q;
        if(flip_y)v+=11;
        int y=cy+(bottom?0:-12);
        rdpq_texture_rectangle_raw(TILE0,cx-12,y,cx,y+12,u,v,1,flip_y?-1:1);
        rdpq_texture_rectangle_raw(TILE0,cx,y,cx+12,y+12,u+11,v,-1,flip_y?-1:1);
    }
}
static int hud_text_width(const char *text){return (int)strlen(text)*5-1;}
static void hud_text(const char *text,int x,int y,color_t color){
    set_combiner(1);
    for(int shadow=1;shadow>=0;shadow--){
        rdpq_set_prim_color(shadow?hud_shadow:color);
        for(unsigned i=0;text[i];i++){
            int glyph=hud_glyph(text[i]);if(glyph<0)continue;
            if(shadow&&glyph<10){
                int px=x+i*5-1,py=y-1;
                rdpq_texture_rectangle(TILE0,px,py,px+6,py+8,glyph*6,116);
                continue;
            }
            int px=x+i*5+shadow,py=y+shadow;
            rdpq_texture_rectangle(TILE0,px,py,px+4,py+6,(glyph%10)*6,(glyph/10)*8);
        }
    }
}
static void hud_number(int value,int x,int y,unsigned places,color_t color){
    char text[16];unsigned at=sizeof(text)-1;
    unsigned magnitude=value<0?0u-(unsigned)value:(unsigned)value;
    text[at]=0;
    do {text[--at]='0'+magnitude%10;magnitude/=10;}while(magnitude);
    while(sizeof(text)-1-at<places&&at>1)text[--at]='0';
    if(value<0)text[--at]='-';
    hud_text(text+at,x,y,color);
}
static void hud_vitals(const bg_player *p,int x,int y){
    /* A one-pixel step at either end echoes Halo without its long diagonals. */
    hud_sprite(0,72,46,7,x+1,y+1,hud_shadow);
    hud_sprite(0,72,46,7,x,y,p->shield<=0?red:hud_cyan);
    pixel(x+2,y+2,42,3,hud_dim);
    int fill=(int)ceilf(fminf(fmaxf(p->shield,0),100)*.42f);
    if(fill)pixel(x+2,y+2,fill,3,hud_cyan);
    if(p->shield>100){
        fill=(int)ceilf(fminf(p->shield-100,100)*.42f);
        pixel(x+2,y+2,fill,3,RGBA32(255,48,48,255));
    }
    if(p->shield>200){
        fill=(int)ceilf(fminf(p->shield-200,100)*.42f);
        pixel(x+2,y+2,fill,3,RGBA32(48,255,64,255));
    }
    /* Eight upright health cells, aligned to the shield's right edge. */
    pixel(x+12,y+7,33,5,hud_backing);
    hud_sprite(0,67,31,3,x+13,y+8,hud_dim);
    int cells=(int)ceilf(fminf(fmaxf(p->health,0),100)*.08f);
    if(cells)hud_sprite(0,67,cells*4-1,3,x+13,y+8,
        p->health<=33?red:p->health<=67?RGBA32(255,217,65,255):hud_cyan);
}
static void hud_ammunition(const bg_player *p,unsigned weapon,int x,int y){
    const bg_weapon_def *def=&bg_weapon_defs[weapon];
    color_t tint=p->overheated?red:hud_cyan;
    hud_sprite(40,32,19,10,x+1,y+1,hud_shadow);
    hud_sprite(40,32,19,10,x,y,hud_cyan);
    hud_number(p->ammo<0?0:p->ammo,x+2,y+2,def->energy?3:2,tint);
    for(int i=0;i<2;i++){
        int gx=x+23+i*14;
        hud_sprite(42+i*8,45,6,7,gx+1,y+2,hud_shadow);
        hud_sprite(42+i*8,45,6,7,gx,y+1,p->grenade_kind==i?hud_cyan:hud_dim);
        hud_number(p->grenades[i],gx+7,y+2,1,p->grenade_kind==i?hud_cyan:hud_dim);
    }
    int my=y+12,ammo=p->ammo;
    if(ammo<0)ammo=0;
    if(ammo>def->magazine)ammo=def->magazine;
    if(def->energy){
        /* Battery digits above; heat grows toward the right independently. */
        pixel(x,my,39,4,hud_shadow);pixel(x+1,my+1,37,2,hud_dim);
        int heat=(int)ceilf(fminf(fmaxf(p->heat,0),1)*37);
        if(heat)pixel(x+1,my+1,heat,2,p->heat>.75f?red:hud_cyan);
        hud_text("HEAT",x,my+6,p->overheated?red:hud_cyan);
        return;
    }
    if(weapon==BG_W_AR){
        pixel(x-1,my-1,41,13,hud_backing);
        hud_sprite(0,32,39,11,x,my,hud_dim);
        /* Twenty columns, each with three rounds: deplete right to left,
         * then bottom to top within a column, as in the source ammo meter.
         * A partial column still represents exactly one or two rounds. */
        int columns=ammo/3,remainder=ammo%3;
        if(columns)hud_sprite(0,32,columns*2-1,11,x,my,hud_cyan);
        if(remainder)hud_sprite(columns*2,32,1,remainder*4-1,x+columns*2,my,hud_cyan);
        hud_number(p->reserve<0?0:p->reserve,x,my+13,3,hud_cyan);
    }else if(def->magazine>20){
        pixel(x,my,39,4,hud_shadow);pixel(x+1,my+1,37,2,hud_dim);
        int fill=(ammo*37+def->magazine-1)/def->magazine;
        if(fill)pixel(x+1,my+1,fill,2,hud_cyan);
        hud_number(p->reserve<0?0:p->reserve,x,my+7,3,hud_cyan);
    }else{
        int v=44,step=3,w=2,count=def->magazine;
        if(weapon==BG_W_NEEDLER){v=50;step=2;w=1;}
        else if(weapon==BG_W_SNIPER){v=55;step=10;w=8;}
        else if(weapon==BG_W_ROCKET){v=61;step=21;w=18;}
        int full=(count-1)*step+w,filled=ammo?(ammo-1)*step+w:0;
        if(filled>full)filled=full;
        pixel(x-1,my-1,full+2,7,hud_backing);
        hud_sprite(0,v,full,5,x,my,hud_dim);
        if(filled)hud_sprite(0,v,filled,5,x,my,hud_cyan);
        hud_number(p->reserve<0?0:p->reserve,x,my+7,3,hud_cyan);
    }
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

static void interaction_label(const bg_player*p,char *out,unsigned size){
    bg_use_target target=bg_interaction_target(p-bg_players);
    const char*vehicles[]={"WARTHOG","GHOST","SCORPION","BANSHEE"};
    out[0]=0;
    if(target.kind==BG_USE_PICKUP)snprintf(out,size,"PICK UP");
    else if(target.kind==BG_USE_EXIT)snprintf(out,size,"EXIT %s",vehicles[bg_vehicles[target.object].kind]);
    else if(target.kind==BG_USE_FLIP)snprintf(out,size,"FLIP %s",vehicles[bg_vehicles[target.object].kind]);
    else if(target.kind==BG_USE_ENTER){
        const bg_vehicle*v=&bg_vehicles[target.object];
        const bg_seat_definition*s=&bg_seat_definitions[v->kind][target.seat];
        const char*role=s->flags&4?"DRIVE":s->flags&8?"GUNNER":"PASSENGER";
        if(target.seat==0)snprintf(out,size,"%s %s",role,vehicles[v->kind]);
        else snprintf(out,size,"%s",role);
    }
}
static void hud_button(unsigned id,int x,int y){
    /* Unlike the one-bit text bank, icons encode dim inactive buttons and
     * opaque dark letter/arrow cutouts. Preserve both intensity and alpha. */
    set_combiner(0);rdpq_set_prim_color(hud_cyan);
    rdpq_texture_rectangle(TILE0,x,y,x+hud_button_width[id],y+hud_button_height[id],(id%4)*16,(id/4)*16);
}
static void interaction_prompt(const bg_player*p,bg_control_style style,int x,int y,int width){
    char label[48];interaction_label(p,label,sizeof(label));if(!label[0])return;
    bg_use_target target=bg_interaction_target(p-bg_players);
    unsigned icon=style==BG_CONTROLS_XBOX?HUD_BUTTON_C_LEFT:HUD_BUTTON_B;
    bool hold=target.kind==BG_USE_PICKUP;
    int prefix=hold?24:0,iw=hud_button_width[icon];
    int start=x+(width-prefix-iw-3-hud_text_width(label))/2;
    if(hold)hud_text("HOLD",start,y,hud_cyan);
    hud_text(label,start+prefix+iw+3,y,hud_cyan);
    rdpq_tex_upload(TILE0,&button_atlas,NULL);
    hud_button(icon,start+prefix,y-(hud_button_height[icon]-6)/2);
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
    hud_pixels_init();
    pixel_atlas=surface_make(hud_pixels,FMT_IA4,HUD_PIXEL_W,HUD_PIXEL_H,HUD_PIXEL_W/2);
    data_cache_hit_writeback(hud_pixels,sizeof(hud_pixels));
    hud_buttons_init();
    button_atlas=surface_make(hud_button_pixels,FMT_IA4,HUD_BUTTON_W,HUD_BUTTON_H,HUD_BUTTON_W/2);
    data_cache_hit_writeback(hud_button_pixels,sizeof(hud_button_pixels));
}

void bg_hud_draw(unsigned index,int x,int y,int width,int height,bg_control_style style) {
    const bg_player *p=&bg_players[index];
    float scale=width<200?.45f:.5f;
    int margin=width<200?5:9;
    unsigned weapon=(unsigned)p->weapon<BG_WEAPON_COUNT?(unsigned)p->weapon:BG_W_AR;
    const bg_vehicle *vehicle=p->vehicle>=0&&(unsigned)p->vehicle<bg_vehicle_count?
        &bg_vehicles[p->vehicle]:NULL;
    bool personal=bg_player_personal_weapon(p);
    float aim_x,aim_y;
    unsigned views=height>=240?1:width<200?4:2;
    bg_hud_aim_point(views,index,x,y,width,height,&aim_x,&aim_y);
    current_combiner=current_filter=-1;
    rdpq_mode_begin();
    rdpq_set_mode_standard();
    rdpq_mode_zbuf(false,false);rdpq_mode_persp(false);rdpq_mode_tlut(TLUT_NONE);
    rdpq_mode_blender(RDPQ_BLENDER_MULTIPLY);
    rdpq_mode_end();
    rdpq_set_scissor(x,y,x+width,y+height);
    if (scoped(p)) scope_mask(p,x,y,width,height,aim_x,aim_y);

    if (p->health>0) {
        if (scoped(p)) scope_marks(p,aim_x,aim_y,height);
        if (!p->zoom) radar(index,x+margin,y+height-margin-bg_hud_images[BG_H_MOTION_BG].h*scale,scale);
    }

    /* Pixel HUD: all coordinates and glyph extents are native integers. */
    set_filter(true);set_combiner(1);
    rdpq_tex_upload(TILE0,&pixel_atlas,NULL);
    if(p->health>0){
        const bg_seat_definition*seat=bg_player_seat(p);
        int id=personal?(int)reticles[weapon]:seat&&(seat->flags&8)?vehicle_reticles[vehicle->kind]:-1;
        if(p->seat_state!=BG_SEAT_STABLE)id=-1;
#ifdef BG_SHIELD_QA
        id=-1; /* Inspection camera looks at this actor, not down its sights. */
#endif
        if(id>=0)hud_reticle(id,(int)roundf(aim_x),(int)roundf(aim_y));
    }
    int left=x+margin,top=y+margin,right=x+width-margin;
    hud_vitals(p,right-46,top);
    if(personal)hud_ammunition(p,weapon,left,top);
    hud_number(p->score,right-(p->score<0?15:10),y+height-margin-6,2,hud_cyan);
    if(scoped(p)){
        int ox=p->weapon==BG_W_PISTOL?(height<200?34:53):(height<200?24:75);
        int oy=p->weapon==BG_W_PISTOL?(height<200?34:53):(height<200?15:52);
        hud_text(p->weapon==BG_W_SNIPER&&p->zoom==2?"10X":"2X",
            (int)roundf(aim_x)+ox-5,(int)roundf(aim_y)+oy-3,hud_cyan);
    }
    int status=-1,status_y=y+height-margin-6;
    if (p->health<=0) {
        int seconds=(int)ceilf(p->respawn);
        status_y=y+height/2+8;
        if(seconds>=0&&seconds<=3)status=HUD_RESPAWN_0+seconds;
        else {
            char label[32];snprintf(label,sizeof(label),"RESPAWN IN %d",seconds);
            hud_text(label,x+(width-hud_text_width(label))/2,status_y,hud_cyan);
        }
    } else if (personal&&p->reload>0) status=HUD_RELOAD;
    else if (personal&&p->overheated) status=HUD_OVERHEAT;
    else {
        interaction_prompt(p,style,x,status_y,width);
    }
    status=control_status(status,style);
    if(status>=0){
        const char *label=status_strings[status];
        hud_text(label,x+(width-hud_text_width(label))/2,status_y,
            status==HUD_OVERHEAT?red:hud_cyan);
    }
#ifdef BG_INTERACTION_QA
    if(BG_INTERACTION_QA==4){
        const bg_vehicle*v=&bg_vehicles[index];char state[32];
        snprintf(state,sizeof(state),"UP %d %s",(int)lroundf(v->up[1]*100),v->flipping?"ROLLING":v->up[1]>=BG_VEHICLE_FLIP_MAX_UP?"READY":"FLIPPED");
        rdpq_tex_upload(TILE0,&pixel_atlas,NULL);
        hud_text(state,x+(width-hud_text_width(state))/2,y+height/2-18,hud_cyan);
    }
#endif
    rdpq_set_mode_standard();
}
