/* Isolate the real vehicle-contact phase with original map/solver geometry.
 * Shallow contacts are staged after walking, immediately before vehicles move. */
#include "game.c"
#include <assert.h>
#include <stdio.h>

int main(void) {
    unsigned hits[2] = {0}, deaths[2] = {0}, credited = 0;
    for (unsigned fast = 0; fast < 2; fast++) {
        for (unsigned kind = 0; kind < 4; kind++) {
            for (unsigned side = 0; side < 4; side++) {
                for (unsigned gap = 0; gap < 4; gap++) {
                    bg_set_players(4);
                    bg_reset();
                    bg_vehicle_count = bg_pickup_count = 0;
                    bg_set_score_limit(1000);
                    for (unsigned p = 0; p < 4; p++) {
                        bg_players[p].health = bg_players[p].shield = 100;
                        bg_players[p].pos[0] = 50 + p * 3;
                        bg_players[p].pos[2] = 50;
                    }
                    float pos[3] = {-12, bg_floor(-12, 5, 100), 5};
                    int vi = bg_add_vehicle(kind, pos, 0);
                    bg_input quiet[4] = {0};
                    for (unsigned t = 0; t < 90; t++)
                        update_vehicles(quiet, 1.f / 30);
                    bg_vehicle *v = &bg_vehicles[vi];
                    bg_player *p = &bg_players[1];
                    float dir[3] = {side == 0 ? -1 : side == 1 ? 1 : 0, 0,
                                    side == 2 ? -1 : side == 3 ? 1 : 0};
                    float origin[3] = {v->pos[0] - dir[0] * 6, v->pos[1] + .35f,
                                       v->pos[2] - dir[2] * 6};
                    float distance = bg_vehicle_hit_ray(v, origin, dir, 12);
                    if (distance >= 12)
                        continue;
                    for (unsigned a = 0; a < 3; a++)
                        p->pos[a] = origin[a] + dir[a] *
                            (distance - bg_movement.radius + gap * .025f);
                    p->pos[1] = bg_floor(p->pos[0], p->pos[2], 100) + .015f;
                    if (!bg_vehicle_contacts_player(v, p))
                        continue;
                    hits[fast]++;
                    bg_player *driver = &bg_players[0];
                    driver->vehicle = vi;
                    driver->seat = 0;
                    driver->seat_state = BG_SEAT_STABLE;
                    v->occupants[0] = 0;
                    v->velocity[0] = fast ? 4.f : .1f;
                    v->velocity[1] = v->velocity[2] = 0;
                    v->physics_valid = false;
                    memset(p->velocity, 0, sizeof(p->velocity));
                    p->vy = 0;
                    update_vehicles(quiet, 1.f / 30);
                    if (!fast)
                        assert(p->health == 100 && p->shield == 100);
                    if (p->health <= 0) {
                        deaths[fast]++;
                        for (unsigned e = 0; e < bg_event_count; e++)
                            if (bg_events[e].kind == BG_EVENT_KILL &&
                                bg_events[e].player == 0 && bg_events[e].weapon == 1)
                                credited++;
                    }
                }
            }
        }
    }
    printf("low-speed contacts %u fatalities %u; fast contacts %u fatalities %u "
           "driver credits %u\n", hits[0], deaths[0], hits[1], deaths[1], credited);
    assert(hits[0] >= 40 && deaths[0] == 0);
    assert(hits[1] >= 40 && deaths[1] >= 20 && credited == deaths[1]);
}
