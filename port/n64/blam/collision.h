#ifndef HALO_N64_BLAM_COLLISION_H
#define HALO_N64_BLAM_COLLISION_H
#include <stdbool.h>
#include <stdint.h>

/* Original collision-BSP record layouts. Xbox long is explicit int32_t here
 * so host tests and big-endian N64 use identical array strides. */
typedef union { struct { float x,y; };float n[2]; } blam_point2;
typedef union { struct { float x,y,z; };float n[3]; } blam_point3;
typedef union { struct { float i,j; };float n[2]; } blam_vector2;
typedef union { struct { float i,j,k; };float n[3]; } blam_vector3;
typedef struct { blam_vector2 n;float d; } blam_plane2;
typedef struct { blam_vector3 n;float d; } blam_plane3;
typedef struct tag_block { int32_t count;const void *address;const void *definition; } blam_tag_block;
typedef struct bsp3d_node { int32_t plane_designator,children[2]; } blam_bsp3d_node;
typedef struct bsp2d_node { blam_plane2 plane;int32_t child_indices[2]; } blam_bsp2d_node;
typedef struct collision_leaf { uint16_t flags;int16_t bsp2d_reference_count;int32_t first_bsp2d_reference_index; } blam_collision_leaf;
typedef struct bsp2d_reference { int32_t plane_designator,root_index; } blam_bsp2d_reference;
typedef struct collision_surface { int32_t plane_designator,first_edge_index;uint8_t flags,breakable_surface_index;int16_t material_index; } blam_collision_surface;
typedef struct collision_edge { int32_t vertex_indices[2],edge_indices[2],surface_indices[2]; } blam_collision_edge;
typedef struct collision_vertex { blam_point3 point;int32_t first_edge_index; } blam_collision_vertex;
typedef struct bsp3d { blam_tag_block nodes,planes; } blam_bsp3d;
typedef struct bsp2d { blam_tag_block nodes; } blam_bsp2d;
typedef struct collision_bsp {
    blam_bsp3d bsp3d;
    blam_tag_block leaves,bsp2d_references;
    blam_bsp2d bsp2d;
    blam_tag_block surfaces,edges,vertices;
} blam_collision_bsp;
typedef struct { float fraction;float normal[3];int32_t surface;int16_t material; } blam_collision_hit;

/* Coordinates and vectors are original Halo XYZ world units. Displacement is
 * the complete segment, with the returned hit fraction between zero and one. */
bool blam_collision_segment(const blam_collision_bsp *bsp,const float origin[3],
                             const float displacement[3],bool back_faces,
                             blam_collision_hit *hit);
#endif
