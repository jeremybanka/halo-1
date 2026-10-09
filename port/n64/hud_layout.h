#ifndef HALO_N64_HUD_LAYOUT_H
#define HALO_N64_HUD_LAYOUT_H

/* Xbox's reticle is at the title-safe window center, not necessarily the
 * pixel viewport center. See source/main/main.c:compute_window_bounds,
 * source/rasterizer/xbox/rasterizer_xbox.c:RASTERIZER_FRAME_BOUNDS_*, and
 * source/interface/hud_draw.c:hud_calculate_point. Coordinates below retain
 * the original 640x480 canvas until the final viewport-local conversion.
 * The eight Xbox weapon aim overlays have tag anchor_offset=(0,0).
 */
static inline void bg_hud_aim_point(unsigned views,unsigned player,
    float x,float y,float width,float height,float *aim_x,float *aim_y)
{
    unsigned columns=views>=3?2:1,rows=views==1?1:2;
    unsigned column=player%columns,row=player/columns;
    unsigned frame_width=544/columns,frame_height=408/rows;
    unsigned inset=views==1?0:4;
    unsigned left=48+column*frame_width+column*inset;
    unsigned right=48+(column+1)*frame_width-(column==0?inset:0);
    unsigned top=36+row*frame_height+row*inset;
    unsigned bottom=36+(row+1)*frame_height-(row==0?inset:0);
    /* Original integer midpoint and original pixel viewport origin. */
    float local_x=(float)((left+right)/2)-(float)(column*(640/columns));
    float local_y=(float)((top+bottom)/2)-(float)(row*(480/rows));
    *aim_x=x+local_x*width/(float)(640/columns);
    *aim_y=y+local_y*height/(float)(480/rows);
}

/* Tiny3D is column-major with camera forward along -Z and screen Y down.
 * Translate the projection so that this unchanged forward/shot ray lands on
 * the same point as the HUD. Call after set_projection and before look_at:
 * look_at then rebuilds the camera/projection product and culling planes.
 * Preserve the port's existing FOV, zoom, depth and camera orientation.
 */
static inline void bg_hud_aim_projection(float projection[4][4],
    unsigned views,unsigned player)
{
    float x,y;
    bg_hud_aim_point(views,player,0,0,1,1,&x,&y);
    projection[2][0]=1.f-2.f*x;
    projection[2][1]=2.f*y-1.f;
}
#endif
