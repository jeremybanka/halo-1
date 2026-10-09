#ifndef BG_FIRSTPERSON_AMMO_H
#define BG_FIRSTPERSON_AMMO_H
#include <t3d/t3d.h>
/* Call once after Tiny3D initialization. The eight private vertex buffers use
 * the same two fenced geometry slots as the caller's normal FP buffers. */
void bg_fp_ammo_init(void);
/* Call once from animate_firstperson after ordinary animation, before any
 * draw borrows this slot/player. Reload elapsed is -1 outside a reload. */
void bg_fp_ammo_prepare(unsigned slot,unsigned player,unsigned weapon,unsigned clip,
    unsigned f0,unsigned f1,int fraction,int ammo,int reserve,float reload_elapsed,
    T3DVertPacked*firstperson_vertices);
/* AR only: current Tiny3D matrix must be that player's ordinary FP matrix.
 * Preserves the RDP mode stack and matrix, adds 8 vertices / 4 triangles. */
void bg_fp_ammo_draw(unsigned slot,unsigned player);
#endif
