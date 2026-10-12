#!/usr/bin/env python3
"""Bake native one-bit weapon silhouettes from an owned Xbox HUD icon sheet.

All game-derived pixels stay in the local build directory, outside source Git.
No filtering, fractional coordinates or runtime bitmap mutation is required.
"""
import argparse
import contextlib
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
# Runtime weapon order; indices come from weapon HUD messaging_information.
SEQUENCES = (8, 9, 6, 11, 10, 12, 4, 5, 7)
NAMES = ("Assault Rifle", "Pistol", "Plasma Pistol", "Plasma Rifle", "Needler",
         "Shotgun", "Sniper Rifle", "Rocket Launcher", "Flamethrower")


def refine_native_mask(weapon, mask):
    """Preserve identifying features that BOX coverage loses at native size.

    Corrections are deliberately local to the source-derived 31x12 fit; a
    global threshold change would thicken unrelated edges and close holes.
    """
    if weapon == 0:
        # Open the thumb hole one column toward the butt. Restore the rear
        # receiver's raised shoulder and the front taper of the top housing.
        for y in (7, 8):
            mask.putpixel((6, y), 0)
        for x in range(2, 7):
            mask.putpixel((x, 1), 255)
        for x in range(23, 26):
            mask.putpixel((x, 0), 255)
    elif weapon == 1:
        # A closed trigger guard, with an open interior and a stepped lower
        # corner: both ends connect to the pistol rather than floating.
        for point in ((8, 4), (7, 7), (6, 8), (7, 8)):
            mask.putpixel(point, 255)
    elif weapon == 7:
        # Retain the narrow under-barrel rail connecting the forward grip.
        for x in range(20, 29):
            mask.putpixel((x, 4), 255)
        # An isolated coverage sample from the rear ring is not a silhouette.
        mask.putpixel((0, 3), 0)
    return mask


def bake(output):
    from reclaimer.meta.wrappers.halo1_map import Halo1Map
    from reclaimer.bitmaps.bitmap_decompilation import extract_bitmaps
    output.mkdir(parents=True, exist_ok=True)
    cache = ROOT / "build/n64/assets/bloodgulch-decompressed.map"
    with (output / "extraction.log").open("w") as log, contextlib.redirect_stdout(log):
        halo = Halo1Map()
        halo.load_map(cache)
        entries = halo.tag_index.tag_index
        tag = next(i for i, e in enumerate(entries)
                   if e.path == r"ui\hud\bitmaps\combined\hud_msg_icons")
        meta = halo.get_meta(tag)
        sprites = [meta.sequences.STEPTREE[i].sprites.STEPTREE[0] for i in SEQUENCES]
        halo.meta_to_tag_data(meta, "bitm", entries[tag])
        extract_bitmaps(meta, "source", out_dir=output, bitmap_ext="png", halo_map=halo)
    atlas = Image.new("L", (64, 64))
    records, references, icons = [], [], []
    for i, sprite in enumerate(sprites):
        sheet = Image.open(output / f"source__{sprite.bitmap_index}.png").convert("RGBA")
        bounds = tuple(round(v * n) for v, n in zip(
            (sprite.left_side, sprite.top_side, sprite.right_side, sprite.bottom_side),
            (sheet.width, sheet.height, sheet.width, sheet.height)))
        alpha = sheet.crop(bounds).getchannel("A")
        alpha = alpha.crop(alpha.getbbox())
        # Fit the long barrels and vertical grips without changing aspect ratio.
        scale = min(31 / alpha.width, 12 / alpha.height)
        w, h = max(1, round(alpha.width * scale)), max(1, round(alpha.height * scale))
        threshold = 48 if i == 6 else 72
        mask = alpha.resize((w, h), Image.Resampling.BOX).point(lambda a: 255 if a >= threshold else 0)
        # The sniper's thin source barrel must remain a connected native pixel.
        # BOX coverage retains these features; no generic erosion/dilation.
        mask = refine_native_mask(i, mask)
        x, y = i % 2 * 32, i // 2 * 12
        atlas.paste(mask, (x, y))
        records.append((x, y, w, h))
        references.append({"name": NAMES[i], "sequence": SEQUENCES[i], "threshold": threshold,
                           "source_crop": list(bounds), "size": [w, h]})
        icons.append((alpha, mask))
        mask.save(output / f"weapon-{i}.png")
    pixels = atlas.tobytes()
    packed = bytes((15 if pixels[i] else 0) << 4 | (15 if pixels[i + 1] else 0)
                   for i in range(0, len(pixels), 2))
    source = ['/* Locally derived Xbox messaging icons; do not redistribute. */',
              '#include "asset_prompt_icons.h"',
              'const uint8_t bg_prompt_icon_pixels[2048] __attribute__((aligned(16)))={']
    source += [','.join(map(str, packed[i:i+32])) + ',' for i in range(0, len(packed), 32)]
    source += ['};', 'const bg_prompt_icon bg_prompt_icons[9]={']
    source += ['{' + ','.join(map(str, r)) + '},' for r in records]
    source += ['};']
    target = output / "prompt_icons_data.c"
    target.write_text('\n'.join(source) + '\n')
    report = {"source_sha256": hashlib.sha256(cache.read_bytes()).hexdigest(), "tag": tag,
              "icons": references, "atlas_bytes": len(packed),
              "generated_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
              "inputs": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in (Path(__file__).resolve(), ROOT/'port/n64/asset_prompt_icons.h')}}
    (output / "icons-report.json").write_text(json.dumps(report, indent=2) + '\n')
    # Native masks are shown enlarged with nearest-neighbor only, next to source.
    gallery = Image.new("RGB", (760, 9 * 100), "#091923")
    draw = ImageDraw.Draw(gallery)
    for i, (reference, icon) in enumerate(icons):
        y = i * 100
        draw.text((12, y + 10), NAMES[i], fill="#64dcff")
        reference.thumbnail((240, 70), Image.Resampling.NEAREST)
        gallery.paste(Image.new("RGB", reference.size, "#75baff"), (190, y+20), reference)
        enlarged = icon.resize((icon.width*5, icon.height*5), Image.Resampling.NEAREST)
        gallery.paste(Image.new("RGB", enlarged.size, "#64dcff"), (500, y+20), enlarged)
    gallery.save(output / "silhouettes.png")
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'build/n64/generated/prompt-icons')
    print(bake(parser.parse_args().output))
