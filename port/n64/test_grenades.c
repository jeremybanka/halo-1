#include "combat.h"
#include "movement.h"
#include "shield_fixture.h"
#include "blam/vehicle_physics.h"
#include <stdio.h>

static const float dt = 1.f / 30;
static void close_to(float actual, float expected) {
    if (fabsf(actual - expected) >= .002f)
        fprintf(stderr, "actual %.9g expected %.9g\n", actual, expected);
    assert(fabsf(actual - expected) < .002f);
}
static void reset(void) {
    shield_fixture_reset();
    for (unsigned p = 0; p < BG_PLAYERS; p++) {
        bg_players[p].pos[0] = 30 + p;
        bg_players[p].pos[2] = 30;
    }
}
/* Select actual Xbox polygons, away from triangle edges and other players. */
static bool floor_for(int wanted, float point[3], float normal[3]) {
    const float down[3] = {0, -1, 0};
    for (int x = -30; x <= 30; x++)
        for (int z = -30; z <= 30; z++) {
            float origin[3] = {x + .37f, 20, z + .43f};
            int material = -1;
            float hit = bg_world_projectile_raycast(origin, down, 30, normal, &material);
            if (hit < 30 && material == wanted && normal[1] > .5f) {
                memcpy(point, origin, 12);
                point[1] -= hit;
                return true;
            }
        }
    return false;
}
static bg_projectile *frag(const float point[3], float height, float vx, float vy) {
    bg_projectile *q = bg_projectile_create();
    assert(q);
    q->kind = BG_P_FRAG;
    q->owner = 0;
    q->life = .5f;
    memcpy(q->pos, point, 12);
    q->pos[1] += height;
    q->velocity[0] = vx;
    q->velocity[1] = vy;
    return q;
}
static void launch(void) {
    for (unsigned kind = 0; kind < 2; kind++) {
        reset();
        bg_player *p = &bg_players[0];
        p->pos[0] = -4;
        p->pos[2] = 4;
        p->pos[1] = bg_floor(-4, 4, 100) + .015f;
        p->pitch = .4f;
        p->grenade_kind = kind;
        bg_input in[4] = {{.grenade = true}};
        bg_tick(in, dt);
        const bg_projectile *q = bg_projectile_at(0);
        assert(q && q->kind == (kind ? BG_P_PLASMA_GRENADE : BG_P_FRAG));
        /* unit_throw_grenade_release: Spartan grenade_velocity=10, along aim. */
        close_to(q->velocity[0], 10 * cosf(.4f));
        close_to(q->velocity[1], 10 * sinf(.4f) - bg_movement.gravity * dt);
        close_to(q->velocity[2], 0);
    }
}
static void rebound(int material, float normal_retained, float tangent_retained) {
    reset();
    float point[3], normal[3];
    assert(floor_for(material, point, normal));
    float tangent[3] = {normal[1], -normal[0], 0};
    float tangent_length = hypotf(tangent[0], tangent[1]);
    for (unsigned a = 0; a < 3; a++)
        tangent[a] /= tangent_length;
    bg_projectile *q = frag(point, 0, 0, 0);
    float initial[3];
    for (unsigned a = 0; a < 3; a++) {
        q->pos[a] += .05f * normal[a];
        initial[a] = q->velocity[a] = tangent[a] - 4 * normal[a];
    }
    shield_fixture_ticks(1);
    assert(q->active && q->countdown && q->attached == -1);
    /* Independent source calculation: midpoint sweep, impact-time gravity,
     * material reflection and integration through the remainder of the tick. */
    float impact_time = .05f / (4 + bg_movement.gravity * normal[1] * dt * .5f);
    float remaining = dt - impact_time;
    float incoming[3], along = 0, clearance = 0;
    memcpy(incoming, initial, 12);
    incoming[1] -= bg_movement.gravity * impact_time;
    for (unsigned a = 0; a < 3; a++)
        along += incoming[a] * normal[a];
    for (unsigned a = 0; a < 3; a++) {
        float reflected = (incoming[a] - along * normal[a]) * tangent_retained - along * normal[a] * normal_retained;
        close_to(q->velocity[a], reflected - (a == 1 ? bg_movement.gravity * remaining : 0));
        float contact = .05f * normal[a] + initial[a] * impact_time - (a == 1 ? bg_movement.gravity * dt * .5f * impact_time : 0);
        close_to(q->pos[a] - point[a], contact + .001f * normal[a] + reflected * remaining - (a == 1 ? bg_movement.gravity * remaining * remaining * .5f : 0));
        clearance += (q->pos[a] - point[a]) * normal[a];
    }
    float peak = clearance;
    for (unsigned t = 0; t < 12; t++) {
        shield_fixture_ticks(1);
        clearance = 0;
        for (unsigned a = 0; a < 3; a++)
            clearance += (q->pos[a] - point[a]) * normal[a];
        peak = fmaxf(peak, clearance);
        assert(clearance >= -.002f);
    }
    assert(peak > (material == 1 ? .08f : .18f));
    printf("material %d: rebound clearance %.4f\n", material, peak);
    shield_fixture_ticks(60);
    assert(!bg_projectile_at(0));
}
static void short_contact(void) {
    reset();
    float point[3], normal[3];
    assert(floor_for(1, point, normal));
    bg_projectile *q = frag(point, 0, 0, 0);
    for (unsigned a = 0; a < 3; a++) {
        q->pos[a] += normal[a] * .0005f;
        q->velocity[a] = -normal[a] * .01f;
    }
    shield_fixture_ticks(1);
    assert(q->countdown && q->attached == -2);
    assert(q->pos[1] > point[1]);
    assert(q->velocity[0] == 0 && q->velocity[1] == 0 && q->velocity[2] == 0);
    shield_fixture_ticks(43);
    assert(bg_projectile_at(0));
    shield_fixture_ticks(1);
    assert(!bg_projectile_at(0));
}
static void wall_contact(void) {
    reset();
    const float dirs[4][3] = {{1, 0, 0}, {-1, 0, 0}, {0, 0, 1}, {0, 0, -1}};
    for (int x = -35; x <= 35; x++)
        for (int z = -45; z <= 45; z++)
            for (unsigned d = 0; d < 4; d++) {
                float origin[3] = {x + .37f, 1.0f, z + .43f};
                float normal[3];
                int material = -1;
                float hit = bg_world_projectile_raycast(origin, dirs[d], 3, normal, &material);
                if (hit >= 3 || fabsf(normal[1]) > .001f || (material != 2 && material != 7))
                    continue;
                for (unsigned a = 0; a < 3; a++)
                    origin[a] += dirs[d][a] * hit;
                bg_projectile *q = frag(origin, 0, 0, 0);
                for (unsigned a = 0; a < 3; a++) {
                    q->pos[a] += normal[a] * .03f;
                    q->velocity[a] = -6 * normal[a];
                }
                shield_fixture_ticks(1);
                float outward = 0, clearance = 0;
                for (unsigned a = 0; a < 3; a++) {
                    outward += q->velocity[a] * normal[a];
                    clearance += (q->pos[a] - origin[a]) * normal[a];
                }
                close_to(outward, 1.8f);
                assert(clearance > .04f && !q->countdown && q->attached == -1);
                return;
            }
    assert(!"No stone wall fixture found");
}
int main(void) {
    launch();
    rebound(1, .2f, .1f); /* sand */
    rebound(2, .3f, .2f); /* stone */
    short_contact();
    wall_contact();
    puts("PASS: Xbox grenade launch, material rebound, remaining-tick motion, wall reflection, short contacts, rest and arming");
}
