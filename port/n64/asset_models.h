#ifndef BG_ASSET_MODELS_H
#define BG_ASSET_MODELS_H
#include <stdint.h>
#include <stdbool.h>
#include <t3d/t3d.h>
/* Model-local precision is independent of the much larger terrain range. */
#define BG_MODEL_SCALE 128.0f
#define BG_OBJECT_SCALE 1024.0f
/* Stable ordering: the first eight entries match the multiplayer weapon IDs. */
enum { BG_M_AR, BG_M_PISTOL, BG_M_PLASMA_PISTOL, BG_M_PLASMA_RIFLE,
       BG_M_NEEDLER, BG_M_SHOTGUN, BG_M_SNIPER, BG_M_ROCKET,
       BG_M_WARTHOG, BG_M_GHOST, BG_M_SCORPION, BG_M_BANSHEE,
       BG_M_FRAG, BG_M_PLASMA_GRENADE, BG_M_FLAMETHROWER, BG_M_SPARTAN,
       BG_M_HEALTHPACK, BG_M_OVERSHIELD, BG_M_CAMOUFLAGE, BG_M_COUNT };
typedef struct { T3DVertPacked *vertices; uint16_t vertex_count; float radius; } bg_model_asset;
extern const bg_model_asset bg_model_assets[BG_M_COUNT];
/* Same Warthog/Ghost/Scorpion/Banshee order as the vehicle game enum. */
extern const bg_model_asset bg_vehicle_lods[4];
enum { BG_PART_BODY, BG_PART_WHEEL, BG_PART_TURRET, BG_PART_BARREL };
/* Vertex ranges address the corresponding whole vehicle model. All first
 * indices are even; odd triangle groups end with one degenerate triangle.
 * Pivots are vehicle-local, Y-up Halo units (multiply by BG_OBJECT_SCALE
 * before rotation inside a scaled model instance).
 * Wheel rotation uses local Z. Turrets rotate around local Y. Barrels inherit
 * turret yaw around turret_pivot, then pitch around their own local Z pivot. */
typedef struct { uint16_t first,count; uint8_t kind; float pivot[3]; } bg_vehicle_part;
typedef struct { const bg_vehicle_part *parts; uint8_t count; float turret_pivot[3]; } bg_vehicle_rig;
extern const bg_vehicle_rig bg_vehicle_rigs[4];
enum { BG_A_IDLE, BG_A_RUN, BG_A_FIRE, BG_A_RELOAD, BG_A_DEATH,
       BG_A_JUMP, BG_A_MELEE, BG_A_THROW, BG_A_DRIVE,
       BG_A_PASSENGER, BG_A_GUNNER, BG_A_COUNT };
/* Positions are frame-major, unique-track-major XYZ in Y-up coordinates.
 * Each rendered triangle corner indexes its exact original motion track. */
typedef struct { const uint8_t *positions; const uint16_t *indices;
                 uint16_t frames, vertices, tracks; float duration;
                 int16_t origin[3]; } bg_anim_asset;
extern const bg_anim_asset bg_animations[BG_A_COUNT];
extern const bg_model_asset bg_spartan_lod;
/* Source Xbox multipurpose blue-channel color-change masks, one per corner. */
extern const uint8_t bg_spartan_team_mask[], bg_spartan_lod_team_mask[];
extern const bg_anim_asset bg_spartan_lod_animations[BG_A_COUNT];
/* Original animated right-hand marker. Position is player-local Y-up Halo
 * units. Quaternion is standard Hamilton XYZW, already converted to Y-up.
 * Multiply the player's world transform by this local attachment transform. */
typedef struct { float pos[3],quat[4]; } bg_attachment_pose;
typedef struct { const bg_attachment_pose *poses; uint16_t frames; float duration; } bg_attachment_clip;
extern const bg_attachment_clip bg_weapon_attachment[BG_A_COUNT];
enum { BG_S_AR, BG_S_PISTOL, BG_S_PLASMA_PISTOL, BG_S_PLASMA_RIFLE,
       BG_S_NEEDLER, BG_S_SHOTGUN, BG_S_SNIPER, BG_S_ROCKET,
       BG_S_FLAMETHROWER, BG_S_RELOAD, BG_S_PISTOL_RELOAD, BG_S_NEEDLER_RELOAD,
       BG_S_SHOTGUN_RELOAD, BG_S_SNIPER_RELOAD, BG_S_ROCKET_RELOAD,
       BG_S_EXPLOSION, BG_S_PLASMA_EXPLOSION, BG_S_WARTHOG, BG_S_GHOST, BG_S_SCORPION,
       BG_S_JUMP, BG_S_FOOTSTEP, BG_S_SHIELD_HIT, BG_S_SHIELD_CHARGE,
       BG_S_DEATH, BG_S_RESPAWN, BG_S_SLAYER, BG_S_GAME_OVER,
       BG_S_DOUBLE_KILL, BG_S_TRIPLE_KILL, BG_S_KILLING_SPREE, BG_S_TELEPORTER, BG_S_AMBIENCE,
       BG_S_BANSHEE, BG_S_WARTHOG_GUN, BG_S_SCORPION_GUN, BG_S_GHOST_GUN,
       BG_S_BANSHEE_GUN, BG_S_BANSHEE_BOMB, BG_S_COUNT };
typedef struct { const int8_t *samples; uint32_t count; uint16_t rate; bool loop; } bg_audio_asset;
extern const bg_audio_asset bg_audio_assets[BG_S_COUNT];
#endif
