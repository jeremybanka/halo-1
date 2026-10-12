#include "residency.h"
#include "scene.h"
#include "sound.h"
#include "blam/vehicle_physics.h"
#include "map.h"
#include "asset_interaction.h"
#include "interaction_cache.h"
void bg_residency_prepare_match(unsigned players, unsigned map) {
    bg_scene_reserve_firstperson(players);
    /* Blood Gulch carries the larger collision/vehicle bank. Keep pose bytes
     * identical while spending less RAM on redundant cached frame pairs. */
    bg_interaction_render_reserve(map == BG_MAP_BLOOD_GULCH ? 4 : BG_POSE_CACHE_SLOTS);
#ifdef BG_FRONTEND
    /* Scene model command tables are initialized before frontend entry. */
    bg_scene_load_bodies();
#endif
#ifdef BG_STREAM_MAPS
    if (bg_map_loaded()) bg_vehicle_world_preload();
#endif
}
void bg_residency_menu(bool release_bodies) {
    bg_vehicle_world_release();
    bg_scene_release_firstperson();
    if (release_bodies)
        bg_scene_release_bodies();
#ifdef BG_STREAM_MAPS
    bg_scene_release_world();
    bg_map_unload();
#endif
    bg_sound_frontend(true);
}
void bg_residency_quit_confirmation(void) {
    bg_scene_release_firstperson();
    bg_scene_release_bodies();
}
void bg_residency_gameplay(void) {
    bg_scene_load_bodies();
    bg_scene_load_firstperson();
}
