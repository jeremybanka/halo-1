# N64 menu artwork

The shell retains the Xbox widget positions and texture dimensions. These six
small RGBA PNGs replace the A/B legends, the two controller sprites used by the
join/pregame screens, and the Split Screen / Cooperative Play illustrations. Extraction
downsamples them by two exactly like the original bitmaps. Their hashes are
included in `frontend-report.json`; changing an asset requires regenerating the
bank with `build/n64-python/bin/python port/n64/extract_frontend.py`.

- `n64-a.png`: blue A; `n64-b.png`: green B. Circular N64-style plastic buttons.
- `m64-join.png` and `m64-connected.png`: downsampled from the transparent
  official [ModRetro M64 Pro Controller product image](https://modretro.com/products/m64-pro-controller),
  clear colorway, retrieved 2026-10-03.
  [Source WebP](https://modretro.com/cdn/shop/files/M64_controller_clear_01_small_79239c08-f228-4e5e-a380-5bf8f19b9d65.webp?v=1783744143&width=1946).
  Product artwork belongs to ModRetro. Retain this attribution when redistributing.
- `m64-splitscreen.png`: built-in imagegen adaptation of the locally extracted
  Split Screen illustration, with the official M64 photo as its controller
  reference. The TV/console arrangement and blue outline treatment are retained.
  The dimmed Cooperative Play illustration receives the same controller update.
  Network modes without controller drawings keep their original illustrations.

The built-in imagegen tool produced the buttons and illustration (not the
controller photographs). Only mechanical alpha-bound crops, resizing, and
transparent texture-sheet packing were applied afterward. The source photograph
and full-size generation outputs are retained locally under the build audit and
Codex generated-images directories; these final game assets are self-contained.

## Final generation prompts

### Cooperative-play illustration

Edit the first image: a Halo CE cooperative-play menu illustration. Replace ONLY its two Xbox Duke controllers at the lower left with two ModRetro M64 Pro controllers matching the trident silhouette and button layout in reference two. Keep the CRT television with a horizontal two-player split, Xbox console at lower right, arrangement, blue luminous outlines, dark blue shading and transparent background. Preserve composition and relative sizes. Controllers have three grips, long center grip, analog stick in middle, D-pad left, yellow C buttons right, blue A green B. Faithful original low-resolution 2001 game menu artwork. Crop tightly to complete illustration with no blank margins, no extra labels or captions; omit stray vertical line at far right of reference. Will be reduced to about 145x90 pixels.

### Split-screen illustration

Edit the first image: a Halo CE split-screen menu illustration. Replace its four Xbox Duke controllers with four ModRetro M64 Pro controllers matching the trident silhouette and button layout in the second reference. Keep the CRT television with its four black screen quadrants, the Xbox console, connecting cables, arrangement, blue luminous outlines, dark blue subdued shading, and transparent background. Preserve the TV and console shape, proportions and position. All four controllers must have three grips including a long center grip, one analog stick in the middle, D-pad left and yellow C buttons right, blue A and green B. The whole illustration must stay compact, legible and faithful to original low-resolution 2001 game menu pixel artwork, not photorealistic. Crop the canvas tightly around the complete illustration; no large blank margins, no extra text, no captions. Asset will be reduced to about 145x90 pixels.

### Buttons

A transparent sprite sheet with exactly two Nintendo 64 controller face-button icons side by side, blue A on the left and green B on the right. Both identical diameter and centered in their respective square halves. Front-on circular colored plastic buttons, modest beveled rim, subtle top-left shine, deep embossed readable black letter A and B respectively. Classic N64 blue A and green B, NOT Xbox green A/red B. Clean simple authentic late-1990s game menu graphics, strong readable letters. Equal size circular silhouettes, no perspective oval, no glow, no extra labels, no panel or shadows outside circles. Actual transparent background. These will be used at 11x11 pixels, so prioritize solid simple silhouettes and bold single letters. Tight bounding squares with minimal padding.
