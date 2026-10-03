#ifndef BG_RENDER_VISIBILITY_H
#define BG_RENDER_VISIBILITY_H

/* Keep CPU submission alive for four native framebuffer pixels beyond every
 * viewport edge. This changes only the four side planes used by AABB tests;
 * projection, near/far clipping and RDP scissoring stay exact. Tiny3D still
 * clips crossing triangles using its guard band (never vertex rejection).
 *
 * In homogeneous clip space the left plane is x + (1 + 2*b/w)*w >= 0.
 * Forming it from the final camera/projection also supports off-axis aiming.
 * AABB tests only use the sign, so plane normalization is unnecessary. */
#define BG_CULL_BLEED_PIXELS 4.f
static inline void bg_visibility_side_planes(float planes[6][4],
        const float camera_projection[4][4],float width,float height){
    const float bleed[2]={1.f+2.f*BG_CULL_BLEED_PIXELS/width,
                         1.f+2.f*BG_CULL_BLEED_PIXELS/height};
    for(unsigned a=0;a<2;a++)for(unsigned c=0;c<4;c++){
        float w=camera_projection[c][3]*bleed[a];
        planes[a*2][c]=w+camera_projection[c][a];
        planes[a*2+1][c]=w-camera_projection[c][a];
    }
}
#endif
