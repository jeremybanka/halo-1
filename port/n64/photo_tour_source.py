"""Create an isolated native photo fixture through the production renderer."""
def walking_benchmark_source(source):
    source=source.replace('static float game_time;','''static float game_time;
#include "photo_tour.h"
static void photo_walk_benchmark(bg_input in[4],float time){
    static unsigned previous=~0u;
    unsigned tick=(unsigned)(time*30.f+.01f),station=(tick/180)%12;
    unsigned photo=station*2+1;
    if(previous!=tick/180){previous=tick/180;bg_photo_begin(photo);bg_scene_reset();}
    bg_photo_input(photo,tick%180,in);
}
''')
    source=source.replace('            bg_replay_input(in, game_time);\n            views = 4;\n            bg_set_players(4);',
                          '            photo_walk_benchmark(in, game_time);\n            views = 1;\n            bg_set_players(1);')
    source=source.replace('static unsigned slot, views = 4, triangles, fps;',
                          'static unsigned slot, views = 1, triangles, fps;')
    assert 'photo_walk_benchmark(in, game_time)' in source
    return source

def photo_source(source):
    include='#include "photo_tour.h"\n'
    at='static float game_time;'
    assert source.count(at)==1
    source=source.replace(at,at+'\n'+include+r'''
static unsigned photo_index;
static bool photo_debug=true;
static void photo_select(unsigned index){
    rspq_wait();photo_index=index;views=1;game_time=0;
    bg_photo_begin(index);bg_scene_reset();bg_hud_messages_reset();
    for(unsigned tick=0;tick<bg_photo_ticks(index);tick++){
        bg_input in[4];bg_photo_input(index,tick,in);
        bg_clear_events();bg_tick(in,BLAM_TICK_SECONDS);
        game_time+=BLAM_TICK_SECONDS;bg_hud_messages_update();
        bg_scene_update(BLAM_TICK_SECONDS,game_time);bg_sound_update();
    }
    const bg_player*q=&bg_players[0];
    debugf("PHOTO %u tick=%u pos=%.9f,%.9f,%.9f yaw=%.9f pitch=%.9f crouch=%.9f grounded=%d\n",
        index,bg_photo_ticks(index),(double)q->pos[0],(double)q->pos[1],(double)q->pos[2],
        (double)q->yaw,(double)q->pitch,(double)q->crouch_amount,q->grounded);
}
''')
    a=source.index('#ifdef BG_SNAPSHOT_TICK\n    /* No rendering')
    b=source.index('#ifdef BG_SHOWCASE',a)
    source=source[:a]+'''    unsigned char initial_photo=0;
    FILE*photo_file=fopen("rom:/photo-index.bin","rb");
    if(photo_file){assertf(fread(&initial_photo,1,1,photo_file)==1,"Photo selector");fclose(photo_file);}
    assertf(initial_photo<BG_PHOTO_COUNT,"Photo index");photo_select(initial_photo);
'''+source[b:]
    at='        uint64_t now = get_ticks_us();'
    a=source.index(at,source.index('int main(void)'))+len(at)
    source=source[:a]+r'''
        joypad_poll();joypad_buttons_t photo_buttons=joypad_get_buttons_pressed(JOYPAD_PORT_1);
        if(photo_buttons.start)photo_select((photo_index+1)%BG_PHOTO_COUNT);
        if(photo_buttons.b)photo_debug=!photo_debug;
'''+source[a:]
    at='        rdpq_set_scissor(0, 0, 320, 240);'
    # Insert after the final HUD scissor, never at menu/result scissors.
    a=source.index(at,source.index('        /* Complete every 3D view before the HUD'))+len(at)
    source=source[:a]+r'''
        if(photo_debug){
            const bg_player*q=&bg_players[0];
            fill(0,194,320,46,RGBA32(0,0,0,255));rdpq_set_mode_standard();
            rdpq_text_printf(NULL,1,4,204,"PHOTO %02u / %s",photo_index,bg_photo_stations[photo_index/2].label);
            rdpq_text_printf(NULL,1,4,215,"XYZ %.3f %.3f %.3f",(double)q->pos[0],(double)q->pos[1],(double)q->pos[2]);
            rdpq_text_printf(NULL,1,4,226,"YAW %.4f PITCH %.4f C %.3f",(double)q->yaw,(double)q->pitch,(double)q->crouch_amount);
            rdpq_text_printf(NULL,1,4,237,"T%u G%d W%d Z%d FOV1.08 START:NEXT B:HUD",bg_photo_ticks(photo_index),q->grounded,q->weapon,q->zoom);
        }
''' +source[a:]
    return source
