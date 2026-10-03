"""Check nonblocking batch wakeups against the installed libdragon implementation."""
import argparse
from pathlib import Path
from test_render_matrix import compact, function

ROOT = Path(__file__).resolve().parents[2]


def check(main, sdk, before=None):
    source=main.read_text();view=compact(function(source,'draw_view'))
    assert view.count('rspq_flush();')==1
    assert view.index('rspq_block_run(world_blocks[b]);') < view.index('rspq_flush();') < view.index('t3d_matrix_push_pos(1);')
    loop=compact(function(source,'main'))
    assert 'for(unsignedp=0;p<views;p++){draw_view(p);rspq_flush();pump_audio();}' in loop
    queue=(sdk/'src/rspq/rspq.c').read_text()
    flush=compact(function(queue,'rspq_flush'))
    wake=compact(function(queue,'rspq_flush_internal'))
    assert 'if(rspq_block)return;' in flush and 'rspq_flush_internal();' in flush
    assert wake.count('*SP_STATUS=SP_WSTATUS_SET_SIG_MORE|SP_WSTATUS_CLEAR_HALT|SP_WSTATUS_CLEAR_BROKE;')==2
    for forbidden in ('rspq_int_write','rspq_write','rspq_wait','rspq_syncpoint','RSP_WAIT_LOOP'):
        assert forbidden not in flush and forbidden not in wake, forbidden
    header=(sdk/'include/rspq.h').read_text()
    assert 'writing a command via #rspq_write is not enough' in header
    assert 'This function does not block' in header
    if before:
        # A complete source comparison excludes only comments/whitespace and
        # wakeup calls. Every graphics command, fence, state change and mixer
        # call must remain at its prior position in the command sequence.
        assert compact(before.read_text()).replace('rspq_flush();','')==compact(source).replace('rspq_flush();','')
    print('Terrain/view wakeups precede audio; SDK flush neither waits nor adds queue commands; source command sequence unchanged.' if before else
          'Terrain/view wakeups precede audio; installed SDK flush neither waits nor adds queue commands.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sdk-source',type=Path,default=ROOT.parent/'n64-2048/.build/libdragon-src')
    p.add_argument('--before',type=Path)
    args=p.parse_args();check(ROOT/'port/n64/main.c',args.sdk_source,args.before)
