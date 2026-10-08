#ifndef BG_HUD_BUTTONS_H
#define BG_HUD_BUTTONS_H
/* Immutable native-size IA4 icons. Uses hud_font from hud_pixels.h.
 * C directions form a diamond of four buttons: filled = requested direction.
 * No scaling or filtered sampling is needed at any viewport size. */
enum { HUD_BUTTON_A,HUD_BUTTON_B,HUD_BUTTON_L,HUD_BUTTON_R,HUD_BUTTON_Z,
       HUD_BUTTON_C_UP,HUD_BUTTON_C_DOWN,HUD_BUTTON_C_LEFT,HUD_BUTTON_C_RIGHT,
       HUD_BUTTON_START,HUD_BUTTON_DPAD,HUD_BUTTON_COUNT };
enum { HUD_BUTTON_W=64,HUD_BUTTON_H=48 };
static uint8_t hud_button_pixels[HUD_BUTTON_W*HUD_BUTTON_H/2] __attribute__((aligned(16)));
static const uint8_t hud_button_width[HUD_BUTTON_COUNT]={10,10,14,14,14,13,13,13,13,14,13};
static const uint8_t hud_button_height[HUD_BUTTON_COUNT]={10,10,10,10,10,13,13,13,13,10,13};
static void hud_button_ink(unsigned id,int x,int y,unsigned ink){
    unsigned n=((id/4)*16+y)*HUD_BUTTON_W+(id%4)*16+x;
    uint8_t mask=n&1?0x0f:0xf0;
    hud_button_pixels[n/2]=(hud_button_pixels[n/2]&~mask)|(n&1?ink:ink<<4);
}
static void hud_buttons_init(void){
    const char letters[]="ABLRZ";
    for(unsigned id=0;id<HUD_BUTTON_COUNT;id++){
        int w=hud_button_width[id],h=hud_button_height[id];
        if(id>=HUD_BUTTON_C_UP&&id<=HUD_BUTTON_C_RIGHT){
            const int origins[4][2]={{4,0},{4,8},{0,4},{8,4}};
            for(unsigned d=0;d<4;d++)for(int y=0;y<5;y++)for(int x=0;x<5;x++){
                if((x==0||x==4)&&(y==0||y==4))continue;
                bool edge=x==0||x==4||y==0||y==4;
                hud_button_ink(id,origins[d][0]+x,origins[d][1]+y,
                    d==id-HUD_BUTTON_C_UP?15:edge?5:1);
            }
            unsigned d=id-HUD_BUTTON_C_UP;
            /* Direction triangle, cut out of the selected button. */
            for(int y=0;y<3;y++)for(int x=0;x<3;x++){
                bool ink=d==0?y>=abs(x-1):d==1?2-y>=abs(x-1):d==2?x>=abs(y-1):2-x>=abs(y-1);
                if(ink)hud_button_ink(id,origins[d][0]+1+x,origins[d][1]+1+y,1);
            }
        }else if(id==HUD_BUTTON_DPAD){
            for(int y=0;y<h;y++)for(int x=0;x<w;x++)
                if((x>=4&&x<=8)||(y>=4&&y<=8)){
                    bool edge=x==0||x==12||y==0||y==12||
                        ((x==4||x==8)&&(y<4||y>8))||((y==4||y==8)&&(x<4||x>8));
                    hud_button_ink(id,x,y,edge?15:1);
                }
        }else{
            for(int y=0;y<h;y++){
                int inset=y==0||y==h-1?2:y==1||y==h-2?1:0;
                int left=inset,right=w-1-inset;
                /* L/R have an outside shoulder and a square inside edge.
                 * Z retains matching shoulders on both sides. */
                if(id==HUD_BUTTON_L)right=w-1;
                if(id==HUD_BUTTON_R)left=0;
                for(int x=left;x<=right;x++)
                    hud_button_ink(id,x,y,y==0||y==h-1||x==left||x==right?15:1);
            }
            if(id<=HUD_BUTTON_Z){
                const uint8_t*glyph=hud_font[hud_glyph(letters[id])];
                for(int y=0;y<6;y++)for(int x=0;x<4;x++)
                    if(glyph[y]&(8>>x))hud_button_ink(id,(w-4)/2+x,2+y,15);
            }else{ /* Conventional Start/play triangle. */
                for(int y=0;y<5;y++)for(int x=0;x<=2-abs(y-2);x++)hud_button_ink(id,6+x,2+y,15);
            }
        }
    }
}
#endif
