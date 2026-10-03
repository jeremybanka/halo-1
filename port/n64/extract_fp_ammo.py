#!/usr/bin/env python3
"""Extract owned Xbox AR digit shader and Needler ammunition-overlay metadata."""
import argparse
import contextlib
import json
from pathlib import Path


def extract(assets):
    from reclaimer.meta.wrappers.halo1_map import Halo1Map
    from reclaimer.animation.animation_decompilation import extract_animation
    from reclaimer.bitmaps.bitmap_decompilation import extract_bitmaps
    assets = Path(assets)
    with (assets / 'firstperson-ammo-extraction.log').open('w') as log, contextlib.redirect_stdout(log):
        h = Halo1Map(); h.load_map(assets / 'bloodgulch-decompressed.map')
        entries = h.tag_index.tag_index
        def tag(path, kind):
            i = next(i for i, t in enumerate(entries) if t.path == path and t.class_1.enum_name == kind)
            return i, h.get_meta(i)
        mi, model = tag(r'weapons\assault rifle\fp\fp', 'model')
        materials = []
        for index, material in enumerate(model.shaders.STEPTREE):
            entry = entries[material.shader.id & 65535]
            if entry.path != r'weapons\assault rifle\fp\shaders\numbers':
                continue
            shader = h.get_meta(material.shader.id).schi_attrs
            ref = shader.maps.STEPTREE[0].bitmap
            b = h.get_meta(ref.id); h.meta_to_tag_data(b, 'bitm', entries[ref.id & 65535])
            textures = assets / 'firstperson-ammo-textures'; textures.mkdir(exist_ok=True)
            extract_bitmaps(b, 'ar_digits', out_dir=textures, bitmap_ext='png', halo_map=h)
            frames = [str(p.resolve()) for p in sorted(textures.glob('ar_digits*.png'))]
            materials.append({'material': index, 'shader': entry.path,
                'permutation': int(material.permutation_index),
                'limit': int(shader.chicago_shader.numeric_counter_limit), 'textures': frames})
        if sorted(m['permutation'] for m in materials) != [0, 1] or any(m['limit'] != 60 or len(m['textures']) != 10 for m in materials):
            raise ValueError('Unexpected original AR numeric shader contract')
        ai, animations = tag(r'weapons\needler\fp\fp', 'model_animations')
        h.meta_to_tag_data(animations, 'antr', entries[ai])
        index = next(i for i, a in enumerate(animations.animations.STEPTREE) if a.name == 'first-person ammunition')
        source = animations.animations.STEPTREE[index]
        animation = extract_animation(index, animations, write_jma=False)
        # Reclaimer prefixes overlay exports with a synthetic default frame.
        # Xbox indexes the 21 real stored frames directly by rounds_loaded.
        frames = animation.frames[1:]
        if source.type.enum_name != 'overlay' or len(frames) != source.frame_count or len(frames) != 21:
            raise ValueError('Unexpected original Needler ammunition overlay')
        flags = {name: int(getattr(source, name + '_flags0')) | (int(getattr(source, name + '_flags1')) << 32)
                 for name in ('rot', 'trans', 'scale')}
        result = {'ar': {'tag': mi, 'materials': materials}, 'needler': {
            'tag': ai, 'animation_index': index, 'name': source.name,
            'flags': flags, 'frames': [[{'p': [n.pos_x / 100, n.pos_y / 100, n.pos_z / 100],
                'q': [n.rot_i, n.rot_j, n.rot_k, n.rot_w], 's': n.scale} for n in frame] for frame in frames]},
            'source_references': ['source/rasterizer/xbox/rasterizer_xbox_transparent_geometry.c:numeric counter',
                'source/items/weapons.c:primary_ammunition', 'source/interface/first_person_weapons.c:ammunition overlay',
                'source/models/model_animations.c:overlay_animation_apply']}
    (assets / 'firstperson-ammo.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Extracted AR limit 60 / two original decimal surfaces and 21 native Needler ammunition poses.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, default=Path('build/n64/assets'))
    extract(parser.parse_args().assets)
