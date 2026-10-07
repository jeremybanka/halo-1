/* Separate TU: original BSP traversal is an independent BVH sweep oracle. */
#include "collision.h"
extern const blam_collision_bsp bg_blam_collision_bsp;
bool reference_segment(const float*p,const float*d,bool back,float*t){
 blam_collision_hit hit;
 bool result=blam_collision_segment(&bg_blam_collision_bsp,p,d,back,&hit);
 if(result)*t=hit.fraction;
 return result;
}
