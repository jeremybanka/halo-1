#include <stdio.h>
#include <stdlib.h>
#include "asset_pve.h"
#include "pve_motion_cache.h"
#include "pve_prepare_math.h"
#include "pve_preparation_reference.inc"
bg_pve_actor bg_pve_actors[BG_PVE_MAX];
static uint8_t pve_pose_owner[BG_PVE_MAX+1][2];
static uint32_t pve_frame_keys[BG_PVE_MAX][2];
#include "pve_preparation_share.inc"
static bg_pve_motion_cache cache;
static bg_motion_track decoded[8192];
static uint32_t random_state=0xce6401;
static unsigned random_u(void){random_state=random_state*1664525u+1013904223u;return random_state;}
static uint8_t pattern(unsigned at){return (at^(at>>8)^(at>>16))&255;}
static void cache_churn(void){
    unsigned hits=0;
    for(unsigned n=0;n<3000;n++){
        if(n%500==0)bg_pve_motion_cache_reset(&cache);
        unsigned source=((n/2)%43)*4096,size=(n%13==0?98336:16+((n/2)%1200)*16);bool hit;
        uint8_t*p=bg_pve_motion_reserve(&cache,source,size,&hit);hits+=hit;
        assert(!((uintptr_t)p&15));
        if(!hit)for(unsigned j=0;j<size;j++)p[j]=pattern(source+j);
        for(unsigned j=0;j<size;j++)assert(p[j]==pattern(source+j));
        for(unsigned i=0;i<BG_PVE_MOTION_CACHE_ENTRIES;i++){
            const bg_pve_motion_entry*e=&cache.entries[i];
            assert(e->offset+e->size<=BG_PVE_MOTION_CACHE_BYTES);
            for(unsigned j=0;j<e->size;j++)assert(cache.bytes[e->offset+j]==pattern(e->source+j));
        }
    }
    assert(hits>1000);printf("PASS 3000 aligned cache requests: %u hits; wrap, overlap eviction, 98336-byte requests and resets retain exact ROM bytes\n",hits);
    bg_pve_motion_cache_reset(&cache);
}
static void aliases(void){
    unsigned stored[2][BG_PVE_MAX][2]={0},shares=0,distinct=0;
    for(unsigned frame=0;frame<4000;frame++){
        unsigned slot=frame%2,other[BG_PVE_MAX][2];memcpy(other,stored[slot^1],sizeof(other));
        memset(pve_frame_keys,0,sizeof(pve_frame_keys));
        for(unsigned i=0;i<BG_PVE_MAX;i++)for(unsigned l=0;l<2;l++)pve_pose_owner[i][l]=i;
        for(unsigned i=0;i<BG_PVE_MAX;i++){
            bg_pve_actors[i].kind=((frame/5)+(i/3))%BG_PVE_KINDS;
            for(unsigned lod=0;lod<2;lod++){
                if(random_u()%5==0)continue; // visibility/LOD changes
                unsigned clip=(frame/3)%PVE_CLIPS,mix=frame%256;
                uint32_t key=1+(clip<<24)+(2u<<16)+(3u<<8)+mix;
                if(bg_pve_actors[i].kind==BG_PVE_JACKAL&&i%2)key+=1u<<30;
                unsigned owner=pve_pose_owner[i][lod]=pve_shared_pose(i,lod,key);
                if(owner==i){stored[slot][i][lod]=1+frame*64+i*2+lod;distinct++;}
                else{
                    assert(owner<i&&pve_pose_owner[owner][lod]==owner);
                    assert(pve_frame_keys[owner][lod]==key&&bg_pve_actors[owner].kind==bg_pve_actors[i].kind);
                    assert(stored[slot][owner][lod]>frame*64);shares++;
                }
            }
        }
        /* Other in-flight slot is read-only. All four cameras consume only
         * current-frame owners, without changing any shared vertex data. */
        for(unsigned view=0;view<4;view++)for(unsigned i=0;i<BG_PVE_MAX;i++)for(unsigned l=0;l<2;l++)
            if(pve_frame_keys[i][l])assert(stored[slot][pve_pose_owner[i][l]][l]>frame*64);
        assert(!memcmp(other,stored[slot^1],sizeof(other)));
    }
    assert(shares>10000&&distinct>10000);
    printf("PASS actual pose-owner lookup: 4000 alternating fenced-frame simulations, %u shared / %u distinct poses; species, LOD, shield and slot isolation\n",shares,distinct);
}
int main(int argc,char**argv){
    assert(argc==2);FILE*f=fopen(argv[1],"rb");assert(f);fseek(f,0,SEEK_END);size_t size=ftell(f);rewind(f);
    uint8_t*rom=malloc(size);assert(rom&&fread(rom,1,size,f)==size);fclose(f);
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    for(size_t i=0;i<size;i+=2){uint8_t v=rom[i];rom[i]=rom[i+1];rom[i+1]=v;}
#endif
    cache_churn();aliases();unsigned poses=0,hits=0;uint64_t vertices=0;
    for(unsigned kind=0;kind<BG_PVE_MODELS;kind++)for(unsigned lod=0;lod<2;lod++){
        const bg_model_asset*m=&bg_pve_models[kind][lod];size_t bytes=m->vertex_count*16;
        T3DVertPacked*before=malloc(bytes),*after=malloc(bytes);assert(before&&after);
        for(unsigned c=0;c<PVE_CLIPS;c++){
            const bg_pve_animation*clip=&bg_pve_animations[kind][lod][c];assert(clip->vertices==m->vertex_count);
            for(unsigned f0=0;f0<clip->frames;f0++)for(unsigned fm=0;fm<256;fm++)for(unsigned down=0;down<(kind==BG_PVE_JACKAL?2:1);down++){
                unsigned f1=f0+1<clip->frames?f0+1:f0;int mix=fm;
                unsigned offset=(uintptr_t)clip->positions+f0*clip->tracks*6,start=offset&~15u;
                unsigned end=((uintptr_t)clip->positions+(f1+1)*clip->tracks*6+15)&~15u;assert(end<=size);
                bool hit;uint8_t*span=bg_pve_motion_reserve(&cache,start,end-start,&hit);hits+=hit;
                if(!hit)memcpy(span,rom+start,end-start);
                assert(!memcmp(span,rom+start,end-start));
                const uint16_t*samples=(const uint16_t*)(span+offset-start);
                memcpy(before,m->vertices,bytes);
                for(unsigned v=0;v<m->vertex_count/2;v++){before[v].normA=random_u();before[v].normB=random_u();}
                memcpy(after,before,bytes);
                reference_apply(clip,(const uint16_t*)(rom+offset),f0,f1,mix,kind,lod,down?0:100,before);
                bg_pve_motion_decode(decoded,clip->tracks,samples,samples+(f1-f0)*clip->tracks*3,clip->origin,mix);
                bg_motion_scatter(after,clip->vertices,clip->indices,decoded);
                if(down)for(unsigned v=0;v<clip->vertices;v++)if(bg_pve_shield_vertices[lod][v])memset(v&1?after[v/2].posB:after[v/2].posA,0,6);
                assert(!memcmp(before,after,bytes));poses++;vertices+=clip->vertices;
            }
        }
        free(before);free(after);
    }
    free(rom);printf("PASS %u exact packed poses / %llu vertices against independent pre-change loops; all species, LODs, clips, frame pairs and all 256 interpolation bins; normals/color/UV retained; %u motion hits\n",poses,(unsigned long long)vertices,hits);
}
