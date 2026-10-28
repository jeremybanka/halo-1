/* Host-only adapter to the recovered source routines. Coordinates use the
 * N64 frame at this boundary; the reference converts back to source axes. */
#ifndef TEST_SPAWN_REFERENCE_H
#define TEST_SPAWN_REFERENCE_H
#include <stdbool.h>
typedef struct {
    unsigned count, ticks;
    bool teams, ctf, assault;
    struct { float pos[3]; unsigned team; bool present; } players[4];
    float flags[2][3]; /* Authored markers, before floor projection/slot swap. */
} spawn_reference_state;
float spawn_reference_rating(const spawn_reference_state *state,unsigned player,
                             const float pos[3],int team);
#endif
