/* Compact service boundary for verbatim CE actor movement routines. */
#include "vehicle_ai.h"
#include "blam/vehicle_private.h"
enum {_actor_facing_forward,_actor_facing_backward,_actor_facing_left,_actor_facing_right,_actor_facing_free};
enum {_actor_vehicle_driver_none,_actor_movement_type_flaming=99,_game_connection_local};
struct actor_datum {
 struct {int definition_index;} meta;
 struct {real_vector3d facing_vector;int vehicle_driver_type,pathfinding_surface_index;struct {real_point3d body_position;} position;} input;
 struct {bool face_exactly,moving_forced_by_aiming;float face_exactly_oversteer_angle;real_vector3d moving_forced_aim_direction;struct {struct {bool keep_moving;} destination_orders;} path;} control;
 struct {struct {bool move_face_exactly;int override_movement_facing;} move;} orders;
 struct {bool flying;} state;
 struct {bool ignorant_of_broken_surfaces;} emotions;
 struct {int movement_type;} output;
};
struct actor_definition {struct {float runtime_begin_movement_angle_cosine;} moving;};
struct path_collision_result {int unused;};
static struct actor_datum context;
static struct actor_definition definition;
static const real_vector3d zero={.n={0,0,0}},up={.n={0,0,1}},forward={.n={1,0,0}};
static const real_vector3d *global_zero_vector3d=&zero,*global_up3d=&up,*global_forward3d=&forward;
static const struct {bool oversteer_disable,print_oversteer;} ai_debug={0};
static float tolerance,stopping,maximum_stopping;
static struct actor_datum*actor_get(int32_t i){(void)i;return &context;}
static struct actor_definition*actor_definition_get(int i){(void)i;return &definition;}
static float actor_destination_tolerance(int32_t i){(void)i;return tolerance;}
static void actor_get_stopping_distances(int32_t i,float*a,float*b){(void)i;*a=stopping;*b=maximum_stopping;}
/* The CE 2D surface hint is replaced by vehicle-width swept clearance in the
 * caller. No infantry BSP index is fabricated for a vehicle route. */
static void actor_find_pathfinding_location(int32_t i){(void)i;context.input.pathfinding_surface_index=NONE;}
#define global_structure_bsp_get() NULL
#define structure_test_line2d(bsp,ignorant,start,surface,end,end_surface,result) ((void)(result),false)
#define console_printf(...) ((void)0)
#define game_connection() _game_connection_local
#define match_assert_valid_real_normal3d(f,l,v) match_assert_valid_real_vector3d(f,l,v)
#define valid_real_normal2d(v) (isfinite((v)->i)&&isfinite((v)->j))
#define valid_realcmp(a,b) (fabsf((a)-(b))<.0001f)
#define valid_real_vector3d_axes3(a,b,c) true
#include "enemy_vehicle_ai_original.inc"
void bg_vehicle_ai_movement(unsigned kind,const float facing[3],const float aim[3],const float desired[3],float speed,bool keep_moving,float*oversteer,float out_facing[3],float out_throttle[3]){
 const bg_vehicle_ai_definition*d=&bg_vehicle_ai_defs[kind];bool flying=kind==BG_V_BANSHEE;
 memset(&context,0,sizeof(context));memcpy(context.input.facing_vector.n,facing,12);
 context.input.vehicle_driver_type=1;context.input.pathfinding_surface_index=NONE;
 context.orders.move.override_movement_facing=NONE;context.orders.move.move_face_exactly=true;
 context.control.moving_forced_by_aiming=!flying;memcpy(context.control.moving_forced_aim_direction.n,aim,12);
 context.control.face_exactly_oversteer_angle=*oversteer;context.control.path.destination_orders.keep_moving=keep_moving;
 context.state.flying=flying;definition.moving.runtime_begin_movement_angle_cosine=d->begin_angle;
 tolerance=d->destination;float current=speed/30.f,reference=fmaxf(d->speed,current),decel=d->acceleration;
 if(flying){current=0;reference=.083333336f;decel=.016666668f;}
 float stopping_decel=flying?.026666667f:decel;
 stopping=decel>0?current*current/(stopping_decel*2):0;
 maximum_stopping=decel>0?(reference*reference-current*current)/(decel*2)+reference*reference/(stopping_decel*2):0;
 real_vector3d movement,face,throttle;memcpy(movement.n,desired,12);short direction;boolean thwarted,complete;
 actor_move_calculate_movement(0,flying,flying?0:NONE,!flying,d->sideslip*d->sideslip,flying,d->steering,d->oversteer[0],d->oversteer[1],0,d->throttle>0?d->throttle:1,&movement,&face,&direction,&throttle,&thwarted,&complete);
 memcpy(out_facing,face.n,12);memcpy(out_throttle,throttle.n,12);*oversteer=context.control.face_exactly_oversteer_angle;
 if(complete&&!keep_moving)memset(out_throttle,0,12);
}
