#include "damage_flash.h"
/* Diagnostic-only: frozen native frames, not performance measurements. */
static unsigned polish_frame,polish_page;
static bg_player polish_players[4];
#ifdef BG_SCOPE_QA
#include "scope_qa.h"
#define POLISH_PAGES BG_SCOPE_QA_PAGES
#else
#define POLISH_PAGES 20
#endif
static void m64_polish_stage(unsigned *count) {
    if(!polish_frame)memcpy(polish_players,bg_players,sizeof(polish_players));
    polish_page=polish_frame/3;
    if(polish_page>=POLISH_PAGES)polish_page=POLISH_PAGES-1;
#ifdef BG_SCOPE_QA
    scope_qa_stage(count,polish_page);return;
#endif
    *count=polish_page<8?1+polish_page/2:(polish_page==10?3:1);
    if(polish_page>=14)*count=polish_page==19?3:4;
    bg_set_players(*count);
    memcpy(bg_players,polish_players,sizeof(polish_players));
    for(unsigned p=0;p<*count;p++) {
        bg_players[p].health=100;bg_players[p].shield=100;
        for(unsigned d=0;d<4;d++)bg_players[p].damage_indicator[d]=(polish_page<8&&(polish_page&1))?.8f:0;
        if(polish_page>=11&&polish_page<=13){bg_players[p].pitch=-.6f;bg_players[p].flashlight_on=polish_page==12;}
        if(polish_page==13){bg_players[p].weapon=BG_W_PISTOL;bg_players[p].zoom=1;bg_players[p].damage_indicator[0]=.8f;}
    }
    if(polish_page>=15&&polish_page<=17) {
        bg_damage_flash_start(&bg_players[2],BG_D_AR,1);
        bg_players[2].damage_flash_time=fmaxf(0,bg_players[2].damage_flash_time-(polish_page-15)*.05f);
    }
    if(polish_page==18)bg_damage_flash_start(&bg_players[1],BG_D_PLASMA_RIFLE,1);
    if(polish_page==19){bg_damage_flash_start(&bg_players[2],BG_D_AR,1);bg_players[2].damage_indicator[0]=.8f;}
    bg_scene_update(0,0);
}
static void m64_polish_overlay(void) {
#ifdef BG_SCOPE_QA
    return;
#endif
    if(polish_page==8||polish_page==9) {
        bg_menu m;bg_menu_init(&m,1);m.open=true;m.page=BG_MENU_CONTROLS;
        m.styles[0]=polish_page==8?BG_CONTROLS_DUKE:BG_CONTROLS_BOND;
        rdpq_set_scissor(0,0,320,240);bg_menu_draw(&m);
    }
    if(polish_page==10)bg_scores_draw(2,0,120,320,120);
}
static void m64_polish_photo(surface_t *screen) {
    if(polish_frame%3!=2 || polish_frame>=POLISH_PAGES*3){polish_frame++;return;}
    rdpq_detach_wait();
    debugf("FF_PHOTO_BEGIN tick=%u width=320 height=240 format=RGBA5551\n",polish_page);
    static const char digits[]="0123456789abcdef";
    for(unsigned first=0;first<320*240;first+=64){
        char hex[257];
        for(unsigned j=0;j<64;j++){
            unsigned n=first+j;const uint16_t *row=(const uint16_t*)((const uint8_t*)UncachedAddr(screen->buffer)+(n/320)*screen->stride);
            unsigned value=row[n%320];for(unsigned k=0;k<4;k++)hex[j*4+k]=digits[(value>>(12-k*4))&15];
        }
        hex[256]=0;debugf("FF_PIX %u %s\n",first,hex);
    }
    debugf("FF_PHOTO_END\n");
    for(unsigned p=0;p<bg_player_count();p++)debugf("POLISH_POSE page=%u p=%u pos=%.6f,%.6f,%.6f yaw=%.6f pitch=%.6f crouch=%.6f\n",polish_page,p,bg_players[p].pos[0],bg_players[p].pos[1],bg_players[p].pos[2],bg_players[p].yaw,bg_players[p].pitch,bg_players[p].crouch_amount);
    if(polish_page==POLISH_PAGES-1)debugf("M64_POLISH_QA PASS\n");
    polish_frame++;rdpq_attach(screen,NULL);
}
