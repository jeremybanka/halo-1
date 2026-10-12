#ifndef BG_MAP_FORMAT_H
#define BG_MAP_FORMAT_H
#include <stdint.h>
/* Private, big-endian ROM bank. Sections are independently allocated so no
 * map requires one large contiguous heap block. Every offset is 16-aligned. */
enum {
    BG_MAP_VERTICES, BG_MAP_CHUNKS, BG_MAP_INDICES, BG_MAP_TEXTURES,
    BG_MAP_TEXTURE_SIZES, BG_MAP_TEXTURE_CI4, BG_MAP_TEXTURE_OVERLAY,
    BG_MAP_PALETTE, BG_MAP_COLLISION_VERTICES, BG_MAP_COLLISION_FACES,
    BG_MAP_COLLISION_FLAGS, BG_MAP_GRID, BG_MAP_GRID_INDICES,
    BG_MAP_GRID_BOUNDS, BG_MAP_SPAWNS, BG_MAP_SLAYER_SPAWNS,
    BG_MAP_ITEMS, BG_MAP_START, BG_MAP_TELEPORTERS, BG_MAP_VEHICLES,
    BG_MAP_SKY, BG_MAP_ORIGIN, BG_MAP_WORLD_LAYOUT, BG_MAP_SECTIONS
};
enum { BG_MAP_MAGIC = 0x484d3634, BG_MAP_VERSION = 1,
       BG_MAP_HEADER_BYTES = 16 + BG_MAP_SECTIONS * 12 };
typedef struct { uint32_t offset, count, stride; } bg_map_section;
/* BG_MAP_TEXTURE_OVERLAY byte: legacy 0/1 retain identical draw commands.
 * New maps may add 2 = alpha-tested depth writer, 4 = two-sided geometry.
 * Transparent and depth-writing cutout flags are mutually exclusive. */
#endif
