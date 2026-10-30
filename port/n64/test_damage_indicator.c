#include "damage_indicator.h"
#include "view_layout.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void){
 for(unsigned facing=0;facing<4;facing++)for(unsigned side=0;side<4;side++){
   float t[4]={0},yaw=facing*1.5707963268f;
   float angle=yaw+side*1.5707963268f;
   float d[3]={cosf(angle)*10,0,-sinf(angle)*10};
   bg_damage_indicator_hit(t,yaw,0,d);
   assert(t[side]>0);
   for(unsigned i=0;i<4;i++)if(i!=side)assert(t[i]==0);
 }
 float t[4]={0};bg_damage_indicator_hit(t,0,0,(float[]){0,0,0});assert(t[0]==0);
 bg_damage_indicator_hit(t,0,0,(float[]){1,4,0});assert(t[0]>0);
 bg_damage_indicator_hit(t,0,0,(float[]){-1,-4,0});assert(t[0]>0&&t[2]>0);
 for(unsigned count=1;count<=4;count++){
   unsigned char occupied[240][320]={0};
   for(unsigned p=0;p<count;p++){
     bg_view_rect r=bg_view_area(count,p);
     assert(r.x>=0&&r.y>=0&&r.x+r.w<=320&&r.y+r.h<=240);
     for(int y=r.y;y<r.y+r.h;y++)for(int x=r.x;x<r.x+r.w;x++)assert(!occupied[y][x]++);
   }
   for(unsigned y=0;y<240;y++)for(unsigned x=0;x<320;x++)assert(occupied[y][x]);
 }
 puts("PASS directional quadrants, yaw, simultaneous/elevated hits, coincident origin and full non-overlapping 1–4 view coverage");
}
