#include "pve_crunch_lod.h"
#include <assert.h>
#include <stdio.h>
int main(void){
 float cam[4][4]={{1,0,0,0},{0,1,0,0},{0,0,1,0},{0,0,0,1}};
 float proj[4][4]={{1.25,0,0,0},{0,1.6666667f,0,0},{0,0,1,0},{0,0,0,1}};
 bg_pve_crunch_state s={0};bg_cull_bounds b={.min={-10,-10,-101},.max={10,10,-99},.valid=true};
 assert(bg_pve_crunch_select(&s,1,0,&b,cam,proj,160,120,4,true,false));
 assert(!bg_pve_crunch_select(&s,1,0,&b,cam,proj,160,120,4,true,true));
 assert(!bg_pve_crunch_select(&s,1,0,&b,cam,proj,160,120,4,false,false));
 b.min[0]=b.min[1]=-15;b.max[0]=b.max[1]=15;
 assert(!bg_pve_crunch_select(&s,1,0,&b,cam,proj,160,120,4,true,false));
 s.small=true;assert(bg_pve_crunch_select(&s,1,0,&b,cam,proj,160,120,4,true,false));
 assert(!bg_pve_crunch_select(&s,2,0,&b,cam,proj,160,120,4,true,false));
 s.small=true;assert(!bg_pve_crunch_select(&s,2,1,&b,cam,proj,160,120,4,true,false));
 b.min[2]=-5;b.max[2]=-3;assert(!bg_pve_crunch_select(&s,2,1,&b,cam,proj,160,120,4,true,false));
 unsigned passed=0;
 for(unsigned i=0;i<40000;i++){
  float angle=(i%93)*.031f;cam[0][0]=cam[2][2]=cosf(angle);cam[0][2]=-sinf(angle);cam[2][0]=sinf(angle);
  b.min[0]=(i%47)*15-350;b.max[0]=b.min[0]+2+(i%55);
  b.min[1]=(i%31)*17-200;b.max[1]=b.min[1]+2+(i%61);
  b.min[2]=-10-(i%5000);b.max[2]=b.min[2]+2+(i%17);
  for(unsigned v=1;v<=4;v++){
   unsigned width=v<3?320:160,height=v==1?240:120;
   if(!bg_pve_crunch_below(&b,cam,proj,width,height,4,28))continue;
   double lo[2]={1e30,1e30},hi[2]={-1e30,-1e30};
   for(unsigned corner=0;corner<8;corner++){
    double q[3]={0};for(unsigned a=0;a<3;a++)for(unsigned j=0;j<3;j++)q[a]+=((corner&(1u<<j))?b.max[j]:b.min[j])*(double)cam[j][a];
    assert(-q[2]>4.001);
    for(unsigned a=0;a<2;a++){double pixel=q[a]*(a?height:width)*.5*proj[a][a]/-q[2];lo[a]=fmin(lo[a],pixel);hi[a]=fmax(hi[a],pixel);}
   }
   assert(hi[0]-lo[0]<27.501&&hi[1]-lo[1]<27.501);passed++;
  }
 }
 assert(passed>10000);printf("PASS %u conservative 1-4P box projections; zoom/near-plane, original near tier, hysteresis, recycled generation/species\n",passed);
}
