"""Source material approximations for new maps; legacy banks are untouched."""
import contextlib,io,math
from pathlib import Path
import numpy as np
from PIL import Image
from extract_ground import compose

class Materials:
    def __init__(self,halo,directory):
        self.halo=halo;self.entries=halo.tag_index.tag_index;self.directory=directory
        directory.mkdir(parents=True,exist_ok=True)
        self.ids={};self.images=[];self.flags=[];self.records=[];self.palette=bytes(32)
        self.sizes=[];self.ci4=[];self.tiles=[];self.bitmaps={}
    def bitmap(self,ref):
        from reclaimer.bitmaps.bitmap_decompilation import extract_bitmaps
        if ref.id==0xffffffff:return None
        index=ref.id&65535
        if index not in self.bitmaps:
            name='bitmap-'+str(index);meta=self.halo.get_meta(index)
            self.halo.meta_to_tag_data(meta,'bitm',self.entries[index])
            with contextlib.redirect_stdout(io.StringIO()):
                extract_bitmaps(meta,name,out_dir=self.directory,bitmap_ext='png',halo_map=self.halo)
            files=sorted(self.directory.glob(name+'*.png'),key=lambda p:int(p.stem.split('__')[-1]) if '__' in p.stem else 0)
            self.bitmaps[index]=Image.open(files[0]).convert('RGBA')
        return self.bitmaps[index].copy()
    def add(self,path):
        if path in self.ids:return self.ids[path]
        index=next(i for i,e in enumerate(self.entries) if e.path==path)
        shader=self.halo.get_meta(index);kind=self.entries[index].class_1.enum_name
        flags=0;size=32;image=None;ground=False;note='Filtered original diffuse bitmap'
        if hasattr(shader,'senv_attrs'):
            attrs=shader.senv_attrs;diffuse=attrs.diffuse;image=self.bitmap(diffuse.base_map)
            if attrs.environment_shader.flags.alpha_tested:flags|=2
            if attrs.environment_shader.type.enum_name=='blended' and diffuse.secondary_detail_map.id!=0xffffffff:
                maps=[image,*[self.bitmap(ref) for ref in (diffuse.primary_detail_map,diffuse.secondary_detail_map,diffuse.micro_detail_map)]]
                assert all(m is not None for m in maps)
                maps[0]=maps[0].resize((512,512),Image.Resampling.BOX)
                scales=[diffuse.primary_detail_map_scale,diffuse.secondary_detail_map_scale,diffuse.micro_detail_map_scale]
                image=compose(*maps,scales).convert('RGBA');ground=True;size=64
                note='Source alpha grass/sand mask and double-multiply detail bake; 64px CI4'
        elif hasattr(shader,'soso_attrs'):
            attrs=shader.soso_attrs;image=self.bitmap(attrs.maps.diffuse_map)
            f=attrs.model_shader.flags;flags=(0 if f.not_alpha_tested else 2)|(4 if f.two_sided else 0)
        elif hasattr(shader,'sotr_attrs') or hasattr(shader,'schi_attrs'):
            attrs=shader.sotr_attrs if hasattr(shader,'sotr_attrs') else shader.schi_attrs
            image=self.bitmap(attrs.maps.STEPTREE[0].bitmap);flags=1
            f=attrs.generic_transparent_shader.flags if hasattr(attrs,"generic_transparent_shader") else attrs.chicago_shader.chicago_shader_flags
            if f.two_sided:flags|=4
            tint=tuple(shader.shdr_attrs.radiosity_light_color)
            if max(tint)>0 and image is not None:
                image.putdata([(round(r*tint[0]),round(g*tint[1]),round(b*tint[2]),a) for r,g,b,a in image.getdata()])
            note='Original emissive texture/tint, static alpha-tested approximation'
        elif hasattr(shader,'sgla_attrs'):
            attrs=shader.sgla_attrs;image=self.bitmap(attrs.diffuse_properties.map);flags=1
            note='Original glass diffuse with pixel coverage approximation; no cubemap reflection'
        elif hasattr(shader,'swat_attrs'):
            attrs=shader.swat_attrs.water_shader;image=self.bitmap(attrs.base_map);flags=1
            tint=tuple(attrs.perpendicular_tint_color)
            if image is not None:
                image.putdata([(round(r*tint[0]),round(g*tint[1]),round(b*tint[2]),a) for r,g,b,a in image.getdata()])
            note='Original water flow map and reflection tint; static pixel coverage approximation'
        else:raise ValueError('Unsupported map shader '+kind+' '+path)
        if image is None:
            color=tuple(round(c*255) for c in shader.shdr_attrs.radiosity_light_color)
            image=Image.new('RGBA',(size,size),(*color,255))
        image=image.resize((size,size),Image.Resampling.BOX)
        if hasattr(shader,'sgla_attrs') or hasattr(shader,'swat_attrs'):
            pixels=list(image.getdata());image.putdata([(r,g,b,255 if (i%size+i//size)%2==0 else 0) for i,(r,g,b,a) in enumerate(pixels)])
        elif flags&1:
            image.putdata([(r,g,b,255 if max(r,g,b)>=24 else 0) for r,g,b,a in image.getdata()])
        if ground:
            assert self.palette==bytes(32),'Only one CI4 ground palette per map'
            quant=image.convert('RGB').quantize(colors=16,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
            pal=quant.getpalette();colors=[((pal[i*3]>>3)<<11)|((pal[i*3+1]>>3)<<6)|((pal[i*3+2]>>3)<<1)|1 for i in range(16)]
            import struct
            self.palette=struct.pack('>16H',*colors)
            indices=list(quant.getdata());tile=bytes((a<<4)|b for a,b in zip(indices[::2],indices[1::2]));image=quant.convert('RGBA')
        else:
            import struct
            tile=struct.pack('>1024H',*[((r>>3)<<11)|((g>>3)<<6)|((b>>3)<<1)|int(a>=128) for r,g,b,a in image.getdata()])
        assert len(tile)==2048
        ident=len(self.images);self.ids[path]=ident;self.images.append(image);self.flags.append(flags)
        self.sizes.append(size);self.ci4.append(int(ground));self.tiles.append(tile)
        image.save(self.directory/f'packed-{ident}.png')
        self.records.append({'path':path,'source_kind':kind,'flags':flags,'size':size,'ci4':ground,'approximation':note})
        return ident
