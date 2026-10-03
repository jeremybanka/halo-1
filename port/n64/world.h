#ifndef HALO_N64_WORLD_H
#define HALO_N64_WORLD_H
#include <stdint.h>

#define BG_SCALE 32.0f
#define BG_GRID 24
typedef struct { float p[3][3]; } bg_triangle;
typedef struct { uint16_t first, count; } bg_cell;
typedef struct { float pos[3], yaw; int team; } bg_spawn;
typedef struct {
    uint32_t first;
    uint16_t count, material;
    int16_t bounds[6];
    uint16_t index_first, index_count;
} bg_chunk;
extern const bg_triangle bg_collision[];
extern const unsigned bg_collision_count;
extern const bg_cell bg_grid[BG_GRID*BG_GRID];
extern const uint16_t bg_grid_indices[];
extern const float bg_grid_origin[2], bg_grid_size[2];
extern const bg_spawn bg_spawns[];
extern const unsigned bg_spawn_count;
extern const unsigned bg_chunk_count, bg_vertex_count, bg_material_count;
extern const bg_chunk bg_chunks[];
/* Plain local indices, converted once to Tiny3D triangle lists at startup.
 * Each chunk starts on an eight-byte boundary, loads at most60 paired vertices,
 * and references at most120 triangle corners. */
extern int16_t bg_chunk_indices[];
extern const unsigned bg_spartan_vertices, bg_rifle_vertices;
#endif
