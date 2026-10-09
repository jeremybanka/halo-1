#ifndef BG_INTERACTION_POSES_H
#define BG_INTERACTION_POSES_H
#include <stdint.h>
#include "render_bounds.h"
/* Frames are read from DragonFS, never copied wholesale into RDRAM. Each
 * frame is padded to 16 bytes and contains big-endian XYZ int16 positions. */
typedef struct {
    uint32_t offset, stride;
    uint16_t vertices, frames;
    float duration;
    bg_bounds bounds;
} bg_rom_pose;
extern const bg_rom_pose bg_locomotion_poses[6][2], bg_locomotion_grips[6];
extern const bg_rom_pose bg_seat_poses[][3][2];
extern const bg_rom_pose bg_body_ready_poses[2], bg_body_ready_grip;
extern const bg_rom_pose bg_seat_grips[], bg_hatch_poses[2][2];
extern const bg_rom_pose bg_ready_poses[9], bg_ready_ar_digits, bg_ready_scope,
    bg_ready_needles[21];
extern const bg_rom_pose bg_ready_plasma[2];
extern const uint16_t bg_ready_needle_vertices[];
enum {
#define BG_SERVICE(id, name, weapon, clip) BG_SERVICE_##name = id,
#include "interaction_services.def"
#undef BG_SERVICE
    BG_SERVICE_COUNT
};
extern const bg_rom_pose bg_service_poses[BG_SERVICE_COUNT], bg_service_details[BG_SERVICE_COUNT],
    bg_service_vents[BG_SERVICE_COUNT], bg_reload_ar_digits, bg_shotgun_fire_muzzle;
extern const unsigned bg_interaction_scratch_bytes;

#endif
