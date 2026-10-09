#ifndef BG_COMBAT_GEOMETRY_H
#define BG_COMBAT_GEOMETRY_H
#include "game.h"
typedef struct {int16_t bounds[6];uint16_t first,count,right;} bg_hit_node;
typedef struct {const int16_t (*vertices)[3];const uint16_t (*triangles)[3];const bg_hit_node *nodes;uint16_t vertex_count,triangle_count;int16_t bounds[6];} bg_hit_mesh;
extern const bg_hit_mesh bg_vehicle_hit_meshes[4];
float bg_vehicle_hit_ray(const bg_vehicle*v,const float origin[3],const float direction[3],float distance);
bool bg_vehicle_contacts_player(const bg_vehicle*v,const bg_player*p);
#endif
