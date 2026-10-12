#ifndef BG_ASSET_PROMPT_ICONS_H
#define BG_ASSET_PROMPT_ICONS_H
#include <stdint.h>
/* Locally baked Xbox messaging silhouettes. One-bit IA4, native pixels. */
enum { BG_PROMPT_ICON_W = 64, BG_PROMPT_ICON_H = 64, BG_PROMPT_ICON_COUNT = 9 };
typedef struct { uint8_t x, y, w, h; } bg_prompt_icon;
extern const uint8_t bg_prompt_icon_pixels[BG_PROMPT_ICON_W * BG_PROMPT_ICON_H / 2];
extern const bg_prompt_icon bg_prompt_icons[BG_PROMPT_ICON_COUNT];
#endif
