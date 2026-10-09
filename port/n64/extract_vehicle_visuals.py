#!/usr/bin/env python3
"""Pack original damaged Covenant LODs and death-effect sprites from owned b40."""
import contextlib,hashlib,json
from pathlib import Path
from PIL import Image
from extract_extended import open_cache,tag_values
from model_colors import bake_triangle
from pack_assets import position
from pack_mesh import indexed_mesh,emit_batches
ROOT=Path(__file__).resolve().parents[2]
A=ROOT/'build/n64/assets';OUT=ROOT/'build/n64/generated'
def extract():
 directory=A/'vehicle-visuals';directory.mkdir(exist_ok=True)
 report={'models':{},'textures':[]};lines=['/* Generated owned vehicle assets; do not commit. */','#include "vehicle_visuals.h"']
 with (directory/'extract.log').open('w') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
  from reclaimer.meta.wrappers.halo1_map import Halo1Map
  from reclaimer.model.model_decompilation import extract_model
  from reclaimer.bitmaps.bitmap_decompilation import extract_bitmaps
  cache=A/'b40-decompressed.map'
  if cache.exists():h=Halo1Map();h.load_map(cache)
  else:h=open_cache(ROOT/'dist/halo-windows-release/maps/b40.map',A)
  entries=h.tag_index.tag_index
  def tag(path,kind):
   ix=next(i for i,e in enumerate(entries) if e.path==path and e.class_1.enum_name==kind)
   return ix,h.get_meta(ix)
  bitmaps={}
  def bitmap(ref):
   ix=ref.id&65535
   if ix not in bitmaps:
    m=h.get_meta(ix);h.meta_to_tag_data(m,'bitm',entries[ix]);prefix=f'bitmap-{ix}'
    extract_bitmaps(m,prefix,out_dir=directory,bitmap_ext='png',halo_map=h)
    bitmaps[ix]=(m,[Image.open(p).convert('RGBA') for p in sorted(directory.glob(prefix+'*.png'))])
   return bitmaps[ix]
  previews={};bounds={};initializers={}
  for name in ('ghost','banshee'):
   ix,m=tag(f'vehicles\\{name}\\{name}','model');h.meta_to_tag_data(m,'mode',entries[ix])
   for geometry in m.geometries.STEPTREE:
    for part in geometry.parts.STEPTREE:
     v=part.compressed_vertices.STEPTREE.data
     for off in range(0,len(v),32):
      if v[off+28]>=128 and v[off+29]<128:v[off+28],v[off+29]=v[off+29],v[off+28]
   source=next(l for l in extract_model(m,write_jms=False) if l.name=='~damaged low')
   images=[];paths=[]
   for s in m.shaders.STEPTREE:
    shader=h.get_meta(s.shader.id&65535);ref=shader.soso_attrs.maps.diffuse_map if hasattr(shader,'soso_attrs') else None
    images.append(bitmap(ref)[1][0] if ref and ref.id!=0xffffffff else None);paths.append(s.shader.filepath)
   pos=[];colors=[];materials=[]
   for t in source.tris:
    vertices=[source.verts[i] for i in (t.v0,t.v1,t.v2)]
    tri={'material':t.shader,'p':[[v.pos_x/100,v.pos_y/100,v.pos_z/100] for v in vertices],'uv':[[v.tex_u,1-v.tex_v] for v in vertices]}
    pos.extend([[round(x*1024) for x in position(p,(0,0,0))] for p in tri['p']]);colors.extend(bake_triangle(tri,images,{}));materials.extend([t.shader]*3)
   mesh=indexed_mesh(pos,colors,[0]*len(pos),None,None,reorder_static=True,color_tolerance=32,material_keys=materials)
   ident='wreck_'+name;verts=mesh['vertices'];xyz=lambda p:'{'+','.join(map(str,p))+'}';rgba=lambda c:(c[0]<<24)|(c[1]<<16)|(c[2]<<8)|255
   lines.append(f'static T3DVertPacked {ident}[] __attribute__((aligned(16)))={{')
   for a,b in zip(verts[::2],verts[1::2]):lines.append('{'+f'{xyz(a[0])},0,{xyz(b[0])},0,0x{rgba(a[1]):08x},0x{rgba(b[1]):08x},{{0,0}},{{0,0}}'+'},')
   lines.append('};');emit_batches(lines,ident,mesh)
   radius=max(sum(x*x for x in p)**.5/1024 for p in pos)
   initializers[name]='{'+f'{ident},{len(verts)},{radius:.7f}f,{ident}_batches,{ident}_indices,{len(mesh["batches"])},{len(source.tris)}'+'}'
   order=[3*t+k for t in mesh['triangle_order'] for k in range(3)]
   previews[name]={'positions':[[v/1024 for v in pos[i]] for i in order],'colors':[mesh['colors'][i] for i in order],'triangle_count':len(source.tris)}
   bounds[name]=[[min(p[a]/1024 for p in pos) for a in range(3)],[max(p[a]/1024 for p in pos) for a in range(3)]]
   report['models'][name]={'source':entries[ix].path,'permutation':source.name,'triangles':len(source.tris),'vertices':len(verts),'shaders':paths}
  lines.append('const bg_model_asset bg_covenant_wrecks[2]={'+','.join(initializers[n] for n in ('ghost','banshee'))+'};')
  lines.append('const bg_bounds bg_covenant_wreck_bounds[2]={'+','.join('{'+','.join('{'+','.join(f'{v:.7f}f' for v in row)+'}' for row in bounds[n])+'}' for n in ('ghost','banshee'))+'};')
  _,death=tag(r'vehicles\wraith\effects\death explosion','effect');report['death_effect']=tag_values(death)
  _,system=tag(r'effects\particle systems\explosion large','particle_system');report['explosion_system']=tag_values(system)
  # Original warm fire -> gray smoke plus burning flame, metal panels, sparks.
  paths=[(r'effects\particles\flash\bitmaps\fire cloud',True),(r'effects\particles\air\bitmaps\smoke cloud',False),(r'effects\particles\flash\bitmaps\burning flame',True)]
  for particle in (r'effects\particles\solid\panel debris',r'effects\particles\flash\sparks trail'):
   _,p=tag(particle,'particle');paths.append((p.bitmap.filepath,particle.endswith('sparks trail')))
  sprites=[]
  for path,additive in paths:
   ix,m=tag(path,'bitmap')
   class Ref: id=ix
   meta,images=bitmap(Ref);seq=meta.sequences.STEPTREE[0] if meta.sequences.size else None
   sprite=seq.sprites.STEPTREE[0] if seq and seq.sprites.size else None
   index=sprite.bitmap_index if sprite else seq.first_bitmap_index if seq else 0
   im=images[index].copy()
   if sprite:im=im.crop(tuple(round(v*(im.width if i%2==0 else im.height)) for i,v in enumerate((sprite.left_side,sprite.top_side,sprite.right_side,sprite.bottom_side))))
   im=im.resize((16,16),Image.Resampling.BOX)
   if additive:im.putdata([(round(r*255/peak),round(g*255/peak),round(b*255/peak),round(a*peak/255)) if (peak:=max(r,g,b)) else (0,0,0,0) for r,g,b,a in im.getdata()])
   im.save(directory/f'packed-{len(sprites)}.png');sprites.append(im);report['textures'].append({'path':path,'bitmap':index,'additive':additive})
  lines.append('const uint32_t bg_vehicle_fx_textures[5][256] __attribute__((aligned(8)))={')
  for im in sprites:lines.append('{'+','.join(f'0x{r:02x}{g:02x}{b:02x}{a:02x}' for r,g,b,a in im.getdata())+'},')
  lines.append('};')
 target=OUT/'vehicle_visuals_data.c';target.write_text('\n'.join(lines)+'\n')
 (OUT/'wreck-preview.json').write_text(json.dumps(previews))
 report['inputs']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),cache)}
 report['generated_sha256']=hashlib.sha256(target.read_bytes()).hexdigest()
 (OUT/'vehicle-visuals-report.json').write_text(json.dumps(report,indent=2)+'\n')
 print('Packed original damaged low LODs and five 16x16 death-effect sprites.')
if __name__=='__main__':extract()
