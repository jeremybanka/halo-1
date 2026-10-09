#!/usr/bin/env python3
"""Bake the owned Xbox ground shader's diffuse colors into a small terrain map.

No artistic green multiplier: retain base alpha, source sand/grass blend,
filtered detail layers and the original two double-multiply stages. This is
an offline diffuse approximation; runtime shading remains separate.
"""
import contextlib,hashlib,json,math
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/n64/assets/ground'

def sample_repeat(image,uv):
    """Normalized bilinear texel-center sampling with wrap, like the source."""
    a=np.asarray(image.convert('RGB'),dtype=np.float64)/255
    h,w=a.shape[:2];p=uv*np.array([w,h])-.5;lo=np.floor(p).astype(np.int64);f=p-lo
    x,y=lo[...,0]%w,lo[...,1]%h;xx,yy=(x+1)%w,(y+1)%h
    return (a[y,x]*(1-f[...,0:1])+a[y,xx]*f[...,0:1])*(1-f[...,1:2])+(a[yy,x]*(1-f[...,0:1])+a[yy,xx]*f[...,0:1])*f[...,1:2]

def filtered_detail(image,scale,size):
    # A baked texel covers scale*source_size/size detail texels. Integrate the
    # detail footprint before sampling, rather than aliasing hundreds of blades.
    lod=max(0,math.log2(max(image.size)*scale/size));lo=math.floor(lod);frac=lod-lo
    yy,xx=np.mgrid[:size,:size];uv=(np.stack([xx,yy],axis=-1)+.5)/size*scale
    def level(n):
        dims=tuple(max(1,d>>n) for d in image.size)
        return sample_repeat(image.resize(dims,Image.Resampling.BOX),uv)
    return level(lo)*(1-frac)+level(lo+1)*frac

def compose(base,sand,grass,micro,scales):
    a=np.asarray(base.convert('RGBA'),dtype=np.float64)/255
    size=base.width;mask=a[...,3:4]
    detail=filtered_detail(sand,scales[0],size)*mask+filtered_detail(grass,scales[1],size)*(1-mask)
    color=np.clip(2*a[...,:3]*detail,0,1)
    return Image.fromarray(np.uint8(np.clip(2*color*filtered_detail(micro,scales[2],size),0,1)*255+.5))

def extract():
    from reclaimer.meta.wrappers.halo1_map import Halo1Map
    from reclaimer.bitmaps.bitmap_decompilation import extract_bitmaps
    OUT.mkdir(parents=True,exist_ok=True)
    cache=ROOT/'build/n64/assets/bloodgulch-decompressed.map'
    with (OUT/'extract.log').open('w') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
        h=Halo1Map();h.load_map(cache);es=h.tag_index.tag_index
        path='levels\\test\\bloodgulch\\shaders\\blood ground'
        ix=next(i for i,e in enumerate(es) if e.path==path)
        s=h.get_meta(ix).senv_attrs;d=s.diffuse
        assert s.environment_shader.type.enum_name=='blended'
        assert d.detail_map_function.enum_name==d.micro_detail_map_function.enum_name=='double_biased_multiply'
        refs=[d.base_map,d.primary_detail_map,d.secondary_detail_map,d.micro_detail_map]
        images=[]
        for n,ref in enumerate(refs):
            i=ref.id&65535;m=h.get_meta(i);h.meta_to_tag_data(m,'bitm',es[i])
            extract_bitmaps(m,f'source-{n}',out_dir=OUT,bitmap_ext='png',halo_map=h)
            images.append(Image.open(OUT/f'source-{n}.png').convert('RGBA'))
        scales=[d.primary_detail_map_scale,d.secondary_detail_map_scale,d.micro_detail_map_scale]
        baked=compose(*images,scales);baked.save(OUT/'blended-512.png')
        for size in (32,64,128):
            images[0].convert('RGB').resize((size,size),Image.Resampling.LANCZOS).save(OUT/f'base-{size}.png')
            baked.resize((size,size),Image.Resampling.LANCZOS).save(OUT/f'blended-{size}.png')
    report={'shader':path,'textures':[r.filepath for r in refs],'scales':scales,
            'description':'Source alpha blend and double multiply, detail mip footprint filtered at 512; diffuse only, no lightmap or display-gamma emulation.',
            'inputs':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__).resolve(),cache]},
            'files':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.glob('*.png')}}
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Baked original ground shader: 32, 64, 128 pixels; original grass/sand mask retained.')
if __name__=='__main__':extract()
