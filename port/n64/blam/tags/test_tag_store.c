#include "tag_store.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void put32(uint8_t *p,uint32_t v){p[0]=v>>24;p[1]=v>>16;p[2]=v>>8;p[3]=v;}
static void invalid_field(uint8_t *copy,const uint8_t *original,size_t size,size_t offset,uint32_t value){
    memcpy(copy,original,size);put32(copy+offset,value);bgtg_store s;assert(!bgtg_open(&s,copy,size));
}
int main(int argc,char **argv){
    assert(argc==2);FILE *f=fopen(argv[1],"rb");assert(f);assert(!fseek(f,0,SEEK_END));
    long n=ftell(f);assert(n>32);rewind(f);size_t bytes=(size_t)n;
    uint8_t *data=malloc(bytes),*copy=malloc(bytes);assert(data&&copy);
    assert(fread(data,1,bytes,f)==bytes);fclose(f);bgtg_store store;
    assert(bgtg_open(&store,data,bytes));assert(store.tag_count==1565);
    unsigned bound=0,unbound=0,weapon=0;bool saw_ar=false,saw_spartan=false;
    for(uint32_t i=0;i<store.tag_count;i++){
        bgtg_record record;assert(bgtg_record_get(&store,BGTG_HANDLE_BASE+i,&record));
        const uint8_t *meta=bgtg_get(&store,record.id,record.group);
        assert(!bgtg_get(&store,record.id,0x61626364));
        if(record.offset==BGTG_MISSING){assert(!meta);unbound++;continue;}
        assert(meta==store.payload+record.offset);bound++;
        if(record.group==0x77656170){weapon++;assert(record.bytes==1288);assert(bgtg_get(&store,record.id,0x6974656d));assert(bgtg_get(&store,record.id,0x6f626a65));}
        if(record.group==0x77656170&&!strcmp(record.name,"weapons\\assault rifle\\assault rifle"))saw_ar=true;
        if(record.group==0x62697064&&!strcmp(record.name,"characters\\cyborg_mp\\cyborg_mp")){saw_spartan=true;assert(record.bytes==1268);}
    }
    assert(bound==91&&unbound==1474&&weapon==12&&saw_ar&&saw_spartan);
    assert(!bgtg_get(&store,0,0));assert(!bgtg_get(&store,BGTG_HANDLE_BASE+store.tag_count,0));
    uint8_t *relocated=malloc(store.payload_bytes);assert(relocated);
    assert(!bgtg_relocate32(&store,relocated,store.payload_bytes-1,0x80400000));
    assert(!bgtg_relocate32(&store,relocated,store.payload_bytes,0xfffffffcu));
    assert(!bgtg_relocate32(&store,relocated,store.payload_bytes,0x80400001));
    assert(bgtg_relocate32(&store,relocated,store.payload_bytes,0x80400000));
    for(uint32_t i=0;i<store.relocation_count;i++){
        const uint8_t *r=store.relocations+i*8;
        assert(bgtg_u32(relocated+bgtg_u32(r))==0x80400000+bgtg_u32(r+4));
    }
    for(size_t size=0;size<bytes;size+=97){bgtg_store s;assert(!bgtg_open(&s,data,size));}
    invalid_field(copy,data,bytes,0,0);invalid_field(copy,data,bytes,4,2);
    invalid_field(copy,data,bytes,8,UINT32_MAX);invalid_field(copy,data,bytes,12,0);
    invalid_field(copy,data,bytes,16,UINT32_MAX);invalid_field(copy,data,bytes,20,0);
    invalid_field(copy,data,bytes,24,UINT32_MAX);invalid_field(copy,data,bytes,28,UINT32_MAX);
    invalid_field(copy,data,bytes,32,0);invalid_field(copy,data,bytes,32+24,store.payload_bytes);
    size_t rel=(size_t)(store.relocations-data);
    invalid_field(copy,data,bytes,rel,store.payload_bytes-1);
    invalid_field(copy,data,bytes,rel+4,store.payload_bytes);
    invalid_field(copy,data,bytes,rel+8,bgtg_u32(store.relocations));
    uint32_t random=0x854241f3u;
    for(unsigned i=0;i<2000;i++){
        memcpy(copy,data,bytes);random=random*1664525u+1013904223u;size_t at=random%bytes;
        copy[at]^=(uint8_t)(1u<<(i%8));bgtg_store fuzz;(void)bgtg_open(&fuzz,copy,bytes);
    }
    printf("BGTG: %u bound, %u explicitly unbound tags; %u relocations; class inheritance, truncation, corruption and 2000 mutation checks passed\n",bound,unbound,store.relocation_count);
    free(relocated);free(copy);free(data);return 0;
}
