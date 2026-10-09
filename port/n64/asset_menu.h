#ifndef BG_ASSET_MENU_H
#define BG_ASSET_MENU_H
#include <stdint.h>

enum { BG_MENU_FONT_LARGE, BG_MENU_FONT_SMALL, BG_MENU_FONT_COUNT };
enum { BG_MENU_GLYPH_FIRST=32, BG_MENU_GLYPH_COUNT=64,
       BG_MENU_ATLAS_WIDTH=128, BG_MENU_ATLAS_HEIGHT=64,
       BG_MENU_ATLAS_BYTES=4096 };
typedef struct {
    uint8_t page,s,t,w,h,advance;
    int8_t origin_x,origin_y;
} bg_menu_glyph;
typedef struct {
    const uint8_t *pixels;
    const bg_menu_glyph *glyphs;
    uint8_t pages,ascending,descending,leading;
} bg_menu_font;
typedef struct { const uint32_t *pixels; uint16_t w,h; } bg_menu_patch;
extern const bg_menu_font bg_menu_fonts[BG_MENU_FONT_COUNT];
/* Nine slices of the original Xbox pausebox, row-major. */
extern const bg_menu_patch bg_menu_panel[9];
#endif
