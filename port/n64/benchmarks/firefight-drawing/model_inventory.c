#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdint.h>
#include "asset_pve.h"
static unsigned loads(const bg_model_asset*m){unsigned n=0;for(unsigned i=0;i<m->batch_count;i++)n+=(m->batches[i].count+1)&~1u;return m->batch_count?n:(m->vertex_count+1)&~1u;}
static int same_attributes(const T3DVertPacked*v,unsigned a,unsigned b){
 const T3DVertPacked*x=&v[a/2],*y=&v[b/2];
 return (a&1?x->normB:x->normA)==(b&1?y->normB:y->normA)&&
 (a&1?x->rgbaB:x->rgbaA)==(b&1?y->rgbaB:y->rgbaA)&&
 !memcmp(a&1?x->stB:x->stA,b&1?y->stB:y->stA,4);
}
static int same_motion(const unsigned char*motion,unsigned k,unsigned l,unsigned a,unsigned b){
    int same=1;for(unsigned c=0;c<PVE_CLIPS;c++){
     const bg_pve_animation*t=&bg_pve_animations[k][l][c];
     if(t->indices[a]!=t->indices[b]){
      const unsigned char*bank=motion+(uintptr_t)t->positions;
      for(unsigned frame=0;frame<t->frames;frame++)if(memcmp(bank+(frame*t->tracks+t->indices[a])*6,bank+(frame*t->tracks+t->indices[b])*6,6)){same=0;break;}
      if(!same)break;
     }
    }
return same;
}
int main(int argc,char**argv){
 if(argc!=2)return 2;FILE*f=fopen(argv[1],"rb");if(!f)return 2;fseek(f,0,SEEK_END);long size=ftell(f);rewind(f);unsigned char*motion=malloc(size);if(!motion||fread(motion,1,size,f)!=(size_t)size)return 2;fclose(f);
 for(unsigned k=0;k<BG_PVE_MODELS;k++)for(unsigned l=0;l<2;l++){
  const bg_model_asset*m=&bg_pve_models[k][l];unsigned unique=0,position_classes=0;
  for(unsigned a=0;a<m->vertex_count;a++){
   int found=0;
   for(unsigned b=0;b<a&&!found;b++)if(same_attributes(m->vertices,a,b)){
    int same=same_motion(motion,k,l,a,b);
    if(same&&k==BG_PVE_JACKAL&&bg_pve_shield_vertices[l][a]!=bg_pve_shield_vertices[l][b])same=0;
    found=same;
   }
   unique+=!found;
   found=0;for(unsigned b=0;b<a&&!found;b++)found=same_motion(motion,k,l,a,b);position_classes+=!found;
  }
  printf("NPC kind=%u lod=%u loads=%u packed=%u triangles=%u batches=%u idle_tracks=%u exact_full_motion_attribute_classes=%u full_motion_position_classes=%u\n",k,l,loads(m),m->vertex_count,m->triangle_count,m->batch_count,bg_pve_animations[k][l][0].tracks,unique,position_classes);
 }
 for(unsigned k=0;k<BG_M_COUNT;k++)printf("MODEL kind=%u near=%u far=%u triangles=%u\n",k,loads(&bg_model_assets[k]),loads(&bg_pickup_lods[k]),bg_model_assets[k].triangle_count);
 printf("SPARTAN far=%u triangles=%u\n",loads(&bg_spartan_lod),bg_spartan_lod.triangle_count);
}
