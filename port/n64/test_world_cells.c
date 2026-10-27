#include "render_world_cells.h"
#include <assert.h>
#include <stdio.h>
int main(void){
 const uint32_t bits[]={1,2,4,8,16,32,64,128};
 const bg_world_cells_data d={{-2,-2,-2},{2,2,2},{2,2,2},1,8,1,bits,0,0};
 for(unsigned y=0;y<2;y++)for(unsigned z=0;z<2;z++)for(unsigned x=0;x<2;x++){
  float eye[]={-1.f+2*x,-1.f+2*y,-1.f+2*z};unsigned index=(y*2+z)*2+x;
  const uint32_t *row=bg_world_cells_row(&d,1,eye);assert(row==bits+index);
  for(unsigned b=0;b<8;b++)assert(bg_world_cells_keep(&d,row,b)==(b==index));
  assert(bg_world_cells_keep(&d,row,8));
 }
 assert(bg_world_cells_row(&d,1,(float[]){0,0,0})==bits+7);
 assert(bg_world_cells_row(&d,1,(float[]){-2,-2,-2})==bits);
 assert(!bg_world_cells_row(&d,1,(float[]){2,0,0}));
 assert(!bg_world_cells_row(&d,1,(float[]){-2.001,0,0}));
 assert(!bg_world_cells_row(&d,2,(float[]){0,0,0}));
 assert(!bg_world_cells_row(&d,1,(float[]){NAN,0,0}));
 assert(!bg_world_cells_row(&d,1,(float[]){0,INFINITY,0}));
 assert(!bg_world_cells_row(0,1,(float[]){0,0,0}));
 assert(bg_world_cells_keep(&d,0,0));
 const uint16_t lookup[]={3,3,0,0,2,2,1,1};
 const bg_world_cells_data fine={{-1,-1,-1},{1,1,1},{2,2,2},1,8,1,bits,lookup,&d};
 assert(bg_world_cells_row_view(&fine,1,(float[]){-.5,-.5,-.5},0)==bits+3);
 assert(bg_world_cells_row_view(&fine,1,(float[]){.5,-.5,-.5},0)==bits+3);
 assert(bg_world_cells_row_view(&fine,1,(float[]){-.5,-.5,-.5},1)==bits);
 assert(bg_world_cells_row_view(&fine,1,(float[]){1.5,0,0},0)==bits+7);
 assert(!bg_world_cells_row_view(&fine,1,(float[]){2,0,0},0));
 assert(!bg_world_cells_row_view(&fine,2,(float[]){0,0,0},1));
 assert(!bg_world_cells_row_view(&fine,1,(float[]){NAN,0,0},0));
 assert(!bg_world_cells_row_view(0,1,(float[]){0,0,0},1));
 puts("PASS: cell layout, shared boundaries, upper/outside/map/NaN/infinity fallback and chunk bounds");
}
