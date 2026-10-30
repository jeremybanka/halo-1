"""CE grid/channel oracle and real skin/marker/collision/cache checks."""
import contextlib
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/player-aim/host'
OUT.mkdir(parents=True, exist_ok=True)
PROBE = r'''
#include "player_aim.h"
#include "interaction.h"
#include <string.h>
bg_player bg_players[BG_PLAYERS];
void fixture(float crouch,int state,float pitch,float time,float action){
 bg_player*p=&bg_players[0];memset(p,0,sizeof(*p));p->health=100;p->vehicle=-1;p->grounded=true;p->weapon=BG_W_AR;
 p->pitch=pitch;p->crouch_amount=crouch;p->locomotion_time=time;p->anim_time=action;p->fire_ticks[0]=10;
 if(state&1)p->velocity[0]=1;
 if(state&2){p->fire_ticks[0]=(unsigned)action;p->flash=.05f;}
 if(state&4){p->reload_duration=3;p->reload=3-action;}
 if(state&8){p->grounded=false;p->airborne_time=time;}
}
'''
(OUT / 'probe.c').write_text(PROBE)
subprocess.run(['clang', '-std=c17', '-O2', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror', '-Iport/n64',
                str(OUT / 'probe.c'), 'port/n64/player_aim.c', 'port/n64/blam/runtime.c',
                'build/n64/generated/player_animation_data.c', 'build/n64/generated/interaction_defs.c',
                'build/n64/generated/movement_data.c', '-lm', '-o', str(OUT / 'pose.dylib')], cwd=ROOT, check=True)
lib = C.CDLL(str(OUT / 'pose.dylib'))
F = C.c_float
class Node(C.Structure):
    _fields_ = [('q', F * 4), ('p', F * 3)]
class Screen(C.Structure):
    _fields_ = [('yaw', F * 2), ('pitch', F * 2), ('yaw_count', C.c_uint8 * 2), ('pitch_count', C.c_uint8 * 2)]
lib.fixture.argtypes = [F, C.c_int, F, F, F]
lib.bg_player_apply_aim.argtypes = [C.POINTER(Node), C.c_int, C.POINTER(Screen), F, F]
lib.bg_player_node_matrices.restype = C.POINTER(F)
lib.bg_player_skin_points.argtypes = [C.c_uint, C.c_uint, C.c_void_p]
lib.bg_player_animated_hits.argtypes = [C.c_uint, C.c_void_p, C.c_uint]
lib.bg_player_hand_transform.argtypes = [C.c_uint, C.c_void_p]
report = json.loads((ROOT / 'build/n64/generated/player-animation-report.json').read_text())
bank = (ROOT / 'build/n64/frontend-files/player-animation.bin').read_bytes()

def nlerp(a, b, t):
    value = a * (1 - t) + b * (t if np.dot(a, b) >= 0 else -t)
    return value / np.linalg.norm(value)

def mul(a, b):
    x, y, z, w = a; X, Y, Z, W = b
    return np.array([w*X+x*W+y*Z-z*Y, w*Y+y*W+z*X-x*Z, w*Z+z*W+x*Y-y*X, w*W-x*X-y*Y-z*Z])

# Read the actual uncompressed source records independently of the JMA export
# convention. This catches the extra default-frame offset in overlay exports.
with (OUT / 'source-load.log').open('w') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
    from reclaimer.meta.wrappers.halo1_map import Halo1Map
    h = Halo1Map(); h.load_map(ROOT / 'build/n64/assets/bloodgulch-decompressed.map')
entries = h.tag_index.tag_index
ix = next(i for i, t in enumerate(entries) if t.class_1.enum_name == 'model_animations' and t.path == r'characters\cyborg\cyborg')
graph = h.get_meta(ix); h.meta_to_tag_data(graph, 'antr', entries[ix])
grid_records = cases = 0
rng = np.random.default_rng(64)
for index, clip in enumerate(report['clips']):
    if 'aim-' not in clip['name'] and clip['name'] != 'stand look':
        continue
    source = graph.animations.STEPTREE[clip['source_index']]
    assert not source.flags.compressed_data
    raw = bytes(source.frame_data.STEPTREE)
    poses = np.array([np.frombuffer(bank, dtype='>i2', count=19 * 7,
                         offset=clip['offset'] + f * clip['stride']).reshape(19, 7)
                      for f in range(clip['frames'])], dtype=float)
    poses[:, :, :4] /= 32767
    poses[:, :, :4] /= np.linalg.norm(poses[:, :, :4], axis=2, keepdims=True)
    poses[:, :, 4:] /= 4096
    for f in range(clip['frames']):
        cursor = f * source.frame_size
        for node in range(19):
            if clip['rotations'] & (1 << node):
                q = np.array(struct.unpack_from('>4h', raw, cursor), dtype=float); cursor += 8
                q /= np.linalg.norm(q)
                assert abs(np.dot(q, poses[f, node, :4])) > .99999999, (clip['name'], f, node, q, poses[f,node,:4], np.dot(q,poses[f,node,:4]))
                grid_records += 1
            if clip['translations'] & (1 << node):
                p = struct.unpack_from('>3f', raw, cursor); cursor += 12
                assert np.max(np.abs(p - poses[f, node, 4:])) <= 1 / 8192 + 1e-7
                grid_records += 1
        assert cursor == (f + 1) * source.frame_size
    unit = next(u for u in graph.units.STEPTREE if u.label == ('crouch' if clip['name'].startswith('crouch') else 'stand'))
    obj = unit if clip['name'] == 'stand look' else next(w for w in unit.weapons.STEPTREE if w.name == 'rifle')
    screen = Screen((obj.right_yaw_per_frame, obj.left_yaw_per_frame),
                    (obj.down_pitch_per_frame, obj.up_pitch_per_frame),
                    (obj.right_frame_count, obj.left_frame_count), (obj.down_frame_count, obj.up_frame_count))
    width = sum(screen.yaw_count) + 1
    for yaw in [-4, -1.4923, -.73, 0, .73, 1.4923, 4]:
        for pitch in [-4, -1.4923, -.73, 0, .73, 1.4923, 4]:
            base = rng.normal(size=(19, 7)); base[:, :4] /= np.linalg.norm(base[:, :4], axis=1, keepdims=True)
            expected = base.copy()
            x = np.clip(yaw / screen.yaw[yaw >= 0] if screen.yaw[yaw >= 0] else 0,
                        -screen.yaw_count[0], screen.yaw_count[1]) + screen.yaw_count[0]
            y = np.clip(pitch / screen.pitch[pitch >= 0] if screen.pitch[pitch >= 0] else 0,
                        -screen.pitch_count[0], screen.pitch_count[1]) + screen.pitch_count[0]
            x0, y0 = int(x), int(y); x1, y1 = min(x0 + 1, width - 1), min(y0 + 1, sum(screen.pitch_count))
            a, b, c, d = [poses[yy * width + xx] for xx, yy in [(x0,y0),(x1,y0),(x0,y1),(x1,y1)]]
            for n in range(19):
                if clip['rotations'] & (1 << n):
                    q = nlerp(nlerp(a[n,:4], b[n,:4], x-x0), nlerp(c[n,:4], d[n,:4], x-x0), y-y0)
                    expected[n,:4] = mul(q, base[n,:4])
                if clip['translations'] & (1 << n):
                    expected[n,4:] += ((a[n,4:]*(1-x+x0)+b[n,4:]*(x-x0))*(1-y+y0) +
                                       (c[n,4:]*(1-x+x0)+d[n,4:]*(x-x0))*(y-y0))
            nodes = (Node * 19)(*[Node(tuple(row[:4]), tuple(row[4:])) for row in base])
            lib.bg_player_apply_aim(nodes, index, C.byref(screen), yaw, pitch)
            actual = np.array([[*n.q, *n.p] for n in nodes])
            assert np.max(np.abs(actual - expected)) < 1e-5, (clip['name'], yaw, pitch)
            cases += 1

# Independent original-mesh skinning oracle. This validates bone-local
# pretransforms and seam deduplication against the approved unmodified meshes.
world = json.loads((ROOT / 'build/n64/assets/extended-reduced.json').read_text())
mapping = json.loads((ROOT / 'build/n64/generated/world-mesh-sources.json').read_text())
inverse = np.ctypeslib.as_array((F * (19 * 12)).in_dll(lib, 'bg_player_inverse_bind')).reshape(19, 3, 4).copy()
meshes = []
for name, model in [('spartan', world['models']['spartan']), ('spartan_lod', world['spartan_lod'])]:
    corners = [(p, ws) for t in model['triangles'] for p, ws in zip(t['p'], t['weights'])]
    meshes.append([corners[i] for i in mapping[name]])
max_skin_error = 0
skin_samples = 0
radius = report['cull_radius']
for crouch in (0, .3, 1):
    for state in (0, 1, 2, 3, 4, 5, 8, 10):
        for time in (0, .19, .43):
            points_by_pitch = []
            for pitch in (-1.49225651, -.75, 0, .75, 1.49225651):
                lib.fixture(crouch, state, pitch, time, 1.2)
                revision = lib.bg_player_pose_revision(0)
                assert revision == lib.bg_player_pose_revision(0), 'Unchanged pose missed its cache'
                for lod, count in enumerate(report['vertices']):
                    out = np.zeros((count, 3), dtype=np.int16)
                    lib.bg_player_skin_points(0, lod, out.ctypes.data)
                    assert np.max(np.abs(out / 128)) <= radius
                    nodes = np.ctypeslib.as_array(lib.bg_player_node_matrices(0), shape=(19*12,)).reshape(19,3,4)
                    homogeneous = np.zeros((19,4,4)); homogeneous[:,:3] = inverse; homogeneous[:,3,3] = 1
                    skin = nodes @ homogeneous
                    reference = np.array([sum((skin[bone] @ [*p,1]) * weight for bone, weight in ws)
                                          for p, ws in meshes[lod]])[:, [0,2,1]] * [128,128,-128]
                    reference = np.trunc(reference + np.where(reference < 0, -.5, .5))
                    error = int(np.max(np.abs(out - reference)))
                    assert error <= 1, (crouch, state, time, pitch, lod, error)
                    max_skin_error = max(max_skin_error, error)
                    skin_samples += count
                hits = np.zeros((report['collision_vertices'], 3), dtype=np.int16)
                lib.bg_player_animated_hits(0, hits.ctypes.data, len(hits))
                hand = np.zeros((3, 4), dtype=np.float32)
                lib.bg_player_hand_transform(0, hand.ctypes.data)
                assert np.max(np.abs(hand[:, :3].T @ hand[:, :3] - np.eye(3))) < 1e-5
                assert np.max(np.abs(hand[:, 3])) <= radius
                points_by_pitch.append(hits)
            assert np.count_nonzero(points_by_pitch[0] != points_by_pitch[-1]) > 50
result = dict(source_grid_channels=grid_records, grid_oracle_cases=cases,
              skinned_vertex_samples=skin_samples, max_skin_error_quantization_units=max_skin_error,
              collision_marker_and_bounds=True)
(OUT / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
print('PASS', json.dumps(result))
