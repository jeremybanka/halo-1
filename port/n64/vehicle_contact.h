#ifndef BG_VEHICLE_CONTACT_H
#define BG_VEHICLE_CONTACT_H
#include <math.h>
#include <stdbool.h>
#include <stdint.h>

/* physics.c:physics_compute_biped_collision, after biped_accelerate.
 * Keep the native 30 Hz constants and source XYZ summation order. The port's
 * coordinates are X/Y-up/Z, and its velocities are units per second. Testing
 * the pre-impulse relative speed or rounding the thresholds to integers changes
 * the source boundary. Clearance remains the bounded capsule adapter. */
static bool bg_vehicle_contact_damage(const float vehicle_velocity[3],
                                      const float biped_velocity_after_impulse[3],
                                      bool own_previous_vehicle,uint32_t ticks_since_exit){
    if(own_previous_vehicle&&ticks_since_exit<=90)return false;
    float x=vehicle_velocity[0]/30.f,y=-vehicle_velocity[2]/30.f,z=vehicle_velocity[1]/30.f;
    float bx=biped_velocity_after_impulse[0]/30.f,by=-biped_velocity_after_impulse[2]/30.f,bz=biped_velocity_after_impulse[1]/30.f;
    float dx=x-bx,dy=y-by,dz=z-bz;
    return sqrtf((x*x+y*y)+z*z)>.06666667f||(dx*dx+dy*dy)+dz*dz>.0011111111f;
}
#endif
