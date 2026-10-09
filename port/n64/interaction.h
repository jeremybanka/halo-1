#ifndef BG_INTERACTION_H
#define BG_INTERACTION_H
#include <stdbool.h>
#include <stdint.h>
#define BG_VEHICLE_SEATS 5
#define BG_USE_HOLD_TICKS 7
#define BG_VEHICLE_FLIP_MAX_UP .70710678f
/* The existing Warthog seat IDs are retained: driver, gunner, passenger. */
typedef struct {
    float anchor[3],entry[3],camera[3],yaw,exit_offset[3],exit_velocity[3],enter_start[3];
    float enter_time,exit_time;
    uint16_t flags;
    uint8_t pose;
} bg_seat_definition;
extern const bg_seat_definition bg_seat_definitions[4][BG_VEHICLE_SEATS];
extern const uint8_t bg_seat_counts[4];
extern const float bg_ready_times[9];
enum { BG_USE_NONE, BG_USE_PICKUP, BG_USE_ENTER, BG_USE_EXIT, BG_USE_FLIP };
enum { BG_SEAT_STABLE, BG_SEAT_ENTERING, BG_SEAT_EXITING };
typedef struct { int kind,object,seat; } bg_use_target;
#endif
