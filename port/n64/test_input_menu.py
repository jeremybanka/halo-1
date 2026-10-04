"""Exercise the actual main input adapter with SDK types and fake controllers.

Only controller reads and game actions are mocked. control_buttons(), input(),
and the normal frame's input-latch block are extracted from main.c; the actual
menu and controls implementations are linked. This checks CPU behavior, not
controller hardware or rendered menu appearance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from test_render_matrix import function

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/n64/test-input-menu'

PRELUDE = r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "menu.h"
static bg_menu menu;
static bool paused;
static bool scores[4];
static unsigned views,polls,resets,view_resets,sets,last_set;
static unsigned reads[3][4];
static float game_time;
bg_player bg_players[BG_PLAYERS];
static joypad_inputs_t physical[4],snapshot[4];
static joypad_buttons_t previous[4],edges[4];
static void joypad_poll(void){
    polls++;
    for(unsigned p=0;p<4;p++){
        snapshot[p]=physical[p];edges[p].raw=snapshot[p].btn.raw&~previous[p].raw;
        previous[p]=snapshot[p].btn;
    }
}
static joypad_inputs_t joypad_get_inputs(unsigned p){assert(p<4);reads[0][p]++;return snapshot[p];}
static joypad_buttons_t joypad_get_buttons(unsigned p){assert(p<4);reads[1][p]++;return snapshot[p].btn;}
static joypad_buttons_t joypad_get_buttons_pressed(unsigned p){assert(p<4);reads[2][p]++;return edges[p];}
void bg_reset(void){resets++;for(unsigned p=0;p<4;p++)bg_players[p].vehicle=-1;}
static void reset_view_state(void){view_resets++;}
void bg_set_players(unsigned n){sets++;last_set=n;assert(n==1||n==2||n==4);}
'''

TEST = r'''
static unsigned comparisons;
#define FIELDS(X) X(forward) X(strafe) X(turn) X(look) X(jump) X(fire) X(reload) \
 X(switch_weapon) X(grenade) X(switch_grenade) X(interact) X(melee) X(zoom) X(crouch) X(secondary_fire)
static void same(const bg_input *a,const bg_input *b){
#define CHECK(f) assert(a->f==b->f);
    FIELDS(CHECK)
#undef CHECK
    comparisons++;
}
static void all_zero(const bg_input in[4]){
    const bg_input zero={0};for(unsigned p=0;p<4;p++)same(&in[p],&zero);
}
static const joypad_buttons_t physical_buttons[]={
    {.a=1},{.b=1},{.l=1},{.r=1},{.z=1},{.start=1},
    {.d_up=1},{.d_down=1},{.d_left=1},{.d_right=1},
    {.c_up=1},{.c_down=1},{.c_left=1},{.c_right=1}
};
static const uint32_t logical_buttons[]={
    BG_BUTTON_A,BG_BUTTON_B,BG_BUTTON_L,BG_BUTTON_R,BG_BUTTON_Z,BG_BUTTON_START,
    BG_BUTTON_D_UP,BG_BUTTON_D_DOWN,BG_BUTTON_D_LEFT,BG_BUTTON_D_RIGHT,
    BG_BUTTON_C_UP,BG_BUTTON_C_DOWN,BG_BUTTON_C_LEFT,BG_BUTTON_C_RIGHT
};
static joypad_buttons_t physical_bits(uint32_t logical){
    joypad_buttons_t result={0};
    for(unsigned b=0;b<14;b++)if(logical&logical_buttons[b])result.raw|=physical_buttons[b].raw;
    return result;
}
static void init(unsigned count){
    memset(physical,0,sizeof(physical));memset(snapshot,0,sizeof(snapshot));
    memset(previous,0,sizeof(previous));memset(edges,0,sizeof(edges));
    memset(reads,0,sizeof(reads));memset(bg_players,0,sizeof(bg_players));
    memset(scores,0,sizeof(scores));
    for(unsigned p=0;p<4;p++)bg_players[p].vehicle=-1;
    views=count;paused=false;polls=resets=view_resets=sets=last_set=0;game_time=27.5f;
    bg_menu_init(&menu,count);
}
static void read_test(void){
    for(unsigned r=0;r<3;r++)for(unsigned p=0;p<4;p++)assert(reads[r][p]==polls);
}
static bool frame(unsigned p,uint32_t buttons,bg_input out[4]){
    memset(physical,0,sizeof(physical));physical[p].btn=physical_bits(buttons);
    bool consumed=input(out);read_test();return consumed;
}
static bool tap(unsigned p,uint32_t buttons,bg_input out[4]){
    frame(p,0,out);return frame(p,buttons,out);
}
static void adapter_test(void){
    assert(sizeof(joypad_buttons_t)==2);
    for(unsigned raw=0;raw<=65535;raw++){
        joypad_buttons_t buttons={.raw=raw};uint32_t expected=0;
        for(unsigned b=0;b<14;b++)if(buttons.raw&physical_buttons[b].raw)expected|=logical_buttons[b];
        assert(control_buttons(buttons)==expected);comparisons++;
    }
    for(unsigned count=1;count<=4;count*=2)for(unsigned style_mask=0;style_mask<16;style_mask++)
    for(unsigned b=0;b<14;b++)if(logical_buttons[b]!=BG_BUTTON_START){
        init(count);
        for(unsigned p=0;p<4;p++){
            menu.styles[p]=(style_mask&(1u<<p))?BG_CONTROLS_XBOX:BG_CONTROLS_N64;
            physical[p].btn=physical_buttons[b];
            physical[p].stick_x=(int8_t)(-67+35*p);physical[p].stick_y=(int8_t)(71-41*p);
            bg_players[p].vehicle=p%2?-1:0;
        }
        for(unsigned held_frame=0;held_frame<2;held_frame++){
            bg_input actual[4];memset(actual,0x5a,sizeof(actual));assert(!input(actual));
            for(unsigned p=0;p<4;p++){
                bg_input expected={0};
                if(p<count){
                    bg_control_state raw={.stick_x=physical[p].stick_x,.stick_y=physical[p].stick_y,
                        .held=logical_buttons[b],.pressed=held_frame?0:logical_buttons[b]};
                    bg_controls_map(&expected,&raw,menu.styles[p],bg_players[p].vehicle>=0);
                }
                same(&actual[p],&expected);
                assert(scores[p]==(p<count&&menu.styles[p]==BG_CONTROLS_XBOX&&logical_buttons[b]==BG_BUTTON_R));
            }
        }
        read_test();assert(!resets&&!sets&&!view_resets);
    }
}
static void owner_style_test(void){
    bg_input out[4];init(4);
    assert(tap(2,BG_BUTTON_START|BG_BUTTON_A|BG_BUTTON_Z,out));all_zero(out);
    assert(paused&&menu.open&&menu.owner==2&&menu.page==BG_MENU_ROOT);
    assert(frame(2,BG_BUTTON_START|BG_BUTTON_A|BG_BUTTON_Z,out));all_zero(out);
    assert(tap(1,BG_BUTTON_A|BG_BUTTON_D_DOWN,out));all_zero(out);assert(menu.row==0);
    tap(2,BG_BUTTON_D_DOWN,out);assert(menu.row==BG_MENU_CONTROLS_ROW);
    tap(2,BG_BUTTON_A,out);assert(menu.page==BG_MENU_CONTROLS&&menu.styles[2]==BG_CONTROLS_N64);
    tap(2,BG_BUTTON_D_RIGHT,out);assert(menu.styles[2]==BG_CONTROLS_XBOX);
    for(unsigned p=0;p<4;p++)if(p!=2)assert(menu.styles[p]==BG_CONTROLS_N64);
    tap(2,BG_BUTTON_START|BG_BUTTON_A|BG_BUTTON_Z,out);all_zero(out);assert(!paused);
    frame(2,BG_BUTTON_C_LEFT|BG_BUTTON_D_UP,out);
    assert(out[2].reload&&out[2].interact&&out[2].forward==1&&!out[2].switch_weapon);
    frame(2,BG_BUTTON_C_UP|BG_BUTTON_D_UP,out);
    assert(out[2].switch_weapon&&out[2].forward==1&&!out[2].reload&&!out[2].interact&&!out[2].zoom&&!scores[2]);
    frame(2,BG_BUTTON_R|BG_BUTTON_D_UP,out);
    assert(out[2].forward==1&&!out[2].switch_weapon&&!out[2].reload&&!out[2].interact&&!out[2].zoom&&scores[2]);
    frame(2,BG_BUTTON_R|BG_BUTTON_C_UP|BG_BUTTON_D_UP,out);
    assert(out[2].switch_grenade&&!out[2].zoom&&!out[2].switch_weapon&&!out[2].reload&&!out[2].interact&&scores[2]);
    frame(2,BG_BUTTON_R|BG_BUTTON_C_UP|BG_BUTTON_D_UP,out);
    assert(!out[2].switch_grenade&&!out[2].zoom&&!out[2].switch_weapon&&scores[2]); /* held chord has no repeat edge */
    frame(2,BG_BUTTON_C_UP|BG_BUTTON_D_UP,out);
    assert(!out[2].switch_grenade&&!out[2].zoom&&!out[2].switch_weapon&&!scores[2]); /* releasing R does not switch */
    frame(2,BG_BUTTON_C_RIGHT,out);
    assert(out[2].zoom&&!out[2].switch_grenade&&!out[2].switch_weapon);
    frame(2,BG_BUTTON_C_RIGHT,out);assert(!out[2].zoom); /* no held repeat */
    frame(2,BG_BUTTON_R,out);
    frame(2,BG_BUTTON_R|BG_BUTTON_C_RIGHT,out);
    assert(out[2].zoom&&!out[2].switch_grenade&&!out[2].switch_weapon&&scores[2]);
    frame(0,BG_BUTTON_R|BG_BUTTON_D_UP,out);assert(out[0].switch_weapon&&out[0].zoom&&!out[0].reload&&!scores[0]);
    frame(0,BG_BUTTON_C_LEFT,out);assert(out[0].strafe==-1&&!out[0].reload&&!out[0].interact&&!out[0].switch_weapon);
    tap(2,BG_BUTTON_START|BG_BUTTON_R,out);all_zero(out);assert(paused&&!scores[2]);
    frame(2,BG_BUTTON_R,out);all_zero(out);assert(!scores[2]);
    frame(2,BG_BUTTON_START|BG_BUTTON_R,out);all_zero(out);assert(!paused&&!scores[2]);
    frame(2,BG_BUTTON_R,out);assert(scores[2]);
    frame(2,0,out);assert(!scores[2]);
    assert(!resets&&!sets&&!view_resets);
}
static void resume_and_latch_test(void){
    const uint32_t resume[]={BG_BUTTON_A,BG_BUTTON_B,BG_BUTTON_START};
    for(unsigned p=0;p<4;p++)for(unsigned choice=0;choice<3;choice++){
        init(4);bg_input out[4],latch[4]={0};
        for(unsigned q=0;q<4;q++)latch[q].reload=latch[q].jump=latch[q].zoom=true;
        physical[p].btn=physical_bits(BG_BUTTON_START|BG_BUTTON_A|BG_BUTTON_Z);
        poll_latched(out,latch);all_zero(out);all_zero(latch);assert(paused);
        memset(physical,0,sizeof(physical));poll_latched(out,latch);all_zero(out);
        physical[p].btn=physical_bits(resume[choice]|BG_BUTTON_Z);
        poll_latched(out,latch);all_zero(out);all_zero(latch);assert(!paused);
        assert(!resets&&!sets&&!view_resets);
    }
}
static void setup_test(void){
    bg_input out[4];init(4);
    menu.styles[0]=BG_CONTROLS_XBOX;menu.styles[2]=BG_CONTROLS_XBOX;
    tap(0,BG_BUTTON_START,out);tap(0,BG_BUTTON_D_DOWN,out);tap(0,BG_BUTTON_A,out);
    assert(menu.page==BG_MENU_SETUP&&!sets);
    const unsigned counts[]={1,2,4};
    for(unsigned n=0;n<3;n++){
        tap(0,BG_BUTTON_D_RIGHT,out);all_zero(out);
        assert(views==counts[n]&&last_set==views&&sets==n+1&&paused);
        assert(menu.styles[0]==BG_CONTROLS_XBOX&&menu.styles[2]==BG_CONTROLS_XBOX);
        if(views<4){
            unsigned owner=menu.owner,row=menu.row;
            tap(3,BG_BUTTON_START|BG_BUTTON_A|BG_BUTTON_D_DOWN,out);all_zero(out);
            assert(menu.owner==owner&&menu.row==row&&menu.page==BG_MENU_SETUP);
        }
    }
    tap(0,BG_BUTTON_D_DOWN,out);tap(0,BG_BUTTON_A|BG_BUTTON_Z,out);all_zero(out);
    assert(resets==1&&view_resets==1&&game_time==0&&!paused&&views==4);
    assert(menu.styles[0]==BG_CONTROLS_XBOX&&menu.styles[2]==BG_CONTROLS_XBOX);
    tap(0,BG_BUTTON_START,out);tap(0,BG_BUTTON_D_DOWN,out);tap(0,BG_BUTTON_A,out);
    tap(3,BG_BUTTON_START|BG_BUTTON_A,out);all_zero(out);
    assert(menu.owner==3&&menu.page==BG_MENU_ROOT&&menu.row==0);
    tap(3,BG_BUTTON_D_DOWN,out);assert(menu.row==BG_MENU_CONTROLS_ROW);
    tap(3,BG_BUTTON_A,out);assert(menu.page==BG_MENU_CONTROLS&&resets==1&&sets==3);
    tap(3,BG_BUTTON_START,out);assert(!paused);
    views=1;menu.player_count=1;
    assert(!tap(3,BG_BUTTON_START|BG_BUTTON_Z|BG_BUTTON_A,out));all_zero(out);assert(!paused);
}
static void simultaneous_and_stick_test(void){
    init(4);bg_input out[4];input(out);
    physical[3].btn=physical_bits(BG_BUTTON_START);physical[1].btn=physical_bits(BG_BUTTON_START|BG_BUTTON_A);
    physical[1].stick_y=-80;physical[2].stick_y=-80;
    assert(input(out));all_zero(out);assert(menu.owner==1&&menu.row==0);
    physical[1].btn.raw=physical[3].btn.raw=0;
    for(unsigned n=0;n<5;n++){input(out);assert(menu.row==0);all_zero(out);}
    physical[2].btn=physical_bits(BG_BUTTON_START);input(out);assert(menu.owner==2&&menu.row==0);
    physical[2].btn.raw=0;input(out);assert(menu.row==0);
    physical[2].stick_y=0;input(out);physical[2].stick_y=-80;input(out);
    assert(menu.row==BG_MENU_CONTROLS_ROW);all_zero(out);
    assert(!resets&&!sets);
}
int main(void){
    adapter_test();owner_style_test();resume_and_latch_test();setup_test();simultaneous_and_stick_test();
    printf("PASS: %u actual-main input comparisons; SDK fields, independent layouts, ownership, no-leak transitions, setup, restart, inactive ports and analog rearm\n",comparisons);
}
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk', type=Path, default=ROOT.parent/'n64-2048/.build/libdragon')
    parser.add_argument('--out', type=Path, default=OUT, help='Proof/output directory; use a new path to retain an earlier run')
    args = parser.parse_args()
    OUT = args.out.resolve()
    sdk_header = args.sdk/'mips64-elf/include/joypad.h'
    sdk = sdk_header.read_text()
    typedefs = []
    for start, end in [('typedef union joypad_buttons_u', '} joypad_buttons_t;'),
                       ('typedef struct __attribute__((packed)) joypad_inputs_s', '} joypad_inputs_t;')]:
        offset = sdk.index(start)
        typedefs.append(sdk[offset:sdk.index(end, offset)+len(end)])
    main_path = ROOT/'port/n64/main.c'
    main = main_path.read_text()
    functions = ('static uint32_t control_buttons(joypad_buttons_t buttons){'+function(main, 'control_buttons')+'}\n'
                 'static bool input(bg_input in[4]){'+function(main, 'input')+'}\n')
    marker = 'bg_input in[4]={0};if(input(in))memset(latch,0,sizeof(latch));clock.paused=paused;'
    start = main.index(marker)
    block = main[start:main.index('unsigned ticks=blam_clock_update', start)]
    # sizeof(latch) was an array in main; retain that actual type inside this wrapper.
    wrapper = ('static void poll_latched(bg_input out[4],bg_input pending[4]){\n'
               'struct {bool paused;} clock={0};bg_input latch[4];memcpy(latch,pending,sizeof(latch));\n'+block+
               '\nassert(clock.paused==paused);memcpy(out,in,sizeof(in));memcpy(pending,latch,sizeof(latch));}\n')
    OUT.mkdir(parents=True, exist_ok=True)
    source = OUT/'actual_input.c'
    source.write_text('#include <stdint.h>\n'+'\n'.join(typedefs)+'\n'+PRELUDE+functions+wrapper+TEST)
    outputs = {}
    for mode, flags in [('strict', []), ('target-math', ['-ffast-math', '-ftrapping-math', '-fno-associative-math'])]:
        binary = OUT/('input-'+mode)
        subprocess.run(['clang', '-std=c11', '-O2', '-g', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=address,undefined', '-fno-omit-frame-pointer', *flags,
                        '-I'+str(ROOT/'port/n64'), str(source), str(ROOT/'port/n64/menu.c'),
                        str(ROOT/'port/n64/controls.c'), '-lm', '-o', str(binary)], check=True)
        outputs[mode] = subprocess.check_output([str(binary)], text=True).strip()
        print(outputs[mode])
    paths = [main_path, ROOT/'port/n64/menu.h', ROOT/'port/n64/menu.c',
             ROOT/'port/n64/controls.h', ROOT/'port/n64/controls.c', sdk_header, Path(__file__), source]
    (OUT/'proof.json').write_text(json.dumps({'status': 'pass', 'checks': outputs,
        'scope': 'Actual CPU adapter/latch/menu/controls; mocked controller snapshots and game actions; no target performance claim.',
        'sha256': {str(path): sha(path) for path in paths}}, indent=2)+'\n')
