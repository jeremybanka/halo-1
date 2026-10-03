"""Keep early depth clearing independent of CPU frame preparation.

This checks the reviewed call boundary and SDK implementation, not GPU timing.
Optional before/after comparison requires every rendering command to remain
identical; only the attach/clear placement and its profiling attribution move.
"""
import argparse
from pathlib import Path
import re
from test_render_matrix import compact, function

ROOT = Path(__file__).resolve().parents[2]
EXTERNAL = set('''CachedAddr assertf bg_projectile_at bg_raycast
    bg_bounds_expand bg_bounds_quantize bg_bounds_transform bg_bounds_union
    bg_motion_decode bg_motion_scatter blam_quaternions_interpolate_and_normalize
    data_cache_hit_writeback floorf fmaxf fminf fabsf sqrtf sinf cosf get_ticks_us memcpy memset memcmp bg_vehicle_pose_key
    t3d_mat4_from_srt_euler t3d_mat4_from_srt t3d_mat4_to_fixed_3x4 t3d_mat4_mul
    t3d_mat4fp_set_pos t3d_mat3_mul_vec3 t3d_mat4fp_from_srt_euler
    t3d_vertbuffer_get_color t3d_frustum_vs_aabb_s16 t3d_viewport_look_at
    t3d_viewport_set_area t3d_viewport_set_projection'''.split())


def calls(body):
    body = re.sub(r'/\*.*?\*/|//[^\n]*', '', body, flags=re.S)
    # A pointer-to-array cast such as (float (*)[4]) is not a function call.
    return set(re.findall(r'\b([A-Za-z_]\w*)\s*\(', body)) - {'if', 'for', 'while', 'switch', 'sizeof', 'return', 'float'}


def check(main, sdk, tiny, before=None):
    source = main.read_text()
    # Follow the actual inline projection helpers too, rather than allowing an
    # unchecked external call across the CPU-only preparation boundary.
    helpers = source + '\n' + '\n'.join((main.parent/name).read_text() for name in
        ('render_micro_lod.h', 'render_lod.h', 'hud_layout.h', 'render_visibility.h'))
    visited = set()

    def visit(name):
        if name in visited:
            return
        visited.add(name)
        for call in calls(function(helpers, name)):
            if call not in EXTERNAL:
                # Unknown calls must resolve to a reviewed local CPU helper.
                # A new draw/queue call fails instead of silently crossing this boundary.
                visit(call)

    visit('prepare_frame')
    api = (tiny / 'src/t3d/t3d.c').read_text()
    header = (tiny / 'src/t3d/t3d.h').read_text()
    for text, names in ((api, ('t3d_viewport_set_projection', 't3d_viewport_set_perspective',
                              't3d_viewport_look_at')), (header, ('t3d_viewport_set_area',
                                                               't3d_viewport_set_w_normalize'))):
        for name in names:
            body = function(text, name)
            assert not any(token in body for token in ('rspq_', 'rdpq_', 't3d_matrix_set', 't3d_viewport_attach'))
    attach = (sdk / 'src/rdpq/rdpq_attach.c').read_text()
    assert 'rdpq_detach();' in compact(function(attach, '__rdpq_clear_z'))
    assert 'detach();' in compact(function(attach, 'rdpq_detach_cb'))
    assert 'rspq_flush();' in compact(function(attach, 'detach'))

    loop = compact(function(source, 'main'))
    clear = 'rdpq_attach(screen,&depth);rdpq_clear_z(ZBUF_MAX);'
    fence = 'if(pending[slot])while(!rspq_syncpoint_check(fences[slot]))pump_audio();'
    assert loop.count(clear) == 1
    assert loop.index(fence) < loop.index(clear) < loop.index('prepare_frame();') < loop.index('draw_view(p);')
    if before:
        old = compact(before.read_text()).replace(clear, '')
        new = compact(source).replace(clear, '')
        new = new.replace('#ifdefBG_PROFILEuint64_tattach_us=get_ticks_us()-profile_start;profile_start=get_ticks_us();#endif', '')
        new = new.replace('draw_us=get_ticks_us()-profile_start+attach_us;', 'draw_us=get_ticks_us()-profile_start;')
        assert old == new, 'Changes beyond the attach/clear movement and profiling attribution'
    print(f'PASS: {len(visited)} CPU-only local preparation helpers; SDK viewport setters enqueue nothing; '
          'clear wakes asynchronously after slot fence; draw command order preserved.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk-source', type=Path, default=ROOT.parent / 'n64-2048/.build/libdragon-src')
    parser.add_argument('--tiny3d', type=Path, default=ROOT.parent / 'n64-3d-splitscreen/.build/tiny3d')
    parser.add_argument('--before', type=Path)
    args = parser.parse_args()
    check(ROOT / 'port/n64/main.c', args.sdk_source, args.tiny3d, args.before)
