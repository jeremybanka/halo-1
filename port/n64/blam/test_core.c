#include "core.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

typedef struct { int16_t identifier,pad;uint32_t value; } item;

static void test_data(void){
    blam_data_pool pool;item entries[4];blam_handle h[4];
    assert(!blam_data_init(&pool,"objects",entries,4,1));
    assert(blam_data_init(&pool,"objects",entries,4,sizeof(item)));
    for(unsigned i=0;i<4;i++){
        h[i]=blam_data_new(&pool);assert(h[i]==((UINT32_C(0xe26f)+i)<<16|i));
        item *p=blam_data_get(&pool,h[i]);assert(p==entries+i&&p->value==0);p->value=100+i;
    }
    assert(blam_data_count(&pool)==4&&blam_data_new(&pool)==BLAM_DATUM_NONE);
    assert(!blam_data_get(&pool,0)&&!blam_data_get(&pool,BLAM_DATUM_NONE));
    assert(blam_data_next(&pool,BLAM_DATUM_NONE)==h[0]);
    assert(blam_data_prev(&pool,BLAM_DATUM_NONE)==h[3]);
    assert(blam_data_delete(&pool,h[0])&&!blam_data_delete(&pool,h[0]));
    assert(blam_data_prev(&pool,h[1])==BLAM_DATUM_NONE); /* Leading hole regression. */
    blam_handle reused=blam_data_new(&pool);assert((reused&0xffff)==0&&reused!=h[0]);
    assert(!blam_data_get(&pool,h[0])&&blam_data_get(&pool,reused));
    blam_data_clear(&pool);assert(blam_data_count(&pool)==0);
    /* Exercise salt wrap and the reserved zero identifier. */
    for(unsigned i=0;i<70000;i++){
        blam_handle current=blam_data_new(&pool);assert(current!=BLAM_DATUM_NONE&&(current>>16));
        assert(blam_data_get(&pool,current)&&blam_data_delete(&pool,current));
    }
    assert(blam_data_next(&pool,BLAM_DATUM_NONE)==BLAM_DATUM_NONE);
}
static void test_memory(void){
    union { uint64_t alignment;unsigned char bytes[2048]; } arena;
    blam_memory_pool *pool=blam_memory_init(&arena,sizeof(arena),"objects");
    void *a=NULL,*b=NULL,*c=NULL;assert(pool);
    size_t initial=blam_memory_free_bytes(pool);
    assert(blam_memory_alloc(pool,&a,97));assert(blam_memory_alloc(pool,&b,111));
    assert(blam_memory_alloc(pool,&c,131));memset(a,0xa1,97);memset(b,0xb2,111);memset(c,0xc3,131);
    void *oldb=b;blam_memory_free(pool,&a);assert(!a);
    assert(blam_memory_free_bytes(pool)>blam_memory_contiguous_bytes(pool));
    blam_memory_compact(pool);assert(b!=oldb);
    for(unsigned i=0;i<111;i++)assert(((unsigned char*)b)[i]==0xb2);
    for(unsigned i=0;i<131;i++)assert(((unsigned char*)c)[i]==0xc3);
    assert(blam_memory_resize(pool,&b,500));
    for(unsigned i=0;i<111;i++)assert(((unsigned char*)b)[i]==0xb2);
    assert(!blam_memory_resize(pool,&b,4096));
    assert(blam_memory_resize(pool,&b,17));
    blam_memory_free(pool,&c);blam_memory_compact(pool);
    for(unsigned i=0;i<17;i++)assert(((unsigned char*)b)[i]==0xb2);
    blam_memory_free(pool,&b);assert(blam_memory_free_bytes(pool)==initial);
    assert(blam_memory_contiguous_bytes(pool)==initial);
    assert(blam_memory_required(initial)==sizeof(arena));
}
static void test_objects(void){
    union { uint64_t alignment;unsigned char bytes[4096]; } arena;
    blam_object_store store;blam_object_header headers[8];blam_handle handles[8];
    assert(blam_objects_init(&store,headers,8,&arena,sizeof(arena)));
    for(unsigned i=0;i<8;i++){
        handles[i]=blam_object_new(&store,127,(uint8_t)i);assert(handles[i]!=BLAM_DATUM_NONE);
        unsigned char *p=blam_object_get(&store,handles[i]);assert(p&&p[0]==0&&p[126]==0);
        memset(p,(int)i+1,127);assert(headers[i].type==i&&headers[i].data_size==127);
    }
    assert(blam_object_new(&store,1,0)==BLAM_DATUM_NONE);
    void *old=blam_object_get(&store,handles[7]);
    for(unsigned i=0;i<8;i+=2)assert(blam_object_delete(&store,handles[i]));
    blam_objects_compact(&store);assert(blam_object_get(&store,handles[7])!=old);
    for(unsigned i=0;i<8;i++){
        unsigned char *p=blam_object_at(&store,i);
        if(i&1){assert(p&&p[0]==i+1&&p[126]==i+1);assert(blam_object_handle_at(&store,i)==handles[i]);}
        else assert(!p&&!blam_object_get(&store,handles[i]));
    }
    blam_handle h=blam_object_new(&store,127,9);assert((h&0xffff)==0&&h!=handles[0]);
    assert(!blam_object_delete(&store,handles[0]));
    /* Allocation failure must roll back the header and retain every live object. */
    unsigned count=blam_data_count(&store.data);
    assert(blam_object_new(&store,32000,0)==BLAM_DATUM_NONE&&blam_data_count(&store.data)==count);
    assert(((unsigned char *)blam_object_get(&store,h))[0]==0);
}
int main(void){test_data();test_memory();test_objects();puts("Original Blam data + movable memory pool + object headers passed");return 0;}
