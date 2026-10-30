#ifndef BG_PLAYER_AIM_QA_H
#define BG_PLAYER_AIM_QA_H
/* Frozen source-pose readback, never used to make timing claims. */
static unsigned model_qa_page;
static float aim_floor;
static const char *const model_qa_labels[] = {
    "IDLE AIM", "RUN AIM", "RUN + FIRE AIM", "CROUCH AIM", "CROUCH RUN + FIRE",
    "RUN + RELOAD AIM", "CROUCH RUN + RELOAD", "AIRBORNE AIM", "READY AIM", "MELEE LOOK"};
static bool model_qa_firstperson(void) { return false; }
static void model_qa_stage(uint64_t now) {
    (void)now;
    static unsigned frame;
    static bool initialized;
    if (!initialized) {
        initialized = true; bg_set_players(4); bg_reset(); bg_scene_reset();
        for (unsigned i = 0; i < bg_vehicle_count; i++) bg_vehicles[i].active = false;
        for (unsigned i = 0; i < bg_pickup_count; i++) bg_pickups[i].active = false;
        aim_floor = bg_floor(0, 4, 100) + .015f;
    }
    unsigned sample = frame++ % 50;
    model_qa_page = sample / 5;
    *qa.seconds = .23f;
    for (unsigned p = 0; p < 4; p++) {
        bg_player *q = &bg_players[p];
        q->pos[0] = 0; q->pos[1] = aim_floor; q->pos[2] = 4;
        q->yaw = 0; q->pitch = (float[]){-1.49225651f, -.75f, 0, .75f, 1.49225651f}[sample % 5];
        q->invisibility = p ? 1 : 0; q->vehicle = -1; q->health = 100; q->grounded = true;
        q->weapon = BG_W_AR; q->slot = 0;
        q->weapon_ready = q->melee_time = q->reload = q->landing_time = q->grenade_cooldown = 0;
        q->crouched = model_qa_page == 3 || model_qa_page == 4 || model_qa_page == 6;
        q->crouch_amount = q->crouched;
        q->velocity[0] = model_qa_page == 1 || model_qa_page == 2 || model_qa_page == 4 ||
                         model_qa_page == 5 || model_qa_page == 6;
        q->animation = q->velocity[0] ? BG_ANIM_RUN : BG_ANIM_IDLE;
        q->fire_ticks[0] = 10; q->flash = 0;
        q->locomotion_time = .23f; q->anim_time = .04f;
        if (model_qa_page == 2 || model_qa_page == 4) {
            q->animation = BG_ANIM_FIRE; q->fire_ticks[0] = 2; q->flash = .05f;
        }
        if (model_qa_page == 5 || model_qa_page == 6) {
            q->animation = BG_ANIM_RELOAD; q->reload_duration = 3; q->reload = 1.7f; q->anim_time = 1.3f;
        }
        if (model_qa_page == 7) {
            q->grounded = false; q->airborne_time = .23f; q->animation = BG_ANIM_JUMP; q->anim_time = .23f;
        }
        if (model_qa_page == 8) q->weapon_ready = .2f;
        if (model_qa_page == 9) {
            q->melee_time = .3f; q->anim_time = .3f; q->animation = BG_ANIM_MELEE;
        }
    }
}
static void model_qa_camera(unsigned p, T3DVec3 *eye, T3DVec3 *target) {
    const float dirs[4][3] = {{1,.1f,0},{-1,.1f,0},{0,.1f,1},{0,.1f,-1}};
    for (unsigned a = 0; a < 3; a++) {
        target->v[a] = (float[]){0, aim_floor + .42f, 4}[a] * BG_SCALE;
        eye->v[a] = target->v[a] + dirs[p][a] * 1.25f * BG_SCALE;
    }
}
#endif
