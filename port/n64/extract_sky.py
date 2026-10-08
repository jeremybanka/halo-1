#!/usr/bin/env python3
"""Reduce the owned Xbox Blood Gulch sky's base color to an elevation ramp.

Raycast the original dome and interpolate its UVs before sampling; averaging
azimuth removes texture detail without inventing a hue/saturation multiplier.
"""
import contextlib
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'build/n64/assets/sky'
GENERATED = ROOT/'build/n64/generated'


def extract():
    from reclaimer.meta.wrappers.halo1_map import Halo1Map
    from reclaimer.model.model_decompilation import extract_model
    from reclaimer.bitmaps.bitmap_decompilation import extract_bitmaps
    OUT.mkdir(parents=True, exist_ok=True)
    cache = ROOT/'build/n64/assets/bloodgulch-decompressed.map'
    with (OUT/'extract.log').open('w') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        h = Halo1Map(); h.load_map(cache); entries = h.tag_index.tag_index
        paths = {e.path: i for i, e in enumerate(entries)}
        model_path = 'sky\\mp clear afternoon\\mp clear afternoon'
        shader_path = 'sky\\clear afternoon\\shaders\\sky clear blue'
        shader = h.get_meta(paths[shader_path])
        base = shader.schi_attrs.maps.STEPTREE[-1]
        assert base.color_function.enum_name == 'current'
        assert base.map_u_scale == base.map_v_scale == 1
        bitmap = h.get_meta(base.bitmap.id & 65535)
        h.meta_to_tag_data(bitmap, 'bitm', entries[base.bitmap.id & 65535])
        extract_bitmaps(bitmap, 'source', out_dir=OUT, bitmap_ext='png', halo_map=h)
        meta = h.get_meta(paths[model_path])
        h.meta_to_tag_data(meta, 'mode', entries[paths[model_path]])
        model = max((m for m in extract_model(meta, write_jms=False) if m.tris), key=lambda m: len(m.tris))
        material = next(i for i, s in enumerate(meta.shaders.STEPTREE) if s.shader.filepath == shader_path)
    pos = np.array([[v.pos_x, v.pos_y, v.pos_z] for v in model.verts]) / 1e6
    uv = np.array([[v.tex_u, 1-v.tex_v] for v in model.verts])
    ids = np.array([[t.v0, t.v1, t.v2] for t in model.tris if t.shader == material])
    a, b, c = (pos[ids[:, j]] for j in range(3))
    e1, e2 = b-a, c-a
    pixels = np.asarray(Image.open(OUT/'source.png').convert('RGB'), dtype=float)
    ramp = []
    for elevation in np.linspace(0, 1, 33):
        colors = []
        for azimuth in np.linspace(0, 2*np.pi, 96, endpoint=False):
            z = max(elevation, 1e-5)
            d = np.array([np.sqrt(1-z*z)*np.cos(azimuth), np.sqrt(1-z*z)*np.sin(azimuth), z])
            cross = np.cross(d, e2); det = np.sum(e1*cross, axis=1)
            inv = np.divide(1, det, out=np.zeros_like(det), where=abs(det)>1e-9)
            u = np.sum(-a*cross, axis=1)*inv
            q = np.cross(-a, e1); v = np.sum(d*q, axis=1)*inv
            t = np.sum(e2*q, axis=1)*inv
            hits = np.flatnonzero((abs(det)>1e-9)&(u>=-1e-6)&(v>=-1e-6)&(u+v<=1+1e-6)&(t>0))
            assert len(hits), (elevation, azimuth)
            j = hits[np.argmin(t[hits])]
            tex = uv[ids[j, 0]]*(1-u[j]-v[j])+uv[ids[j, 1]]*u[j]+uv[ids[j, 2]]*v[j]
            xy = np.clip(tex*np.array([pixels.shape[1], pixels.shape[0]])-.5, 0, 254.999)
            x, y = np.floor(xy).astype(int); fx, fy = xy-[x, y]
            colors.append((pixels[y,x]*(1-fx)+pixels[y,x+1]*fx)*(1-fy)+(pixels[y+1,x]*(1-fx)+pixels[y+1,x+1]*fx)*fy)
        ramp.append(np.rint(np.mean(colors, axis=0)).astype(int).tolist())
    output = GENERATED/'sky_data.c'
    output.write_text('/* Generated from the locally owned Xbox sky; do not commit. */\n#include <stdint.h>\nconst uint8_t bg_sky_rgb[33][3]={\n'+''.join('    {'+','.join(map(str,c))+'},\n' for c in ramp)+'};\n')
    preview = np.array(ramp, dtype=np.uint8)[::-1, None, :].repeat(192, axis=1)
    Image.fromarray(preview).resize((192,528), Image.Resampling.NEAREST).save(OUT/'ramp.png')
    report = {'model': model_path, 'shader': shader_path, 'bitmap': base.bitmap.filepath,
              'description': 'Original dome UV raycast, bilinear base RGB, 96-azimuth mean at 33 uniformly spaced sin(elevation) samples; no cloud/star/ring/planet layers or Xbox display gamma.',
              'rgb': ramp, 'inputs': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__).resolve(), cache]},
              'generated_sha256': hashlib.sha256(output.read_bytes()).hexdigest()}
    (GENERATED/'sky-report.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Sky ramp: horizon', ramp[0], '30 degrees', ramp[16], 'zenith', ramp[-1])


if __name__ == '__main__':
    extract()
