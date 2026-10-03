#ifndef BG_RENDER_LOD_H
#define BG_RENDER_LOD_H
#include <stdbool.h>

/* Bound the projected diameter of an arbitrary mesh contained in a sphere.
 * The projection Jacobian is bounded by (distance+radius)/(depth-radius)^2
 * throughout that sphere. projection_size is viewport height * abs(P[1][1]).
 * Squaring the rearranged inequality avoids a square root on VR4300. */
static inline bool bg_lod_diameter_below(float radius,float projection_size,
        float depth,float distance_squared,float pixels) {
    float nearest=depth-radius;
    if(radius<=0||nearest<=0||projection_size<=0)return false;
    float limit=pixels*nearest*nearest/(radius*projection_size)-radius;
    return limit>0&&distance_squared<limit*limit;
}
#endif
