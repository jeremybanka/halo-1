"""Check deferred first-view pumping without changing PCM or voice progression."""
from runtime_source import read_runtime, validation_output
import argparse
from pathlib import Path
import re
import subprocess
from test_render_matrix import compact, function

ROOT = Path(__file__).resolve().parents[2]


def check_source(before=None):
    source = read_runtime(ROOT/'port/n64/main.c')
    main = compact(function(source, 'main'))
    assert 'pump_audio();#ifdefBG_PROFILEsim_us=' not in main
    assert 'if(pending[slot])while(!rspq_syncpoint_check(fences[slot]))pump_audio();' in main
    assert 'for(unsignedp=0;p<views;p++){triangles=bg_scene_draw(p);rspq_flush();pump_audio();}' in main
    assert 'while(!(screen=display_try_get()))pump_audio();' in main
    assert 'pump_audio();' in function(source, 'paced_acquire')
    # Between the removed refill and the retained first-view refill there is
    # no simulation tick, event processing, or voice update. RSP callbacks do
    # not invoke any sound API either. Extra consumed buffers therefore append
    # samples from the same voice state, without skipping/restarting voices.
    for name in ('prepare_frame', 'draw_view', 'frame_complete', 'paced_vi'):
        assert not re.search(r'\bbg_sound_\w+\s*\(', function(source, name)), name
    if before:
        old = before.read_text()
        expected = compact(function(old, 'main'))
        token = 'pump_audio();#ifdefBG_PROFILEsim_us='
        assert expected.count(token) == 1
        expected = expected.replace(token, '#ifdefBG_PROFILEsim_us=')
        assert main == expected, 'Main control flow changed beyond the single deferred pump'
        for name in ('prepare_frame', 'draw_view', 'frame_complete', 'paced_vi', 'paced_acquire'):
            assert function(source,name) == function(old,name), name


C_TEST = r'''
#include "sound_mix.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static uint32_t seed=0xCE064;
static uint32_t rnd(void){seed=1664525u*seed+1013904223u;return seed;}
int main(void){
    static int8_t samples[14][4096];
    static int16_t a[10560],b[10560];
    bg_audio_asset clips[14];unsigned checked=0;
    for(unsigned trial=0;trial<400;trial++){
        bg_sound_voice original[14]={0},deferred[14];
        for(unsigned c=0;c<14;c++){
            for(unsigned n=0;n<4096;n++)samples[c][n]=(int8_t)(rnd()>>24);
            clips[c]=(bg_audio_asset){samples[c],1+rnd()%4096,11025,false};
            original[c]=(bg_sound_voice){rnd()%5?&clips[c]:NULL,rnd()%clips[c].count,
                rnd()%65536,rnd()%262144,(int)(rnd()%257),(int)(rnd()%257),rnd()%2};
        }
        memcpy(deferred,original,sizeof(original));
        /* Hardware consumes between zero and six 880-frame buffers while
         * CPU graphics work runs. The refill boundary may move anywhere;
         * the concatenated output and final voice state must be identical. */
        unsigned buffers=1+rnd()%6,split=rnd()%(buffers+1),frames=buffers*880;
        bg_sound_mix(original,14,a,split*880);
        bg_sound_mix(original,14,a+split*1760,(buffers-split)*880);
        bg_sound_mix(deferred,14,b,frames);
        assert(!memcmp(a,b,frames*2*sizeof(*a)));
        for(unsigned c=0;c<14;c++){
            assert(original[c].asset==deferred[c].asset);
            assert(original[c].frame==deferred[c].frame);
            assert(original[c].fraction==deferred[c].fraction);
            assert(original[c].step==deferred[c].step);
        }
        checked+=frames;
    }
    printf("PASS: deferred refill boundaries preserve %u stereo PCM frames and all voice cursors.\n",checked);
}
'''


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--before',type=Path)
    args=p.parse_args();check_source(args.before)
    out=validation_output('audio-after-view');out.mkdir(parents=True,exist_ok=True)
    test=out/'test_refill.c';test.write_text(C_TEST)
    binary=out/'test_refill'
    subprocess.run(['clang','-std=c17','-O1','-g','-Wall','-Wextra','-Werror',
        '-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(ROOT/'port/n64'),
        str(test),str(ROOT/'port/n64/sound_mix.c'),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
    print('PASS: acquisition/slot/view refills retained; only pre-prepare pump removed; no intervening voice mutation.')
