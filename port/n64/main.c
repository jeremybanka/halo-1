#include "telemetry.h"
#include <libdragon.h>
#include <t3d/t3d.h>
#include "runtime_config.h"
#include <math.h>
#include <string.h>
#include "game.h"
#include "combat_geometry.h"
#include "blam/vehicle_physics.h"
#include "blam/vehicle_profile.h"
#include "controls.h"
#include "menu.h"
#include "camouflage.h"
#include "menu_draw.h"
#include "frontend.h"
#include "frontend_draw.h"
#ifdef BG_FRONTEND_QA
#include "frontend_qa.h"
#endif
#ifdef BG_MENU_QA
#include "menu_qa.h"
#endif
#include "firstperson_ammo.h"
#include "weapon_effects_draw.h"
#include "rspq_metrics.h"
#include "blam/runtime.h"
#include "sound.h"
#include "hud.h"
#include "replay.h"
#ifdef BG_EFFECTS_QA
#include "effects_qa.h"
#endif
#ifdef BG_DESTRUCTION_QA
#include "destruction_qa.h"
#endif
#include "scene.h"
#include "presentation.h"
#include "residency.h"
#include "asset_interaction.h"
#include "runtime_qa.h"

static rspq_syncpoint_t fences[BG_FRAME_SLOTS];
static bool pending[BG_FRAME_SLOTS];
static unsigned slot, views = 4, triangles, fps;
static bg_menu menu;
#ifdef BG_FRONTEND
static bg_frontend front;
static uint64_t match_ended;
static bool front_active(void) {
    return front.page != BG_FRONT_PLAY;
}
#else
static inline bool front_active(void) {
    return false;
}
#endif
#ifndef BG_SNAPSHOT_TICK
static bool paused;
static bool scores[BG_PLAYERS];
#endif
static float game_time;
#ifdef BG_PROFILE
static unsigned sim_us, prep_us, draw_us, wait_us;
static unsigned queue_us;
#ifdef BG_RSPQ_OVERRIDE
static bg_rspq_metrics previous_queue_metrics;
#endif
static unsigned hud_us, audio_us, overlay_us, present_us;
static unsigned geometry_rsp_us, geometry_rdp_us;
#ifndef BG_BENCHMARK
static uint32_t frame_times[120], frame_time_count, frame_time_next;
static unsigned frame_average, frame_minimum, frame_p95, frame_maximum;
static void profile_frame_time(uint32_t elapsed) {
    frame_times[frame_time_next++ % 120] = elapsed;
    if (frame_time_count < 120)
        frame_time_count++;
}
static void profile_frame_summary(void) {
    uint32_t sorted[120];
    uint64_t sum = 0;
    for (unsigned i = 0; i < frame_time_count; i++) {
        uint32_t value = frame_times[i];
        sum += value;
        unsigned j = i;
        while (j && sorted[j - 1] > value) {
            sorted[j] = sorted[j - 1];
            j--;
        }
        sorted[j] = value;
    }
    if (frame_time_count) {
        frame_average = sum / frame_time_count;
        frame_minimum = sorted[0];
        frame_p95 = sorted[(frame_time_count * 95 + 99) / 100 - 1];
        frame_maximum = sorted[frame_time_count - 1];
    }
}
#endif
#endif
#ifdef BG_BENCHMARK
static bg_benchmark benchmark;
#endif
#ifdef BG_VI_MEASURE
static unsigned result_heap_free, result_held_peak;
#ifdef BG_PRESENT_TRACK
static unsigned result_ready_peak, result_outstanding_peak;
#endif
#endif
#if defined(BG_VI_MEASURE) || defined(BG_PACED30)
static uint32_t simulation_pose;
static uint64_t frame_sample_us;
#ifdef BG_PACED30
static unsigned paced_dropped_ticks;
#endif
static void frame_present(surface_t *screen, unsigned vehicle) {
#ifdef BG_BENCHMARK
    bg_cadence_frame sample_data = {0};
    bg_cadence_frame *sample = &sample_data;
    sample->sim_ms = (uint32_t)(game_time * 1000.f);
    sample->triangles = triangles;
    sample->vertices = bg_scene_profile.submitted_vertices;
    memcpy(sample->category_triangles, bg_scene_profile.category_triangles,
           sizeof(sample->category_triangles));
    for (unsigned p = 0; p < 4; p++) {
        if (bg_players[p].vehicle >= 0)
            sample->vehicle_mask |= 1u << p;
        if (bg_players[p].zoom)
            sample->zoom_mask |= 1u << p;
        if (bg_players[p].health <= 0)
            sample->dead_mask |= 1u << p;
    }
#endif
    bg_presentation_submit(screen, vehicle, simulation_pose, frame_sample_us
#ifdef BG_BENCHMARK
                           ,
                           sample
#endif
    );
}
#endif
#ifdef BG_BENCHMARK
static uint64_t benchmark_origin, benchmark_previous;
static uint64_t audio_pump_previous;
static uint32_t audio_pump_max_gap;
static unsigned benchmark_vehicle, benchmark_triangles, benchmark_vertices,
    benchmark_phases[BG_BENCHMARK_PHASES];
static unsigned benchmark_categories[BG_BENCHMARK_CATEGORIES];
#endif
#ifdef BG_GPU_DIAGNOSTIC
static volatile bool diagnostic_rdp_done;
static void diagnostic_rdp_complete(void *unused) {
    (void)unused;
    diagnostic_rdp_done = true;
}
#endif
#ifdef RDPQ_VALIDATE
static unsigned validation_errors, validation_warnings;
static char validation_line[192], validation_message[96];
static unsigned validation_length;
static int validation_write(void *cookie, const char *text, int length) {
    for (int i = 0; i < length; i++) {
        if (text[i] == '\n') {
            validation_line[validation_length] = 0;
            if (strstr(validation_line, "[RDPQ_VALIDATION]")) {
                if (strstr(validation_line, "ERROR:") || strstr(validation_line, "CRASH:"))
                    validation_errors++;
                if (strstr(validation_line, "WARN:"))
                    validation_warnings++;
                if (strstr(validation_line, "ERROR:") || strstr(validation_line, "WARN:"))
                    snprintf(validation_message, sizeof(validation_message), "%.95s",
                             validation_line + 18);
            }
            validation_length = 0;
        } else if (validation_length + 1 < sizeof(validation_line))
            validation_line[validation_length++] = text[i];
    }
    return fwrite(text, 1, length, (FILE *)cookie);
}
#endif

static void pump_audio(void) {
#ifdef BG_PROFILE
    uint64_t begin = get_ticks_us();
#endif
#ifdef BG_BENCHMARK
    /* Reuse the profiler timestamp; no extra clock read in polling loops.
     * This is a scheduling gap, not an assertion about SDK queue occupancy. */
    if (audio_pump_previous && benchmark_origin && begin >= benchmark_origin + 1000000) {
        uint64_t gap = begin - audio_pump_previous;
        if (gap > audio_pump_max_gap)
            audio_pump_max_gap = gap > UINT32_MAX ? UINT32_MAX : (uint32_t)gap;
    }
    audio_pump_previous = begin;
#endif
    bg_sound_pump();
#ifdef BG_PROFILE
    audio_us += get_ticks_us() - begin;
#endif
}
static void fill(int x, int y, int w, int h, color_t color) {
    rdpq_set_mode_fill(color);
    rdpq_fill_rectangle(x, y, x + w, y + h);
}
#ifndef BG_SNAPSHOT_TICK
static uint32_t control_buttons(joypad_buttons_t buttons) {
    uint32_t bits = 0;
#define BUTTON(field, name)                                                                        \
    if (buttons.field)                                                                             \
    bits |= BG_BUTTON_##name
    BUTTON(a, A);
    BUTTON(b, B);
    BUTTON(l, L);
    BUTTON(r, R);
    BUTTON(z, Z);
    BUTTON(start, START);
    BUTTON(d_up, D_UP);
    BUTTON(d_down, D_DOWN);
    BUTTON(d_left, D_LEFT);
    BUTTON(d_right, D_RIGHT);
    BUTTON(c_up, C_UP);
    BUTTON(c_down, C_DOWN);
    BUTTON(c_left, C_LEFT);
    BUTTON(c_right, C_RIGHT);
#undef BUTTON
    return bits;
}
static bool input(bg_input in[4]) {
    bg_control_state raw[4];
    bg_menu_input navigation[4];
    joypad_poll();
    for (unsigned i = 0; i < 4; i++) {
        joypad_inputs_t stick = joypad_get_inputs(i);
        joypad_buttons_t held = joypad_get_buttons(i), pressed = joypad_get_buttons_pressed(i);
        raw[i] = (bg_control_state){.stick_x = stick.stick_x,
                                    .stick_y = stick.stick_y,
                                    .held = control_buttons(held),
                                    .pressed = control_buttons(pressed)};
    }
#ifdef BG_FRONTEND_QA
    bg_front_qa_input(&front, raw, get_ticks_us());
#endif
#ifdef BG_MENU_QA
    bg_menu_qa_input(raw, get_ticks_us());
#endif
#ifdef BG_SCORES_BENCHMARK
    /* A separately named replay measures all four live score overlays. */
    for (unsigned i = 0; i < 4; i++)
        raw[i] = (bg_control_state){.held = BG_BUTTON_R};
#endif
#ifdef BG_FRONTEND
    if (front_active()) {
        bg_front_action action = bg_front_update(&front, raw, get_ticks_us());
        bg_sound_front_effect(front.sound);
        memset(in, 0, sizeof(bg_input) * 4);
        memset(scores, 0, sizeof(scores));
        if (action == BG_FRONT_START_MATCH) {
            bg_front_draw_release();
            views = front.count;
            bg_set_players(views);
            bg_set_score_limit(15);
            bg_reset();
            game_time = 0;
            match_ended = 0;
            bg_scene_reset();
            bg_scene_load_bodies();
            menu.player_count = views;
            menu.open = false;
            menu.shell_session = true;
            for (unsigned p = 0; p < views; p++) {
                bg_player_profiles[p] = front.profile[front.ports[p]];
                menu.styles[p] = front.styles[bg_player_profiles[p]];
                bg_scene_profile_changed(p);
            }
            bg_sound_frontend(false);
        } else if (action == BG_FRONT_RESUME_MATCH) {
            bg_front_draw_release();
            menu.open = false;
        } else if (action == BG_FRONT_LEAVE_MATCH) {
            menu.open = false;
            bg_residency_menu(true);
        }
        paused = front_active();
        return true;
    }
    bg_front_map_controls(&front, raw, raw);
#endif
    bg_menu_inputs(&menu, raw, navigation);
    bg_menu_result result = bg_menu_update(&menu, navigation, views);
    paused = menu.open;
#ifdef BG_FRONTEND
    for (unsigned p = 0; p < views; p++)
        front.styles[front.profile[front.ports[p]]] = menu.styles[p];
    if (result.action == BG_MENU_ACTION_QUIT) {
        /* The full-screen confirmation needs its backdrop bank. Simulation
         * state survives; resume lazily recreates these render-only buffers. */
        bg_residency_quit_confirmation();
        bg_front_quit(&front);
        paused = true;
    }
#endif
    if (result.action == BG_MENU_ACTION_RESTART) {
        bg_reset();
        game_time = 0;
        bg_scene_reset();
#ifdef BG_FRONTEND
        match_ended = 0;
#endif
    }
    if (result.action == BG_MENU_ACTION_PLAYER_COUNT) {
        views = result.player_count;
        bg_set_players(views);
    }
    memset(in, 0, sizeof(bg_input) * 4);
    memset(scores, 0, sizeof(scores));
    if (!result.consumed)
        for (unsigned i = 0; i < views; i++) {
            bg_controls_map(&in[i], &raw[i], menu.styles[i], bg_players[i].vehicle >= 0);
            scores[i] = bg_controls_show_scores(&raw[i], menu.styles[i]);
        }
#ifdef BG_MENU_QA
    bg_menu_qa_check(&menu, views, &result, in);
#endif
    return result.consumed;
}
#ifdef BG_PACED30
static surface_t *paced_acquire(blam_clock *clock, uint64_t *previous, bg_input latch[4],
                                bg_input in[4], unsigned *ticks, bool *first,
                                uint64_t *ui_deadline) {
    unsigned pending_ticks = 0, dropped_ticks = 0;
    uint64_t last_poll = 0;
    for (;;) {
        uint64_t now = get_ticks_us();
        if (!last_poll || now - last_poll >= 2000) {
            if (input(in)) {
                memset(latch, 0, sizeof(bg_input) * 4);
                /* Pausing/resuming consumes no queued gameplay input, as in
                 * the ordinary local clock's paused update. */
                clock->ticks -= pending_ticks;
                pending_ticks = 0;
            }
            for (unsigned p = 0; p < 4; p++) {
#define EDGE(field)                                                                                \
    latch[p].field |= in[p].field;                                                                 \
    in[p].field = latch[p].field
                EDGE(jump);
                EDGE(reload);
                EDGE(switch_weapon);
                EDGE(grenade);
                EDGE(switch_grenade);
                EDGE(melee);
                EDGE(zoom);
#undef EDGE
            }
            bg_presentation_mode(views >= 3 && !front_active());
            last_poll = now;
        }
        clock->paused = paused;
        dropped_ticks += bg_paced_clock_accumulate(clock, now - *previous, &pending_ticks);
        *previous = now;
        /* Wait BEFORE acquiring: a repeated simulation pose never locks a
         * display surface. Paused menus may redraw on a wall-time permit. */
        bool redraw = views < 3 || pending_ticks || *first || (paused && now >= *ui_deadline);
#ifdef BG_PRESENT_TRACK
        /* Drain old SDK-ready/in-flight frames before fresh paced prefill.
         * Input, clock accumulation and audio above/below continue normally. */
        if (bg_presentation_draining())
            redraw = false;
#endif
        surface_t *screen = redraw ? display_try_get() : NULL;
        if (screen) {
            if (dropped_ticks)
                clock->leftover_dt = 0;
            paced_dropped_ticks += dropped_ticks;
            *ticks = pending_ticks;
            *first = false;
            *ui_deadline = now + 33333;
            frame_sample_us = last_poll;
            return screen;
        }
        pump_audio();
    }
}
#endif
#endif
#ifndef BG_SNAPSHOT_TICK
static void draw_menu(void) {
    bg_menu_draw(&menu);
}
#endif
#ifndef BG_FRONTEND
static void draw_result(void) {
    fill(66, 45, 188, 146, RGBA32(12, 27, 56, 255));
    fill(66, 45, 188, 2, RGBA32(114, 176, 233, 255));
    rdpq_set_mode_standard();
    rdpq_text_print(NULL, 1, 124, 64, "GAME OVER");
    rdpq_text_printf(NULL, 1, 112, 80, "PLAYER %d WINS", bg_match_winner() + 1);
    for (unsigned p = 0; p < views; p++) {
        fill(83, 90 + p * 17, 5, 9, bg_scene_team_color(bg_player_profiles[p]));
        rdpq_set_mode_standard();
        rdpq_text_printf(NULL, 1, 96, 98 + p * 17, "PLAYER %u       %2d", p + 1,
                         bg_players[p].score);
    }
    rdpq_text_print(NULL, 1, 90, 178, "START FOR MATCH OPTIONS");
}
#endif
#ifdef BG_BENCHMARK
static void benchmark_page(surface_t *screen, bool completed) {
    rdpq_attach(screen, NULL);
    rdpq_set_mode_standard();
    rdpq_set_scissor(0, 0, 320, 240);
    rdpq_clear(RGBA32(9, 20, 39, 255));
    rdpq_text_print(NULL, 1, 8, 16,
                    completed ? "RDP COMPLETION / 4-PLAYER" : "CPU ACQUISITION / 4-PLAYER");
#ifdef BG_GPU_DIAGNOSTIC
    rdpq_text_print(NULL, 1, 8, 38, "GPU DIAGNOSTIC / SERIALIZED");
#endif
    rdpq_text_printf(NULL, 1, 8, 28, "%u MS MEASURED / 1S WARMUP",
                     (unsigned)((completed ? bg_presentation_cadence()->result[0].elapsed
                                           : benchmark.result[0].elapsed) /
                                1000));
    const char *labels[] = {"ALL FRAMES", "COMBAT", "VEHICLES"};
    for (unsigned g = 0; g < 3; g++) {
        bg_benchmark_result completion = {0};
        if (completed) {
            const bg_cadence_result *c = &bg_presentation_cadence()->result[g];
            completion.elapsed = c->elapsed;
            completion.frames = c->frames;
            completion.minimum = c->minimum;
            completion.maximum = c->maximum;
            completion.p95 = c->p95;
            completion.slow_frames = c->slow_frames;
        }
        const bg_benchmark_result *r = completed ? &completion : &benchmark.result[g];
        unsigned average = r->frames ? r->elapsed / r->frames : 0;
        unsigned fps10 = r->elapsed ? (uint64_t)r->frames * 10000000 / r->elapsed : 0;
        int y = 48 + g * 42;
        rdpq_text_printf(NULL, 1, 8, y, "%s: %u FRAMES / %u.%u FPS", labels[g], r->frames,
                         fps10 / 10, fps10 % 10);
        rdpq_text_printf(NULL, 1, 8, y + 12, "AVG %u.%u  P95 %u.%u  MAX %u.%u MS", average / 1000,
                         (average / 100) % 10, r->p95 / 1000, (r->p95 / 100) % 10,
                         r->maximum / 1000, (r->maximum / 100) % 10);
        rdpq_text_printf(NULL, 1, 8, y + 24, "MIN %u.%u MS / >33.33MS: %u", r->minimum / 1000,
                         (r->minimum / 100) % 10, r->slow_frames);
        debugf(
            "BENCH %s group=%s frames=%u elapsed_us=%llu avg_us=%u min_us=%u p95_us=%u max_us=%u "
            "over_33333=%u triangles_avg=%u triangles_max=%u vertices_avg=%u vertices_max=%u\n",
            completed ? "rdp_completed" : "cpu_acquisition", labels[g], r->frames,
            (unsigned long long)r->elapsed, average, r->minimum, r->p95, r->maximum, r->slow_frames,
            r->frames ? (unsigned)(r->triangles / r->frames) : 0, r->max_triangles,
            r->frames ? (unsigned)(r->vertices / r->frames) : 0, r->max_vertices);
    }
    if (completed) {
        rdpq_text_print(NULL, 1, 8, 180, "TIMESTAMP AT RDP FULL-SYNC CALLBACK");
#ifdef BG_PACED30
        rdpq_text_print(NULL, 1, 8, 192, "EXPERIMENT: TWO-RETRACE FIFO");
#else
        rdpq_text_print(NULL, 1, 8, 192, "DISPLAY_SHOW PIPELINE UNCHANGED");
#endif
        rdpq_text_print(NULL, 1, 8, 204, "NOT A VI SCANOUT MEASUREMENT");
        rdpq_text_print(NULL, 1, 8, 228, "TAIL PAGE IN 8S / A TO SWITCH");
        if (bg_presentation_cadence()->overflow)
            rdpq_text_print(NULL, 1, 8, 216, "CAPACITY EXCEEDED: P95 INVALID");
        return;
    }
    const bg_benchmark_result *r = &benchmark.result[0];
    unsigned average_phases[BG_BENCHMARK_PHASES];
    for (unsigned p = 0; p < BG_BENCHMARK_PHASES; p++)
        average_phases[p] = r->frames ? r->phase_us[p] / r->frames : 0;
    rdpq_text_printf(NULL, 1, 8, 180, "TRIANGLES AVG %u / MAX %u",
                     r->frames ? (unsigned)(r->triangles / r->frames) : 0, r->max_triangles);
    rdpq_text_printf(NULL, 1, 8, 192, "SIM %u ANIM %u WORLD %u OBJ %u MS", average_phases[0] / 1000,
                     average_phases[2] / 1000, average_phases[4] / 1000, average_phases[5] / 1000);
    rdpq_text_printf(NULL, 1, 8, 204, "HULL %u POSE %u PILL %u PLAYER %u US", average_phases[13],
                     average_phases[14], average_phases[15], average_phases[16]);
#ifdef BG_GPU_DIAGNOSTIC
    rdpq_text_printf(NULL, 1, 8, 216, "GPU WAIT RSP %u RDP %u MS", average_phases[10] / 1000,
                     average_phases[11] / 1000);
#else
    rdpq_text_printf(NULL, 1, 8, 216, "CAM %u MATRIX %u FP %u US", average_phases[1],
                     average_phases[3], average_phases[6]);
#endif
    unsigned cats[BG_BENCHMARK_CATEGORIES];
    for (unsigned c = 0; c < BG_BENCHMARK_CATEGORIES; c++)
        cats[c] = r->frames ? r->category_triangles[c] / r->frames : 0;
    rdpq_text_print(NULL, 1, 8, 228, "RDP PAGE IN 8S / A TO SWITCH");
    if (benchmark.overflow)
        rdpq_text_print(NULL, 1, 8, 234, "SAMPLE CAPACITY EXCEEDED: P95 INVALID");
    debugf("BENCH phase_us sim=%u camera=%u animation=%u matrix=%u world=%u objects=%u "
           "firstperson=%u hud=%u audio=%u wait=%u geometry_rsp_wait=%u geometry_rdp_wait=%u "
           "queue_stall=%u overflow=%u\n",
           average_phases[0], average_phases[1], average_phases[2], average_phases[3],
           average_phases[4], average_phases[5], average_phases[6], average_phases[7],
           average_phases[8], average_phases[9], average_phases[10], average_phases[11],
           average_phases[12], benchmark.overflow);
    debugf("BENCH triangles world=%u vehicles=%u bodies_held=%u pickups=%u effects=%u "
           "firstperson=%u\n",
           cats[0], cats[1], cats[2], cats[3], cats[4], cats[5]);
}
static void benchmark_cost_page(surface_t *screen, bool collision) {
    rdpq_attach(screen, NULL);
    rdpq_set_mode_standard();
    rdpq_set_scissor(0, 0, 320, 240);
    rdpq_clear(RGBA32(9, 20, 39, 255));
    rdpq_text_print(NULL, 1, 8, 16, "MEAN PHASE US / INCLUSIVE");
    rdpq_text_print(NULL, 1, 84, 32, "ALL");
    rdpq_text_print(NULL, 1, 160, 32, "COMBAT");
    rdpq_text_print(NULL, 1, 236, 32, "VEHICLES");
    static const char *const labels[] = {"SIM",    "PLAYERS",  "PHYSICS", "SHOTS", "CAMERA",
                                         "BODIES", "VEH-PREP", "PICKUPS", "VIEWS", "ANIM",
                                         "WORLD",  "OBJECTS",  "AUDIO",   "QUEUE"};
    static const unsigned indices[] = {0, 21, 22, 23, 1, 17, 18, 19, 20, 2, 4, 5, 8, 12};
    static const char *const collision_labels[] = {"GROUND",    "FEATURES", "TESTS",
                                                   "SWEEPS",    "PAIRS",    "SUSPEND",
                                                   "WORLD-CAM", "HULL-CAM", "AIM-CAM"};
    for (unsigned row = 0; row < (collision ? BG_VP_COUNT + 2 : 14); row++) {
        int y = 48 + (int)row * 12;
        rdpq_text_print(NULL, 1, 8, y,
                        collision ? (row < BG_VP_COUNT    ? collision_labels[row]
                                     : row == BG_VP_COUNT ? "PHYSICS"
                                                          : "VIEWS")
                                  : labels[row]);
        for (unsigned group = 0; group < 3; group++) {
            const bg_benchmark_result *r = &benchmark.result[group];
            unsigned average = r->frames ? r->phase_us[collision ? (row < BG_VP_COUNT    ? 24 + row
                                                                    : row == BG_VP_COUNT ? 22
                                                                                         : 20)
                                                                 : indices[row]] /
                                               r->frames
                                         : 0;
            rdpq_text_printf(NULL, 1, 84 + group * 76, y, "%5u", average);
        }
    }
    rdpq_text_print(NULL, 1, 8, 224, "QUEUE OVERLAPS WORLD/OBJECTS/HUD");
}
static void benchmark_tail_page(surface_t *screen, unsigned first) {
    rdpq_attach(screen, NULL);
    rdpq_set_mode_standard();
    rdpq_set_scissor(0, 0, 320, 240);
    rdpq_clear(RGBA32(9, 20, 39, 255));
    rdpq_text_printf(NULL, 1, 8, 16, "SLOWEST RDP COMPLETIONS / %u-%u", first + 1, first + 4);
    rdpq_text_print(NULL, 1, 8, 28, "SCENE AT COMPLETING FRAME / 4 VIEWS");
    for (unsigned i = first; i < first + 4 && i < bg_presentation_tail()->count; i++) {
        const bg_cadence_tail_entry *entry = &bg_presentation_tail()->entry[i];
        const bg_cadence_frame *f = &entry->frame;
        const unsigned *c = f->category_triangles;
        int y = 46 + (i - first) * 40;
        rdpq_text_printf(NULL, 1, 8, y, "#%u %u.%uMS T%u.%uS VERT%u", i + 1, entry->elapsed / 1000,
                         (entry->elapsed / 100) % 10, f->sim_ms / 1000, (f->sim_ms / 100) % 10,
                         f->vertices);
        rdpq_text_printf(NULL, 1, 8, y + 12, "TRI %u W%u V%u B%u", f->triangles, c[0], c[1], c[2]);
        rdpq_text_printf(NULL, 1, 8, y + 24, "P%u E%u F%u / M%X Z%X D%X", c[3], c[4], c[5],
                         (unsigned)f->vehicle_mask, (unsigned)f->zoom_mask, (unsigned)f->dead_mask);
        debugf("BENCH rdp_tail rank=%u interval_us=%u sim_ms=%u vertices=%u triangles=%u world=%u "
               "vehicles=%u bodies_held=%u pickups=%u effects=%u firstperson=%u mounted_mask=%u "
               "zoom_mask=%u dead_mask=%u\n",
               i + 1, entry->elapsed, f->sim_ms, f->vertices, f->triangles, c[0], c[1], c[2], c[3],
               c[4], c[5], (unsigned)f->vehicle_mask, (unsigned)f->zoom_mask,
               (unsigned)f->dead_mask);
    }
    rdpq_text_print(NULL, 1, 8, 204, "M MOUNTED / Z ZOOM / D DEAD");
    rdpq_text_print(NULL, 1, 8, 216, "MASK BITS 1/2/4/8 = PLAYERS 1/2/3/4");
    rdpq_text_print(NULL, 1, 8, 228, "NEXT PAGE IN 8S / A TO SWITCH");
}
#endif
#ifdef BG_VI_MEASURE
static void benchmark_vi_page(surface_t *screen) {
    rdpq_attach(screen, NULL);
    rdpq_set_mode_standard();
    rdpq_set_scissor(0, 0, 320, 240);
    rdpq_clear(RGBA32(9, 20, 39, 255));
#if defined(BG_VI_BENCHMARK) && defined(BG_PACED30)
    rdpq_text_printf(NULL, 1, 8, 16, "QUIET VI / PACED30 / %u BUFFERS",
                     (unsigned)BG_PACED30_BUFFERS);
#elif defined(BG_VI_BENCHMARK)
    rdpq_text_print(NULL, 1, 8, 16, "QUIET VI ONLY / UNPACED");
#elif defined(BG_PACED30)
    rdpq_text_print(NULL, 1, 8, 16, "VI FRESH POSES / PACED30 EXPERIMENT");
#else
    rdpq_text_print(NULL, 1, 8, 16, "VI FRESH POSES / UNPACED");
#endif
    rdpq_text_printf(NULL, 1, 8, 28, "%u MS / 1S WARMUP / 2 VI TARGET",
                     (unsigned)(bg_presentation_meter()->fresh.result[0].elapsed / 1000));
    const char *labels[] = {"ALL", "COMBAT", "VEHICLES"};
    for (unsigned g = 0; g < 3; g++) {
        const bg_cadence_result *c = &bg_presentation_meter()->fresh.result[g];
        const bg_vi_result *r = &bg_presentation_meter()->result[g];
        unsigned fps10 = c->elapsed ? (uint64_t)c->frames * 10000000 / c->elapsed : 0;
        int y = 48 + g * 42;
        rdpq_text_printf(NULL, 1, 8, y, "%s: %u POSES / %u.%u FPS", labels[g], c->frames,
                         fps10 / 10, fps10 % 10);
        rdpq_text_printf(NULL, 1, 8, y + 12, "P95 %u.%u MAX %u.%u MS / MAX %u VI", c->p95 / 1000,
                         (c->p95 / 100) % 10, c->maximum / 1000, (c->maximum / 100) % 10,
                         r->max_gap);
        rdpq_text_printf(NULL, 1, 8, y + 24, "1VI %u  2VI %u  >2VI %u", r->gap_one, r->gap_two,
                         r->gap_long);
        debugf("BENCH vi_fresh group=%s frames=%u elapsed_us=%llu p95_us=%u max_us=%u gap1=%u "
               "gap2=%u gap_long=%u max_gap=%u flips=%u duplicate_poses=%u skipped_poses=%u "
               "deadlines=%u missed=%u sample_latency_avg=%u sample_latency_max=%u "
               "ready_wait_avg=%u ready_wait_max=%u\n",
               labels[g], c->frames, (unsigned long long)c->elapsed, c->p95, c->maximum, r->gap_one,
               r->gap_two, r->gap_long, r->max_gap, r->flips, r->duplicates, r->skipped_poses,
               r->due, r->missed, c->frames ? (unsigned)(r->latency_us / c->frames) : 0,
               r->max_latency_us, c->frames ? (unsigned)(r->ready_wait_us / c->frames) : 0,
               r->max_ready_wait_us);
    }
    const bg_cadence_result *c = &bg_presentation_meter()->fresh.result[0];
    const bg_vi_result *r = &bg_presentation_meter()->result[0];
    unsigned latency = c->frames ? r->latency_us / c->frames : 0,
             ready = c->frames ? r->ready_wait_us / c->frames : 0;
    rdpq_text_printf(NULL, 1, 8, 180, "BUFFER FLIPS %u / SAME POSE %u", r->flips, r->duplicates);
    rdpq_text_printf(NULL, 1, 8, 192, "SAMPLE->VI AVG %u MAX %u MS", latency / 1000,
                     r->max_latency_us / 1000);
    rdpq_text_printf(NULL, 1, 8, 204, "READY->VI AVG %u MAX %u MS", ready / 1000,
                     r->max_ready_wait_us / 1000);
    unsigned dropped = 0;
#ifdef BG_PACED30
    dropped = paced_dropped_ticks;
#endif
    rdpq_text_printf(NULL, 1, 8, 216, "MISS %u / POSE SKIP %u / DROP %u", r->missed,
                     r->skipped_poses, dropped);
    debugf("BENCH paced_catchup_dropped_ticks_total=%u (includes warmup; original seven-tick "
           "catch-up ceiling)\n",
           dropped);
#ifdef BG_BENCHMARK
    rdpq_text_printf(NULL, 1, 8, 228, "PUMP GAP MAX %u.%u MS / VI ORIGIN",
                     (unsigned)(audio_pump_max_gap / 1000),
                     (unsigned)((audio_pump_max_gap / 100) % 10));
    debugf("BENCH audio_pump_max_entry_gap_us=%u (after warmup; not SDK queue occupancy)\n",
           (unsigned)audio_pump_max_gap);
#else
#ifdef BG_PRESENT_TRACK
    rdpq_text_printf(NULL, 1, 8, 228, "QPEAK H%u R%u S%u / FREE%uK", result_held_peak,
                     result_ready_peak, result_outstanding_peak, result_heap_free / 1024);
#else
    rdpq_text_printf(NULL, 1, 8, 228, "HELD PEAK %u / LIVE FREE %uK", result_held_peak,
                     result_heap_free / 1024);
#endif
#endif
}
static void benchmark_results(surface_t *screen) {
    /* Snapshot queue peaks before teardown releases every held frame at once.
     * These are whole-run peaks, including warmup. Heap is live, with audio and
     * the result screen still allocated; no per-frame allocator walk occurs. */
    heap_stats_t result_heap;
    sys_get_heap_stats(&result_heap);
    result_heap_free = result_heap.total - result_heap.used;
#ifdef BG_PACED30
    bg_presentation_pressure pressure = bg_presentation_peaks();
    result_held_peak = pressure.held;
#ifdef BG_PRESENT_TRACK
    result_ready_peak = pressure.ready;
    result_outstanding_peak = pressure.outstanding;
#endif
#endif
    debugf("BENCH display_buffers=%u held_peak=%u live_heap_free_bytes=%u (whole-run peak "
           "including warmup; before teardown)\n",
           (unsigned)BG_PACED30_BUFFERS, result_held_peak, result_heap_free);
#ifdef BG_PRESENT_TRACK
    debugf("BENCH sdk_ready_peak=%u submitted_not_presented_peak=%u (excludes currently acquired "
           "unsubmitted surface)\n",
           result_ready_peak, result_outstanding_peak);
#endif
    /* The ISR stops writing before publication; sorting happens only here. */
#ifdef BG_BENCHMARK
    bg_benchmark_finish(&benchmark);
#endif
    bg_presentation_finish_metrics();
#ifdef BG_PACED30
    /* Flush existing callbacks before handing every retained surface back to
     * ordinary FIFO presentation. No locked surface is abandoned at results. */
    bg_presentation_stop();
#endif
    audio_close();
    /* Results retain their measured live heap value. Retire scene residency
     * before allocating text for the diagnostic pages. */
    bg_vehicle_world_release();
#ifdef BG_BENCHMARK
    unsigned page = BG_BENCHMARK_PAGE;
#endif
    for (;;) {
#ifdef BG_BENCHMARK
        if (page < 2)
            benchmark_page(screen, page == 1);
        else if (page < 4)
            benchmark_tail_page(screen, (page - 2) * 4);
        else if (page == 4)
            benchmark_vi_page(screen);
        else
            benchmark_cost_page(screen, page == 6);
#else
        benchmark_vi_page(screen);
#endif
        rdpq_detach_show();
        rspq_wait();
        uint64_t next_page = get_ticks_us() + 8000000;
        do {
            wait_ms(20);
            joypad_poll();
        } while (!joypad_get_buttons_pressed(0).a && get_ticks_us() < next_page);
#ifdef BG_BENCHMARK
#ifndef BG_BENCHMARK_HOLD_PAGE
        page = (page + 1) % 7;
#endif
#endif
        screen = display_get();
    }
}
#endif
int main(void) {
    debug_init_isviewer();
    debug_init_usblog();
    bg_qa_bind(&views, &game_time);
#ifdef BG_BLAM_BSP
    assertf(get_memory_size() >= 8 * 1024 * 1024,
            "Original Blam BSP requires an 8 MiB Expansion Pak");
#endif
    bg_presentation_observer_init();
    display_init(RESOLUTION_320x240, DEPTH_16_BPP, BG_PACED30_BUFFERS, GAMMA_NONE,
                 FILTERS_RESAMPLE);
    bg_presentation_paced_init();
    joypad_init();
    rdpq_init();
#ifdef RDPQ_VALIDATE
    FILE *original_log = stderr;
    stderr = funopen(original_log, NULL, validation_write, NULL, NULL);
    assertf(stderr, "Validation log allocation");
    setvbuf(stderr, NULL, _IONBF, 0);
    rdpq_debug_start();
#endif
    t3d_init((T3DInitParams){});
    bg_fp_ammo_init();
    bg_fx_draw_init();
    rdpq_text_register_font(1, rdpq_font_load_builtin(FONT_BUILTIN_DEBUG_VAR));
    bg_menu_init(&menu, views);
#ifdef BG_SCORES_BENCHMARK
    for (unsigned p = 0; p < 4; p++)
        menu.styles[p] = BG_CONTROLS_XBOX;
#endif
#ifndef BG_SNAPSHOT_TICK
    bg_menu_draw_init();
#endif
    surface_t depth = surface_alloc(FMT_RGBA16, 320, 240);
    bg_scene_init();
    bg_hud_init();
    bg_set_players(views);
    bg_reset();
    bg_sound_init();
    assertf(dfs_init(DFS_DEFAULT_LOCATION) == DFS_ESUCCESS, "Game filesystem");
#ifdef BG_FRONTEND
    bg_front_init(&front);
    paused = true;
    bg_residency_menu(false);
#endif
#ifdef BG_SNAPSHOT_TICK
    /* No rendering or wall-clock scheduling during this advance. Presentation
     * state follows every tick, including recoil timestamps, explosions and
     * wheel rotations; the final state is then rendered indefinitely. */
    views = 4;
    game_time = 0;
    bg_scene_reset();
    for (uint32_t tick = 0; tick != (uint32_t)BG_SNAPSHOT_TICK; tick++) {
        bg_replay_snapshot_tick(&game_time);
        bg_scene_update(BLAM_TICK_SECONDS, game_time);
        bg_sound_update();
    }
    debugf("SNAPSHOT fixed_ticks=%u game_time=%.9g / frozen pixel QA, not FPS proof\n",
           (unsigned)BG_SNAPSHOT_TICK, game_time);
#endif
#ifdef BG_SHOWCASE
    bg_showcase_begin(BG_SHOWCASE);
    views = bg_showcase_views();
    menu.player_count = views;
#endif
#ifdef BG_INTERACTION_QA
    for (unsigned p = 0; p < BG_PLAYERS; p++)
        menu.styles[p] = p & 1 ? BG_CONTROLS_XBOX : BG_CONTROLS_N64;
    bg_qa_interaction_stage();
#endif
#ifdef BG_SHIELD_QA
    bg_qa_shield_stage();
    for (unsigned p = 0; p < 4; p++)
        debugf("SHIELD P%u vitality=%.2f hit=%.2f break=%.2f charge=%d overcharge=%d health=%.2f\n",
               p, bg_players[p].shield, bg_players[p].shield_hit, bg_players[p].shield_break,
               bg_players[p].shield_charging, bg_players[p].shield_overcharging,
               bg_players[p].health);
#endif
    heap_stats_t heap;
    sys_get_heap_stats(&heap);
    debugf("HALO N64 world=%u textures=%u RAM=%d free=%d\n", bg_collision_count, bg_material_count,
           get_memory_size(), heap.total - heap.used);
    uint64_t previous = get_ticks_us(), fps_time = previous;
    unsigned frames = 0;
#ifndef BG_SNAPSHOT_TICK
    blam_clock clock;
    blam_clock_reset(&clock);
    bg_input latch[4] = {0};
#ifdef BG_PACED30
    bool first_pose = true;
    uint64_t ui_deadline = 0;
#if defined(BG_PROFILE) && !defined(BG_BENCHMARK)
    uint64_t last_acquisition = previous;
#endif
#endif
#endif
    while (1) {
#ifdef BG_PROFILE
        uint64_t profile_start = get_ticks_us();
        bg_scene_profile.camera_us = bg_scene_profile.animation_us = bg_scene_profile.matrix_us =
            bg_scene_profile.world_us = bg_scene_profile.object_us = bg_scene_profile.fp_us =
                hud_us = audio_us = 0;
        memset(bg_geometry_profile, 0, sizeof(bg_geometry_profile));
        memset(bg_tick_profile, 0, sizeof(bg_tick_profile));
        memset(&bg_vehicle_profile, 0, sizeof(bg_vehicle_profile));
        geometry_rsp_us = geometry_rdp_us = 0;
        memset(bg_scene_profile.category_triangles, 0, sizeof(bg_scene_profile.category_triangles));
        bg_scene_profile.animated_vertices = bg_scene_profile.animated_tracks = 0;
#endif
#ifdef BG_PACED30
        unsigned ticks;
        bg_input in[4] = {0};
        surface_t *screen =
            paced_acquire(&clock, &previous, latch, in, &ticks, &first_pose, &ui_deadline);
#else
        surface_t *screen;
        while (!(screen = display_try_get()))
            pump_audio();
#endif
#ifdef BG_PROFILE
        wait_us = get_ticks_us() - profile_start;
        profile_start = get_ticks_us();
#endif
        uint64_t now = get_ticks_us();
#ifdef BG_MODEL_QA
        bg_qa_stage(now);
#endif
#ifndef BG_SNAPSHOT_TICK
#ifdef BG_VI_BENCHMARK
        /* Only the actual VI observer measures this run. No CPU/RDP cadence,
         * per-draw counters or audio polling timestamps execute in this mode. */
        if (bg_vi_complete(bg_presentation_meter()))
            benchmark_results(screen);
#endif
#ifndef BG_PACED30
        float dt = (now - previous) * .000001f;
#endif
#ifdef BG_BENCHMARK
        if (!benchmark_origin)
            benchmark_origin = now;
        if (benchmark_previous >= benchmark_origin + 1000000 &&
            benchmark.result[0].elapsed < 75000000)
            bg_benchmark_add(&benchmark, now - benchmark_previous, benchmark_vehicle,
                             benchmark_triangles, benchmark_vertices, benchmark_phases,
                             benchmark_categories);
        if (benchmark.result[0].elapsed >= 75000000 &&
            bg_cadence_complete(bg_presentation_cadence()) &&
            bg_vi_complete(bg_presentation_meter()))
            benchmark_results(screen);
        benchmark_previous = now;
#endif
#if defined(BG_PROFILE) && !defined(BG_BENCHMARK)
#ifdef BG_PACED30
        if (frames || frame_time_count)
            profile_frame_time(now - last_acquisition);
        last_acquisition = now;
#else
        if (frames || frame_time_count)
            profile_frame_time(now - previous);
#endif
#endif
#ifndef BG_PACED30
        previous = now;
        bg_input in[4] = {0};
        if (input(in))
            memset(latch, 0, sizeof(latch));
        clock.paused = paused;
        for (unsigned p = 0; p < 4; p++) {
#define EDGE(field)                                                                                \
    latch[p].field |= in[p].field;                                                                 \
    in[p].field = latch[p].field
            EDGE(jump);
            EDGE(reload);
            EDGE(switch_weapon);
            EDGE(grenade);
            EDGE(switch_grenade);
            EDGE(melee);
            EDGE(zoom);
#undef EDGE
        }
        unsigned ticks = blam_clock_update(&clock, dt);
#endif
        for (unsigned t = 0; t < ticks; t++) {
#ifdef BG_DEMO
            bg_replay_input(in, game_time);
            views = 4;
            bg_set_players(4);
#endif
#ifdef BG_SHOWCASE
            bg_showcase_input(in, game_time);
            views = bg_showcase_views();
#endif
#ifdef BG_FRONTEND_QA
            bg_front_qa_tick(in, game_time);
#endif
#ifdef BG_RELOAD_QA
            bg_qa_reload_input(in, game_time);
            views = 4;
            bg_set_players(4);
#endif
#ifdef BG_EFFECTS_QA
            bg_effects_qa_input(in, game_time);
            views = 4;
            bg_set_players(4);
#endif
#ifdef BG_DESTRUCTION_QA
            bg_destruction_qa_input(in, game_time);
            views = 4;
            bg_set_players(4);
#endif
#ifdef BG_MOVEMENT_QA
            bg_qa_movement_input(in, game_time);
#endif
#ifdef BG_COMBAT_QA
            bg_qa_combat_input(in, game_time);
#endif
            bg_clear_events();
            bg_tick(in, BLAM_TICK_SECONDS);
            game_time += BLAM_TICK_SECONDS;
#ifdef BG_SHOWCASE
            bg_showcase_observe();
#endif
            bg_scene_update(BLAM_TICK_SECONDS, game_time);
            bg_sound_update();
            for (unsigned p = 0; p < 4; p++) {
                if (bg_players[p].vehicle < 0)
                    in[p].jump = false;
                in[p].reload = in[p].switch_weapon = in[p].grenade = in[p].switch_grenade =
                    in[p].melee = in[p].zoom = false;
            }
            memset(latch, 0, sizeof(latch));
        }
#if defined(BG_VI_MEASURE) || defined(BG_PACED30)
        simulation_pose = clock.ticks;
#ifndef BG_PACED30
        frame_sample_us = now;
#endif
#endif
#endif
#ifdef BG_PROFILE
        sim_us = get_ticks_us() - profile_start;
        profile_start = get_ticks_us();
#endif
#ifdef BG_FRONTEND
        if (!front_active() && bg_match_finished()) {
            if (!match_ended)
                match_ended = now;
            if (now - match_ended >= 2500000) {
                int final_scores[4];
                for (unsigned p = 0; p < 4; p++)
                    final_scores[p] = bg_players[p].score;
                bg_front_results(&front, final_scores, bg_match_winner());
                front.statistics = *bg_match_stats();
                menu.open = false;
                paused = true;
                bg_residency_menu(true);
            }
        }
        if (front_active()) {
            bg_interaction_render_release();
#ifdef BG_PACED30
            bg_presentation_mode(false);
#endif
            bg_vehicle_world_release();
            rdpq_attach(screen, &depth);
            rdpq_clear_z(ZBUF_MAX);
            bg_front_draw(&front, now);
            pump_audio();
#ifdef BG_FRONTEND_QA
            sys_get_heap_stats(&heap);
            rdpq_set_mode_standard();
            rdpq_text_printf(NULL, 1, 4, 215, "LIVE HEAP %uK", (heap.total - heap.used) / 1024);
            rdpq_text_printf(NULL, 1, 4, 237, "SCRIPTED FRONTEND %u/%u%s", bg_front_qa_step() + 1,
                             bg_front_qa_steps(), bg_front_qa_done() ? " PASS" : "");
#ifdef RDPQ_VALIDATE
            rdpq_text_printf(NULL, 1, 4, 226, "RDP %u ERRORS %u WARNINGS", validation_errors,
                             validation_warnings);
            if (validation_errors || validation_warnings)
                rdpq_text_print(NULL, 1, 4, 215, validation_message);
#endif
#endif
#ifdef BG_PACED30
            frame_present(screen, 0);
#else
            rdpq_detach_show();
#endif
            continue;
        }
#endif
        bg_residency_gameplay();
        if (pending[slot])
            while (!rspq_syncpoint_check(fences[slot]))
                pump_audio();
#ifdef BG_PROFILE
        wait_us += get_ticks_us() - profile_start;
        profile_start = get_ticks_us();
#endif
        /* Frame preparation only writes the fenced geometry slot on the CPU.
         * Begin this frame's ordered depth clear while those matrices/vertices
         * are prepared; clear_z's nested detach already wakes the RSP. */
        rdpq_attach(screen, &depth);
        rdpq_clear_z(ZBUF_MAX);
#ifdef BG_PROFILE
        uint64_t attach_us = get_ticks_us() - profile_start;
        profile_start = get_ticks_us();
#endif
        if (views == 3)
            rdpq_clear(RGBA32(0, 0, 0, 255));
        bg_scene_prepare(slot, views, game_time);
#ifdef BG_PROFILE
        prep_us = get_ticks_us() - profile_start;
        profile_start = get_ticks_us();
#endif
        triangles = 0;
#ifdef BG_PROFILE
        bg_scene_profile.submitted_vertices = 0;
#endif
        for (unsigned p = 0; p < views; p++) {
            triangles = bg_scene_draw(p);
            /* Submit each completed view before mixing audio. This is a
             * nonblocking wakeup, not a fence or a new RDP command. */
            rspq_flush();
            pump_audio();
        }
#ifdef BG_GPU_DIAGNOSTIC
        uint64_t geometry_begin = get_ticks_us();
#endif
        /* All RSP reads of this slot's vertices, matrices and viewports end
         * with the 3D pass. HUD rectangles are copied into commands on the
         * CPU; HUD textures/blocks are immutable and own no slot resources.
         * Release geometry before HUD work so the CPU can prepare its next
         * use while that work drains. RDP completion/display ownership still
         * belongs to detach below, independently of this RSP-only fence. */
        fences[slot] = rspq_syncpoint_new();
        pending[slot] = true;
#ifdef BG_GPU_DIAGNOSTIC
        /* Diagnostic-only serialization: separate pending 3D work from HUD
         * submission. These results are not the production FPS benchmark. */
        rspq_flush();
        while (!rspq_syncpoint_check(fences[slot]))
            pump_audio();
        geometry_rsp_us = get_ticks_us() - geometry_begin;
        geometry_begin = get_ticks_us();
        diagnostic_rdp_done = false;
        rdpq_sync_full(diagnostic_rdp_complete, NULL);
        rspq_flush();
        while (!diagnostic_rdp_done)
            pump_audio();
        geometry_rdp_us = get_ticks_us() - geometry_begin;
#endif
        /* Complete every 3D view before the HUD pass to keep sprite/text
         * submission together. HUD scissoring preserves each viewport. */
#ifdef BG_PROFILE
        uint64_t hud_begin = get_ticks_us();
#endif
        for (unsigned p = 0; p < views; p++) {
            const T3DViewport *vp = bg_scene_viewport(p);
            bg_hud_draw(p, vp->offset[0], vp->offset[1], vp->size[0], vp->size[1], menu.styles[p]);
        }
#ifndef BG_SNAPSHOT_TICK
        for (unsigned p = 0; p < views; p++)
            if (scores[p]) {
                const T3DViewport *vp = bg_scene_viewport(p);
                bg_scores_draw(p, vp->offset[0], vp->offset[1], vp->size[0], vp->size[1]);
            }
#endif
#ifdef BG_PROFILE
        hud_us = get_ticks_us() - hud_begin;
#endif
        rdpq_set_scissor(0, 0, 320, 240);
        if (views > 1)
            fill(0, 119, 320, 2, RGBA32(0, 0, 0, 255));
        if (views >= 3)
            fill(159, 0, 2, 240, RGBA32(0, 0, 0, 255));
#if defined(BG_DEMO) && !defined(BG_VI_MEASURE) && !defined(BG_SNAPSHOT_TICK)
        rdpq_set_mode_standard();
        rdpq_text_printf(NULL, 1, 116, 118, "REPLAY %u FPS", fps);
#endif
#ifdef BG_FRONTEND_QA
        sys_get_heap_stats(&heap);
        rdpq_set_mode_standard();
        rdpq_text_printf(NULL, 1, 4, 215, "LIVE HEAP %uK", (heap.total - heap.used) / 1024);
        rdpq_text_printf(NULL, 1, 4, 237, "SCRIPTED FRONTEND COMBAT");
#endif
#ifdef BG_COMBAT_QA
        rdpq_set_mode_standard();
#if BG_COMBAT_QA == 7
        rdpq_text_printf(NULL, 1, 4, 225, "CAMO VISIBILITY %d%% / %d%%",
                         (int)(bg_player_visibility(&bg_players[1]) * 100),
                         (int)(bg_player_visibility(&bg_players[3]) * 100));
#elif BG_COMBAT_QA == 5
        rdpq_text_printf(NULL, 1, 4, 225, "P3 AMMO %d / %d | FRAG %d PLASMA %d", bg_players[2].ammo,
                         bg_players[2].reserve, bg_players[2].grenades[0],
                         bg_players[2].grenades[1]);
#elif BG_COMBAT_QA == 6
        rdpq_text_printf(NULL, 1, 4, 225, "16 SLAYER POINTS | THREE CAMPERS");
#else
        rdpq_text_printf(NULL, 1, 4, 225, "TARGETS S/H: %.1f/%.1f | %.1f/%.1f",
                         bg_players[1].shield, (double)bg_players[1].health, bg_players[3].shield,
                         (double)bg_players[3].health);
#endif
        rdpq_text_printf(NULL, 1, 4, 237, "SCRIPTED | %s", bg_qa_combat_title());
#endif
#ifdef BG_MOVEMENT_QA
        rdpq_set_mode_standard();
        rdpq_text_printf(NULL, 1, 4, 237, "SCRIPTED | %s", bg_qa_movement_title());
#endif
#ifdef BG_DESTRUCTION_QA
        rdpq_set_mode_standard();
        rdpq_text_print(NULL, 1, 4, 237, bg_destruction_qa_label());
#endif
#ifdef BG_EFFECTS_QA
        rdpq_set_mode_standard();
        rdpq_text_print(NULL, 1, 4, 237, bg_effects_qa_label());
#endif
#ifdef BG_MODEL_QA
        rdpq_set_mode_standard();
        rdpq_text_printf(NULL, 1, 4, 237, "MODEL QA %u: %s", bg_qa_page(), bg_qa_label());
#endif
#ifdef BG_SHOWCASE
        fill(50, 222, 220, 16, RGBA32(8, 19, 37, 255));
        rdpq_set_mode_standard();
        rdpq_text_printf(NULL, 1, 56, 233, "SCRIPTED | %s", bg_showcase_title());
        const char *caption = bg_showcase_caption();
        if (caption && caption[0]) {
            fill(50, 207, 220, 14, RGBA32(8, 19, 37, 255));
            rdpq_set_mode_standard();
            rdpq_text_print(NULL, 1, 56, 218, caption);
        }
#endif
#ifdef BG_PROFILE
        draw_us = get_ticks_us() - profile_start + attach_us;
        profile_start = get_ticks_us();
#ifndef BG_BENCHMARK
        sys_get_heap_stats(&heap);
        rdpq_set_mode_standard();
        rdpq_text_printf(NULL, 1, 2, 202, "C%u A%u X%u SND%u V%u/%u",
                         bg_scene_profile.camera_us / 1000, bg_scene_profile.animation_us / 1000,
                         bg_scene_profile.matrix_us / 1000, audio_us / 1000,
                         bg_scene_profile.animated_tracks, bg_scene_profile.animated_vertices);
        rdpq_text_printf(NULL, 1, 2, 212, "WRL%u OBJ%u FP%u HUD%u",
                         bg_scene_profile.world_us / 1000, bg_scene_profile.object_us / 1000,
                         bg_scene_profile.fp_us / 1000, hud_us / 1000);
        rdpq_text_printf(NULL, 1, 2, 222, "FRAME %u MIN%u P95%u MAX%u", frame_average / 1000,
                         frame_minimum / 1000, frame_p95 / 1000, frame_maximum / 1000);
        rdpq_text_printf(NULL, 1, 2, 232, "S%u P%u D%u W%u T%u M%d", sim_us / 1000, prep_us / 1000,
                         draw_us / 1000, wait_us / 1000, triangles,
                         (heap.total - heap.used) / 1024);
#endif
#endif
#if defined(RDPQ_VALIDATE) && !defined(BG_MENU_QA)
        rdpq_set_mode_standard();
        rdpq_text_printf(NULL, 1, 4, 215, "RDP %u ERRORS %u WARNINGS", validation_errors,
                         validation_warnings);
        if (validation_errors || validation_warnings)
            rdpq_text_print(NULL, 1, 4, 225, validation_message);
#endif
#ifndef BG_FRONTEND
        if (bg_match_finished())
            draw_result();
#endif
#ifndef BG_SNAPSHOT_TICK
        if (paused)
            draw_menu();
#endif
#ifdef BG_MENU_QA
        rdpq_set_mode_standard();
        fill(0, 0, 320, 12, RGBA32(6, 15, 30, 255));
        rdpq_set_mode_standard();
        rdpq_text_printf(NULL, 1, 4, 9, "SCRIPTED MENU QA %u/40%s", bg_menu_qa_step() + 1,
                         bg_menu_qa_done() ? " PASS" : "");
#ifdef RDPQ_VALIDATE
        fill(0, 228, 320, 12, RGBA32(6, 15, 30, 255));
        rdpq_set_mode_standard();
        rdpq_text_printf(NULL, 1, 4, 237, "RDP %u ERRORS %u WARNINGS", validation_errors,
                         validation_warnings);
#endif
#endif
#ifdef BG_PROFILE
        overlay_us = get_ticks_us() - profile_start;
        profile_start = get_ticks_us();
#endif
#if defined(BG_VI_MEASURE) || defined(BG_PACED30)
        frame_present(screen, fmodf(game_time, 75.f) >= 36.f);
#else
        rdpq_detach_show();
#endif
        slot = (slot + 1) % BG_FRAME_SLOTS;
#ifdef BG_PROFILE
        present_us = get_ticks_us() - profile_start;
#ifdef BG_RSPQ_OVERRIDE
        bg_rspq_metrics current_queue_metrics;
        bg_rspq_get_metrics(&current_queue_metrics);
        queue_us = current_queue_metrics.stall_us - previous_queue_metrics.stall_us;
        previous_queue_metrics = current_queue_metrics;
#endif
#endif
#ifdef BG_BENCHMARK
        benchmark_vehicle = fmodf(game_time, 75.f) >= 36.f;
        benchmark_triangles = triangles;
        benchmark_vertices = bg_scene_profile.submitted_vertices;
        const unsigned phase_values[BG_BENCHMARK_PHASES] = {sim_us,
                                                            bg_scene_profile.camera_us,
                                                            bg_scene_profile.animation_us,
                                                            bg_scene_profile.matrix_us,
                                                            bg_scene_profile.world_us,
                                                            bg_scene_profile.object_us,
                                                            bg_scene_profile.fp_us,
                                                            hud_us,
                                                            audio_us,
                                                            wait_us,
                                                            geometry_rsp_us,
                                                            geometry_rdp_us,
                                                            queue_us,
                                                            bg_geometry_profile[0],
                                                            bg_geometry_profile[1],
                                                            bg_geometry_profile[2],
                                                            bg_geometry_profile[3],
                                                            bg_scene_profile.body_prepare_us,
                                                            bg_scene_profile.vehicle_prepare_us,
                                                            bg_scene_profile.pickup_prepare_us,
                                                            bg_scene_profile.view_prepare_us,
                                                            bg_tick_profile[0],
                                                            bg_tick_profile[1],
                                                            bg_tick_profile[2],
                                                            bg_vehicle_profile.us[0],
                                                            bg_vehicle_profile.us[1],
                                                            bg_vehicle_profile.us[2],
                                                            bg_vehicle_profile.us[3],
                                                            bg_vehicle_profile.us[4],
                                                            bg_vehicle_profile.us[5],
                                                            bg_vehicle_profile.us[6],
                                                            bg_vehicle_profile.us[7],
                                                            bg_vehicle_profile.us[8]};
        memcpy(benchmark_phases, phase_values, sizeof(benchmark_phases));
        memcpy(benchmark_categories, bg_scene_profile.category_triangles,
               sizeof(benchmark_categories));
#endif
        frames++;
        if (now - fps_time >= 1000000) {
            fps = frames * 1000000ULL / (now - fps_time);
            frames = 0;
            fps_time = now;
#ifdef BG_TELEMETRY
            bg_telemetry_report();
#endif
#if defined(BG_PROFILE) && !defined(BG_BENCHMARK)
            sys_get_heap_stats(&heap);
            profile_frame_summary();
            debugf("PHASE camera=%u anim=%u matrix=%u world=%u objects=%u fp=%u hud=%u audio=%u "
                   "overlay=%u present=%u queue=%u tracks=%u corners=%u frame_avg=%u frame_min=%u "
                   "frame_p95=%u frame_max=%u samples=%u\n",
                   bg_scene_profile.camera_us, bg_scene_profile.animation_us,
                   bg_scene_profile.matrix_us, bg_scene_profile.world_us,
                   bg_scene_profile.object_us, bg_scene_profile.fp_us, hud_us, audio_us, overlay_us,
                   present_us, queue_us, bg_scene_profile.animated_tracks,
                   bg_scene_profile.animated_vertices, frame_average, frame_minimum, frame_p95,
                   frame_maximum, (unsigned)frame_time_count);
            debugf("PERF views=%u fps=%u triangles=%u free=%d audio=%d p1=(%.2f %.2f %.2f)\n",
                   views, fps, triangles, heap.total - heap.used, audio_can_write(),
                   bg_players[0].pos[0], bg_players[0].pos[1], bg_players[0].pos[2]);
#endif
        }
    }
}
