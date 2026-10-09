#include "tag_store.h"
#include <string.h>

uint32_t bgtg_u32(const void *p){
    const uint8_t *b=p;return (uint32_t)b[0]<<24|(uint32_t)b[1]<<16|(uint32_t)b[2]<<8|b[3];
}
static void put32(uint8_t *p,uint32_t n){p[0]=n>>24;p[1]=n>>16;p[2]=n>>8;p[3]=n;}
static bool range(size_t total,uint32_t offset,uint32_t count,uint32_t stride){
    return offset<=total&&count<=(total-offset)/stride;
}
static bool name_valid(const bgtg_store *s,uint32_t offset){
    return offset&&offset<s->payload_bytes&&memchr(s->payload+offset,0,s->payload_bytes-offset);
}
bool bgtg_open(bgtg_store *store,const void *file,size_t bytes){
    if(!store)return false;
    memset(store,0,sizeof(*store));if(!file||bytes<32)return false;
    const uint8_t *b=file;
    if(bgtg_u32(b)!=0x42475447u||bgtg_u32(b+4)!=1)return false;
    uint32_t tags=bgtg_u32(b+8),records=bgtg_u32(b+12),relocs=bgtg_u32(b+16);
    uint32_t relocation_offset=bgtg_u32(b+20),payload=bgtg_u32(b+24),payload_bytes=bgtg_u32(b+28);
    if(!tags||tags>65536||records!=32||!range(bytes,records,tags,28)||
       relocation_offset!=records+tags*28||!range(bytes,relocation_offset,relocs,8)||
       (uint64_t)relocation_offset+(uint64_t)relocs*8!=payload||
       !range(bytes,payload,payload_bytes,1)||(uint64_t)payload+payload_bytes!=bytes||payload_bytes<4)return false;
    bgtg_store s={b,b+records,b+relocation_offset,b+payload,tags,relocs,payload_bytes};
    if(bgtg_u32(s.payload))return false;
    for(uint32_t i=0;i<tags;i++){
        const uint8_t *r=s.records+i*28;uint32_t off=bgtg_u32(r+16),size=bgtg_u32(r+20);
        if(bgtg_u32(r)!=BGTG_HANDLE_BASE+i||!name_valid(&s,bgtg_u32(r+24)))return false;
        if(off==BGTG_MISSING){if(size)return false;}
        else if(!off||(off&3)||!size||!range(payload_bytes,off,size,1))return false;
    }
    uint32_t previous=0;
    for(uint32_t i=0;i<relocs;i++){
        const uint8_t *r=s.relocations+i*8;uint32_t at=bgtg_u32(r),target=bgtg_u32(r+4);
        if((at&3)||at<4||!range(payload_bytes,at,1,4)||!target||target>=payload_bytes||
           (i&&at<=previous)||bgtg_u32(s.payload+at)!=target)return false;
        previous=at;
    }
    *store=s;return true;
}
bool bgtg_record_get(const bgtg_store *s,uint32_t id,bgtg_record *out){
    if(!s||!s->file||!out||id<BGTG_HANDLE_BASE||id-BGTG_HANDLE_BASE>=s->tag_count)return false;
    const uint8_t *r=s->records+(id-BGTG_HANDLE_BASE)*28;
    *out=(bgtg_record){id,bgtg_u32(r+4),{bgtg_u32(r+8),bgtg_u32(r+12)},
        bgtg_u32(r+16),bgtg_u32(r+20),(const char*)s->payload+bgtg_u32(r+24)};return true;
}
const uint8_t *bgtg_get(const bgtg_store *s,uint32_t id,uint32_t group){
    bgtg_record r;if(!bgtg_record_get(s,id,&r)||r.offset==BGTG_MISSING)return NULL;
    if(group&&group!=r.group&&group!=r.parents[0]&&group!=r.parents[1])return NULL;
    return s->payload+r.offset;
}
bool bgtg_relocate32(const bgtg_store *s,void *destination,size_t capacity,uint32_t base){
    if(!s||!s->file||!destination||capacity<s->payload_bytes||(base&3)||!base||
       s->payload_bytes-1>UINT32_MAX-base)return false;
    uint8_t *d=destination;memmove(d,s->payload,s->payload_bytes);
    for(uint32_t i=0;i<s->relocation_count;i++){
        const uint8_t *r=s->relocations+i*8;put32(d+bgtg_u32(r),base+bgtg_u32(r+4));
    }
    return true;
}
