#!/usr/bin/env python3
"""Extract local Xbox Blood Gulch data. Requires Python 3.11 + reclaimer==2.11.2.

Outputs stay under build/: no game-derived geometry or textures are committed.
Coordinates in the interchange JSON retain Halo's right-handed Z-up basis.
"""
import argparse
import contextlib
import hashlib
import json
import math
import struct
import zlib
from pathlib import Path


def extract(map_path, output):
    from reclaimer.meta.wrappers.halo1_map import Halo1Map
    from reclaimer.bitmaps.bitmap_decompilation import extract_bitmaps
    from reclaimer.model.model_decompilation import extract_model
    from PIL import Image

    output.mkdir(parents=True, exist_ok=True)
    data = map_path.read_bytes()
    if data[:4] != b'daeh' or struct.unpack_from('<I', data, 4)[0] != 5:
        raise ValueError('Expected an original Xbox Halo cache (version 5)')
    expected = struct.unpack_from('<I', data, 8)[0]
    if len(data) < expected:
        data = data[:2048] + zlib.decompress(data[2048:])
    if len(data) != expected:
        raise ValueError('Decompressed map length disagrees with the header')
    raw_path = output / 'bloodgulch-decompressed.map'
    raw_path.write_bytes(data)
    # Reclaimer's optional GUI definition cache is noisy on recent supyr-struct.
    # Retain its diagnostics, and validate every geometry/index below separately.
    with (output / 'reclaimer.log').open('w') as log, contextlib.redirect_stdout(log):
        halo = Halo1Map()
        halo.load_map(raw_path)
        entries = halo.tag_index.tag_index
        bsps = [i for i, tag in enumerate(entries) if tag.class_1.enum_name == 'scenario_structure_bsp']
        if len(bsps) != 1 or 'bloodgulch' not in entries[bsps[0]].path:
            raise ValueError('This proof of concept requires the Blood Gulch BSP')
        bsp = halo.get_meta(bsps[0])
        triangles = list(struct.iter_unpack('<3H', bsp.surface.STEPTREE))
        materials, groups = [], []
        texture_dir = output / 'textures'
        texture_dir.mkdir(exist_ok=True)
        shader_ids = {}
        for lightmap in bsp.lightmaps.STEPTREE:
            for material in lightmap.materials.STEPTREE:
                shader_id = material.shader.id
                if shader_id not in shader_ids:
                    index = len(materials)
                    shader_ids[shader_id] = index
                    entry = {'name': material.shader.filepath, 'texture': None}
                    shader = halo.get_meta(shader_id)
                    if hasattr(shader, 'senv_attrs'):
                        ref = shader.senv_attrs.diffuse.base_map
                        if ref.id != 0xffffffff:
                            bitmap = halo.get_meta(ref.id)
                            # Raw cache offsets are absolute file addresses. The
                            # bitmap exporter expects offsets into the injected
                            # pixel buffer and corrected Xbox mip counts.
                            halo.meta_to_tag_data(bitmap, 'bitm', entries[ref.id & 0xffff])
                            extract_bitmaps(bitmap, f'material_{index:02d}', out_dir=texture_dir,
                                            bitmap_ext='png', halo_map=halo)
                            png = texture_dir / f'material_{index:02d}.png'
                            if not png.is_file():
                                raise ValueError(f'Could not extract {ref.filepath}')
                            image = Image.open(png).convert('RGB')
                            if max(image.getextrema()[channel][1] for channel in range(3)) == 0:
                                raise ValueError(f'Bitmap decoded as entirely black: {ref.filepath}')
                            image.resize((32, 32), Image.Resampling.LANCZOS).save(png)
                            entry['texture'] = str(png.resolve())
                            entry['bitmap'] = ref.filepath
                    materials.append(entry)
                raw = material.compressed_vertices.STEPTREE
                count = material.vertices_count
                if len(raw) < count * 32:
                    raise ValueError('Truncated BSP vertex data')
                verts = [struct.unpack_from('<3f', raw, i*32) for i in range(count)]
                uv = [struct.unpack_from('<2f', raw, i*32+24) for i in range(count)]
                faces = triangles[material.surfaces:material.surfaces+material.surface_count]
                if any(index >= count for tri in faces for index in tri):
                    raise ValueError('BSP triangle index out of bounds')
                if not all(math.isfinite(v) for p in verts for v in p):
                    raise ValueError('Nonfinite BSP position')
                groups.append({'material': shader_ids[shader_id], 'vertices': verts, 'uv': uv, 'faces': faces})
        spawns = [{'position': list(s.position), 'yaw': s.facing, 'team': s.team_index}
                  for s in halo.scnr_meta.player_starting_locations.STEPTREE]
        flags = [{'position': list(s.position), 'yaw': s.facing, 'team': s.team_index,
                  'type': s.type.enum_name} for s in halo.scnr_meta.netgame_flags.STEPTREE]
        models = {}
        for name, tag_path in [('spartan', r'characters\cyborg\cyborg'),
                               ('rifle', r'weapons\assault rifle\assault rifle')]:
            tag_id = next(i for i,t in enumerate(entries) if t.class_1.enum_name == 'model' and t.path == tag_path)
            meta = halo.get_meta(tag_id)
            halo.meta_to_tag_data(meta, 'mode', entries[tag_id])
            lods = extract_model(meta, write_jms=False)
            model = min(lods, key=lambda m: len(m.tris))
            models[name] = {'name': model.name,
                'vertices': [[v.pos_x/100, v.pos_y/100, v.pos_z/100] for v in model.verts],
                'faces': [[t.v0,t.v1,t.v2] for t in model.tris],
                'materials': [t.shader for t in model.tris]}
    result = {'source_sha256': hashlib.sha256(map_path.read_bytes()).hexdigest(),
              'bsp_triangles': len(triangles), 'materials': materials, 'groups': groups,
              'spawns': spawns, 'flags': flags, 'models': models}
    (output / 'bloodgulch-raw.json').write_text(json.dumps(result))
    print(json.dumps({'triangles':len(triangles), 'materials':len(materials),
        'spawns':len(spawns), 'models':{k:len(v['faces']) for k,v in models.items()}}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('map', type=Path)
    parser.add_argument('--output', type=Path, default=Path('build/n64/assets'))
    args = parser.parse_args()
    extract(args.map, args.output)
