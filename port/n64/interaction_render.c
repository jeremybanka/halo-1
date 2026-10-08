#include <libdragon.h>
#include <math.h>
#include <malloc.h>
#include "asset_interaction.h"
#include "asset_firstperson.h"
#include "interaction_cache.h"
static uint8_t *scratch;
static uint32_t rom,rom_size;
static bg_pose_cache cache;
void bg_interaction_render_init(void){
    if(scratch)return;
    rom=dfs_rom_addr("interactions.bin");rom_size=dfs_rom_size("interactions.bin");
    assertf(rom&&rom_size,"Missing Xbox interaction pose bank");
    scratch=memalign(16,bg_pose_cache_bytes(bg_interaction_scratch_bytes));
    assertf(scratch,"Interaction frame scratch allocation");
    cache.storage=scratch;cache.stride=bg_interaction_scratch_bytes;
}
static void read_frames(void*out,uint32_t offset,uint32_t bytes){
    data_cache_hit_invalidate(out,bytes);dma_read(out,rom+offset,bytes);
}
static int sample(const bg_rom_pose*p,float seconds,bool loop,const int16_t**a,const int16_t**b){
    bg_interaction_render_init();
    float phase=fmaxf(0,seconds/p->duration);
    if(loop)phase-=floorf(phase);else phase=fminf(phase,1);
    float frame=phase*(p->frames-1);unsigned f0=frame,f1=f0+1<p->frames?f0+1:f0;
    assertf(p->stride*2<=bg_interaction_scratch_bytes&&p->offset+p->stride*p->frames<=rom_size,"Interaction frame bounds");
    /* Adjacent interpolation frames are contiguous and already padded for
     * DMA. Fetch the identical pair in one transfer instead of two waits. */
    const uint8_t*data=bg_pose_cache_fetch(&cache,p->offset+p->stride*f0,p->stride*(f1==f0?1:2),read_frames);
    *a=(const int16_t*)data;*b=f1==f0?*a:(const int16_t*)(data+p->stride);
    return (frame-f0)*256;
}
void bg_interaction_pose(T3DVertPacked*out,const bg_rom_pose*p,float seconds,bool loop){
    const int16_t*a,*b;int fraction=sample(p,seconds,loop,&a,&b);
    for(unsigned i=0;i<p->vertices;i++){
        int16_t*pos=t3d_vertbuffer_get_pos(out,i);
        for(unsigned c=0;c<3;c++){unsigned k=i*3+c;pos[c]=a[k]+((int)b[k]-a[k])*fraction/256;}
    }
    data_cache_hit_writeback(out,((p->vertices+1)&~1u)*16);
}
void bg_interaction_points(int16_t(*out)[3],const bg_rom_pose*p,float seconds){
    const int16_t*a,*b;int fraction=sample(p,seconds,false,&a,&b);
    for(unsigned i=0;i<p->vertices;i++)for(unsigned c=0;c<3;c++){
        unsigned k=i*3+c;out[i][c]=a[k]+((int)b[k]-a[k])*fraction/256;
    }
}
void bg_interaction_needles(T3DVertPacked*out,unsigned ammo,float seconds){
    if(ammo>20)ammo=20;
    const bg_rom_pose*p=&bg_ready_needles[ammo];const int16_t*a,*b;int fraction=sample(p,seconds,false,&a,&b);
    for(unsigned i=0;i<p->vertices;i++){
        int16_t*pos=t3d_vertbuffer_get_pos(out,bg_ready_needle_vertices[i]);
        for(unsigned c=0;c<3;c++){unsigned k=i*3+c;pos[c]=a[k]+((int)b[k]-a[k])*fraction/256;}
    }
    data_cache_hit_writeback(out,((bg_fp_models[4].vertex_count+1)&~1u)*16);
}
