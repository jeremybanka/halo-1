#!/usr/bin/env python3
"""Pack original first-person poses with finer positional precision than terrain."""
import argparse,json
from pathlib import Path
from pack_assets import position
from pack_animation import emit_clip, clip_initializer
from model_colors import load_images, bake_triangle, bake_team_mask
from pack_mesh import indexed_mesh, emit_batches, trajectory_keys, remap_clip, MODEL_COLOR_TOLERANCE, model_color_tolerance

def prepare_model(w,name):
 """Share only corners with identical complete quantized animation paths."""
 images=load_images(w['textures']);positions=[];colors=[];team_mask=[];uvs=[]
 textured=name=='pistol' and any(t.get('magnum_textured') for t in w['triangles'])
 masks=load_images(w.get('material_multipurpose',[]))
 channels=[2 if source==3 else None for source in w.get('material_change_source',[])]
 for tri in w['triangles']:
  positions.extend([[round(v*256) for v in position(p,(0,0,0))] for p in tri['p']])
  colors.extend(bake_triangle(tri,images,w,firstperson=True))
  team_mask.extend(bake_team_mask(tri,masks,channels))
  uvs.extend([[round(u*64*32),round(v*32*32)] for u,v in tri['uv']] if textured and tri.get('magnum_textured') else [[16,1008]]*3)
 mesh=indexed_mesh(positions,colors,team_mask,trajectory_keys(w['clips'],256),
                   color_tolerance=model_color_tolerance('firstperson',name),
                   material_keys=[(t['material'],tuple(uvs[i*3+j]) if textured else ()) for i,t in enumerate(w['triangles']) for j in range(3)])
 mesh['uvs']=[uvs[i] if textured else [0,0] for i in mesh['sources']]
 clips={name:remap_clip(clip,mesh['sources']) for name,clip in w['clips'].items()}
 preview={'positions':[[v/256 for v in p] for p in positions],
          'colors':mesh['colors'],'triangle_count':len(w['triangles']),
          'team_mask':[m/255 for m in team_mask]}
 if textured:preview.update(uvs=uvs,texture=next(t['texture_path'] for t in w['triangles'] if t.get('magnum_textured')))
 return mesh,clips,preview

def split_details(w,name):
 """Split thin displays; plasma corners share their exact complete trajectories."""
 mats={i for i,n in enumerate(w['material_names']) if
       (name=='sniper' and n.endswith((' screen',' subscreen'))) or
       (name in ('plasma_pistol','plasma_rifle') and w['material_types'][i]=='shader_transparent_meter')}
 detail=[i for i,t in enumerate(w['triangles']) if t['material'] in mats]
 keep=[i for i in range(len(w['triangles'])) if i not in detail]
 body={**w,'triangles':[w['triangles'][i] for i in keep],
       'clips':{n:{**c,'frames':[[p for i in keep for p in f[i*3:i*3+3]] for f in c['frames']]} for n,c in w['clips'].items()}}
 sources=[];indices=[];lookup={}
 images=load_images(w['textures'])
 for i in detail:
  for j in range(3):
   corner=i*3+j
   key=tuple(x for c in w['clips'].values() for f in c['frames'] for x in f[corner])
   key=(w['triangles'][i]['material'],tuple(bake_triangle(w['triangles'][i],images,w,firstperson=True)[j]),key)
   if key not in lookup:lookup[key]=len(sources);sources.append(corner)
   indices.append(lookup[key])
 assert len(sources)<=12
 return body,keep,sources,indices

def pack(source,out,pc_extras=False):
 data=json.loads(source.read_text());out.mkdir(parents=True,exist_ok=True)
 lines=['/* Generated owned Xbox first-person assets; do not commit. */','#include "asset_firstperson.h"'];sizes={};total=0;animation_packing={};animation_bytes=0;previews={};meshes={}
 aliases={} if pc_extras else {'flamethrower':'ar'}
 packed={name:w for name,w in data['weapons'].items() if name not in aliases}
 def xyz(v):return '{'+','.join(map(str,v))+'}'
 def rgba(rgb):return (rgb[0]<<24)|(rgb[1]<<16)|(rgb[2]<<8)|255
 detail_report={};detail_defs={}
 from PIL import Image
 pistol=packed['pistol']
 atlas=Image.open(next(t['texture_path'] for t in pistol['triangles'] if t.get('magnum_textured'))).convert('RGB')
 assert atlas.size==(64,32) and all(atlas.getpixel((x,31))==(255,255,255) for x in range(64))
 texels=[((r>>3)<<11)|((g>>3)<<6)|((b>>3)<<1)|1 for r,g,b in atlas.getdata()]
 lines.append('const uint16_t bg_fp_pistol_texture[2048] __attribute__((aligned(8)))={'+','.join(f'0x{v:04x}' for v in texels)+'};')
 total+=4096
 for name in ('sniper','plasma_pistol','plasma_rifle'):
  w=packed[name];body,keep,sources,indices=split_details(w,name);packed[name]=body
  images=load_images(w['textures']);allcolors=[c for t in w['triangles'] for c in bake_triangle(t,images,w,firstperson=True)]
  colors=[allcolors[i] for i in sources];poses=[];offsets=[]
  for clip in w['clips'].values():
   offsets.append(len(poses))
   for frame in clip['frames']:
    points=[[round(v*4096) for v in position(frame[i],(0,0,0))] for i in sources]
    poses.append(points)
  assert all(-32768<=v<=32767 for f in poses for p in f for v in p)
  prefix='bg_scope' if name=='sniper' else 'bg_detail_'+name
  lines.append(f'const uint32_t {prefix}_colors[{len(colors)}]={{'+','.join(f'0x{rgba(c):08x}' for c in colors)+'};')
  lines.append(f'const uint16_t {prefix}_offsets[4]={{'+','.join(map(str,offsets))+'};')
  lines.append(f'const int16_t {prefix}_poses[][{len(sources)}][3]={{'+','.join('{'+','.join(xyz(p) for p in f)+'}' for f in poses)+'};')
  lines.append(f'static const uint8_t {prefix}_indices[]={{'+','.join(map(str,indices))+'};')
  detail_defs[name]='{'+f'{prefix}_poses[0],{prefix}_offsets,{prefix}_colors,{prefix}_indices,{len(sources)},{len(indices)//3}'+'}'
  size=len(poses)*len(sources)*6+len(colors)*4+8+len(indices);total+=size
  detail_report[name]={'triangles':len(indices)//3,'vertices':len(sources),'scale':4096,'bytes':size,'frames':len(poses)}
 lines.append('const bg_fp_detail_asset bg_fp_details[BG_FP_WEAPONS]={'+','.join(detail_defs.get(n,'{0}') for n in data['weapons'])+'};')
 for name,w in packed.items():
  mesh,clips,previews[name]=prepare_model(w,name);meshes[name]=mesh
  verts=mesh['vertices'];team_mask=[v[2] for v in verts]
  lines.append(f'static const uint8_t fp_{name}_team_mask[]={{'+','.join(map(str,team_mask))+'};')
  total+=len(team_mask)
  sizes[name]=len(verts)
  lines.append(f'static T3DVertPacked fp_{name}[] __attribute__((aligned(16)))={{')
  for i in range(0,len(verts),2):
   a,b=verts[i:i+2];lines.append('{'+f'{xyz(a[0])},0,{xyz(b[0])},0,0x{rgba(a[1]):08x},0x{rgba(b[1]):08x},{xyz(mesh["uvs"][i])},{xyz(mesh["uvs"][i+1])}'+'},')
  lines.append('};');total+=len(verts)*16
  emit_batches(lines,'fp_'+name,mesh);total+=len(mesh['indices'])*2+len(mesh['batches'])*8
  for clipname,clip in clips.items():
   packed_clip=emit_clip(lines,f'fp_{name}_{clipname}',clip,256)
   animation_packing[name,clipname]=packed_clip;total+=packed_clip['bytes'];animation_bytes+=packed_clip['bytes']
 lines.append(f'const unsigned bg_fp_max_vertices={max(sizes.values())};')
 lines.append('const uint8_t *const bg_fp_team_masks[BG_FP_WEAPONS]={'+','.join('fp_'+aliases.get(name,name)+'_team_mask' for name in data['weapons'])+'};')
 lines.append('const bg_model_asset bg_fp_models[BG_FP_WEAPONS]={')
 for name in data['weapons']:
  actual=aliases.get(name,name);mesh=meshes[actual]
  lines.append(f'{{fp_{actual},{sizes[actual]},1.0f,fp_{actual}_batches,fp_{actual}_indices,{len(mesh["batches"])},{len(packed[actual]["triangles"])}}},')
 lines.append('};\nconst bg_anim_asset bg_fp_animations[BG_FP_WEAPONS][BG_FP_CLIPS]={')
 for name in data['weapons']:
  actual=aliases.get(name,name);w=packed[actual]
  lines.append('{')
  for cname,a in w['clips'].items():lines.append(clip_initializer(f'fp_{actual}_{cname}',a,animation_packing[actual,cname]))
  lines.append('},')
 lines.append('};');(out/'firstperson_data.c').write_text('\n'.join(lines)+'\n')
 (out/'firstperson-preview.json').write_text(json.dumps(previews))
 report={'vertices':sizes,'triangle_corners':{n:len(w['triangles'])*3 for n,w in packed.items()},
         'triangles':{n:len(w['triangles']) for n,w in packed.items()},'batches':{n:len(m['batches']) for n,m in meshes.items()},
         'texture_bytes':4096,'vertex_bytes':sum(sizes.values())*16,'team_mask_bytes':sum(sizes.values()),
         'index_bytes':sum(len(m['indices'])*2 for m in meshes.values()),'batch_bytes':sum(len(m['batches'])*8 for m in meshes.values()),
         'color_weld_tolerance':MODEL_COLOR_TOLERANCE,'material_boundaries_preserved':True,'total_bytes':total,'position_scale':256,'animation_bytes':animation_bytes,'animation_uncompressed_bytes':sum(p['uncompressed_bytes'] for p in animation_packing.values()),'pc_extras':pc_extras,'aliases':aliases,
         'scope':detail_report['sniper'],'details':detail_report,
         'color_weld_tolerances':{name:model_color_tolerance('firstperson',name) for name in sizes},
         'clips':{n:{c:a['tag_name'] for c,a in w['clips'].items()} for n,w in packed.items()}}
 (out/'firstperson-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('source',type=Path,nargs='?',default=Path('build/n64/assets/firstperson-reduced.json'))
 p.add_argument('--output',type=Path,default=Path('build/n64/generated'))
 p.add_argument('--pc-extras',action='store_true',help='Include the optional PC flamethrower assets')
 a=p.parse_args();pack(a.source,a.output,a.pc_extras)
