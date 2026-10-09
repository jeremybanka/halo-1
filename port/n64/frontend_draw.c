#include "frontend_draw.h"
#include "asset_frontend.h"
#include "menu_draw.h"
#include <libdragon.h>
#include <t3d/t3d.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Source widget coordinates remain in the Xbox 640x480 space. Only the
 * final raster transform halves them. ROM pixels are resident for one page. */
/* Large pages use independent strips to avoid requiring a contiguous 307 KiB
 * allocation after a match. One overlap row preserves bilinear edges. */
typedef struct {
    unsigned id, count, width, height;
    surface_t *slices;
} cached_image;
static cached_image cache[32];
static unsigned cache_count;
static uint64_t cache_key = UINT64_MAX;
static FILE *bank;
static surface_t fonts[2][4], mesh_textures[8];
static void *font_pixels[2], *vertices[8];
static T3DViewport viewport;
static bool loaded;
/* Menu text commands copy their glyph coordinates into the RDP queue. Keep
 * the batching workspace resident only while the front end is open. */
typedef struct {
    const bg_menu_glyph *g;
    float x, y;
    unsigned font;
    color_t color;
} glyph;
static glyph *letters;
static unsigned letter_count;
static volatile bool graphics_done;
static void graphics_complete(void *unused) {
    (void)unused;
    graphics_done = true;
}
static void graphics_wait(void) {
    graphics_done = false;
    rdpq_sync_full(graphics_complete, NULL);
    rspq_flush();
    while (!graphics_done) {
    }
    rspq_wait();
}
static const unsigned profile_palette[4] = {2, 3, 5, 6};
static const color_t blue = {40, 150, 255, 255}, white = {204, 204, 204, 255};
static void read_bank(void *out, unsigned offset, unsigned length) {
    assertf(bank && fseek(bank, offset, SEEK_SET) == 0, "Front-end asset seek");
    assertf(fread(out, 1, length, bank) == length, "Front-end asset read");
    if (!((uintptr_t)out & 0x20000000))
        data_cache_hit_writeback(out, length);
}
static void clear_cache(void) {
    for (unsigned i = 0; i < cache_count; i++) {
        for (unsigned j = 0; j < cache[i].count; j++)
            surface_free(&cache[i].slices[j]);
        free(cache[i].slices);
    }
    cache_count = 0;
    cache_key = UINT64_MAX;
}
void bg_front_draw_release(void) {
    if (!loaded)
        return;
    graphics_wait();
    clear_cache();
    free(letters);
    letters = NULL;
    for (unsigned f = 0; f < 2; f++) {
        free(font_pixels[f]);
        font_pixels[f] = NULL;
    }
    for (unsigned m = 0; m < bg_shell_mesh_count; m++) {
        free(vertices[m]);
        surface_free(&mesh_textures[m]);
    }
    fclose(bank);
    bank = NULL;
    loaded = false;
}
static void load(void) {
    if (loaded)
        return;
    letters = malloc(1200 * sizeof(*letters));
    assertf(letters, "Front-end glyph workspace");
    bank = fopen("rom:/shell.bin", "rb");
    assertf(bank, "Missing front-end ROM bank");
    for (unsigned f = 0; f < 2; f++) {
        unsigned size = bg_shell_font_pages[f] * BG_MENU_ATLAS_BYTES;
        font_pixels[f] = malloc(size);
        assertf(font_pixels[f], "Front-end font RAM");
        read_bank(font_pixels[f], bg_shell_font_offsets[f], size);
        for (unsigned p = 0; p < bg_shell_font_pages[f]; p++)
            fonts[f][p] = surface_make_linear((uint8_t *)font_pixels[f] + p * BG_MENU_ATLAS_BYTES,
                                              FMT_I4, 128, 64);
    }
    assert(bg_shell_mesh_count <= 8);
    for (unsigned m = 0; m < bg_shell_mesh_count; m++) {
        const bg_shell_mesh *mesh = &bg_shell_meshes[m];
        vertices[m] = malloc(mesh->count * 16);
        assertf(vertices[m], "Front-end backdrop RAM");
        read_bank(vertices[m], mesh->offset, mesh->count * 16);
        const bg_shell_image *im = &bg_shell_images[mesh->image];
        mesh_textures[m] = surface_alloc(FMT_RGBA32, im->w, im->h);
        read_bank(mesh_textures[m].buffer, im->offset, im->w * im->h * 4);
    }
    viewport = t3d_viewport_create();
    loaded = true;
}
static const bg_shell_node *node(unsigned tag) {
    for (unsigned n = 0; n < bg_shell_node_count; n++)
        if (bg_shell_nodes[n].tag == tag)
            return &bg_shell_nodes[n];
    assertf(false, "Unknown front-end widget %u", tag);
    return NULL;
}
static cached_image *picture(unsigned tag, unsigned frame, unsigned width, unsigned height) {
    unsigned id = ~0u;
    for (unsigned n = 0; n < bg_shell_image_count; n++)
        if (bg_shell_images[n].tag == tag && bg_shell_images[n].frame == frame) {
            id = n;
            break;
        }
    if (id == ~0u && frame)
        return picture(tag, 0, width, height);
    assertf(id != ~0u, "Missing front-end picture %u/%u", tag, frame);
    for (unsigned i = 0; i < cache_count; i++)
        if (cache[i].id == id)
            return &cache[i];
    assertf(cache_count < 32, "Front-end page image capacity");
    const bg_shell_image *im = &bg_shell_images[id];
    cached_image *c = &cache[cache_count++];
    width = width < im->w ? width : im->w;
    height = height < im->h ? height : im->h;
    c->id = id;
    c->width = width;
    c->height = height;
    c->count = width * height * 4 > 65536 ? (height + 31) / 32 : 1;
    c->slices = calloc(c->count, sizeof(*c->slices));
    assertf(c->slices, "Front-end texture descriptors");
    for (unsigned n = 0; n < c->count; n++) {
        unsigned first = c->count == 1 ? 0 : n * 32 - (n != 0);
        unsigned end =
            c->count == 1 ? height : (height < (n + 1) * 32 + 1 ? height : (n + 1) * 32 + 1);
        surface_t *slice = &c->slices[n];
        *slice = surface_alloc(FMT_RGBA32, width, end - first);
        assertf(slice->buffer, "Front-end page texture RAM");
        for (unsigned y = first; y < end; y++)
            read_bank((uint8_t *)slice->buffer + (y - first) * width * 4,
                      im->offset + y * im->w * 4, width * 4);
    }
    return c;
}
static void bitmap(unsigned tag, unsigned frame, float x, float y, float w, float h,
                   unsigned alpha) {
    cached_image *c = picture(tag, frame, (unsigned)ceilf(w * .5f), (unsigned)ceilf(h * .5f));
    float sw = fminf(w * .5f, c->width), sh = fminf(h * .5f, c->height);
    float sx = w * .5f / sw, sy = h * .5f / sh;
    rdpq_set_mode_standard();
    rdpq_mode_alphacompare(0);
    rdpq_mode_blender(RDPQ_BLENDER_MULTIPLY);
    rdpq_mode_combiner(RDPQ_COMBINER_TEX_FLAT);
    rdpq_set_prim_color(RGBA32(255, 255, 255, alpha));
    for (unsigned n = 0; n < c->count; n++) {
        unsigned first = c->count == 1 ? 0 : n * 32 - (n != 0);
        if (c->count > 1)
            rdpq_set_scissor(0, y * .5f + n * 32 * sy, 320,
                             y * .5f + (c->height < (n + 1) * 32 ? c->height : (n + 1) * 32) * sy);
        rdpq_tex_blit(&c->slices[n], x * .5f, y * .5f + first * sy,
                      &(rdpq_blitparms_t){.width = sw,
                                          .height = c->count == 1 ? sh : c->slices[n].height,
                                          .scale_x = sx,
                                          .scale_y = sy,
                                          .filtering = true});
    }
    if (c->count > 1)
        rdpq_set_scissor(0, 0, 320, 240);
}

static void art(unsigned tag, unsigned frame, int dx, int dy, unsigned alpha) {
    const bg_shell_node *n = node(tag);
    if (n->bitmap >= 0)
        bitmap(n->bitmap, frame, n->x + dx, n->y + dy, n->w, n->h, alpha);
}
/* Glyphs are batched by immutable atlas page; source font metrics and case
 * are preserved, including original multiline descriptions. */
static unsigned code(unsigned c) {
    return c >= 32 && c < 127 ? c - 32 : '?' - 32;
}
static float width(unsigned font, const char *s, unsigned n) {
    float w = 0;
    for (unsigned i = 0; i < n; i++)
        w += bg_shell_glyphs[font][code((uint8_t)s[i])].advance;
    return w;
}
static void text(unsigned font, float x, float y, float w, float h, unsigned align, color_t color,
                 const char *s) {
    float baseline = y + bg_shell_font_ascending[font], line = font ? 17 : 21;
    while (*s && baseline <= y + h) {
        unsigned n = 0, space = 0;
        float span = 0;
        while (s[n] && s[n] != '\n') {
            float advance = bg_shell_glyphs[font][code((uint8_t)s[n])].advance;
            if (span + advance > w && n)
                break;
            span += advance;
            if (s[n] == ' ')
                space = n;
            n++;
        }
        if (s[n] && s[n] != '\n' && space)
            n = space;
        float px = x;
        if (align == 1)
            px += w - width(font, s, n);
        else if (align == 2)
            px += (w - width(font, s, n)) * .5f;
        for (unsigned i = 0; i < n; i++) {
            const bg_menu_glyph *g = &bg_shell_glyphs[font][code((uint8_t)s[i])];
            if (g->w && g->h) {
                assert(letter_count < 1200);
                letters[letter_count++] = (glyph){g, (px - g->origin_x) * .5f,
                                                  (baseline - g->origin_y) * .5f, font, color};
            }
            px += g->advance;
        }
        s += n;
        if (*s == '\n' || *s == ' ')
            s++;
        baseline += line;
    }
}
static void label(unsigned tag, int dx, int dy, const char *override, color_t color) {
    const bg_shell_node *n = node(tag);
    text(n->font, n->x + dx + n->text_x, n->y + dy + n->text_y, n->w, n->h, n->align, color,
         override ? override : n->text);
}
static void flush(void) {
    rdpq_set_mode_standard();
    rdpq_mode_blender(RDPQ_BLENDER_MULTIPLY);
    rdpq_mode_combiner(RDPQ_COMBINER1((0, 0, 0, PRIM), (TEX0, 0, PRIM, 0)));
    rdpq_mode_filter(FILTER_BILINEAR);
    for (unsigned f = 0; f < 2; f++)
        for (unsigned p = 0; p < bg_shell_font_pages[f]; p++) {
            rdpq_sync_pipe();
            rdpq_sync_load();
            rdpq_tex_upload(TILE0, &fonts[f][p], NULL);
            for (unsigned i = 0; i < letter_count; i++) {
                const glyph *l = &letters[i];
                const bg_menu_glyph *g = l->g;
                if (l->font != f || g->page != p)
                    continue;
                rdpq_set_prim_color(l->color);
                rdpq_texture_rectangle_scaled(TILE0, l->x, l->y, l->x + g->w * .5f,
                                              l->y + g->h * .5f, g->s, g->t, g->s + g->w,
                                              g->t + g->h);
            }
        }
}
static color_t color(bool available, bool focus) {
    color_t c = focus ? white : blue;
    if (!available)
        c.a = 140;
    return c;
}
static void buttons(bool accept) {
    art(302, 0, 371, 414, 255);
    label(304, 392, 414, NULL, blue);
    art(306, 0, 471, 414, accept ? 255 : 140);
    label(308, 492, 414, NULL, color(accept, false));
}
static void backdrop(uint64_t now, bg_front_page page) {
    /* Original ui.map camera transforms. ring_loop changes its target every
     * 200 ticks while each blend takes 400 ticks (30 Hz script clock). */
    static float origin[7], current[7];
    static unsigned target_index, category;
    static uint64_t transition, orbit_start;
    static bool camera_started;
    unsigned wanted_category =
        page == BG_FRONT_MAIN                                                                  ? 0
        : (page == BG_FRONT_SETTINGS || page == BG_FRONT_PROFILE || page == BG_FRONT_CONTROLS) ? 2
                                                                                               : 3;
    if (!camera_started) {
        memcpy(current, bg_shell_cameras[0], sizeof(current));
        memcpy(origin, current, sizeof(origin));
        camera_started = true;
        transition = orbit_start = now;
    }
    float blend = fminf(1.f, (now - transition) / 13333333.f);
    blend = blend * blend * (3 - 2 * blend);
    for (unsigned n = 0; n < 7; n++)
        current[n] = origin[n] + (bg_shell_cameras[target_index][n] - origin[n]) * blend;
    unsigned wanted = wanted_category;
    if (wanted_category == 0) {
        unsigned step = (unsigned)((now - orbit_start) / 6666667) % 11;
        wanted = step ? step + 4 : 0;
    }
    if (wanted != target_index || category != wanted_category) {
        memcpy(origin, current, sizeof(origin));
        target_index = wanted;
        transition = now;
        if (category != wanted_category) {
            category = wanted_category;
            transition = now - 12000000;
        }
    }
    float yaw = current[3], pitch = current[4], roll = current[5];
    float cy = cosf(yaw), sy = sinf(yaw), cp = cosf(pitch), sp = sinf(pitch), cr = cosf(roll),
          sr = sinf(roll);
    T3DVec3 eye = {{current[0] * 32, current[2] * 32, -current[1] * 32}};
    T3DVec3 target = {{eye.v[0] + cp * cy, eye.v[1] + sp, eye.v[2] - cp * sy}};
    T3DVec3 up = {{-sp * cy * cr + sy * sr, cp * cr, sp * sy * cr + cy * sr}};
    /* The closest source menu camera is over 13 units from the ring. A
     * four-unit near plane gives its closely spaced shells better Z precision. */
    t3d_viewport_set_projection(&viewport, 2 * atanf(tanf(current[6] * .5f) * .75f), 4.f, 18000.f);
    t3d_viewport_look_at(&viewport, &eye, &target, &up);
    t3d_viewport_attach(&viewport);
    rdpq_clear(RGBA32(0, 0, 0, 255));
    t3d_frame_start();
    t3d_light_set_ambient((uint8_t[]){255, 255, 255, 255});
    t3d_light_set_count(0);
    rdpq_mode_combiner(RDPQ_COMBINER_TEX_SHADE);
    rdpq_mode_filter(FILTER_BILINEAR);
    rdpq_mode_persp(true);
    for (unsigned m = 0; m < bg_shell_mesh_count; m++) {
        rdpq_sync_pipe();
        rdpq_sync_tile();
        rdpq_sync_load();
        const bg_shell_mesh *mesh = &bg_shell_meshes[m];
        bool depth = mesh->flags & BG_SHELL_DEPTH;
        t3d_state_set_drawflags(T3D_FLAG_SHADED | T3D_FLAG_TEXTURED | T3D_FLAG_CULL_BACK |
                                (depth ? T3D_FLAG_DEPTH : 0));
        rdpq_mode_zbuf(depth, depth && !(mesh->flags & BG_SHELL_DECAL));
        rdpq_mode_blender(mesh->flags & BG_SHELL_BLEND ? RDPQ_BLENDER_MULTIPLY : 0);
        rdpq_sync_pipe();
        rdpq_sync_load();
        rdpq_tex_upload(
            TILE0, &mesh_textures[m],
            &(rdpq_texparms_t){.s.repeats = REPEAT_INFINITE, .t.repeats = REPEAT_INFINITE});
        unsigned count = mesh->count / 3 * 3;
        for (unsigned first = 0; first < count; first += 60) {
            unsigned n = count - first > 60 ? 60 : count - first;
            t3d_vert_load((T3DVertPacked *)vertices[m] + first / 2, 0, (n + 1) & ~1u);
            for (unsigned v = 0; v < n; v += 3)
                t3d_tri_draw(v, v + 1, v + 2);
            t3d_tri_sync();
        }
    }
    rdpq_sync_pipe();
    rdpq_sync_tile();
    rdpq_sync_load();
    rdpq_set_scissor(0, 0, 320, 240);
}
static unsigned type_icon(unsigned type) {
    if (type <= 6 || type == 25)
        return 2;
    if (type <= 11 || type == 23)
        return 3;
    if (type <= 14 || type == 24)
        return 1;
    if (type <= 16 || type == 21 || type == 22)
        return 4;
    return 0;
}
void bg_front_draw(const bg_frontend *f, uint64_t now) {
    /* This front end is unpaced. Waiting protects the single camera and page
     * textures across all asynchronous RSP/RDP work, including page changes. */
    graphics_wait();
    load();
    /* Disjoint fields: profile choices may repeat in unjoined slots, so a
     * summed 32-bit key could alias another page and retain stale textures. */
    uint64_t key = f->page | ((uint64_t)f->row << 4) | ((uint64_t)f->map << 7) |
                   ((uint64_t)f->type << 11) | ((uint64_t)f->settings_profile << 16);
    if (f->page == BG_FRONT_JOIN)
        for (unsigned p = 0; p < 4; p++)
            key |= (uint64_t)(f->profile[p] + 4 * f->joined[p] + 8 * f->ready[p]) << (18 + 4 * p);
    if (key != cache_key) {
        clear_cache();
        cache_key = key;
    }
    letter_count = 0;
    backdrop(now, f->page);
    if (f->page != BG_FRONT_MAIN)
        art(383, 0, 0, 0, 255);
    switch (f->page) {
    case BG_FRONT_MAIN: {
        art(272, 0, 0, 28, 255);
        const unsigned tags[] = {276, 381, 902, 911};
        for (unsigned r = 0; r < 4; r++)
            art(tags[r], f->row == r ? 1 : 0, r ? 192 : 194, 247 + 36 * r,
                bg_front_available(f->page, r) ? 255 : 140);
        break;
    }
    case BG_FRONT_MULTIPLAYER: {
        art(384, 0, 0, 0, 255);
        art(387, 0, 0, 0, 255);
        art(388, f->row, 0, 0, 255);
        const unsigned tags[] = {392, 488, 590, 645};
        for (unsigned r = 0; r < 4; r++) {
            art(tags[r], f->row == r ? 1 : 0, 0, r == 3 ? -11 : -33,
                bg_front_available(f->page, r) ? 255 : 140);
            label(tags[r], 0, r == 3 ? -11 : -33, NULL,
                  color(bg_front_available(f->page, r), f->row == r));
        }
        const char *desc[] = {"Play through the single-player\ncampaign with a friend.",
                              "Play a multiplayer game\non this Xbox.",
                              "Play a multiplayer game\nwith other Xbox consoles.",
                              "Create and edit your\nmultiplayer game types."};
        label(390, 0, 37, desc[f->row], blue);
        buttons(bg_front_available(f->page, f->row));
        break;
    }
    case BG_FRONT_JOIN: {
        art(588, 0, 0, 0, 255);
        for (unsigned p = 0; p < 4; p++) {
            int x = 70 + 258 * (p % 2), y = 76 + 166 * (p / 2);
            char name[32];
            snprintf(name, sizeof(name), "Player %u", f->profile[p] + 1);
            art(f->joined[p] ? 493 : 491, 0, x, y, 255);
            if (!f->joined[p]) {
                label(586, x + 20, y + 20, "Press START to Join", blue);
                art(587, 0, x, y, 255);
            } else {
                art(582, profile_palette[f->profile[p]], x, y, 255);
                label(585, x, y, name, white);
                label(583, x, y,
                      f->ready[p]
                          ? "Profile Selected\n\nPress A when all\nplayers have\nselected profiles"
                          : "Choose a Profile\n\nPress A to select",
                      blue);
            }
        }
        buttons(true);
        break;
    }
    case BG_FRONT_MAP:
    case BG_FRONT_TYPE: {
        bool map = f->page == BG_FRONT_MAP;
        unsigned selected = map ? f->map : f->type, count = map ? 13 : 26;
        art(map ? 576 : 559, 0, 0, 0, 255);
        const unsigned cards[2][3] = {{545, 551, 555}, {563, 568, 572}};
        for (unsigned col = 0; col < 3; col++) {
            unsigned item = (selected + count + col - f->row) % count, tag = cards[map][col];
            bool avail = bg_front_available(f->page, item), focus = col == f->row;
            art(tag, focus ? 1 : 0, 0, 0, avail ? 255 : 140);
            art(tag + 2, map ? item : type_icon(item), 0, 0, avail ? 255 : 140);
            label(tag + 1, 0, 0, map ? bg_front_maps[item].name : bg_shell_type_names[item],
                  color(avail, focus));
            label(tag + 3, 0, 0,
                  map ? bg_shell_map_descriptions[item] : bg_shell_type_descriptions[item],
                  color(avail, false));
        }
        buttons(bg_front_available(f->page, selected));
        break;
    }
    case BG_FRONT_PREGAME: {
        art(500, 0, 0, 0, 255);
        art(502, 0, 56, 78, 255);
        art(505, 0, 56, 115, 255);
        art(508, 1, 105, 144, 255);
        art(521, 0, 0, 0, 255);
        art(523, 2, 4, 32, 255);
        art(525, 9, 4, 32, 255);
        label(518, 71, 82, NULL, blue);
        char value[48];
        snprintf(value, sizeof(value), "%d", f->countdown);
        label(520, 202, 82, value, white);
        for (unsigned p = 0; p < f->count; p++) {
            int y = 205 + 48 * p;
            art(511, 1, 69, y, 255);
            snprintf(value, sizeof(value), "Player %u", f->profile[f->ports[p]] + 1);
            label(513, 133, y, value, white);
        }
        label(535, 4, 32, NULL, blue);
        label(528, 330, 257, "Blood Gulch", white);
        label(530, 400, 278, "Slayer", white);
        label(531, 342, 299, "Free-for-all", white);
        snprintf(value, sizeof(value), "%u", f->count);
        label(532, 459, 320, value, white);
        label(533, 397, 341, "15", white);
        label(534, 426, 341, "Kills", white);
        text(1, 50, 414, 560, 26, 0, blue, "C-LEFT =DELAY GAME       B =BACK       A =START GAME");
        break;
    }
    case BG_FRONT_RESULTS: {
        bitmap(11420, 0, 0, 0, 640, 480, 255);
        /* game_engine_post_rasterize_post_game: six tabs and 18px rows. */
        const unsigned tabs[] = {50, 125, 250, 350, 410, 500};
        const char *const headings[] = {"Place", "Player", "Score", "Kills", "Assists", "Deaths"};
        for (unsigned c = 0; c < 6; c++)
            text(1, tabs[c], 126, c == 1 ? 124 : 85, 26, 0, white, headings[c]);
        unsigned order[4] = {0, 1, 2, 3};
        for (unsigned i = 0; i < f->count; i++)
            for (unsigned j = i + 1; j < f->count; j++)
                if (f->final_scores[order[j]] > f->final_scores[order[i]]) {
                    unsigned t = order[i];
                    order[i] = order[j];
                    order[j] = t;
                }
        unsigned rank = 1;
        for (unsigned i = 0; i < f->count; i++) {
            unsigned p = order[i];
            char value[40];
            float y = 144 + i * 18;
            if (i && f->final_scores[p] != f->final_scores[order[i - 1]])
                rank = i + 1;
            for (unsigned c = 0; c < 6; c++) {
                if (c == 0)
                    snprintf(value, sizeof(value), "%u%s", rank,
                             rank == 1   ? "st"
                             : rank == 2 ? "nd"
                             : rank == 3 ? "rd"
                                         : "th");
                else if (c == 1)
                    snprintf(value, sizeof(value), "Player %u", f->profile[f->ports[p]] + 1);
                else
                    snprintf(value, sizeof(value), "%d",
                             c == 2   ? f->final_scores[p]
                             : c == 3 ? f->statistics.kills[p]
                             : c == 4 ? f->statistics.assists[p]
                                      : f->statistics.deaths[p]);
                text(1, tabs[c], y, c == 1 ? 124 : 85, 26, 0,
                     p == (unsigned)f->winner ? white : blue, value);
            }
        }
        art(306, 0, 380, 410, 255);
        text(0, 402, 410, 180, 26, 0, white, "=CONTINUE");
        break;
    }
    case BG_FRONT_SETTINGS: {
        art(909, 0, 0, 0, 255);
        const unsigned cards[] = {354, 369, 372}, names[] = {355, 370, 373};
        for (unsigned c = 0; c < 3; c++) {
            unsigned p = (f->settings_profile + 4 + c - f->row) % 4;
            char name[32];
            snprintf(name, sizeof(name), "Player %u", p + 1);
            art(cards[c], c == f->row ? 1 : 0, 0, 0, 255);
            label(names[c], 81 + 167 * c, 83, name, color(true, c == f->row));
            bitmap(357, profile_palette[p], 104 + 167 * c, 110, 112, 136, 255);
            text(1, 83 + 167 * c, 267, 145, 90, 0, blue, bg_control_style_name(f->styles[p]));
        }
        buttons(true);
        break;
    }
    case BG_FRONT_PROFILE: {
        art(397, 0, 0, 0, 255);
        art(401, 0, 0, 0, 255);
        const unsigned tags[] = {406, 411, 432, 460, 476};
        for (unsigned r = 0; r < 5; r++) {
            bool enabled = bg_front_available(f->page, r);
            art(tags[r], r == f->row ? 1 : 0, 0, r == 4 ? 22 : 0, enabled ? 255 : 140);
            label(tags[r], 0, r == 4 ? 22 : 0, NULL, color(enabled, r == f->row));
        }
        char name[32];
        snprintf(name, sizeof(name), "Player %u", f->settings_profile + 1);
        bitmap(357, profile_palette[f->settings_profile], 370, 115, 112, 136, 255);
        text(0, 294, 290, 290, 90, 0, blue, "Choose a controller setup.\n\nCurrent Profile:");
        text(0, 432, 353, 145, 26, 0, white, name);
        buttons(bg_front_available(f->page, f->row));
        break;
    }
    case BG_FRONT_CONTROLS: {
        bg_menu m = {.open = true, .owner = f->host, .page = BG_MENU_CONTROLS};
        m.styles[m.owner] = f->styles[f->settings_profile];
        bg_menu_draw_profile(&m, f->settings_profile);
        break;
    }
    case BG_FRONT_QUIT:
        text(0, 95, 140, 450, 35, 0, white, "Quit the current game?");
        text(0, 120, 205, 360, 32, 0, color(true, f->row == 0), "Yes");
        text(0, 120, 245, 360, 32, 0, color(true, f->row == 1), "No");
        buttons(true);
        break;
    default:
        break;
    }
    flush();
}
