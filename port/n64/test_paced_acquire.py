"""Compile the actual acquisition gate with deterministic input/audio/display mocks."""
from runtime_source import read_runtime, validation_output
from pathlib import Path
import subprocess
from test_render_matrix import function

ROOT = Path(__file__).resolve().parents[2]
OUT = validation_output('paced-acquire')
PRELUDE = r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "game.h"
#include "render_pacing.h"
typedef struct {int id;} surface_t;
static surface_t screen;
static uint64_t fake_now,available_at,frame_sample_us;
static unsigned scenario,views,inputs,pumps,acquired,paced_dropped_ticks;
static bool paused,edge_sent,zoom_sent,presentation,shell;
static bool front_active(void){return shell;}
#ifdef BG_PRESENT_TRACK
static volatile bg_present30_tracker present_tracker;
#endif
static uint64_t get_ticks_us(void){return fake_now;}
static void pump_audio(void){
    pumps++;fake_now+=1000;
#ifdef BG_PRESENT_TRACK
    if(scenario==5&&fake_now>=80000)present_tracker.draining=0;
#endif
}
static void bg_presentation_mode(bool enabled){presentation=enabled;}
#ifdef BG_PRESENT_TRACK
static bool bg_presentation_draining(void){return present_tracker.draining;}
#endif
static surface_t*display_try_get(void){
    if(fake_now<available_at)return NULL;
    assert(!acquired);acquired++;return &screen;
}
static bool input(bg_input in[4]){
    bool was_paused=paused;inputs++;memset(in,0,sizeof(bg_input)*4);
    if(scenario==3)paused=fake_now>=10000&&fake_now<210000;
    if(scenario==4&&fake_now>=20000)views=2;
    if(scenario==6&&fake_now>=20000)shell=paused=true;
    if(fake_now>=5000&&!edge_sent){edge_sent=true;in[0].reload=true;}
    if(fake_now>=11000&&!zoom_sent){zoom_sent=true;in[0].zoom=true;}
    in[0].forward=.75f;in[0].fire=true;
    /* A released use button must not survive as a latched edge. */
    in[0].interact=fake_now<16000;
    if(paused||was_paused)memset(in,0,sizeof(bg_input)*4);
    return paused||was_paused;
}
'''
TEST = r'''
static void run(unsigned kind){
    scenario=kind;fake_now=1;views=kind==7?3:4;paused=kind==2;shell=false;
    inputs=pumps=acquired=paced_dropped_ticks=0;edge_sent=zoom_sent=false;
#ifdef BG_PRESENT_TRACK
    present_tracker=(bg_present30_tracker){0};
    if(kind==5)present_tracker.draining=1;
#endif
    available_at=(kind==1||kind==3)?350001:0;
    blam_clock clock;blam_clock_reset(&clock);
    bg_input latch[4]={{0}},in[4]={{0}};
    uint64_t previous=1,ui_deadline=(kind==2||kind==6)?50000:UINT64_MAX;
    unsigned ticks=99;bool first=false;
    assert(paced_acquire(&clock,&previous,latch,in,&ticks,&first,&ui_deadline)==&screen);
    assert(acquired==1&&pumps&&inputs>1&&frame_sample_us<=fake_now);
    assert(ticks<=7&&clock.ticks==ticks);
    if(kind==0||kind==7){
        assert(ticks==1&&fake_now>=33333&&fake_now<35000);
        assert(in[0].reload&&in[0].zoom&&in[0].fire&&latch[0].reload&&latch[0].zoom);
        assert(presentation&&!paced_dropped_ticks&&!in[0].interact&&!latch[0].interact);
    }else if(kind==1){
        assert(ticks==7&&paced_dropped_ticks>=3&&clock.leftover_dt==0);
        assert(in[0].reload&&in[0].zoom&&in[0].fire);
    }else if(kind==2){
        assert(ticks==0&&paused&&fake_now>=50000&&!in[0].fire&&!latch[0].reload);
    }else if(kind==3){
        assert(!paused&&ticks>=3&&ticks<=4&&!paced_dropped_ticks);
        assert(!in[0].reload&&!in[0].zoom&&in[0].fire);
    }else if(kind==6){
        assert(shell&&paused&&!presentation&&ticks==0&&fake_now>=50000);
        assert(!in[0].fire&&!latch[0].reload&&!latch[0].zoom);
    }else if(kind==4){
        assert(views==2&&!presentation&&ticks==0&&fake_now>=20000&&fake_now<22000);
        assert(latch[0].reload&&latch[0].zoom); /* consumed only by a future tick */
#ifdef BG_PRESENT_TRACK
    }else if(kind==5){
        assert(fake_now>=80000&&ticks==2&&presentation&&!paced_dropped_ticks);
        assert(in[0].reload&&in[0].zoom&&in[0].fire);
#endif
    }
}
int main(void){
    for(unsigned i=0;i<5;i++)run(i);run(6);run(7);
#ifdef BG_PRESENT_TRACK
    run(5);
#endif
    puts("Actual paced_acquire: fresh-pose gate, input edges, 350ms stall cap, paused UI, resume 3/4-player pacing, shell transition and 4->2 view transition pass.");
}
'''

if __name__ == '__main__':
    main=read_runtime(ROOT/'port/n64/main.c')
    body=function(main,'paced_acquire')
    signature='static surface_t*paced_acquire(blam_clock*clock,uint64_t*previous,bg_input latch[4],bg_input in[4],unsigned*ticks,bool*first,uint64_t*ui_deadline)'
    OUT.mkdir(parents=True,exist_ok=True)
    source=OUT/'gate.c';source.write_text(PRELUDE+signature+'{'+body+'}\n'+TEST)
    for buffers in (3,4,5):
        binary=OUT/f'gate{buffers}'
        extra=['-DBG_PRESENT_TRACK',f'-DBG_PACED30_BUFFERS={buffers}'] if buffers>=4 else []
        subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror',
                        '-fsanitize=address,undefined','-I'+str(ROOT/'port/n64'),*extra,
                        str(source),str(ROOT/'port/n64/blam/runtime.c'),'-lm','-o',str(binary)],check=True)
        subprocess.run([str(binary)],check=True)
