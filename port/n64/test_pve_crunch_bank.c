#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include <string.h>
#include "asset_pve.h"
int main(int argc,char**argv){
 assert(argc==2);FILE*f=fopen(argv[1],"rb");assert(f);fseek(f,0,SEEK_END);size_t size=ftell(f);rewind(f);uint8_t*rom=malloc(size);assert(rom&&fread(rom,1,size,f)==size);fclose(f);
 unsigned points=0,triangles=0;
 for(unsigned k=0;k<BG_PVE_KINDS;k++)for(unsigned l=0;l<BG_PVE_LODS;l++){
  const bg_model_asset*m=&bg_pve_models[k][l];assert(m->vertex_count&&m->vertex_count%2==0);
  for(unsigned b=0;b<m->batch_count;b++){assert(m->batches[b].first+m->batches[b].count<=m->vertex_count);assert(m->batches[b].count<=64);assert(bg_pve_batch_modes[k][l][b]<=3);}
  triangles+=m->triangle_count;
  for(unsigned c=0;c<PVE_CLIPS;c++){
   const bg_pve_animation*a=&bg_pve_animations[k][l][c],*near=&bg_pve_animations[k][0][c];
   assert(a->duration==near->duration&&a->frames==near->frames&&a->vertices==m->vertex_count);
   size_t start=(uintptr_t)a->positions;assert(start+(size_t)a->frames*a->tracks*6<=size);
   const bg_bounds*box=&bg_pve_crunch_bounds[k][c];
   for(unsigned v=0;v<a->vertices;v++)assert(a->indices[v]<a->tracks);
   for(unsigned n=0;n<a->frames*a->tracks;n++)for(unsigned axis=0;axis<3;axis++){
    const uint8_t*p=rom+start+(n*3+axis)*2;int packed=a->origin[axis]+((p[0]<<8)|p[1]);float x=packed/BG_PVE_SCALE;
    assert(x>=box->min[axis]&&x<=box->max[axis]);points++;
   }
  }
 }
 printf("PASS %u packed animation coordinates inside the all-tier clip bounds; %u triangles, finite frame ranges, timing parity and valid batch limits\n",points,triangles);
 free(rom);
}
