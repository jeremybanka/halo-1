/* Compile original source, generated only to adapt endianness and host ABI.
 * Run prepare_core.py and include its output directory when building. */
#include "core.h"
#include "cseries.h"
#include "data.c"
#include "memory_pool.c"
static struct memory_pool *object_memory_pool;
#include "object_headers.c"

char blam_core_temporary[256];
_Static_assert(sizeof(struct data_array)<=sizeof(blam_data_pool),"data pool storage");
#if UINTPTR_MAX == UINT32_MAX
_Static_assert(sizeof(struct data_array)==56,"original N64 data array ABI");
_Static_assert(sizeof(struct memory_pool)==56,"original N64 memory pool ABI");
_Static_assert(sizeof(struct memory_pool_block)==24,"original N64 block ABI");
_Static_assert(sizeof(struct object_header_datum)==12,"original N64 object header ABI");
#endif

void blam_core_assert(const char *file,int line,const char *expression){
    fprintf(stderr,"Blam assertion %s:%d: %s\n",file,line,expression);
    abort();
}
static struct data_array *array(blam_data_pool *pool){return (struct data_array *)(void *)pool;}
bool blam_data_init(blam_data_pool *pool,const char *name,void *entries,unsigned capacity,unsigned stride){
    if(!pool||!name||!entries||!capacity||capacity>32767||stride<2||stride>32767||(stride&1))return false;
    data_initialize(array(pool),name,(short)capacity,(short)stride);
    array(pool)->data=entries;array(pool)->identifier_zero_invalid=TRUE;
    data_make_valid(array(pool));return true;
}
void blam_data_clear(blam_data_pool *pool){data_delete_all(array(pool));}
blam_handle blam_data_new(blam_data_pool *pool){return (uint32_t)datum_new(array(pool));}
void *blam_data_get(blam_data_pool *pool,blam_handle handle){
    if(handle==BLAM_DATUM_NONE||!(handle>>16))return NULL;
    return datum_try_and_get(array(pool),(long)(int32_t)handle);
}
bool blam_data_delete(blam_data_pool *pool,blam_handle handle){
    if(!blam_data_get(pool,handle))return false;
    datum_delete(array(pool),(long)(int32_t)handle);return true;
}
blam_handle blam_data_next(blam_data_pool *pool,blam_handle previous){return (uint32_t)data_next_index(array(pool),(long)(int32_t)previous);}
blam_handle blam_data_prev(blam_data_pool *pool,blam_handle next){return (uint32_t)data_prev_index(array(pool),(long)(int32_t)next);}
unsigned blam_data_count(const blam_data_pool *pool){return (unsigned)((const struct data_array *)(const void *)pool)->actual_count;}

size_t blam_memory_required(size_t payload_capacity){return payload_capacity+sizeof(struct memory_pool);}
blam_memory_pool *blam_memory_init(void *storage,size_t bytes,const char *name){
    if(!storage||!name||((uintptr_t)storage&(sizeof(void *)-1))||bytes<=sizeof(struct memory_pool)||bytes>INT32_MAX)return NULL;
    struct memory_pool *pool=storage;
    memory_pool_initialize(pool,name,(long)(bytes-sizeof(*pool)));return pool;
}
bool blam_memory_alloc(blam_memory_pool *pool,void **reference,size_t size){
    if(!pool||!reference||size>INT32_MAX-sizeof(struct memory_pool_block)-sizeof(void *))return false;
    return memory_pool_block_allocate(pool,reference,(long)size)!=0;
}
bool blam_memory_resize(blam_memory_pool *pool,void **reference,size_t size){
    if(!pool||!reference||!*reference||size>INT32_MAX-sizeof(struct memory_pool_block)-sizeof(void *))return false;
    return memory_pool_block_reallocate(pool,reference,(long)size)!=0;
}
void blam_memory_free(blam_memory_pool *pool,void **reference){
    if(pool&&reference&&*reference){memory_pool_block_free(pool,reference);*reference=NULL;}
}
void blam_memory_compact(blam_memory_pool *pool){memory_pool_compact(pool);}
size_t blam_memory_free_bytes(blam_memory_pool *pool){return (size_t)memory_pool_get_free_size(pool);}
size_t blam_memory_contiguous_bytes(blam_memory_pool *pool){return (size_t)memory_pool_get_contiguous_free_size(pool);}

bool blam_objects_init(blam_object_store *store,blam_object_header *headers,unsigned capacity,void *arena,size_t bytes){
    if(!store)return false;
    store->memory=blam_memory_init(arena,bytes,"objects");store->capacity=capacity;
    return store->memory&&blam_data_init(&store->data,"object",headers,capacity,sizeof(*headers));
}
blam_handle blam_object_new(blam_object_store *store,size_t size,uint8_t type){
    if(!store||!store->memory||!size||size>32767)return BLAM_DATUM_NONE;
    object_memory_pool=store->memory;
    long index=object_header_new(array(&store->data),NONE,(short)size);
    if(index==NONE&&blam_data_count(&store->data)<store->capacity){
        /* Original pool allocation is tail-only; reclaim holes before retry. */
        memory_pool_compact(store->memory);
        index=object_header_new(array(&store->data),NONE,(short)size);
    }
    if(index!=NONE)((blam_object_header *)datum_get(array(&store->data),index))->type=type;
    return (blam_handle)index;
}
void *blam_object_get(blam_object_store *store,blam_handle handle){
    blam_object_header *header=blam_data_get(&store->data,handle);return header?header->datum:NULL;
}
blam_handle blam_object_handle_at(blam_object_store *store,unsigned slot){
    if(!store||slot>=store->capacity)return BLAM_DATUM_NONE;
    blam_object_header *headers=array(&store->data)->data;
    return headers[slot].identifier?((uint32_t)(uint16_t)headers[slot].identifier<<16)|slot:BLAM_DATUM_NONE;
}
void *blam_object_at(blam_object_store *store,unsigned slot){return blam_object_get(store,blam_object_handle_at(store,slot));}
bool blam_object_delete(blam_object_store *store,blam_handle handle){
    if(!blam_object_get(store,handle))return false;
    object_memory_pool=store->memory;
    object_header_delete(array(&store->data),(long)(int32_t)handle);return true;
}
void blam_objects_compact(blam_object_store *store){memory_pool_compact(store->memory);}
