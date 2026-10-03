#include "menu_draw.h"
#include "asset_menu.h"
#include <assert.h>
#include <libdragon.h>
#include <stdio.h>

enum { TEXT_CAPACITY=320, MAX_FONT_PAGES=4 };
typedef struct {
    const bg_menu_glyph *glyph;
    float x,y,scale;
    color_t color;
    uint8_t font;
} letter;
static surface_t atlases[BG_MENU_FONT_COUNT][MAX_FONT_PAGES],panel[9];
static letter letters[TEXT_CAPACITY];
static unsigned letter_count;
static bool initialized;
/* Resume widget: (40,150,255). Focused text uses the source UI white0.8. */
static const color_t blue={40,150,255,255},white={204,204,204,255};
static const color_t muted={85,105,125,255},soft={133,176,216,255};

static unsigned glyph_index(unsigned ch){
    if(ch>='a'&&ch<='z')ch-='a'-'A';
    if(ch<BG_MENU_GLYPH_FIRST||ch>=BG_MENU_GLYPH_FIRST+BG_MENU_GLYPH_COUNT)ch='?';
    return ch-BG_MENU_GLYPH_FIRST;
}
static float text_width(unsigned font,const char *s,float scale){
    float width=0;
    for(;*s;s++)width+=bg_menu_fonts[font].glyphs[glyph_index((unsigned char)*s)].advance*scale;
    return width;
}
static void text(unsigned font,float x,float baseline,float scale,color_t color,const char *s){
    for(;*s;s++){
        const bg_menu_glyph *g=&bg_menu_fonts[font].glyphs[glyph_index((unsigned char)*s)];
        if(g->w&&g->h){
            assert(letter_count<TEXT_CAPACITY);
            letters[letter_count++]=(letter){g,x-g->origin_x*scale,baseline-g->origin_y*scale,scale,color,(uint8_t)font};
        }
        x+=g->advance*scale;
    }
}
static void flat(void){
    rdpq_mode_combiner(RDPQ_COMBINER_FLAT);
}
static void rectangle(float x,float y,float w,float h,color_t color){
    rdpq_set_prim_color(color);rdpq_fill_rectangle(x,y,x+w,y+h);
}
static void selection(float y,bool active){
    if(active){
        rectangle(31,y,258,25,RGBA32(40,150,255,48));
        rectangle(31,y,2,25,RGBA32(40,150,255,225));
    }
}
static void flush_text(void){
    rdpq_mode_begin();
    rdpq_mode_combiner(RDPQ_COMBINER1((0,0,0,PRIM),(TEX0,0,PRIM,0)));
    rdpq_mode_filter(FILTER_BILINEAR);
    rdpq_mode_end();
    /* Batch by small TMEM-sized page. Every glyph retains its native source
     * bearing/advance; only the coverage precision and screen scale change. */
    for(unsigned f=0;f<BG_MENU_FONT_COUNT;f++)for(unsigned p=0;p<bg_menu_fonts[f].pages;p++){
        bool used=false;
        for(unsigned i=0;i<letter_count;i++)if(letters[i].font==f&&letters[i].glyph->page==p){used=true;break;}
        if(!used)continue;
        rdpq_tex_upload(TILE0,&atlases[f][p],NULL);
        for(unsigned i=0;i<letter_count;i++){
            const letter *l=&letters[i];const bg_menu_glyph *g=l->glyph;
            if(l->font!=f||g->page!=p)continue;
            rdpq_set_prim_color(l->color);
            rdpq_texture_rectangle_scaled(TILE0,l->x,l->y,l->x+g->w*l->scale,l->y+g->h*l->scale,
                g->s,g->t,g->s+g->w,g->t+g->h);
        }
    }
}
static void background(void){
    flat();rectangle(0,0,320,240,RGBA32(0,0,0,170));
    rdpq_mode_combiner(RDPQ_COMBINER_TEX);
    const float xs[4]={18,26,294,302},ys[4]={14,22,218,226};
    for(unsigned row=0;row<3;row++)for(unsigned col=0;col<3;col++){
        unsigned n=row*3+col;
        rdpq_tex_blit(&panel[n],xs[col],ys[row],&(rdpq_blitparms_t){
            .scale_x=(xs[col+1]-xs[col])/panel[n].width,
            .scale_y=(ys[row+1]-ys[row])/panel[n].height,.filtering=true});
    }
    flat();rectangle(33,49,254,1,RGBA32(40,150,255,115));
}
static void root_page(const bg_menu *m){
    static const char *const labels[]={"RESUME","SETUP","CONTROLS"};
    static const char *const help[]={"RETURN TO BLOOD GULCH","LOCAL PLAYERS AND MATCH RESET","CHANGE YOUR CONTROL STYLE"};
    for(unsigned row=0;row<3;row++){
        float y=78+34*row;bool enabled=bg_menu_row_enabled(m,row),selected=m->row==row;
        selection(y,selected&&enabled);
        text(BG_MENU_FONT_LARGE,42,y+18,1.f,enabled?(selected?white:blue):muted,labels[row]);
        if(row==BG_MENU_SETUP_ROW&&!enabled)text(BG_MENU_FONT_SMALL,184,y+17,.66f,muted,"PLAYER 1 ONLY");
    }
    text(BG_MENU_FONT_SMALL,35,195,.70f,soft,help[m->row<3?m->row:0]);
    text(BG_MENU_FONT_SMALL,35,216,.68f,white,"A SELECT     B / START RESUME");
}
static void setup_page(const bg_menu *m){
    selection(82,m->row==BG_MENU_PLAYERS_ROW);selection(125,m->row==BG_MENU_RESTART_ROW);
    text(BG_MENU_FONT_LARGE,42,101,.92f,m->row==BG_MENU_PLAYERS_ROW?white:blue,"PLAYERS");
    char count[12];snprintf(count,sizeof(count),"< %u >",m->player_count);
    text(BG_MENU_FONT_LARGE,226,101,.92f,white,count);
    text(BG_MENU_FONT_LARGE,42,144,.92f,m->row==BG_MENU_RESTART_ROW?white:blue,"RESTART MATCH");
    text(BG_MENU_FONT_SMALL,35,180,.72f,soft,"BLOOD GULCH / LOCAL SPLITSCREEN");
    text(BG_MENU_FONT_SMALL,35,195,.70f,soft,m->row==BG_MENU_PLAYERS_ROW?"CHOOSE 1, 2 OR 4 PLAYERS":"RESET SCORES AND RESPAWN EVERYONE");
    text(BG_MENU_FONT_SMALL,35,216,.66f,white,"LEFT / RIGHT CHANGE    A SELECT    B BACK");
}
static void controls_page(const bg_menu *m){
    static const char *const n64[][2]={
        {"STICK","MOVE FORWARD / BACK + TURN"},{"C LEFT / RIGHT","STRAFE"},
        {"C UP / DOWN","LOOK UP / DOWN"},{"A / Z / L","JUMP / FIRE / GRENADE"},
        {"B / R","RELOAD + USE / WEAPON"},{"D UP / DOWN","ZOOM / MELEE"},
        {"D LEFT / RIGHT","GRENADE TYPE / CROUCH"},{"START","MENU / RESUME"}};
    static const char *const xbox[][2]={
        {"STICK","AIM"},{"D-PAD","MOVE"},{"A / B","JUMP / MELEE"},
        {"Z / L","FIRE / GRENADE"},{"R","RELOAD / USE"},
        {"C LEFT / RIGHT","WEAPON / GRENADE TYPE"},{"C UP / DOWN","ZOOM / CROUCH"},
        {"START","MENU / RESUME"}};
    bool is_xbox=m->styles[m->owner]==BG_CONTROLS_XBOX;
    const char *const (*rows)[2]=is_xbox?xbox:n64;
    selection(55,true);
    text(BG_MENU_FONT_SMALL,42,72,.80f,white,"CONTROL STYLE");
    text(BG_MENU_FONT_LARGE,212,72,.83f,white,is_xbox?"< XBOX >":"< N64 >");
    text(BG_MENU_FONT_SMALL,35,92,.65f,blue,"BUTTON");
    text(BG_MENU_FONT_SMALL,133,92,.65f,blue,"ACTION");
    for(unsigned i=0;i<8;i++){
        text(BG_MENU_FONT_SMALL,35,105+12*i,.70f,white,rows[i][0]);
        text(BG_MENU_FONT_SMALL,133,105+12*i,.66f,soft,rows[i][1]);
    }
    text(BG_MENU_FONT_SMALL,35,203,.56f,soft,"VEHICLES: L ALT FIRE. BANSHEE: A UP, CROUCH DOWN");
    text(BG_MENU_FONT_SMALL,35,217,.64f,white,"LEFT / RIGHT CHANGE    B BACK    START RESUME");
}
void bg_menu_draw_init(void){
    for(unsigned f=0;f<BG_MENU_FONT_COUNT;f++){
        const bg_menu_font *font=&bg_menu_fonts[f];assert(font->pages<=MAX_FONT_PAGES);
        for(unsigned p=0;p<font->pages;p++)atlases[f][p]=surface_make((void*)(font->pixels+p*BG_MENU_ATLAS_BYTES),
            FMT_I4,BG_MENU_ATLAS_WIDTH,BG_MENU_ATLAS_HEIGHT,BG_MENU_ATLAS_WIDTH/2);
        data_cache_hit_writeback((void*)font->pixels,font->pages*BG_MENU_ATLAS_BYTES);
    }
    for(unsigned i=0;i<9;i++){
        panel[i]=surface_make((void*)bg_menu_panel[i].pixels,FMT_RGBA32,bg_menu_panel[i].w,bg_menu_panel[i].h,bg_menu_panel[i].w*4);
        data_cache_hit_writeback((void*)bg_menu_panel[i].pixels,bg_menu_panel[i].w*bg_menu_panel[i].h*4);
    }
    initialized=true;
}
void bg_menu_draw(const bg_menu *m){
    if(!m->open)return;
    assert(initialized&&m->owner<BG_PLAYERS&&m->page<=BG_MENU_CONTROLS);
    letter_count=0;rdpq_sync_pipe();rdpq_mode_push();rdpq_mode_begin();
    rdpq_set_mode_standard();rdpq_mode_blender(RDPQ_BLENDER_MULTIPLY);
    rdpq_mode_zbuf(false,false);rdpq_mode_antialias(AA_NONE);rdpq_mode_filter(FILTER_BILINEAR);
    rdpq_mode_end();rdpq_set_scissor(0,0,320,240);
    background();
    const char *title=m->page==BG_MENU_ROOT?"PAUSED":m->page==BG_MENU_SETUP?"SETUP":"CONTROLS";
    text(BG_MENU_FONT_LARGE,34,40,1.05f,white,title);
    char owner[16];snprintf(owner,sizeof(owner),"PLAYER %u",m->owner+1);
    text(BG_MENU_FONT_SMALL,286-text_width(BG_MENU_FONT_SMALL,owner,.72f),38,.72f,blue,owner);
    if(m->page==BG_MENU_ROOT)root_page(m);
    else if(m->page==BG_MENU_SETUP)setup_page(m);
    else controls_page(m);
    flush_text();rdpq_mode_pop();
}
