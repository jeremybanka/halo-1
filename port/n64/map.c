#include "map.h"
#include "map_format.h"
#include "game.h"
#include "pickup_rules.h"
#include "terrain.h"
#include "sky.h"
#include "blam/vehicle_physics.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef N64
#include <libdragon.h>
#else
#include <assert.h>
#define assertf(c, ...) assert(c)
#endif

void *bg_map_vertex_data, *bg_map_texture_data;
const bg_triangle *bg_collision;
unsigned bg_collision_count, bg_spawn_count, bg_chunk_count, bg_vertex_count, bg_material_count;
const uint8_t *bg_collision_flags, *bg_texture_sizes, *bg_texture_ci4, *bg_texture_overlay;
const bg_cell *bg_grid;
const uint16_t *bg_grid_indices, *bg_ground_palette;
const float *bg_grid_origin, *bg_grid_size;
const bg_spawn *bg_spawns;
const bg_chunk *bg_chunks;
int16_t *bg_chunk_indices;
const uint8_t *bg_slayer_spawns;
const bg_map_item *bg_map_items;
unsigned bg_map_item_count, bg_teleporter_count, bg_map_vehicle_count;
const int *bg_start_weapons, *bg_start_grenades;
const bg_teleporter *bg_teleporters;
const bg_map_vehicle *bg_map_vehicles;
const uint8_t (*bg_sky_rgb)[3];
static void *blocks[BG_MAP_SECTIONS];
static bg_triangle *triangles;
static bool loaded;
static unsigned resident;
static bg_map_info current = {.id = BG_MAP_BLOOD_GULCH, .origin = {68, -118, 0}, .void_height = -8};
static const struct { unsigned id; const char *name,*world; } catalog[] = {
#define BG_MAP(id,symbol,name) {id,name,"rom:/maps/" name "-world.bin"},
#include "map_catalog.def"
#undef BG_MAP
};
static unsigned map_index(unsigned id) {
    for(unsigned i=0;i<sizeof(catalog)/sizeof(*catalog);i++)if(catalog[i].id==id)return i;
    assertf(false, "Unsupported map %u", id);return 0;
}
const bg_map_info *bg_map_current(void) { return &current; }
bool bg_map_loaded(void) { return loaded; }
unsigned bg_map_resident_bytes(void) { return resident; }
const char *bg_map_world_path(void) {
#ifdef N64
    return catalog[map_index(current.id)].world;
#else
    static char path[512];
    const char *directory = getenv("BG_MAP_DIRECTORY");
    snprintf(path, sizeof(path), "%s/%s-world.bin", directory ? directory : "halo64-assets/generated/maps", catalog[map_index(current.id)].name);
    return path;
#endif
}
static uint32_t be32(const uint8_t *p) {
    return (uint32_t)p[0] << 24 | (uint32_t)p[1] << 16 | (uint32_t)p[2] << 8 | p[3];
}
static void validate_world_layout(void) {
    const unsigned strides[7] = {16, 12, 12, 16, 16, 12, 2};
    unsigned end = 0;
    assertf(current.world_bytes < 2 * 1024 * 1024, "Map world bank capacity");
    for (unsigned i = 0; i < 7; i++) {
        const uint32_t *part = current.world_layout[i];
        unsigned size = part[1] * strides[i];
        assertf(part[0] == end && part[1] && part[1] <= 65535 &&
                part[0] <= current.world_bytes && size <= current.world_bytes - part[0],
                "Map world layout %u", i);
        end = part[0] + size;
    }
    assertf(end == current.world_bytes, "Map world bank length");
}
#ifndef __MIPSEB__
/* Host sanitizer fixtures use the same bank and loader as the real ROM. */
static void swap16(uint8_t *p) { uint8_t a = p[0]; p[0] = p[1]; p[1] = a; }
static void swap32(uint8_t *p) { swap16(p); swap16(p + 2); uint8_t a = p[0], b = p[1]; p[0] = p[2]; p[1] = p[3]; p[2] = a; p[3] = b; }
static void host_order(unsigned s, void *memory, unsigned count, unsigned stride) {
    uint8_t *p = memory;
    for (unsigned i = 0; i < count; i++, p += stride) {
        switch (s) {
        case BG_MAP_VERTICES:
            for (unsigned j = 0; j < 16; j += 2) swap16(p + j);
            swap32(p + 16); swap32(p + 20);
            for (unsigned j = 24; j < 32; j += 2) swap16(p + j);
            break;
        case BG_MAP_CHUNKS:
            swap32(p); for (unsigned j = 4; j < 24; j += 2) swap16(p + j); break;
        case BG_MAP_ITEMS:
            for (unsigned j = 0; j < 16; j += 4) swap32(p + j);
            swap16(p + 16); break;
        case BG_MAP_TEXTURES: case BG_MAP_INDICES: case BG_MAP_PALETTE:
        case BG_MAP_COLLISION_FACES: case BG_MAP_GRID: case BG_MAP_GRID_INDICES:
            for (unsigned j = 0; j < stride; j += 2) swap16(p + j); break;
        case BG_MAP_COLLISION_VERTICES: case BG_MAP_GRID_BOUNDS: case BG_MAP_SPAWNS:
        case BG_MAP_START: case BG_MAP_TELEPORTERS: case BG_MAP_VEHICLES:
        case BG_MAP_ORIGIN: case BG_MAP_WORLD_LAYOUT:
            for (unsigned j = 0; j < stride; j += 4) swap32(p + j); break;
        default: break;
        }
    }
}
void bg_map_host_world_order(unsigned block, void *memory, unsigned bytes) {
    uint8_t *p = memory;
    if (block == 1) {
        for (unsigned i = 0; i < bytes; i += 12) { swap32(p+i); swap32(p+i+4); swap16(p+i+10); }
    } else if (block == 0 || block == 3) {
        for (unsigned i = 0; i < bytes; i += 4) swap32(p+i);
    } else {
        for (unsigned i = 0; i < bytes; i += 2) swap16(p+i);
    }
}
#endif
void bg_map_unload(void) {
    bg_vehicle_world_release();
    free(triangles); triangles = NULL;
    for (unsigned s = 0; s < BG_MAP_SECTIONS; s++) { free(blocks[s]); blocks[s] = NULL; }
    bg_map_vertex_data = bg_map_texture_data = NULL;
    bg_collision = NULL; bg_collision_flags = NULL; bg_grid = NULL; bg_grid_indices = NULL;
    bg_grid_origin = bg_grid_size = NULL; bg_spawns = NULL; bg_chunks = NULL; bg_chunk_indices = NULL;
    bg_texture_sizes = bg_texture_ci4 = bg_texture_overlay = NULL; bg_ground_palette = NULL;
    bg_slayer_spawns = NULL; bg_map_items = NULL; bg_start_weapons = bg_start_grenades = NULL;
    bg_teleporters = NULL; bg_map_vehicles = NULL; bg_sky_rgb = NULL;
    bg_collision_count = bg_spawn_count = bg_chunk_count = bg_vertex_count = bg_material_count = 0;
    bg_map_item_count = bg_teleporter_count = bg_map_vehicle_count = 0;
    resident = 0; loaded = false; bg_terrain_reset();
}
bool bg_map_load(unsigned id) {
    if (loaded && current.id == id) return true;
    unsigned index = map_index(id);
    bg_map_unload();
    char path[512];
#ifdef N64
    snprintf(path, sizeof(path), "rom:/maps/%s.map64", catalog[index].name);
#else
    const char *directory = getenv("BG_MAP_DIRECTORY");
    snprintf(path, sizeof(path), "%s/%s.map64", directory ? directory : "halo64-assets/generated/maps", catalog[index].name);
#endif
    FILE *f = fopen(path, "rb"); assertf(f, "Map bank %s", path);
    uint8_t header[BG_MAP_HEADER_BYTES];
    assertf(fread(header, 1, sizeof(header), f) == sizeof(header), "Map header");
    unsigned bytes = be32(header + 12);
    assertf(be32(header) == BG_MAP_MAGIC && be32(header + 4) == BG_MAP_VERSION &&
            be32(header + 8) == id && bytes < 2 * 1024 * 1024, "Map bank format");
    fseek(f, 0, SEEK_END); assertf(ftell(f) == (long)bytes, "Map bank length");
    const unsigned strides[BG_MAP_SECTIONS] = {32,24,2,2048,1,1,1,2,12,6,1,4,2,16,20,1,24,16,28,20,3,16,60};
    bg_map_section sections[BG_MAP_SECTIONS];
    unsigned end = BG_MAP_HEADER_BYTES;
    for (unsigned s = 0; s < BG_MAP_SECTIONS; s++) {
        const uint8_t *p = header + 16 + s * 12;
        sections[s] = (bg_map_section){be32(p), be32(p + 4), be32(p + 8)};
        unsigned size = sections[s].count * sections[s].stride;
        assertf(sections[s].stride == strides[s] && sections[s].count <= 65535 &&
                sections[s].offset >= end && sections[s].offset % 16 == 0 &&
                sections[s].offset <= bytes && size <= bytes - sections[s].offset, "Map section %u", s);
        end = sections[s].offset + size;
    }
    assertf(sections[BG_MAP_CHUNKS].count <= 512 && sections[BG_MAP_TEXTURES].count <= 32 &&
            sections[BG_MAP_VERTICES].count && sections[BG_MAP_CHUNKS].count &&
            sections[BG_MAP_TEXTURES].count && sections[BG_MAP_PALETTE].count == 16 &&
            sections[BG_MAP_TEXTURE_SIZES].count == sections[BG_MAP_TEXTURES].count &&
            sections[BG_MAP_TEXTURE_CI4].count == sections[BG_MAP_TEXTURES].count &&
            sections[BG_MAP_TEXTURE_OVERLAY].count == sections[BG_MAP_TEXTURES].count &&
            sections[BG_MAP_COLLISION_FACES].count && sections[BG_MAP_COLLISION_VERTICES].count &&
            sections[BG_MAP_COLLISION_FLAGS].count == sections[BG_MAP_COLLISION_FACES].count &&
            sections[BG_MAP_SLAYER_SPAWNS].count == sections[BG_MAP_SPAWNS].count &&
            sections[BG_MAP_SPAWNS].count && sections[BG_MAP_SPAWNS].count <= 128 &&
            sections[BG_MAP_ITEMS].count <= BG_MAX_PICKUPS && sections[BG_MAP_VEHICLES].count <= BG_MAX_VEHICLES &&
            sections[BG_MAP_TELEPORTERS].count <= 16 && sections[BG_MAP_GRID].count == BG_GRID * BG_GRID &&
            sections[BG_MAP_GRID_BOUNDS].count == 1 && sections[BG_MAP_START].count == 1 &&
            sections[BG_MAP_ORIGIN].count == 1 && sections[BG_MAP_WORLD_LAYOUT].count == 1 &&
            sections[BG_MAP_SKY].count == 33, "Map section capacities");
    /* The selected world bank is the largest immutable working set. Read
     * its small descriptor and reserve it before finer map allocations. */
    uint8_t descriptor[60];
    fseek(f, sections[BG_MAP_WORLD_LAYOUT].offset, SEEK_SET);
    assertf(fread(descriptor, 1, 60, f) == 60, "Map world descriptor");
    current.id = id; current.world_bytes = be32(descriptor);
    for (unsigned i = 0; i < 7; i++) for (unsigned j = 0; j < 2; j++)
        current.world_layout[i][j] = be32(descriptor + 4 + (i * 2 + j) * 4);
    validate_world_layout();
    bg_vehicle_world_preload();
    /* Only map-bank allocation order changes. Include the collision pointer
     * fixup table among the large blocks, before small metadata creates holes. */
    unsigned order[BG_MAP_SECTIONS + 1], sizes[BG_MAP_SECTIONS + 1];
    for (unsigned s = 0; s < BG_MAP_SECTIONS; s++) {
        order[s] = s;
        sizes[s] = s == BG_MAP_COLLISION_FACES ? 0 : sections[s].count * sections[s].stride;
    }
    order[BG_MAP_SECTIONS] = BG_MAP_SECTIONS;
    sizes[BG_MAP_SECTIONS] = sections[BG_MAP_COLLISION_FACES].count * sizeof(*triangles);
    for (unsigned at = 1; at <= BG_MAP_SECTIONS; at++) {
        unsigned id = order[at], before = at;
        while (before && sizes[order[before - 1]] < sizes[id]) {
            order[before] = order[before - 1]; before--;
        }
        order[before] = id;
    }
    for (unsigned at = 0; at <= BG_MAP_SECTIONS; at++) {
        unsigned s = order[at];
        if (s == BG_MAP_SECTIONS) {
            triangles = malloc(sizes[s]); assertf(triangles, "Map triangle pointers");
            continue;
        }
        /* Face indices are a fixup stream, never resident geometry. Avoid a
         * temporary 32 KiB allocation/hole on the 4 MiB Blood Gulch heap. */
        if (s == BG_MAP_COLLISION_FACES) continue;
        unsigned size = sections[s].count * sections[s].stride;
        if (!size) continue;
        blocks[s] = malloc(size); assertf(blocks[s], "Map RAM section %u (%u)", s, size);
        fseek(f, sections[s].offset, SEEK_SET);
        assertf(fread(blocks[s], 1, size, f) == size, "Map read %u", s);
#ifndef __MIPSEB__
        host_order(s, blocks[s], sections[s].count, sections[s].stride);
#endif
        resident += size;
    }
    bg_collision_count = sections[BG_MAP_COLLISION_FACES].count;
    assertf(sections[BG_MAP_COLLISION_FLAGS].count == bg_collision_count, "Map collision flags");
    const float (*vertices)[3] = blocks[BG_MAP_COLLISION_VERTICES];
    fseek(f, sections[BG_MAP_COLLISION_FACES].offset, SEEK_SET);
    uint8_t faces[128 * 6];
    for (unsigned first = 0; first < bg_collision_count; first += 128) {
        unsigned count = bg_collision_count - first;
        if (count > 128) count = 128;
        assertf(fread(faces, 6, count, f) == count, "Map corner stream");
        for (unsigned i = 0; i < count; i++) for (unsigned j = 0; j < 3; j++) {
            const uint8_t *pair = faces + i * 6 + j * 2;
            unsigned index = (unsigned)pair[0] << 8 | pair[1];
            assertf(index < sections[BG_MAP_COLLISION_VERTICES].count, "Map corner");
            triangles[first + i].p[j] = vertices[index];
        }
    }
    fclose(f);
    resident += bg_collision_count * sizeof(*triangles);
    bg_collision = triangles;
    bg_map_vertex_data = blocks[BG_MAP_VERTICES]; bg_vertex_count = sections[BG_MAP_VERTICES].count * 2;
    bg_chunks = blocks[BG_MAP_CHUNKS]; bg_chunk_count = sections[BG_MAP_CHUNKS].count;
    bg_chunk_indices = blocks[BG_MAP_INDICES]; bg_map_texture_data = blocks[BG_MAP_TEXTURES];
    bg_material_count = sections[BG_MAP_TEXTURES].count;
    bg_texture_sizes = blocks[BG_MAP_TEXTURE_SIZES]; bg_texture_ci4 = blocks[BG_MAP_TEXTURE_CI4];
    bg_texture_overlay = blocks[BG_MAP_TEXTURE_OVERLAY]; bg_ground_palette = blocks[BG_MAP_PALETTE];
    bg_collision_flags = blocks[BG_MAP_COLLISION_FLAGS]; bg_grid = blocks[BG_MAP_GRID]; bg_grid_indices = blocks[BG_MAP_GRID_INDICES];
    bg_grid_origin = blocks[BG_MAP_GRID_BOUNDS]; bg_grid_size = bg_grid_origin + 2;
    bg_spawns = blocks[BG_MAP_SPAWNS]; bg_spawn_count = sections[BG_MAP_SPAWNS].count;
    bg_slayer_spawns = blocks[BG_MAP_SLAYER_SPAWNS]; assertf(sections[BG_MAP_SLAYER_SPAWNS].count == bg_spawn_count, "Map spawn flags");
    bg_map_items = blocks[BG_MAP_ITEMS]; bg_map_item_count = sections[BG_MAP_ITEMS].count;
    bg_start_weapons = blocks[BG_MAP_START]; bg_start_grenades = bg_start_weapons + 2;
    bg_teleporters = blocks[BG_MAP_TELEPORTERS]; bg_teleporter_count = sections[BG_MAP_TELEPORTERS].count;
    bg_map_vehicles = blocks[BG_MAP_VEHICLES]; bg_map_vehicle_count = sections[BG_MAP_VEHICLES].count;
    bg_sky_rgb = blocks[BG_MAP_SKY];
    const float *origin = blocks[BG_MAP_ORIGIN];
    current.id = id; current.bytes = bytes; memcpy(current.origin, origin, 12); current.void_height = origin[3];
    const uint32_t *world = blocks[BG_MAP_WORLD_LAYOUT];
    current.world_bytes = world[0]; memcpy(current.world_layout, world + 1, sizeof(current.world_layout));
    validate_world_layout();
    assertf(bg_grid_size[0] > 0 && bg_grid_size[1] > 0, "Map grid dimensions");
    for (unsigned i = 0; i < BG_GRID * BG_GRID; i++) {
        assertf((unsigned)bg_grid[i].first + bg_grid[i].count <= sections[BG_MAP_GRID_INDICES].count,
                "Map grid cell");
    }
    for (unsigned i = 0; i < sections[BG_MAP_GRID_INDICES].count; i++)
        assertf(bg_grid_indices[i] < bg_collision_count, "Map grid triangle");
    for (unsigned i = 0; i < bg_material_count; i++)
        assertf((bg_texture_sizes[i] == 32 || (bg_texture_sizes[i] == 64 && bg_texture_ci4[i])) &&
                bg_texture_ci4[i] <= 1 && bg_texture_overlay[i] <= 7 &&
                (bg_texture_overlay[i]&3)!=3, "Map texture format");
    for (unsigned i = 0; i < bg_chunk_count; i++) {
        const bg_chunk *c = &bg_chunks[i];
        assertf(c->material < bg_material_count && c->first % 2 == 0 && c->count <= 60 &&
                c->first + ((c->count + 1) & ~1u) <= bg_vertex_count &&
                c->index_first + c->index_count <= sections[BG_MAP_INDICES].count &&
                c->index_first % 4 == 0 && c->index_count <= 120 && c->index_count % 3 == 0,
                "Map render batch");
        for (unsigned j = 0; j < c->index_count; j++) {
            int index = bg_chunk_indices[c->index_first + j];
            assertf(index >= 0 && index < c->count, "Map render index");
        }
    }
    bg_terrain_reset(); loaded = true;
    return true;
}
