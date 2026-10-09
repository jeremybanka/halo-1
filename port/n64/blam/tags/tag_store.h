#ifndef HALO_N64_BLAM_TAG_STORE_H
#define HALO_N64_BLAM_TAG_STORE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* BGTG/1 is an audited metadata prototype, not a full original tag cache.
 * Data and pointer words are BE32. Unbound model/animation/etc. entries resolve
 * to no metadata. No caller should use this as an object_new backend yet. */
enum { BGTG_HANDLE_BASE=0x4e640000u, BGTG_MISSING=0xffffffffu };
typedef struct {
    const uint8_t *file,*records,*relocations,*payload;
    uint32_t tag_count,relocation_count,payload_bytes;
} bgtg_store;
typedef struct { uint32_t id,group,parents[2],offset,bytes;const char *name; } bgtg_record;

/* Validates all file ranges, names and relocations before exposing a view. */
bool bgtg_open(bgtg_store *store,const void *file,size_t bytes);
bool bgtg_record_get(const bgtg_store *store,uint32_t id,bgtg_record *record);
/* requested_group==0 accepts any class; inheritance recognizes both parents. */
const uint8_t *bgtg_get(const bgtg_store *store,uint32_t id,uint32_t requested_group);
/* Copies and relocates to a 32-bit target address. On a big-endian 32-bit N64,
 * target_address must equal (uintptr_t)destination. Hosts can inspect the BE
 * result for format testing, but must not cast its data to native structs. */
bool bgtg_relocate32(const bgtg_store *store,void *destination,size_t capacity,uint32_t target_address);
uint32_t bgtg_u32(const void *p);
#endif
