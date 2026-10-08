#!/usr/bin/env python3
"""Extract the owned Xbox base-light and moss overlay maps (private bank only)."""
import contextlib
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
NAMES=('cap_moss01b','bloodgulch light red','bloodgulch light blue')

def extract():
    from PIL import Image
    from reclaimer.meta.wrappers.halo1_map import Halo1Map
    from reclaimer.bitmaps.bitmap_decompilation import extract_bitmaps
    cache=ROOT/'build/n64/assets/bloodgulch-decompressed.map'
    out=ROOT/'build/n64/assets/environment-overlays';out.mkdir(exist_ok=True)
    materials={}
    with (out/'extract.log').open('w') as log,contextlib.redirect_stdout(log):
        halo=Halo1Map();halo.load_map(cache);entries=halo.tag_index.tag_index
        for name in NAMES:
            i=next(i for i,e in enumerate(entries) if e.path.endswith('\\'+name)
                   and e.class_1.enum_name=='shader_transparent_generic')
            shader=halo.get_meta(i).sotr_attrs
            assert shader.generic_transparent_shader.framebuffer_blend_function.enum_name=='add'
            assert len(shader.maps.STEPTREE)==1
            mapping=shader.maps.STEPTREE[0]
            assert mapping.map_u_scale==mapping.map_v_scale==1
            assert mapping.map_u_offset==mapping.map_v_offset==mapping.map_rotation==0
            ref=mapping.bitmap;bitmap=halo.get_meta(ref.id)
            halo.meta_to_tag_data(bitmap,'bitm',entries[ref.id&65535])
            extract_bitmaps(bitmap,name,out_dir=out,bitmap_ext='png',halo_map=halo)
            source=out/(name+'.png')
            small=Image.open(source).convert('RGB').resize((32,32),Image.Resampling.BOX)
            # An inexpensive RGBA16 cutout approximates the additive artwork.
            # Black contributes nothing in the source shader; it is never an
            # opaque backing triangle. Bilinear filtering softens mask edges.
            small.putalpha(Image.eval(small.convert('HSV').getchannel('V'),lambda x:255 if x>=24 else 0))
            texture=out/(name+'-32.png');small.save(texture)
            materials[entries[i].path]={'texture':str(texture.relative_to(ROOT)),
                'bitmap':ref.filepath,'blend':'add','decal':bool(shader.generic_transparent_shader.flags.decal)}
    files=[p for p in out.glob('*.png')]
    report={'materials':materials,'approximation':'32x32 RGBA16 masked emissive overlays, black transparent',
        'inputs':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__).resolve(),cache]},
        'files':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Extracted three original Xbox environment overlays.')

if __name__=='__main__':extract()
