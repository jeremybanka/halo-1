#ifndef BG_VIEW_LAYOUT_H
#define BG_VIEW_LAYOUT_H
typedef struct { int x,y,w,h; } bg_view_rect;
static inline bg_view_rect bg_view_area(unsigned views,unsigned player){
    if(views==1)return (bg_view_rect){0,0,320,240};
    if(views==2)return (bg_view_rect){0,(int)player*120,320,120};
    if(views==3&&player==2)return (bg_view_rect){0,120,320,120};
    return (bg_view_rect){(int)(player%2)*160,(int)(player/2)*120,160,120};
}
#endif
