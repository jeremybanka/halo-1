#include "residency.h"
#include "scene.h"
#include "sound.h"
#include "blam/vehicle_physics.h"
void bg_residency_menu(bool release_bodies) {
    bg_vehicle_world_release();
    bg_scene_release_firstperson();
    if (release_bodies)
        bg_scene_release_bodies();
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
