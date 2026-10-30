#include "damage_flash.h"
#include "scope_mask.h"
#include "hud.h"
#include "asset_hud.h"
#include "asset_prompt_icons.h"
#include "game.h"
#include "scene.h"
#include "map.h"
#include "camouflage.h"
#include <libdragon.h>
#include <math.h>

/* Original motion sensor and scopes; native pixel art for compact counters
 * and meters. The immutable IA4 bank is uploaded once per player view. */
static surface_t images[BG_H_COUNT];
static surface_t scope_images[BG_SCOPE_COUNT];
static uint8_t scope_tick_pixels[5][1024] __attribute__((aligned(16)));
static uint8_t scope_mask_pixels[1][BG_SCOPE_MASK_BYTES] __attribute__((aligned(16)));
static surface_t native_scope_masks[1][2];

#include "hud_pixels.h"
#include "hud_buttons.h"
static surface_t pixel_atlas;
static surface_t button_atlas;
static surface_t weapon_icon_atlas;
static int current_combiner, current_filter;
/* Static sprite geometry/texture uploads do not depend on health, ammo or
 * tint. Replaying these RDP blocks avoids repeating the large-sprite tiler
 * on the CPU in every viewport. Blocks live for the whole match session. */
typedef struct {
    unsigned id;
    float x, y, scale;
    rspq_block_t *block;
} hud_blit;
static hud_blit blits[192];
static hud_blit scope_blits[20];
static unsigned scope_blit_count;
static unsigned blit_count;
/* Slot+1 links keep zero-initialized empty lists and the original append order.
 * Match coordinates only against this image's entries, not every HUD sprite.
 * The recorded blocks and their lifetime remain unchanged. */
static uint16_t blit_heads[BG_H_COUNT], blit_next[192];
static const color_t blue = {105, 166, 236, 255};
static const color_t bright = {149, 207, 255, 255};
static const color_t red = {248, 63, 58, 255};
static const color_t muted = {41, 70, 106, 255};
static const unsigned reticles[BG_WEAPON_COUNT] = {
    BG_H_RETICLE_AR,           BG_H_RETICLE_PISTOL,  BG_H_RETICLE_PLASMA_PISTOL,
    BG_H_RETICLE_PLASMA_RIFLE, BG_H_RETICLE_NEEDLER, BG_H_RETICLE_SHOTGUN,
    BG_H_RETICLE_SNIPER,       BG_H_RETICLE_ROCKET,  BG_H_RETICLE_AR};
/* Virtual Shade ID uses spare atlas quadrants, not bg_hud_images[]. */
enum { BG_RETICLE_SHADE = BG_H_COUNT };
static const int vehicle_reticles[BG_VEHICLE_COUNT] = {BG_H_RETICLE_WARTHOG, BG_H_RETICLE_GHOST,
                                                       BG_H_RETICLE_SCORPION, BG_H_RETICLE_BANSHEE
#ifdef BG_ENEMY_VEHICLES
                                                       ,BG_H_RETICLE_ROCKET, BG_RETICLE_SHADE
#endif
};

static void set_combiner(int kind) {
    if (current_combiner == kind)
        return;
    rdpq_mode_combiner(kind == 0   ? RDPQ_COMBINER_TEX_FLAT
                       : kind == 1 ? RDPQ_COMBINER1((0, 0, 0, PRIM), (TEX0, 0, PRIM, 0))
                                   : RDPQ_COMBINER_FLAT);
    current_combiner = kind;
}

static void set_filter(bool point) {
    if (current_filter == (int)point)
        return;
    rdpq_mode_filter(point ? FILTER_POINT : FILTER_BILINEAR);
    current_filter = point;
}

static void mode(color_t tint) {
    set_filter(false);
    /* The asset pack already applies the Xbox tag's colors. Normal sprites
     * pass through unmodified; depleted meters dim them, warning states use
     * their original alpha silhouette with a red/overcharge color. */
    bool normal =
        (tint.r == blue.r && tint.g == blue.g) || (tint.r == bright.r && tint.g == bright.g);
    bool dim = tint.r == muted.r && tint.g == muted.g;
    if (normal)
        tint = RGBA32(255, 255, 255, tint.a);
    else if (dim)
        tint = RGBA32(70, 70, 70, tint.a);
    set_combiner(normal || dim ? 0 : 1);
    rdpq_set_prim_color(tint);
}

static void blit_picture(unsigned id, float x, float y, float scale) {
    const bg_hud_image *im = &bg_hud_images[id];
    x += im->x * scale;
    y += im->y * scale;
    /* Moving radar blips are deliberately uncached: their positions can fill
     * an unbounded number of entries. Full caches fall back to ordinary blits. */
    if (id != BG_H_BLIP) {
        uint16_t *link = &blit_heads[id];
        while (*link) {
            unsigned i = *link - 1;
            const hud_blit *b = &blits[i];
            if (b->x == x && b->y == y && b->scale == scale) {
                rspq_block_run(b->block);
                return;
            }
            link = &blit_next[i];
        }
        if (blit_count < sizeof(blits) / sizeof(blits[0])) {
            unsigned i = blit_count++;
            hud_blit *b = &blits[i];
            *b = (hud_blit){.id = id, .x = x, .y = y, .scale = scale};
            rspq_block_begin();
            rdpq_tex_blit(
                &images[id], x, y,
                &(rdpq_blitparms_t){.scale_x = scale, .scale_y = scale, .filtering = true});
            b->block = rspq_block_end();
            blit_next[i] = 0;
            *link = i + 1;
            rspq_block_run(b->block);
            return;
        }
    }
    rdpq_tex_blit(&images[id], x, y,
                  &(rdpq_blitparms_t){.scale_x = scale, .scale_y = scale, .filtering = true});
}

static void picture(unsigned id, float x, float y, float scale, color_t tint) {
    if (bg_hud_images[id].w <= 1 || bg_hud_images[id].h <= 1)
        return;
    mode(tint);
    blit_picture(id, x, y, scale);
}

static void pixel(int x, int y, int w, int h, color_t c) {
    set_combiner(2);
    rdpq_set_prim_color(c);
    rdpq_fill_rectangle(x, y, x + w, y + h);
}

/* This bank stays resident through all counters, bars and labels in a view. */
static const color_t hud_cyan = {100, 220, 255, 255};
static const color_t hud_dim = {25, 62, 77, 255};
static const color_t hud_shadow = {3, 13, 22, 235};
static const color_t hud_backing = {3, 13, 22, 150};
static void hud_sprite(int u, int v, int w, int h, int x, int y, color_t color) {
    if (w <= 0 || h <= 0)
        return;
    set_combiner(1);
    rdpq_set_prim_color(color);
    rdpq_texture_rectangle(TILE0, x, y, x + w, y + h, u, v);
}
static void hud_reticle(unsigned id, int cx, int cy) {
    unsigned q = id >= BG_H_RETICLE_WARTHOG ? 8 + id - BG_H_RETICLE_WARTHOG : id - BG_H_RETICLE_AR;
    unsigned lower = q == 2 ? 12 : q == 11 ? 13 : q == 9 ? 14 : q;
#ifdef BG_ENEMY_VEHICLES
    if(id==BG_RETICLE_SHADE){q=15;lower=16;}
#endif
    set_combiner(1);
    rdpq_set_prim_color(hud_cyan);
    /* Even 24px footprint puts its geometric center exactly on the original
     * integer aim anchor. Each quadrant maps 12 texels to 12 screen pixels.
     * Explicit negative UV steps mirror texels without flipped-rectangle
     * endpoint adjustments or fractional scaling of a cropped Xbox bitmap. */
    for (unsigned bottom = 0; bottom < 2; bottom++) {
        unsigned tile = bottom ? lower : q;
        int u = (tile % 5) * 12, v = 80 + (tile / 5) * 12;
        bool flip_y = bottom && lower == q;
        if (flip_y)
            v += 11;
        int y = cy + (bottom ? 0 : -12);
        rdpq_texture_rectangle_raw(TILE0, cx - 12, y, cx, y + 12, u, v, 1, flip_y ? -1 : 1);
        rdpq_texture_rectangle_raw(TILE0, cx, y, cx + 12, y + 12, u + 11, v, -1, flip_y ? -1 : 1);
    }
}
static int hud_text_width(const char *text) {
    return text[0] ? (int)strlen(text) * 5 - 1 : 0;
}
static void hud_text(const char *text, int x, int y, color_t color) {
    set_combiner(1);
    for (int shadow = 1; shadow >= 0; shadow--) {
        color_t tint = shadow ? hud_shadow : color;
        if (shadow)
            tint.a = (unsigned)tint.a * color.a / 255;
        rdpq_set_prim_color(tint);
        for (unsigned i = 0; text[i]; i++) {
            int glyph = hud_glyph(text[i]);
            if (glyph < 0)
                continue;
            int px = x + i * 5 + shadow, py = y + shadow;
            rdpq_texture_rectangle(TILE0, px, py, px + 4, py + 6, hud_glyph_x(glyph),
                                   hud_glyph_y(glyph));
        }
    }
}
#ifdef BG_FRONTEND_QA
void bg_hud_qa_text(const char *text, int x, int y) {
    current_combiner = current_filter = -1;
    rdpq_set_mode_standard();
    rdpq_mode_zbuf(false, false);
    rdpq_mode_persp(false);
    rdpq_mode_tlut(TLUT_NONE);
    rdpq_mode_blender(RDPQ_BLENDER_MULTIPLY);
    rdpq_set_scissor(0, 0, 320, 240);
    set_filter(true);
    set_combiner(1);
    rdpq_tex_upload(TILE0, &pixel_atlas, NULL);
    hud_text(text, x, y, hud_cyan);
}
#endif
static void hud_number(int value, int x, int y, unsigned places, color_t color) {
    char text[16];
    unsigned at = sizeof(text) - 1;
    unsigned magnitude = value < 0 ? 0u - (unsigned)value : (unsigned)value;
    text[at] = 0;
    do {
        text[--at] = '0' + magnitude % 10;
        magnitude /= 10;
    } while (magnitude);
    while (sizeof(text) - 1 - at < places && at > 1)
        text[--at] = '0';
    if (value < 0)
        text[--at] = '-';
    hud_text(text + at, x, y, color);
}
static void hud_vitals(const bg_player *p, int x, int y) {
    /* A one-pixel step at either end echoes Halo without its long diagonals. */
    hud_sprite(0, 72, 46, 7, x + 1, y + 1, hud_shadow);
    hud_sprite(0, 72, 46, 7, x, y, p->shield <= 0 ? red : hud_cyan);
    pixel(x + 2, y + 2, 42, 3, hud_dim);
    int fill = (int)ceilf(fminf(fmaxf(p->shield, 0), 100) * .42f);
    if (fill)
        pixel(x + 2, y + 2, fill, 3, hud_cyan);
    if (p->shield > 100) {
        fill = (int)ceilf(fminf(p->shield - 100, 100) * .42f);
        pixel(x + 2, y + 2, fill, 3, RGBA32(255, 48, 48, 255));
    }
    if (p->shield > 200) {
        fill = (int)ceilf(fminf(p->shield - 200, 100) * .42f);
        pixel(x + 2, y + 2, fill, 3, RGBA32(48, 255, 64, 255));
    }
    /* Eight upright health cells, aligned to the shield's right edge. */
    pixel(x + 12, y + 7, 33, 5, hud_backing);
    hud_sprite(0, 67, 31, 3, x + 13, y + 8, hud_dim);
    int cells = (int)ceilf(fminf(fmaxf(p->health, 0), 100) * .08f);
    if (cells)
        hud_sprite(0, 67, cells * 4 - 1, 3, x + 13, y + 8,
                   p->health <= 33   ? red
                   : p->health <= 67 ? RGBA32(255, 217, 65, 255)
                                     : hud_cyan);
}
static void hud_ammunition(const bg_player *p, unsigned weapon, int x, int y) {
    const bg_weapon_def *def = &bg_weapon_defs[weapon];
    color_t tint = p->overheated ? red : hud_cyan;
    hud_sprite(40, 32, 19, 10, x + 1, y + 1, hud_shadow);
    hud_sprite(40, 32, 19, 10, x, y, hud_cyan);
    hud_number(p->ammo < 0 ? 0 : p->ammo, x + 2, y + 2, def->energy ? 3 : 2, tint);
    for (int i = 0; i < 2; i++) {
        int gx = x + 23 + i * 14;
        hud_sprite(42 + i * 8, 45, 6, 7, gx + 1, y + 2, hud_shadow);
        hud_sprite(42 + i * 8, 45, 6, 7, gx, y + 1, p->grenade_kind == i ? hud_cyan : hud_dim);
        hud_number(p->grenades[i], gx + 7, y + 2, 1, p->grenade_kind == i ? hud_cyan : hud_dim);
    }
    int my = y + 12, ammo = p->ammo;
    if (ammo < 0)
        ammo = 0;
    if (ammo > def->magazine)
        ammo = def->magazine;
    if (def->energy) {
        /* Battery digits above; heat grows toward the right independently. */
        pixel(x, my, 39, 4, hud_shadow);
        pixel(x + 1, my + 1, 37, 2, hud_dim);
        int heat = (int)ceilf(fminf(fmaxf(p->heat, 0), 1) * 37);
        if (heat)
            pixel(x + 1, my + 1, heat, 2, p->heat > .75f ? red : hud_cyan);
        /* Heat is already represented by the meter and weapon venting. */
        return;
    }
    if (weapon == BG_W_AR) {
        pixel(x - 1, my - 1, 41, 13, hud_backing);
        hud_sprite(0, 32, 39, 11, x, my, hud_dim);
        /* Twenty columns, each with three rounds: deplete right to left,
         * then bottom to top within a column, as in the source ammo meter.
         * A partial column still represents exactly one or two rounds. */
        int columns = ammo / 3, remainder = ammo % 3;
        if (columns)
            hud_sprite(0, 32, columns * 2 - 1, 11, x, my, hud_cyan);
        if (remainder)
            hud_sprite(columns * 2, 32, 1, remainder * 4 - 1, x + columns * 2, my, hud_cyan);
        hud_number(p->reserve < 0 ? 0 : p->reserve, x, my + 13, 3, hud_cyan);
    } else if (def->magazine > 20) {
        pixel(x, my, 39, 4, hud_shadow);
        pixel(x + 1, my + 1, 37, 2, hud_dim);
        int fill = (ammo * 37 + def->magazine - 1) / def->magazine;
        if (fill)
            pixel(x + 1, my + 1, fill, 2, hud_cyan);
        hud_number(p->reserve < 0 ? 0 : p->reserve, x, my + 7, 3, hud_cyan);
    } else {
        int v = 44, step = 3, w = 2, count = def->magazine;
        if (weapon == BG_W_NEEDLER) {
            v = 50;
            step = 2;
            w = 1;
        } else if (weapon == BG_W_SNIPER) {
            v = 55;
            step = 10;
            w = 8;
        } else if (weapon == BG_W_ROCKET) {
            v = 61;
            step = 21;
            w = 18;
        }
        int full = (count - 1) * step + w, filled = ammo ? (ammo - 1) * step + w : 0;
        if (filled > full)
            filled = full;
        pixel(x - 1, my - 1, full + 2, 7, hud_backing);
        hud_sprite(0, v, full, 5, x, my, hud_dim);
        if (filled)
            hud_sprite(0, v, filled, 5, x, my, hud_cyan);
        hud_number(p->reserve < 0 ? 0 : p->reserve, x, my + 7, 3, hud_cyan);
    }
}

static void radar(unsigned p, int x, int y, float scale) {
    float size = bg_hud_images[BG_H_MOTION_BG].w * scale;
    /* cyborg_mp tag colors: background0x28061428, foreground0xa06986a0.
     * The circle's texture is solid white; its original low opacity and dark
     * color belong to the HUD tag, not the bitmap's one-bit alpha channel. */
    picture(BG_H_MOTION_BG, x, y, scale, RGBA32(6, 20, 40, 40));
    picture(BG_H_MOTION_FG, x, y, scale, RGBA32(blue.r, blue.g, blue.b, 160));
    float cx = x + size * .5f, cy = y + size * .5f, radius = size * .41f;
    bg_player *viewer = &bg_players[p];
    const float range = 8.333333f; /* Xbox motion sensor25m; Halo world unit=3m. */
    float sn = sinf(viewer->yaw), cs = cosf(viewer->yaw);
    for (unsigned j = 0; j < bg_unit_count(); j++) {
        bg_player *other = &bg_players[j];
        if (j == p || !bg_motion_sensor_visible(other))
            continue;
        float dx = other->pos[0] - viewer->pos[0], dz = other->pos[2] - viewer->pos[2];
        if (dx * dx + dz * dz > range * range)
            continue;
        int bx = (int)roundf(cx + (dx * sn + dz * cs) * radius / range);
        int by = (int)roundf(cy - (dx * cs - dz * sn) * radius / range);
        picture(BG_H_BLIP, bx - 2, by - 2, .125f, bg_players_allied(p,j)?blue:red);
    }
    pixel((int)cx, (int)cy - 1, 1, 3, bright);
    pixel((int)cx - 1, (int)cy + 1, 3, 1, bright);
}

static void interaction_label(bg_use_target target, char *out, unsigned size) {
    const char *vehicles[] = {"Warthog", "Ghost", "Scorpion", "Banshee", "Wraith", "Shade"};
    out[0] = 0;
    if (target.kind == BG_USE_PICKUP)
        snprintf(out, size, "Pick up");
    /* Exit remains available through use, without a persistent HUD hint. */
    else if (target.kind == BG_USE_FLIP)
        snprintf(out, size, "Flip %s", vehicles[bg_vehicles[target.object].kind]);
    else if (target.kind == BG_USE_ENTER) {
        const bg_vehicle *v = &bg_vehicles[target.object];
        const bg_seat_definition *s = &bg_seat_definitions[v->kind][target.seat];
        const char *role = s->flags & 4 ? "Drive" : s->flags & 8 ? "Gunner" : "Ride";
        snprintf(out, size, "%s %s", role, vehicles[v->kind]);
    }
}
static void hud_button(unsigned id, int x, int y) {
    /* Unlike the one-bit text bank, icons encode dim inactive buttons and
     * opaque dark letter/arrow cutouts. Preserve both intensity and alpha. */
    set_combiner(0);
    rdpq_set_prim_color(hud_cyan);
    rdpq_texture_rectangle(TILE0, x, y, x + hud_button_width[id], y + hud_button_height[id],
                           (id % 4) * 16, (id / 4) * 16);
}
/* Returns the first occupied row, so receipts cannot cover a weapon icon. */
static int interaction_prompt(const bg_player *p, bg_control_style style, int x, int y,
                              int width) {
    char label[48];
    bg_use_target target = bg_interaction_target(p - bg_players);
    interaction_label(target, label, sizeof(label));
    if (!label[0])
        return y;
    unsigned icon = style == BG_CONTROLS_DUKE ? HUD_BUTTON_C_LEFT : HUD_BUTTON_B;
    bool hold = target.kind == BG_USE_PICKUP;
    unsigned weapon = hold ? bg_pickups[target.object].weapon : 0;
    if (hold) {
        bool matching = p->inventory[0] == (int)weapon || p->inventory[1] == (int)weapon;
        if (matching || (p->inventory[0] >= 0 && p->inventory[1] >= 0))
            snprintf(label, sizeof(label), "Swap for");
    }
    int prefix = hold ? 24 : 0, iw = hud_button_width[icon];
    int tw = hud_text_width(label), total = prefix + iw + 3 + tw;
    const bg_prompt_icon *wi = hold ? &bg_prompt_icons[weapon] : NULL;
    /* Long guns get a centered identity row in narrow views, avoiding the
     * radar at lower left. Short guns remain inline. Font never shrinks. */
    bool stacked = wi && width < 200 && total + 4 + wi->w > width - 70;
    if (wi && !stacked)
        total += 4 + wi->w;
    int start = x + (width - total) / 2;
    if (hold)
        hud_text("Hold", start, y, hud_cyan);
    hud_text(label, start + prefix + iw + 3, y, hud_cyan);
    rdpq_tex_upload(TILE0, &button_atlas, NULL);
    hud_button(icon, start + prefix, y - (hud_button_height[icon] - 6) / 2);
    if (wi) {
        int wx = stacked ? x + (width - wi->w) / 2 : start + prefix + iw + 3 + tw + 4;
        int wy = stacked ? y - 14 : y - (wi->h - 6) / 2;
        set_combiner(1);
        rdpq_set_prim_color(hud_cyan);
        rdpq_tex_upload(TILE0, &weapon_icon_atlas, NULL);
        rdpq_texture_rectangle(TILE0, wx, wy, wx + wi->w, wy + wi->h, wi->x, wi->y);
        if (stacked)
            return wy;
    }
    return y - (hud_button_height[icon] - 6) / 2;
}

static void pickup_notices(unsigned player, int x, int bottom, int width, int max_lines) {
    bg_notice messages[BG_NOTICE_SLOTS];
    unsigned count = bg_hud_messages_get(player, messages);
    if (!count)
        return;
    rdpq_tex_upload(TILE0, &pixel_atlas, NULL);
    int lines = 0, max_chars = (width + 1) / 5;
    for (unsigned i = 0; i < count && lines < max_lines; i++) {
        char text[64];
        bg_hud_message_text(player, &messages[i], text, sizeof(text));
        if (!text[0])
            continue;
        char wrapped[2][64] = {{0}};
        size_t length = strlen(text), split = length;
        if (length > (size_t)max_chars) {
            split = max_chars;
            while (split && text[split] != ' ')
                split--;
            if (!split)
                split = max_chars;
        }
        memcpy(wrapped[0], text, split);
        if (split < length)
            snprintf(wrapped[1], sizeof(wrapped[1]), "%s", text + split + (text[split] == ' '));
        unsigned rows = wrapped[1][0] ? 2 : 1;
        if (lines + (int)rows > max_lines)
            break;
        color_t color = hud_cyan;
        color.a = bg_hud_message_alpha(&messages[i]);
        for (unsigned row = 0; row < rows; row++) {
            int py = bottom - (lines + rows - 1 - row) * 8;
            hud_text(wrapped[row], x + (width - hud_text_width(wrapped[row])) / 2, py, color);
        }
        lines += rows;
    }
}

static bool scoped(const bg_player *p) {
    return p->health > 0 && p->vehicle < 0 && p->zoom > 0 &&
           (p->weapon == BG_W_PISTOL || p->weapon == BG_W_SNIPER);
}

/* Source sniper mask: a wide rounded rectangle, not the pistol circle.
 * Rasterize its native-pixel exterior without the source's magnified rim. */
static void scope_sniper_mask(int x,int y,int width,int height,float cx,float cy) {
    int w=lroundf(width*236.f/256),h=lroundf(height*152.f/256);
    int left=lroundf(cx-w*.5f),top=lroundf(cy-h*.5f);
    float rx=width*7.f/256,ry=height*7.f/256;
    color_t edge=RGBA32(0,0,0,bg_scope_images[BG_SCOPE_SNIPER].pixels[0]);
    set_combiner(2);rdpq_set_prim_color(edge);
    unsigned key=2+height/120;
    for(unsigned i=0;i<scope_blit_count;i++) {
        hud_blit *b=&scope_blits[i];
        if(b->id==key&&b->x==cx&&b->y==cy&&b->scale==width){rspq_block_run(b->block);return;}
    }
    bool record=scope_blit_count<sizeof(scope_blits)/sizeof(scope_blits[0]);
    if(record)rspq_block_begin();
    rdpq_fill_rectangle(x,y,x+width,top);
    rdpq_fill_rectangle(x,top+h,x+width,y+height);
    for(int row=0;row<h;) {
        float dy=fmaxf(0,ry-fminf(row+.5f,h-row-.5f))/ry;
        int inset=lroundf(rx*(1-sqrtf(fmaxf(0,1-dy*dy))));
        int end=row+1;
        while(end<h) {
            float next_dy=fmaxf(0,ry-fminf(end+.5f,h-end-.5f))/ry;
            int next=lroundf(rx*(1-sqrtf(fmaxf(0,1-next_dy*next_dy))));
            if(next!=inset)break;
            end++;
        }
        rdpq_fill_rectangle(x,top+row,left+inset,top+end);
        rdpq_fill_rectangle(left+w-inset,top+row,x+width,top+end);
        row=end;
    }
    if(record) {
        hud_blit *b=&scope_blits[scope_blit_count++];
        *b=(hud_blit){.id=key,.x=cx,.y=cy,.scale=width,.block=rspq_block_end()};
        rspq_block_run(b->block);
    }
}

static void scope_mask(const bg_player *p, int x, int y, int width, int height, float cx,
                       float cy) {
    if(p->weapon==BG_W_SNIPER){scope_sniper_mask(x,y,width,height,cx,cy);return;}
    unsigned id = BG_SCOPE_PISTOL;
    unsigned small = height < 240, size = bg_scope_mask_size(height);
    int left = lroundf(cx - size * .5f), top = lroundf(cy - size * .5f);
    color_t edge = RGBA32(0, 0, 0, bg_scope_images[id].pixels[0]);
    /* Extend the exterior once, with no overlap at the texture edges. The
     * viewport scissor also protects adjacent split-screen players. */
    if (top > y) pixel(x, y, width, top - y, edge);
    if (top + (int)size < y + height)
        pixel(x, top + size, width, y + height - top - size, edge);
    int inner_top = top > y ? top : y;
    int inner_bottom = top + (int)size < y + height ? top + (int)size : y + height;
    if (left > x) pixel(x, inner_top, left - x, inner_bottom - inner_top, edge);
    if (left + (int)size < x + width)
        pixel(left + size, inner_top, x + width - left - size, inner_bottom - inner_top, edge);
    mode(RGBA32(0, 0, 0, 255));
    set_filter(true);
    unsigned key = id * 2 + small;
    for (unsigned i = 0; i < scope_blit_count; i++) {
        hud_blit *b = &scope_blits[i];
        if (b->id == key && b->x == left && b->y == top) {
            rspq_block_run(b->block);
            return;
        }
    }
    /* Record the immutable tiled upload once per weapon and viewport. */
    bool record = scope_blit_count < sizeof(scope_blits) / sizeof(scope_blits[0]);
    if (record) rspq_block_begin();
    rdpq_tex_blit(&native_scope_masks[id][small], left, top, NULL);
    if (record) {
        hud_blit *b = &scope_blits[scope_blit_count++];
        *b = (hud_blit){.id = key, .x = left, .y = top, .block = rspq_block_end()};
        rspq_block_run(b->block);
    }
}

static void scope_marks(const bg_player *p, float cx, float cy, int height) {
    bool split = height < 240;
    if (p->weapon == BG_W_SNIPER) {
        /* The source artwork is already packed at half Xbox resolution.
         * Scale its size and anchor offsets together; the previous extra 2x
         * enlargement shifted the visible ink away from the aiming point. */
        static const int offsets[5][2] = {{-101, 18}, {115, 18}, {-33, 0}, {33, 0}, {0, 42}};
        float size = split ? .5f : 1.f, offset = split ? .25f : .5f;
        mode(RGBA32(0, 0, 0, 120));
        set_filter(true);
        for (unsigned i = 0; i < 5; i++) {
            unsigned id = BG_SCOPE_TICK_0 + i;
            const bg_scope_image *im = &bg_scope_images[id];
            rdpq_tex_blit(&scope_images[id], lroundf(cx + offsets[i][0] * offset - im->w * size * .5f),
                          lroundf(cy + offsets[i][1] * offset - im->h * size * .5f),
                          &(rdpq_blitparms_t){.scale_x = size, .scale_y = size, .filtering = false});
        }
    }
}

void bg_hud_init(void) {
    for (unsigned i = 0; i < BG_H_COUNT; i++) {
        const bg_hud_image *im = &bg_hud_images[i];
        images[i] =
            surface_make((void *)im->pixels, FMT_RGBA16, im->tex_w, im->tex_h, im->tex_w * 2);
        data_cache_hit_writeback((void *)im->pixels, im->tex_w * im->tex_h * 2);
    }
    for (unsigned i = 0; i < BG_SCOPE_COUNT; i++) {
        const bg_scope_image *im = &bg_scope_images[i];
        scope_images[i] = surface_make((void *)im->pixels, FMT_I8, im->w, im->h, im->stride);
        data_cache_hit_writeback((void *)im->pixels, im->stride * im->h);
    }
    for(unsigned i=0;i<5;i++) {
        const bg_scope_image *im=&bg_scope_images[BG_SCOPE_TICK_0+i];
        assertf(im->stride*im->h<=sizeof(scope_tick_pixels[i]),"Scope tick buffer");
        for(unsigned n=0;n<im->stride*im->h;n++)scope_tick_pixels[i][n]=im->pixels[n]>=128?255:0;
        scope_images[BG_SCOPE_TICK_0+i]=surface_make(scope_tick_pixels[i],FMT_I8,im->w,im->h,im->stride);
        data_cache_hit_writeback(scope_tick_pixels[i],sizeof(scope_tick_pixels[i]));
    }
    for (unsigned id = 0; id < 1; id++) for (unsigned small = 0; small < 2; small++) {
        unsigned size = small ? BG_SCOPE_SMALL_SIZE : BG_SCOPE_LARGE_SIZE;
        uint8_t *pixels = scope_mask_pixels[id] + (small ? BG_SCOPE_LARGE_SIZE * BG_SCOPE_LARGE_SIZE : 0);
        bg_scope_mask_generate(pixels, size, bg_scope_images[id].pixels[0]);
        native_scope_masks[id][small] = surface_make(pixels, FMT_I8, size, size, size);
        data_cache_hit_writeback(pixels, size * size);
    }
    hud_pixels_init();
    pixel_atlas = surface_make(hud_pixels, FMT_IA4, HUD_PIXEL_W, HUD_PIXEL_H, HUD_PIXEL_W / 2);
    data_cache_hit_writeback(hud_pixels, sizeof(hud_pixels));
    hud_buttons_init();
    button_atlas =
        surface_make(hud_button_pixels, FMT_IA4, HUD_BUTTON_W, HUD_BUTTON_H, HUD_BUTTON_W / 2);
    data_cache_hit_writeback(hud_button_pixels, sizeof(hud_button_pixels));
    weapon_icon_atlas = surface_make((void *)bg_prompt_icon_pixels, FMT_IA4,
                                    BG_PROMPT_ICON_W, BG_PROMPT_ICON_H, BG_PROMPT_ICON_W / 2);
    data_cache_hit_writeback((void *)bg_prompt_icon_pixels, sizeof(bg_prompt_icon_pixels));
}

static void damage_screen_flash(const bg_player *p,int x,int y,int w,int h) {
    float intensity=bg_damage_flash_intensity(p);
    if(intensity<=0)return;
    const bg_damage_flash_definition *d=&bg_damage_flashes[p->damage_flash_profile];
    /* CE lighten = premultiplied color + destination*(1-source alpha).
     * RDP additive overflow wraps above 1.5; cap the additive contribution
     * below .5. The ordinary red bullet flash stays below this limit. */
    if(d->color[3])pixel(x,y,w,h,RGBA32(0,0,0,(unsigned)(d->color[3]*intensity)));
    rdpq_mode_blender(RDPQ_BLENDER_ADDITIVE);
    pixel(x,y,w,h,RGBA32(d->color[0],d->color[1],d->color[2],(unsigned)(255*fminf(.49f,intensity))));
    rdpq_mode_blender(RDPQ_BLENDER_MULTIPLY);
}

static void damage_indicators(const bg_player *p,int x,int y,int w,int h,unsigned views) {
    if(p->health<=0)return;
    const bg_scope_image *a=&bg_damage_images[views>1];
    surface_t bitmap=surface_make((void*)a->pixels,FMT_I8,a->w,a->h,a->stride);
    /* The extracted image points down. RDP blits rotate counter-clockwise;
     * keep all four tips facing inward (top down, bottom up). */
    const float angle[4]={0,1.57079633f,3.14159265f,4.71238898f};
    for(unsigned d=0;d<4;d++)if(p->damage_indicator[d]>0) {
        float cx=x+w*.5f,cy=y+h*.5f,offset=bg_damage_offsets[d]*.5f;
        if(d==0)cy=y+offset;else if(d==2)cy=y+h-offset;
        else if(d==1)cx=x+offset;else cx=x+w-offset;
        mode(RGBA32(bg_damage_color>>24,(bg_damage_color>>16)&255,(bg_damage_color>>8)&255,bg_damage_color&255));
        rdpq_tex_blit(&bitmap,cx,cy,&(rdpq_blitparms_t){.cx=a->w*.5f,.cy=a->h*.5f,
            .scale_x=.5f,.scale_y=.5f,.theta=angle[d],.filtering=true});
    }
}

void bg_hud_draw(unsigned index, int x, int y, int width, int height, bg_control_style style) {
    const bg_player *p = &bg_players[index];
    float scale = width < 200 ? .45f : .5f;
    int margin = width < 200 ? 5 : 9;
    unsigned weapon = (unsigned)p->weapon < BG_WEAPON_COUNT ? (unsigned)p->weapon : BG_W_AR;
    const bg_vehicle *vehicle = p->vehicle >= 0 && (unsigned)p->vehicle < bg_vehicle_count
                                    ? &bg_vehicles[p->vehicle]
                                    : NULL;
    bool carrying=bg_player_objective(index)>=0;
    bool personal = bg_player_personal_weapon(p)&&!carrying;
    float aim_x, aim_y;
    unsigned views = bg_player_count();
    bg_hud_aim_point(views, index, x, y, width, height, &aim_x, &aim_y);
    current_combiner = current_filter = -1;
    rdpq_mode_begin();
    rdpq_set_mode_standard();
    rdpq_mode_zbuf(false, false);
    rdpq_mode_persp(false);
    rdpq_mode_tlut(TLUT_NONE);
    rdpq_mode_blender(RDPQ_BLENDER_MULTIPLY);
    rdpq_mode_end();
    rdpq_set_scissor(x, y, x + width, y + height);
    damage_screen_flash(p,x,y,width,height);
    if (scoped(p))
        scope_mask(p, x, y, width, height, aim_x, aim_y);

    damage_indicators(p,x,y,width,height,views);
    if (p->health > 0) {
        if (scoped(p))
            scope_marks(p, aim_x, aim_y, height);
        if (!p->zoom && bg_mode_radar())
            radar(index, x + margin, y + height - margin - bg_hud_images[BG_H_MOTION_BG].h * scale,
                  scale);
    }

    /* Pixel HUD: all coordinates and glyph extents are native integers. */
    set_filter(true);
    set_combiner(1);
    rdpq_tex_upload(TILE0, &pixel_atlas, NULL);
    if(p->health>0){
        const T3DViewport *vp=bg_scene_viewport(index);
        for(unsigned i=0;i<BG_MAX_OBJECTIVES;i++){
            float pos[3];unsigned kind,team;
            if(!bg_mode_navpoint(index,i,pos,&kind,&team))continue;
            T3DVec3 world={{pos[0]*BG_SCALE,(pos[1]+.65f)*BG_SCALE,pos[2]*BG_SCALE}},screen={{0}};
            float depth=-(world.v[0]*vp->matCamera.m[0][2]+world.v[1]*vp->matCamera.m[1][2]+world.v[2]*vp->matCamera.m[2][2]+vp->matCamera.m[3][2]);
            if(depth<=0)continue;
            t3d_viewport_calc_viewspace_pos((T3DViewport*)vp,&screen,&world);
            int px=(int)fmaxf(x+8,fminf(x+width-8,screen.v[0]));
            int py=(int)fmaxf(y+22,fminf(y+height-25,screen.v[1]));
            const char *label=kind==BG_OBJECTIVE_FLAG?"F":kind==BG_OBJECTIVE_BALL?"B":kind==BG_OBJECTIVE_HILL?"H":"+";
            hud_text(label,px-2,py-3,team==0?red:team==1?blue:hud_cyan);
        }
        if(bg_current_rules()->engine==BG_ENGINE_BALL&&bg_current_rules()->ball_type&&bg_player_ball_count(index)){
            char label[24];
            if(bg_current_rules()->balls>1)snprintf(label,sizeof(label),"Balls: %u",bg_player_ball_count(index));
            else snprintf(label,sizeof(label),"You are it!");
            hud_text(label,x+margin,y+20,hud_cyan);
        }
        int target=bg_player_target(index);
        if(target>=0){char label[24];snprintf(label,sizeof(label),"Target: P%u",bg_player_profiles[target]+1);hud_text(label,x+margin,y+20,hud_cyan);}
    }
    if (p->health > 0) {
        const bg_seat_definition *seat = bg_player_seat(p);
        int id = personal                    ? (int)reticles[weapon]
                 : seat && (seat->flags & 8) ? vehicle_reticles[vehicle->kind]
                                             : -1;
        if (p->seat_state != BG_SEAT_STABLE)
            id = -1;
#ifdef BG_SHIELD_QA
        id = -1; /* Inspection camera looks at this actor, not down its sights. */
#endif
        if (id >= 0)
            hud_reticle(id, (int)roundf(aim_x), (int)roundf(aim_y));
    }
    int left = x + margin, top = y + margin, right = x + width - margin;
    hud_vitals(p, right - 46, top);
    if (personal)
        hud_ammunition(p, weapon, left, top);
    char score[24];int points=bg_display_score(index);
    if(bg_mode_timed(bg_current_rules()))snprintf(score,sizeof(score),"%d:%02d",points/60,points%60);
    else snprintf(score,sizeof(score),"%d",points);
    hud_text(score,right-hud_text_width(score),y+height-margin-6,hud_cyan);
    if (scoped(p)) {
        int ox = p->weapon == BG_W_PISTOL ? (height < 200 ? 34 : 53) : (height < 200 ? 24 : 75);
        int oy = p->weapon == BG_W_PISTOL ? (height < 200 ? 34 : 53) : (height < 200 ? 15 : 52);
        hud_text(p->weapon == BG_W_SNIPER && p->zoom == 2 ? "10X" : "2X",
                 (int)roundf(aim_x) + ox - 5, (int)roundf(aim_y) + oy - 3, hud_cyan);
    }
    int status_y = y + height - margin - 6;
    int notice_bottom = status_y - 14;
    if (p->health <= 0) {
        int seconds = (int)ceilf(p->respawn);
        char label[32];
#ifdef BG_PVE
        if(bg_ff.active){
            if(bg_ff_can_respawn(index))snprintf(label,sizeof(label),"Respawn: %d",seconds<0?0:seconds);
            else snprintf(label,sizeof(label),"Waiting for round clear");
        }else
#endif
        if(bg_player_eliminated(index))snprintf(label,sizeof(label),"Eliminated");
        else if(bg_player_waiting(index))snprintf(label,sizeof(label),"Waiting for respawn");
        else snprintf(label, sizeof(label), "Rejoin in %d", seconds < 0 ? 0 : seconds);
        hud_text(label, x + (width - hud_text_width(label)) / 2, y + height / 2 + 8, hud_cyan);
    } else {
        notice_bottom = interaction_prompt(p, style, x, status_y, width) - 9;
        bg_use_target target = bg_interaction_target(index);
        int swap = personal ? bg_hud_switch_target(p) : -1;
        if(carrying){
            const char *label=style==BG_CONTROLS_DUKE?"C-UP: Drop objective":"R: Drop objective";
            hud_text(label,x+(width-hud_text_width(label))/2,status_y,hud_cyan);
        } else if (swap >= 0 && (target.kind == BG_USE_NONE || target.kind == BG_USE_EXIT)) {
            const bg_prompt_icon *wi = &bg_prompt_icons[swap];
            unsigned icon = style == BG_CONTROLS_DUKE ? HUD_BUTTON_C_UP : HUD_BUTTON_R;
            int total = hud_button_width[icon] + 3 + hud_text_width("Switch") + 4 + wi->w;
            int start = x + (width - total) / 2;
            hud_text("Switch", start + hud_button_width[icon] + 3, status_y, hud_cyan);
            rdpq_tex_upload(TILE0, &button_atlas, NULL);
            hud_button(icon, start, status_y - (hud_button_height[icon] - 6) / 2);
            set_combiner(1);
            rdpq_set_prim_color(hud_cyan);
            rdpq_tex_upload(TILE0, &weapon_icon_atlas, NULL);
            int wx = start + total - wi->w, wy = status_y - (wi->h - 6) / 2;
            rdpq_texture_rectangle(TILE0, wx, wy, wx + wi->w, wy + wi->h, wi->x, wi->y);
            notice_bottom = (wy < notice_bottom + 9 ? wy : notice_bottom + 9) - 9;
        }
    }
    /* Radar keeps its approved appearance. Receipts occupy the available
     * lower HUD strip beside it; long text wraps on the same native grid. */
    int notice_left = left;
    if (p->health > 0 && !p->zoom && bg_mode_radar())
        notice_left += (int)ceilf(bg_hud_images[BG_H_MOTION_BG].w * scale) + 3;
    pickup_notices(index, notice_left, notice_bottom, right - notice_left, height < 200 ? 2 : 3);
#ifdef BG_PVE
    if(bg_ff.active){
        char state[72];unsigned alive=0;
        for(unsigned i=0;i<bg_pve_count;i++)alive+=bg_pve_actors[i].occupied&&bg_players[BG_PLAYERS+i].health>0;
        rdpq_tex_upload(TILE0,&pixel_atlas,NULL);
        if(bg_ff.phase==BG_FF_BONUS)snprintf(state,sizeof(state),"BONUS %us E%u",(unsigned)ceilf(fmaxf(0,bg_ff.timer)),alive);
        else snprintf(state,sizeof(state),"R%u W%u L%u E%u",bg_ff.round+1,bg_ff.wave+1,bg_ff.lives,alive);
        hud_text(state,x+margin,y+height-19,hud_cyan);
        snprintf(state,sizeof(state),"%u  %02u:%02u",(unsigned)bg_ff.team_score,(unsigned)bg_ff.elapsed/60,(unsigned)bg_ff.elapsed%60);
        hud_text(state,x+margin,y+height-10,hud_cyan);
        if(bg_ff.message_time>0&&hud_text_width(bg_ff.message)<width-8)hud_text(bg_ff.message,x+(width-hud_text_width(bg_ff.message))/2,y+25,hud_cyan);
        if(alive<=3&&bg_ff.packet>=bg_ff.packets&&p->health>0){
            const T3DViewport*vp=bg_scene_viewport(index);
            for(unsigned i=0;i<bg_pve_count;i++)if(bg_players[BG_PLAYERS+i].health>0&&bg_pve_actors[i].arrival!=1){
                const float*pos=bg_players[BG_PLAYERS+i].pos;T3DVec3 world={{pos[0]*BG_SCALE,(pos[1]+1)*BG_SCALE,pos[2]*BG_SCALE}},screen={{0}};
                float depth=-(world.v[0]*vp->matCamera.m[0][2]+world.v[1]*vp->matCamera.m[1][2]+world.v[2]*vp->matCamera.m[2][2]+vp->matCamera.m[3][2]);if(depth<=0)continue;
                t3d_viewport_calc_viewspace_pos((T3DViewport*)vp,&screen,&world);int px=(int)fmaxf(x+8,fminf(x+width-8,screen.v[0])),py=(int)fmaxf(y+25,fminf(y+height-30,screen.v[1]));hud_text("!",px,py,red);
            }
        }
    }
#endif
#ifdef BG_INTERACTION_QA
    if (BG_INTERACTION_QA == 4) {
        const bg_vehicle *v = &bg_vehicles[index];
        char state[32];
        snprintf(state, sizeof(state), "UP %d %s", (int)lroundf(v->up[1] * 100),
                 v->flipping                          ? "ROLLING"
                 : v->up[1] >= BG_VEHICLE_FLIP_MAX_UP ? "READY"
                                                      : "FLIPPED");
        rdpq_tex_upload(TILE0, &pixel_atlas, NULL);
        hud_text(state, x + (width - hud_text_width(state)) / 2, y + height / 2 - 18, hud_cyan);
    }
#endif
    rdpq_set_mode_standard();
}
