#ifndef BG_VEHICLE_PRIVATE_H
#define BG_VEHICLE_PRIVATE_H
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <math.h>
#include <float.h>
#include <stdio.h>
typedef float real;
typedef uint8_t byte,boolean;
typedef uint16_t word;
#define TRUE 1
#define FALSE 0
#define NONE (-1)
#define _real_epsilon .0001f
#define _pi 3.14159265358979323846f
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif
#define REAL_MIN (-FLT_MAX)
#define REAL_MAX FLT_MAX
#define MAX(a,b) ((a)>(b)?(a):(b))
#define MIN(a,b) ((a)>(b)?(b):(a))
#define PIN(x,a,b) ((x)<(a)?(a):CEILING((x),(b)))
#define FLOOR(x,a) ((x)<(a)?(a):(x))
#define CEILING(x,b) ((x)>(b)?(b):(x))
#define FLAG(b) (UINT32_C(1)<<(b))
#define TEST_FLAG(f,b) (((f)&FLAG(b))!=0)
#define SET_FLAG(f,b,on) ((f)=(on)?((f)|FLAG(b)):((f)&~FLAG(b)))
#define BIT_VECTOR_TEST_FLAG(f,b) ((f)[(b)>>5]&(UINT32_C(1)<<((b)&31)))
#define NUMBEROF(a) (sizeof(a)/sizeof((a)[0]))
#define DEGREES_TO_RADIANS(a) ((real)((real)(a)*(real)M_PI/180.f))
#define TICKS_PER_SECOND 30
#define VEHICLE_ANGULAR_ACCELERATION 0.0139626344f
#define match_assert(file,line,c) assert(c)
#define match_vassert(file,line,c,...) assert(c)
#define match_assert_valid_real_vector3d(file,line,v) assert(isfinite((v)->i)&&isfinite((v)->j)&&isfinite((v)->k))
#define match_assert_valid_real_vector3d_axes2(file,line,a,b) do{match_assert_valid_real_vector3d(file,line,a);match_assert_valid_real_vector3d(file,line,b);}while(0)
#define TAG_BLOCK_GET_ELEMENT(block,index,type) ((type*)((byte*)(block)->address+(index)*sizeof(type)))
enum {_x,_y,_z};
enum {_friction_type_point,_friction_type_forward,_friction_type_left,_friction_type_up};
enum {_point_at_rest_bit,_point_on_ground_bit,_point_on_volatile_surface_bit,_point_in_water_bit,_point_antigraving_bit};
enum {_powered_mass_point_ground_friction_bit,_powered_mass_point_water_friction_bit,_powered_mass_point_air_friction_bit,_powered_mass_point_water_lift_bit,_powered_mass_point_air_lift_bit,_powered_mass_point_thrust_bit,_powered_mass_point_antigrav_bit};
enum {_object_invisible_bit,_object_on_ground_bit,_object_on_media_bit,_object_partially_under_media_bit,_object_wholly_under_media_bit,_object_at_rest_bit};
enum {_vehicle_type_human_tank,_vehicle_type_human_jeep,_vehicle_type_human_boat,_vehicle_type_human_plane,_vehicle_type_alien_scout,_vehicle_type_alien_fighter};
enum {_unit_control_crouch_modifier_bit=0,_unit_control_jump_bit=1};
enum {_collision_feature_sphere,_collision_feature_cylinder,_collision_feature_prism,NUMBER_OF_COLLISION_FEATURE_TYPES};
#define MAXIMUM_COLLISION_FEATURES_PER_TEST 256
#define MAXIMUM_POINTS_PER_COLLISION_PRISM 8
#define NUMBER_OF_VERTICES_PER_QUADRILATERAL 4
#define MAXIMUM_VERTICES_PER_COLLISION_SURFACE 8
#define NUMBER_OF_MATERIAL_TYPES 33
#define _collision_surface_breakable_bit 3
#define _object_mask_scenery 1
#define _collision_test_for_bipeds_dead_flags 0
#define _collision_test_for_vehicles_flags 0
#define _collision_test_front_facing_surfaces_bit 0
#include "vehicle_math_types.h"
struct tag_block {int32_t count;const void *address;const void *definition;};
struct tag_reference {int32_t index;};
struct location {int32_t leaf;int16_t cluster,bsp;};
struct object_definition {struct {struct tag_reference physics;} object;};
struct unit_definition {struct {struct tag_reference physics;} object;};
struct _object_datum {real_point3d position;real_vector3d forward,up,translational_velocity,angular_velocity;uint32_t flags;struct location location;};
struct _unit_datum {real_vector3d desired_facing_vector;real_vector2d throttle;real seat_power[2];uint32_t control_flags;};
#include "vehicle_types.h"
struct object_datum {int32_t definition_index;struct _object_datum object;};
struct material_definition {float physics_ground_friction_scale,physics_ground_friction_normal_k1_scale,physics_ground_friction_normal_k0_scale,physics_ground_depth_scale,physics_ground_damp_fraction_scale;};
struct collision_result {real t;real_plane3d plane;int32_t surface_index;int16_t material_index;};
struct collision_surface {int32_t plane_designator,first_edge_index;byte flags,breakable_surface_index;int16_t material_index;};
/* Lossless 16-bit topology indices; original float coordinates/planes stay intact. */
struct collision_edge {int16_t vertex_indices[2],edge_indices[2],surface_indices[2];};
struct collision_vertex {real_point3d point;int32_t first_edge_index;};
struct bsp3d {struct tag_block nodes,planes;};
struct collision_bsp {struct bsp3d bsp3d;struct tag_block surfaces,edges,vertices;};
struct vehicle_bvh_node {int16_t bounds[6];uint16_t first,count;};
_Static_assert(sizeof(real_plane3d)==16,"Vehicle bank plane stride");
_Static_assert(sizeof(struct collision_surface)==12,"Vehicle bank surface stride");
_Static_assert(sizeof(struct collision_edge)==12,"Vehicle bank edge stride");
_Static_assert(sizeof(struct collision_vertex)==16,"Vehicle bank vertex stride");
_Static_assert(sizeof(struct vehicle_bvh_node)==16,"Vehicle bank BVH stride");
extern struct collision_bsp bg_vehicle_bsp;
extern const struct vehicle_bvh_node *bg_vehicle_bvh;
extern const uint16_t *bg_vehicle_surface_indices;
extern const int16_t (*bg_vehicle_surface_bounds)[6];
extern const unsigned bg_vehicle_world_bytes,bg_vehicle_world_layout[7][2];
extern const struct physics_definition bg_vehicle_physics_defs[4];
extern const struct vehicle_definition bg_vehicle_drive_defs[4];
extern const struct material_definition bg_vehicle_materials[NUMBER_OF_MATERIAL_TYPES];
extern const float bg_vehicle_seat_times[4][2][2];
struct vehicle_damage_kick {float acceleration;uint32_t flags;};
extern const struct vehicle_damage_kick bg_vehicle_damage_kicks[7];
extern const float bg_vehicle_acceleration_scale[4];
extern const float bg_vehicle_floor, bg_vehicle_ceiling;
/* Original mass-point order maps suspension channels to wheel centers. */
extern const int8_t bg_vehicle_suspension_points[4][8];
extern const float bg_vehicle_suspension_bounds[4][8][2];
#endif
