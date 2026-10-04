#include "menu_draw.h"
#include "asset_menu.h"
#include <assert.h>
#include <libdragon.h>
#include <stdio.h>
#include <string.h>

enum { TEXT_CAPACITY=320, MAX_FONT_PAGES=4, LETTER_FIXED=128 };
typedef struct {
    const bg_menu_glyph *glyph;
    union {
        struct { float x,y,scale; };
        struct { uint16_t x0,y0,x1,y1; int16_t dsdx,dtdy; } fixed;
    };
    color_t color;
    uint8_t font;
} letter;
static surface_t atlases[BG_MENU_FONT_COUNT][MAX_FONT_PAGES],panel[9];
static letter letters[TEXT_CAPACITY];
static unsigned letter_count;
static bool initialized;
enum { SCORE_LAYOUTS=7, SCORE_HEADER_LETTERS=24, SCORE_GLYPHS=104 };
typedef struct {
    rspq_block_t *panel;
    float x,y,w,h,scale;
    unsigned header_count,glyph_count,order[BG_PLAYERS];
    int scores[BG_PLAYERS];
    bool text_valid;
    letter glyphs[SCORE_GLYPHS];
} score_layout;
/* One permanent block per supported count/owner pair (1 + 2 + 4). The
 * referenced panel/font pixels and cached glyph pointers never move or change.
 * Blocks are never freed while queued display work might still refer to them. */
static score_layout score_layouts[SCORE_LAYOUTS];
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
            letters[letter_count++]=(letter){.glyph=g,.x=x-g->origin_x*scale,
                .y=baseline-g->origin_y*scale,.scale=scale,.color=color,.font=(uint8_t)font};
        }
        x+=g->advance*scale;
    }
}
static void prepare_score_rectangle(letter *l){
    assert(!(l->font&LETTER_FIXED));
    const bg_menu_glyph *g=l->glyph;
    /* Match the public scaled helper's float-to-fixed truncation BEFORE
     * dividing. Rounding the scale itself would change sampled font pixels. */
    int32_t x0=l->x*4,y0=l->y*4;
    int32_t x1=(l->x+g->w*l->scale)*4,y1=(l->y+g->h*l->scale)*4;
    if(x0<0||y0<0||x1>4095||y1>4095||x1<x0||y1<y0)return;
    int32_t dsdx=0,dtdy=0;
    if(x1!=x0&&y1!=y0){
        dsdx=((int32_t)g->w<<12)/(x1-x0);
        dtdy=((int32_t)g->h<<12)/(y1-y0);
        if(dsdx>INT16_MAX||dtdy>INT16_MAX)return;
    }
    l->fixed.x0=x0;l->fixed.y0=y0;l->fixed.x1=x1;l->fixed.y1=y1;
    l->fixed.dsdx=dsdx;l->fixed.dtdy=dtdy;l->font|=LETTER_FIXED;
    /* Clipped/flipped or out-of-range future layouts keep the original
     * scaled path. Current seven score layouts all use cached rectangles. */
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
static void flush_text_from(const letter *glyphs,unsigned count){
    rdpq_mode_begin();
    rdpq_mode_combiner(RDPQ_COMBINER1((0,0,0,PRIM),(TEX0,0,PRIM,0)));
    rdpq_mode_filter(FILTER_BILINEAR);
    rdpq_mode_end();
    /* Batch by small TMEM-sized page. Every glyph retains its native source
     * bearing/advance; only the coverage precision and screen scale change. */
    for(unsigned f=0;f<BG_MENU_FONT_COUNT;f++)for(unsigned p=0;p<bg_menu_fonts[f].pages;p++){
        bool used=false;
        for(unsigned i=0;i<count;i++)if((glyphs[i].font&~LETTER_FIXED)==f&&glyphs[i].glyph->page==p){used=true;break;}
        if(!used)continue;
        rdpq_tex_upload(TILE0,&atlases[f][p],NULL);
        color_t previous={0};bool have_color=false;
        for(unsigned i=0;i<count;i++){
            const letter *l=&glyphs[i];const bg_menu_glyph *g=l->glyph;
            if((l->font&~LETTER_FIXED)!=f||g->page!=p)continue;
            /* A font-page upload starts a fresh color run. Every rectangle
             * still sees the same RGBA, without resending it for each glyph. */
            if(!have_color||memcmp(&previous,&l->color,sizeof(previous))){
                rdpq_set_prim_color(l->color);previous=l->color;have_color=true;
            }
            if(l->font&LETTER_FIXED){
                if(l->fixed.x0==l->fixed.x1||l->fixed.y0==l->fixed.y1)continue;
                /* Exact binary fractions round-trip through the public raw
                 * macro; its normal SDK autosync/cycle fixups remain active. */
                rdpq_texture_rectangle_raw(TILE0,l->fixed.x0*.25f,l->fixed.y0*.25f,
                    l->fixed.x1*.25f,l->fixed.y1*.25f,g->s,g->t,
                    l->fixed.dsdx*(1.f/1024),l->fixed.dtdy*(1.f/1024));
            }else{
                rdpq_texture_rectangle_scaled(TILE0,l->x,l->y,l->x+g->w*l->scale,l->y+g->h*l->scale,
                    g->s,g->t,g->s+g->w,g->t+g->h);
            }
        }
    }
}
static void flush_text(void){flush_text_from(letters,letter_count);}
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
        {"Z / L","FIRE / GRENADE"},{"C LEFT","RELOAD / USE"},
        {"C UP / RIGHT","WEAPON / GRENADE TYPE"},{"C DOWN / R","CROUCH / SCORES"},
        {"R + C UP","ZOOM"}};
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
static void prepare_score_layout(unsigned count,unsigned owner,int x,int y,int width,int height){
    score_layout *layout=&score_layouts[count-1+owner];
    assert(!layout->panel);
    letter_count=0;
    float bw=152,bh=50+14*count,scale=1.6f;
    if((width-8)/bw<scale)scale=(width-8)/bw;
    if((height-8)/bh<scale)scale=(height-8)/bh;
    bw*=scale;bh*=scale;
    float bx=x+(width-bw)*.5f,by=y+(height-bh)*.5f;
    layout->x=bx;layout->y=by;layout->w=bw;layout->h=bh;layout->scale=scale;
    float xs[4]={bx,bx+4*scale,bx+bw-4*scale,bx+bw};
    float ys[4]={by,by+4*scale,by+bh-4*scale,by+bh};
    rspq_block_begin();
    flat();rectangle(bx,by,bw,bh,RGBA32(0,0,0,100));
    rdpq_mode_combiner(RDPQ_COMBINER_TEX);
    for(unsigned row=0;row<3;row++)for(unsigned col=0;col<3;col++){
        unsigned n=row*3+col;
        rdpq_tex_blit(&panel[n],xs[col],ys[row],&(rdpq_blitparms_t){
            .scale_x=(xs[col+1]-xs[col])/panel[n].width,
            .scale_y=(ys[row+1]-ys[row])/panel[n].height,.filtering=true});
    }
    flat();rectangle(bx+7*scale,by+24*scale,bw-14*scale,scale,RGBA32(40,150,255,115));
    layout->panel=rspq_block_end();
    text(BG_MENU_FONT_SMALL,bx+8*scale,by+18*scale,.9f*scale,white,"SCORES");
    char value[24];snprintf(value,sizeof(value),"YOU: P%u",owner+1);
    text(BG_MENU_FONT_SMALL,bx+bw-8*scale-text_width(BG_MENU_FONT_SMALL,value,.6f*scale),
        by+17*scale,.6f*scale,blue,value);
    text(BG_MENU_FONT_SMALL,bx+8*scale,by+36*scale,.6f*scale,soft,"#");
    text(BG_MENU_FONT_SMALL,bx+27*scale,by+36*scale,.6f*scale,soft,"PLAYER");
    text(BG_MENU_FONT_SMALL,bx+bw-8*scale-text_width(BG_MENU_FONT_SMALL,"SCORE",.6f*scale),
        by+36*scale,.6f*scale,soft,"SCORE");
    assert(letter_count<=SCORE_HEADER_LETTERS);
    layout->header_count=letter_count;
    for(unsigned i=0;i<letter_count;i++)prepare_score_rectangle(&letters[i]);
    memcpy(layout->glyphs,letters,letter_count*sizeof(*letters));
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
    /* Record immutable panels before gameplay begins. No block is executed
     * here, and no first held-R frame allocates or records display commands. */
    for(unsigned count=1;count<=4;count*=2)for(unsigned owner=0;owner<count;owner++){
        int w=count==4?160:320,h=count==1?240:120;
        int x=count==4?(int)(owner%2)*160:0;
        int y=count==1?0:(int)(count==4?owner/2:owner)*120;
        prepare_score_layout(count,owner,x,y,w,h);
    }
    letter_count=0;initialized=true;
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

static void update_score_text(score_layout *layout,unsigned count,unsigned owner){
    bool changed=!layout->text_valid;
    for(unsigned p=0;p<count;p++)if(layout->scores[p]!=bg_players[p].score)changed=true;
    if(!changed)return;
    for(unsigned p=0;p<count;p++){
        layout->scores[p]=bg_players[p].score;
        unsigned at=p;
        while(at&&layout->scores[layout->order[at-1]]<layout->scores[p]){
            layout->order[at]=layout->order[at-1];at--;
        }
        layout->order[at]=p;
    }
    letter_count=layout->header_count;
    memcpy(letters,layout->glyphs,letter_count*sizeof(*letters));
    float bx=layout->x,by=layout->y,bw=layout->w,scale=layout->scale;
    char value[24];unsigned rank=1;
    for(unsigned row=0;row<count;row++){
        unsigned p=layout->order[row];float line=by+(49+14*row)*scale;
        bool mine=p==owner;
        if(row&&layout->scores[p]!=layout->scores[layout->order[row-1]])rank=row+1;
        snprintf(value,sizeof(value),"%u",rank);
        text(BG_MENU_FONT_SMALL,bx+8*scale,line,.7f*scale,mine?white:soft,value);
        snprintf(value,sizeof(value),"PLAYER %u",p+1);
        text(BG_MENU_FONT_SMALL,bx+27*scale,line,.7f*scale,mine?white:soft,value);
        snprintf(value,sizeof(value),"%d",layout->scores[p]);
        text(BG_MENU_FONT_SMALL,bx+bw-8*scale-text_width(BG_MENU_FONT_SMALL,value,.7f*scale),
            line,.7f*scale,mine?white:soft,value);
    }
    assert(letter_count<=SCORE_GLYPHS);
    layout->glyph_count=letter_count;
    /* The copied heading prefix is already fixed; convert only fresh rows. */
    for(unsigned i=layout->header_count;i<letter_count;i++)prepare_score_rectangle(&letters[i]);
    memcpy(layout->glyphs,letters,letter_count*sizeof(*letters));
    /* Only literal rectangle parameters are submitted to RDP. Neither this
     * CPU list nor the score/order arrays are referenced by queued GPU work. */
    layout->text_valid=true;
}

void bg_scores_draw(unsigned owner,int x,int y,int width,int height){
    unsigned count=bg_player_count();
    assert(initialized&&owner<count&&count<=BG_PLAYERS);
    assert(count==1||count==2||count==4);
    /* count-1+owner maps 1/2/4 views to distinct cache slots. Assert the entire
     * viewport key, so a future layout cannot silently reuse wrong commands. */
    assert(width==(count==4?160:320)&&height==(count==1?240:120));
    assert(x==(count==4?(int)(owner%2)*160:0));
    assert(y==(count==1?0:(int)(count==4?owner/2:owner)*120));
    score_layout *layout=&score_layouts[count-1+owner];
    /* Original split-screen score text ranks players and brightens the viewer's
     * row. Keep those cues; report actual match score, which includes suicides. */
    static const color_t player_colors[BG_PLAYERS]={
        {225,45,38,255},{39,92,215,255},{215,179,44,255},{57,183,69,255}};
    letter_count=0;rdpq_sync_pipe();rdpq_mode_push();rdpq_mode_begin();
    rdpq_set_mode_standard();rdpq_mode_blender(RDPQ_BLENDER_MULTIPLY);
    rdpq_mode_zbuf(false,false);rdpq_mode_antialias(AA_NONE);rdpq_mode_filter(FILTER_BILINEAR);
    rdpq_mode_end();rdpq_set_scissor(x,y,x+width,y+height);
    assert(layout->panel);
    rspq_block_run(layout->panel);
    update_score_text(layout,count,owner);
    /* Every row rectangle still precedes the single combined text flush. */
    flat();
    float bx=layout->x,by=layout->y,bw=layout->w,scale=layout->scale;
    for(unsigned row=0;row<count;row++){
        unsigned p=layout->order[row];float line=by+(49+14*row)*scale;
        if(p==owner)rectangle(bx+5*scale,line-10*scale,bw-10*scale,13*scale,RGBA32(40,150,255,48));
        rectangle(bx+21*scale,line-7*scale,3*scale,7*scale,player_colors[p]);
    }
    flush_text_from(layout->glyphs,layout->glyph_count);
    rdpq_mode_pop();rdpq_set_scissor(0,0,320,240);
}
