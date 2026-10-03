#ifndef HALO_N64_BLAM_CORE_H
#define HALO_N64_BLAM_CORE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* Actual source/memory/data.c storage. Entries begin with a signed 16-bit salt.
 * The explicit-width public handle has the original salt:16/index:16 layout. */
#define BLAM_DATUM_NONE UINT32_C(0xffffffff)
typedef uint32_t blam_handle;
typedef union { uint64_t alignment; unsigned char bytes[80]; } blam_data_pool;
bool blam_data_init(blam_data_pool *pool,const char *name,void *entries,
                    unsigned capacity,unsigned stride);
void blam_data_clear(blam_data_pool *pool);
blam_handle blam_data_new(blam_data_pool *pool);
void *blam_data_get(blam_data_pool *pool,blam_handle handle);
bool blam_data_delete(blam_data_pool *pool,blam_handle handle);
blam_handle blam_data_next(blam_data_pool *pool,blam_handle previous);
blam_handle blam_data_prev(blam_data_pool *pool,blam_handle next);
unsigned blam_data_count(const blam_data_pool *pool);

/* Actual source/memory/memory_pool.c movable blocks. Reference addresses must
 * remain stable until free; compaction rewrites *reference after relocation.
 * Payloads are 4-byte aligned on N64, matching the original Blam pool. */
typedef struct memory_pool blam_memory_pool;
size_t blam_memory_required(size_t payload_capacity);
blam_memory_pool *blam_memory_init(void *storage,size_t storage_bytes,
                                  const char *name);
bool blam_memory_alloc(blam_memory_pool *pool,void **reference,size_t size);
bool blam_memory_resize(blam_memory_pool *pool,void **reference,size_t size);
void blam_memory_free(blam_memory_pool *pool,void **reference);
void blam_memory_compact(blam_memory_pool *pool);
size_t blam_memory_free_bytes(blam_memory_pool *pool);
size_t blam_memory_contiguous_bytes(blam_memory_pool *pool);

/* Original object_header_datum layout (12 bytes on N64), with source object
 * header creation/deletion and its separate, compactable payload arena. */
struct object_datum;
typedef struct object_header_datum {
    int16_t identifier;
    uint8_t flags,type;
    int16_t cluster_index,data_size;
    struct object_datum *datum;
} blam_object_header;
typedef struct {
    blam_data_pool data;
    blam_memory_pool *memory;
    unsigned capacity;
} blam_object_store;
bool blam_objects_init(blam_object_store *store,blam_object_header *headers,
                       unsigned capacity,void *arena,size_t arena_bytes);
blam_handle blam_object_new(blam_object_store *store,size_t size,uint8_t type);
void *blam_object_get(blam_object_store *store,blam_handle handle);
void *blam_object_at(blam_object_store *store,unsigned slot);
blam_handle blam_object_handle_at(blam_object_store *store,unsigned slot);
bool blam_object_delete(blam_object_store *store,blam_handle handle);
void blam_objects_compact(blam_object_store *store);
#endif
