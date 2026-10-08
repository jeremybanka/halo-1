#ifndef BG_HUD_PIXELS_H
#define BG_HUD_PIXELS_H
/* Native 4x6 upright type and one-bit HUD silhouettes in a single IA4 bank.
 * 2,560 bytes, immutable after init: safe with queued, multi-buffered frames.
 * No runtime resampling, per-frame bitmap writes, or glyph allocations. */
enum { HUD_PIXEL_W=64, HUD_PIXEL_H=80 };
static uint8_t hud_pixels[HUD_PIXEL_W*HUD_PIXEL_H/2] __attribute__((aligned(16)));
static const uint8_t hud_font[][6]={
    {6,9,9,9,9,6}, {2,6,2,2,2,7}, {6,9,1,2,4,15},
    {14,1,6,1,9,6}, {2,6,10,15,2,2}, {15,8,14,1,9,6},
    {6,8,14,9,9,6}, {15,1,2,4,4,4}, {6,9,6,9,9,6}, {6,9,9,7,1,6},
    {6,9,9,15,9,9}, {14,9,14,9,9,14}, {7,8,8,8,8,7},
    {14,9,9,9,9,14}, {15,8,14,8,8,15}, {15,8,14,8,8,8},
    {7,8,8,11,9,7}, {9,9,15,9,9,9}, {7,2,2,2,2,7},
    {1,1,1,1,9,6}, {9,10,12,10,9,9}, {8,8,8,8,8,15},
    {9,15,15,9,9,9}, {9,13,13,11,11,9}, {6,9,9,9,9,6},
    {14,9,9,14,8,8}, {6,9,9,9,11,7}, {14,9,9,14,10,9},
    {7,8,6,1,1,14}, {15,2,2,2,2,2}, {9,9,9,9,9,6},
    {9,9,9,9,6,6}, {9,9,9,15,15,9}, {9,9,6,6,9,9},
    {9,9,6,2,2,2}, {15,1,2,4,8,15}, {0,0,0,15,0,0}
};
static int hud_glyph(char c){
    if(c>='0'&&c<='9')return c-'0';
    if(c>='A'&&c<='Z')return c-'A'+10;
    return c=='-'?36:-1;
}
static void hud_ink(int x,int y){
    unsigned n=y*HUD_PIXEL_W+x;
    hud_pixels[n/2]|=x&1?0x0f:0xf0;
}
static void hud_ink_box(int x,int y,int w,int h){
    for(int j=0;j<h;j++)for(int i=0;i<w;i++)hud_ink(x+i,y+j);
}
static void hud_pixels_init(void){
    for(unsigned g=0;g<sizeof(hud_font)/sizeof(hud_font[0]);g++)
        for(int y=0;y<6;y++)for(int x=0;x<4;x++)
            if(hud_font[g][y]&(8>>x))hud_ink((g%10)*6+x,(g/10)*8+y);
    for(int col=0;col<20;col++)for(int row=0;row<3;row++)
        hud_ink_box(col*2,32+row*4,1,3);
    for(int i=0;i<12;i++)hud_ink_box(i*3,44,2,5);
    for(int i=0;i<20;i++)hud_ink_box(i*2,50,1,4);
    for(int i=0;i<4;i++)hud_ink_box(i*10,55,8,5);
    for(int i=0;i<2;i++)hud_ink_box(i*21,61,18,5);
    for(int i=0;i<8;i++)hud_ink_box(i*4,67,3,3);
    /* Ammo frame: upright, with just a one-pixel clipped corner. */
    hud_ink_box(41,32,17,1);hud_ink_box(41,41,17,1);
    hud_ink_box(40,33,1,8);hud_ink_box(58,33,1,8);
    /* Frag and plasma grenade silhouettes at native six-pixel width. */
    hud_ink_box(44,45,3,1);hud_ink_box(43,46,2,1);
    hud_ink_box(43,47,4,4);hud_ink_box(42,48,6,2);
    hud_ink_box(52,45,2,1);hud_ink_box(51,46,4,1);
    hud_ink_box(50,47,6,3);hud_ink_box(51,50,4,1);
    /* Halo-style shield silhouette without the long diagonal tail. */
    hud_ink_box(1,72,44,1);hud_ink_box(1,78,44,1);
    hud_ink_box(0,73,1,5);hud_ink_box(45,73,1,5);
}
#endif
