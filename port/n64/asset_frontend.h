#ifndef BG_ASSET_FRONTEND_H
#define BG_ASSET_FRONTEND_H
#include <stdint.h>
#include "asset_menu.h"
typedef struct { uint32_t offset; uint16_t w,h,tag,frame; } bg_shell_image;
typedef struct {
 uint16_t tag; int16_t x,y,w,h,bitmap; uint8_t font,align;
 int16_t text_x,text_y; uint32_t rgba; const char *text;
} bg_shell_node;
enum { BG_SHELL_BLEND=1, BG_SHELL_DEPTH=2, BG_SHELL_DECAL=4 };
typedef struct { uint32_t offset; uint16_t count,image; uint8_t flags; } bg_shell_mesh;
extern const float bg_shell_cameras[15][7];
extern const bg_shell_image bg_shell_images[];
extern const unsigned bg_shell_image_count;
extern const bg_shell_node bg_shell_nodes[];
extern const unsigned bg_shell_node_count;
extern const bg_shell_mesh bg_shell_meshes[];
extern const unsigned bg_shell_mesh_count;
extern const uint32_t bg_shell_font_offsets[2];
extern const uint8_t bg_shell_font_pages[2],bg_shell_font_ascending[2];
extern const bg_menu_glyph bg_shell_glyphs[2][95];
extern const char *const bg_shell_map_descriptions[13];
extern const char *const bg_shell_type_names[26];
extern const char *const bg_shell_type_descriptions[26];
extern const uint32_t bg_shell_music_loop;
#endif
