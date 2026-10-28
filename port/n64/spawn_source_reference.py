"""Compile the original spawn-rating bodies, with only engine storage stubbed.

No private coordinates are baked into this test. The runtime supplies live
map starts and unit origins. This tests weighting, not original unit lifecycle,
scenario eligibility, vehicle queries or the complete Xbox engine.
"""
from pathlib import Path
import re
from test_render_matrix import function

ROOT = Path(__file__).resolve().parents[2]


def generate(output):
    engine = (ROOT / 'source/game/game_engine.c').read_text()
    ctf = (ROOT / 'source/game/game_engine_ctf.c').read_text()
    math = (ROOT / 'source/math/real_math.h').read_text()
    # Bind the few storage-adapter assumptions to their source definitions.
    assert re.search(r'CTF_STARTING_LOCATION_RATING_WARMUP\s*=\s*TICKS_PER_SECOND', ctf)
    assert re.search(r'TICKS_PER_SECOND\s*=\s*30', (ROOT / 'source/cseries/cseries.h').read_text())
    init = function(ctf, 'ctf_engine_initialize_for_new_map')
    swap = re.search(r'flag_slot = team_index;\s*if \(game_engine_get_variant\(\)->game_engine_variant.ctf.assault\)\s*flag_slot = \(team_index \+ 1\) % 2;', init)
    assert swap, 'Source flag-slot initialization changed'
    code = r'''
#include <math.h>
#include "test_spawn_reference.h"
#define NONE (-1)
#define FALSE false
#define PIN(x,lo,hi) ((x)<(lo)?(lo):((x)>(hi)?(hi):(x)))
enum { CTF_STARTING_LOCATION_RATING_WARMUP=30 };
typedef float real;
typedef bool boolean;
typedef struct { real x,y,z; } real_point3d;
typedef struct { real i,j,k; } real_vector3d;
struct player_datum { int team_index,unit_index; };
struct player_starting_location { real_point3d position; int team_index; };
struct scenario_netgame_flag { real_point3d position; };
struct data_iterator { unsigned index; };
struct variant {
    struct { bool teams; } universal_variant;
    struct { struct { bool assault; } ctf; } game_engine_variant;
};
static struct variant global_variant;
static struct { real (*starting_location_rating)(long,struct player_starting_location const *); }
    engine_storage, *game_engine=&engine_storage;
static struct player_datum player_data[4];
static real_point3d origins[4];
static struct scenario_netgame_flag authored_flags[2];
static struct { struct scenario_netgame_flag *flags[2]; } ctf_globals;
static const spawn_reference_state *state;
static struct player_datum *player_get(long p) { return &player_data[p]; }
static void data_iterator_new(struct data_iterator *i,void *data) { i->index=0; }
static void *data_iterator_next(struct data_iterator *i) {
    return i->index<state->count?&player_data[i->index++]:0;
}
static void object_get_origin(int unit,real_point3d *p) { *p=origins[unit]; }
static bool game_engine_running(void) { return true; }
static bool game_engine_test_flag(long flag) { return flag==0&&state->ctf; }
static bool game_engine_has_teams(void) { return state->teams; }
static struct variant *game_engine_get_variant(void) { return &global_variant; }
static long game_time_get(void) { return state->ticks; }
'''
    signatures = [
        (math, 'real square_root(real x)'),
        (math, 'real_vector3d *vector_from_points3d(real_point3d const *a, real_point3d const *b, real_vector3d *result)'),
        (math, 'real magnitude_squared3d(real_vector3d const *v)'),
        (math, 'real distance_squared3d(real_point3d const *a, real_point3d const *b)'),
        (math, 'real distance3d(real_point3d const *a, real_point3d const *b)'),
        (engine, 'real game_engine_get_distance_rating_for_spawn(long player_index, real_point3d const *position)'),
        (engine, 'real game_engine_get_friendly_bonus(long player_index, real_point3d const *position)'),
        (ctf, 'real ctf_engine_starting_location_rating(long player_index, struct player_starting_location const *starting_location)'),
        (engine, 'real default_starting_location_rate_function(long player_index, struct player_starting_location const *starting_location)'),
    ]
    for source, signature in signatures:
        name = re.search(r'(\w+)\(', signature)[1]
        code += '\nstatic ' + signature + ' {' + function(source, name) + '}\n'
    code += r'''
static real_point3d source_point(const float p[3]) {
    return (real_point3d){p[0],-p[2],p[1]};
}
float spawn_reference_rating(const spawn_reference_state *s,unsigned player,
                             const float pos[3],int team) {
    state=s;
    global_variant.universal_variant.teams=s->teams;
    global_variant.game_engine_variant.ctf.assault=s->assault;
    for(unsigned i=0;i<s->count;i++) {
        player_data[i]=(struct player_datum){s->teams?s->players[i].team:i,
                                            s->players[i].present?(int)i:NONE};
        origins[i]=source_point(s->players[i].pos);
    }
    for(long team_index=0;team_index<2;team_index++) {
        long flag_slot;
        SLOT_SWAP
        authored_flags[team_index].position=source_point(s->flags[team_index]);
        ctf_globals.flags[flag_slot]=&authored_flags[team_index];
    }
    game_engine->starting_location_rating=s->ctf?ctf_engine_starting_location_rating:0;
    struct player_starting_location start={source_point(pos),team};
    return default_starting_location_rate_function(player,&start);
}
'''.replace('SLOT_SWAP', swap[0])
    output.write_text(code)
