#ifndef BG_ASSET_HUD_H
#define BG_ASSET_HUD_H
#include <stdint.h>
/* w/h retain the Xbox layout rectangle. Only transparent padding is removed
 * from the stored texture; offsets and one border texel preserve filtering. */
typedef struct { const uint16_t *pixels; uint16_t w,h,tex_w,tex_h,x,y; } bg_hud_image;
enum { BG_H_SHIELD_BG, BG_H_HEALTH_BG, BG_H_MOTION_BG, BG_H_SHIELD_METER,
       BG_H_HEALTH_METER, BG_H_AMMO_BG,
       BG_H_RETICLE_AR, BG_H_RETICLE_PISTOL, BG_H_RETICLE_PLASMA_PISTOL,
       BG_H_RETICLE_PLASMA_RIFLE, BG_H_RETICLE_NEEDLER, BG_H_RETICLE_SHOTGUN,
       BG_H_RETICLE_SNIPER, BG_H_RETICLE_ROCKET,
       BG_H_AMMO_AR, BG_H_AMMO_PISTOL, BG_H_AMMO_NEEDLER, BG_H_AMMO_SHOTGUN,
       BG_H_AMMO_SNIPER, BG_H_AMMO_ROCKET,
       BG_H_DIGIT_0, BG_H_DIGIT_1, BG_H_DIGIT_2, BG_H_DIGIT_3, BG_H_DIGIT_4,
       BG_H_DIGIT_5, BG_H_DIGIT_6, BG_H_DIGIT_7, BG_H_DIGIT_8, BG_H_DIGIT_9,
       BG_H_GRENADE_FRAG, BG_H_GRENADE_PLASMA, BG_H_BLIP, BG_H_RADAR_SWEEP, BG_H_MOTION_FG,
       BG_H_RETICLE_WARTHOG, BG_H_RETICLE_GHOST, BG_H_RETICLE_SCORPION, BG_H_RETICLE_BANSHEE,
       BG_H_ZOOM_2X, BG_H_ZOOM_10X,
       BG_H_COUNT };
/* Native Xbox HUD bitmap dimensions; render at 0.5 for a 320x240 full view. */
extern const bg_hud_image bg_hud_images[BG_H_COUNT];
/* Original split-screen masks and sniper ticks reduced to I8. Separate alpha
 * precision avoids the one-bit alpha used by ordinary RGBA16 HUD sprites. */
enum { BG_SCOPE_PISTOL, BG_SCOPE_SNIPER, BG_SCOPE_TICK_0, BG_SCOPE_TICK_1,
       BG_SCOPE_TICK_2, BG_SCOPE_TICK_3, BG_SCOPE_TICK_4, BG_SCOPE_COUNT };
typedef struct { const uint8_t *pixels; uint16_t w,h,stride; } bg_scope_image;
extern const bg_scope_image bg_scope_images[BG_SCOPE_COUNT];
#endif
