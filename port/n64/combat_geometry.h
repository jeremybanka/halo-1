#ifndef BG_COMBAT_GEOMETRY_H
#define BG_COMBAT_GEOMETRY_H
#include "game.h"
#if defined(N64) && defined(BG_PROFILE)
extern uint32_t bg_geometry_profile[4];
#endif
typedef struct {int16_t bounds[6];uint16_t first,count,right;} bg_hit_node;
typedef struct {uint8_t kind;float pivot[3];} bg_hit_part;
typedef struct {const int16_t (*frames)[4][3];uint16_t count;} bg_hit_hatch;
extern const bg_hit_hatch bg_hit_hatches[2][2];
typedef struct {const int16_t (*vertices)[3];const uint16_t (*triangles)[3];const bg_hit_node *nodes;const uint8_t *materials;uint16_t vertex_count,triangle_count;int16_t bounds[6];const uint8_t *groups;const bg_hit_part *parts;uint16_t part_count,node_count,turret_part;} bg_hit_mesh;
const bg_hit_mesh *bg_vehicle_collision_pose(const bg_vehicle*v);
typedef struct {uint32_t offset;uint16_t stride,count;float duration;} bg_hit_clip;
extern const bg_hit_clip bg_player_hit_clips[];
extern const uint16_t bg_player_hit_triangles[][3],bg_player_hit_groups[][2];
extern const uint8_t bg_player_hit_regions[];
extern const unsigned bg_player_hit_vertex_count,bg_player_hit_group_count;
float bg_player_hit_ray(unsigned player,const float origin[3],const float direction[3],float distance,int *region);
extern const bg_hit_mesh bg_vehicle_hit_meshes[4];
float bg_vehicle_hit_ray_material(const bg_vehicle*v,const float origin[3],const float direction[3],float distance,unsigned *material);
float bg_vehicle_hit_ray(const bg_vehicle*v,const float origin[3],const float direction[3],float distance);
/* In-place camera fan distances, preserving the five independent ray predicates. */
void bg_vehicle_camera_packet(const bg_vehicle*v,const float origin[3],const float directions[5][3],const float reaches[5],float distances[5]);
bool bg_vehicle_resolve_player(const bg_vehicle*v,bg_player*p);
bool bg_vehicle_contacts_player(const bg_vehicle*v,const bg_player*p);
#endif
