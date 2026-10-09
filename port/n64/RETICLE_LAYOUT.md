# Xbox reticle placement

The aiming reticle is centered in the original **title-safe window**, which
differs from the pixel viewport in split screen. It is not a universal lowered
fraction. The top players aim below their viewport center; the bottom players
aim above it. Four-player reticles also move inward horizontally.

The source chain is:

- `source/rasterizer/xbox/rasterizer_xbox.c`, `RASTERIZER_FRAME_BOUNDS_*`:
  the 640×480 Xbox title-safe rectangle is `(48,36)`–`(592,444)`.
- `source/main/main.c`, `compute_subframe_counts` / `compute_window_bounds`:
  divide that rectangle among players, inset the split-facing safe edges by
  four Xbox pixels, and expand outer **pixel viewport** edges to the screen.
  `main_game_render` stores both rectangles in the camera;
  `set_window_camera_values` preserves them when copying the render camera.
- `source/interface/hud_weapon.c`, `crosshairs_draw`: crosshair elements use
  `_hud_anchor_center`. `source/interface/hud_draw.c`, `hud_calculate_point`:
  anchor at the integer safe-window midpoint, subtract the pixel viewport
  origin, then add the tag placement offset.
- The eight Xbox weapon aiming sprites and four vehicle aiming sprites have
  zero anchor offset in the owned Blood Gulch / a30 caches. Sniper decoration
  and zoom labels have separate nonzero offsets; they do not redefine aim.
- `source/render/render_cameras.c`, `render_camera_build_frustum_bounds` and
  `render_camera_build_frustum`: the same window/viewport rectangles produce
  an off-axis projection. `render_camera_view_to_screen` therefore maps the
  unchanged camera-forward ray to that same HUD anchor.

At the port's 320×240 resolution, the screen-space aim positions are:

| Layout | Player positions in screen pixels |
| --- | --- |
| One player | `(160,120)` |
| Two players | `(159,68)`, `(159,172)` |
| Four players | `(91,68)`, `(229,68)`, `(91,172)`, `(229,172)` |

`hud_layout.h` retains the original coordinates until converting to the actual
viewport's local size. `bg_hud_aim_projection` changes only Tiny3D projection
offsets `[2][0]` and `[2][1]`; the port's existing FOV, zoom and depth terms stay
unchanged. Call it **after** `t3d_viewport_set_projection` and **before**
`t3d_viewport_look_at`, which builds the matching camera/projection product and
frustum. Culling margins must be derived after that operation. Camera aim and
gameplay shot directions are not rotated to fake the HUD offset.

HUD reticles, scope marks and scope mask centers share this anchor. Any mask
strip exposed by the offset extends the original mask's constant edge alpha.
Unrelated HUD corners retain the existing N64 layout adaptation. Three-player
layout is not exposed by this port and is outside this helper's contract.

Run the focused host test with:

```sh
clang -std=c11 -Wall -Wextra -Werror -fsanitize=address,undefined \
  port/n64/test_hud_layout.c -lm -o build/n64/test_hud_layout
build/n64/test_hud_layout
```

The test independently transcribes the original window and projection formula,
checks all seven supported viewports and forward rays at ten zoom scales, and
checks Tiny3D fixed16.16 projection rounding. Fresh local tag evidence is saved
in `build/n64/reticle-layout/aim-tag-offsets.json`.
