#!/usr/bin/env python3
"""Extract original first-person weapons, hands and animation from local Blood Gulch."""
import argparse,contextlib,json
from pathlib import Path
from extract_extended import MODEL_PATHS

def extract(output,reference_output=None):
 from reclaimer.meta.wrappers.halo1_map import Halo1Map
 from reclaimer.model.model_decompilation import extract_model
 from reclaimer.animation.animation_decompilation import extract_animation
 from reclaimer.bitmaps.bitmap_decompilation import extract_bitmaps
 output=Path(output);output.mkdir(parents=True,exist_ok=True)
 names=list(MODEL_PATHS)[:8]+['flamethrower'];result={'weapons':{},'reference_note':'Highest source LOD and full-resolution diffuse bitmaps. Multipass glass/meters use separately identified native-color approximations, not recreated Xbox shaders.'}
 with (output/'firstperson-extraction.log').open('w') as log,contextlib.redirect_stdout(log):
  h=Halo1Map();h.load_map(output/'bloodgulch-decompressed.map');entries=h.tag_index.tag_index
  textures=output/'firstperson-textures-reference';textures.mkdir(exist_ok=True)
  def rgb(color):return [round(max(0,min(1,float(getattr(color,c))))*255) for c in ('r','g','b')]
  def bitmap(ref,name):
   if ref is None or ref.id==0xffffffff:return None
   b=h.get_meta(ref.id);h.meta_to_tag_data(b,'bitm',entries[ref.id&65535])
   extract_bitmaps(b,name,out_dir=textures,bitmap_ext='png',halo_map=h)
   paths=sorted(textures.glob(name+'*.png'))
   return str(paths[0].resolve()) if paths else None
  def model(path,name):
   ix=next(i for i,t in enumerate(entries) if t.class_1.enum_name=='model' and t.path==path)
   m=h.get_meta(ix);h.meta_to_tag_data(m,'mode',entries[ix])
   for g in m.geometries.STEPTREE:
    for p in g.parts.STEPTREE:
     v=p.compressed_vertices.STEPTREE.data
     for off in range(0,len(v),32):
      if v[off+28]>=128 and v[off+29]<128:v[off+28],v[off+29]=v[off+29],v[off+28]
   candidates=extract_model(m,write_jms=False)
   # Prefer explicit source superhigh, never choose a lower LOD by triangle count.
   highest=[a for a in candidates if a.name.endswith(' superhigh')]
   a=max(highest or candidates,key=lambda a:len(a.tris))
   tex=[];material_names=[];material_types=[];material_colors=[];overrides=[];texture_sources=[]
   multipurpose=[];change_source=[]
   for si,s in enumerate(m.shaders.STEPTREE):
    shader=h.get_meta(s.shader.id);entry=entries[s.shader.id&65535];ref=None;color=None;override=None;multi=None;change=0
    material_names.append(entry.path);material_types.append(entry.class_1.enum_name)
    if hasattr(shader,'soso_attrs'):
     ref=shader.soso_attrs.maps.diffuse_map
     change=int(shader.soso_attrs.color_change_source.data)
     if change:multi=bitmap(shader.soso_attrs.maps.multipurpose_map,name+'_'+str(si)+'_multipurpose')
    elif hasattr(shader,'schi_attrs') and shader.schi_attrs.maps.STEPTREE:
     ref=shader.schi_attrs.maps.STEPTREE[0].bitmap
    elif hasattr(shader,'sotr_attrs') and shader.sotr_attrs.maps.STEPTREE:
     ref=shader.sotr_attrs.maps.STEPTREE[0].bitmap
    elif hasattr(shader,'sgla_attrs'):
     # The outer Needler crystal has no diffuse map: its color is a glass
     # reflection tint. Record this as an explicit flat approximation.
     color=rgb(shader.sgla_attrs.reflection_properties.perpendicular_tint_color)
     override=color
    elif hasattr(shader,'smet_attrs'):
     color=rgb(shader.smet_attrs.colors.gadient_min);override=color
    p=bitmap(ref,name+'_'+str(si))
    tex.append(p);texture_sources.append(ref.filepath if ref is not None else None)
    material_colors.append(color);overrides.append(override);multipurpose.append(multi);change_source.append(change)
   return {'vertices':[[v.pos_x/100,v.pos_y/100,v.pos_z/100] for v in a.verts],
    'uv':[[v.tex_u,1-v.tex_v] for v in a.verts],'weights':[[v.node_0,v.node_1,v.node_1_weight] for v in a.verts],
    'faces':[[t.v0,t.v1,t.v2] for t in a.tris],'materials':[t.shader for t in a.tris],
    'textures':tex,'textures_fullres':tex,'material_names':material_names,
    'material_types':material_types,'material_colors':material_colors,'material_overrides':overrides,
    'texture_sources':texture_sources,'material_multipurpose':multipurpose,'material_change_source':change_source,
    'source_lod':a.name,'source_triangle_count':len(a.tris),
    'available_lods':[{'name':v.name,'triangles':len(v.tris)} for v in candidates],
    'source_tag':path,'nodes':[{'name':n.name,'parent':n.parent_index,'q':[n.rot_i,n.rot_j,n.rot_k,n.rot_w],
    'p':[n.pos_x/100,n.pos_y/100,n.pos_z/100]} for n in a.nodes]}
  result['hands']=model(r'characters\cyborg\fp\fp','hands')
  for name in names:
   path=MODEL_PATHS[name].rsplit('\\',1)[0]+r'\fp\fp';gun=model(path,name)
   ix=next(i for i,t in enumerate(entries) if t.class_1.enum_name=='model_animations' and t.path==path)
   m=h.get_meta(ix);h.meta_to_tag_data(m,'antr',entries[ix]);clips={}
   patterns={'idle':['first-person idle'],'fire':['first-person firing','first-person fire-1'],
     'reload':['first-person reload-full','first-person reload-empty','first-person overheat','first-person reload'],
     'melee':['first-person melee']}
   for cname,candidates in patterns.items():
    chosen=None
    for candidate in candidates:
     chosen=next((i for i,a in enumerate(m.animations.STEPTREE) if a.name==candidate),None)
     if chosen is not None:break
    if chosen is None:chosen=next((i for i,a in enumerate(m.animations.STEPTREE) if any(c in a.name for c in candidates)),None)
    if chosen is None:
     chosen=next(i for i,a in enumerate(m.animations.STEPTREE) if a.name=='first-person idle')
    a=extract_animation(chosen,m,write_jma=False)
    clips[cname]={'name':a.name,'duration':a.frame_count/30,
     'frames':[[{'p':[n.pos_x/100,n.pos_y/100,n.pos_z/100],'q':[n.rot_i,n.rot_j,n.rot_k,n.rot_w]} for n in f] for f in a.frames]}
   result['weapons'][name]={'gun':gun,'nodes':[{'name':n.name,'parent':n.parent_node_index} for n in m.nodes.STEPTREE],'clips':clips}
 raw=json.dumps(result)
 (output/'firstperson-raw.json').write_text(raw)
 if reference_output is not None:
  reference_output=Path(reference_output);reference_output.parent.mkdir(parents=True,exist_ok=True)
  reference_output.write_text(raw)
 print(json.dumps({k:{'triangles':len(v['gun']['faces']),'clips':{n:a['name'] for n,a in v['clips'].items()}} for k,v in result['weapons'].items()},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=Path('build/n64/assets'))
 p.add_argument('--reference-output',type=Path,help='Also save an unreduced reference JSON; textures remain full-resolution')
 a=p.parse_args();extract(a.output,a.reference_output)
