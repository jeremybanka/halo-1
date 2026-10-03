#!/usr/bin/env python3
"""Extract original first-person weapons, hands and animation from local Blood Gulch."""
import contextlib,json
from pathlib import Path
from extract_extended import MODEL_PATHS

def extract(output):
 from reclaimer.meta.wrappers.halo1_map import Halo1Map
 from reclaimer.model.model_decompilation import extract_model
 from reclaimer.animation.animation_decompilation import extract_animation
 from reclaimer.bitmaps.bitmap_decompilation import extract_bitmaps
 from PIL import Image
 names=list(MODEL_PATHS)[:8]+['flamethrower'];result={'weapons':{}}
 with (output/'firstperson-extraction.log').open('w') as log,contextlib.redirect_stdout(log):
  h=Halo1Map();h.load_map(output/'bloodgulch-decompressed.map');entries=h.tag_index.tag_index
  textures=output/'firstperson-textures';textures.mkdir(exist_ok=True)
  def model(path,name):
   ix=next(i for i,t in enumerate(entries) if t.class_1.enum_name=='model' and t.path==path)
   m=h.get_meta(ix);h.meta_to_tag_data(m,'mode',entries[ix])
   for g in m.geometries.STEPTREE:
    for p in g.parts.STEPTREE:
     v=p.compressed_vertices.STEPTREE.data
     for off in range(0,len(v),32):
      if v[off+28]>=128 and v[off+29]<128:v[off+28],v[off+29]=v[off+29],v[off+28]
   a=min(extract_model(m,write_jms=False),key=lambda x:len(x.tris));tex=[]
   for si,s in enumerate(m.shaders.STEPTREE):
    shader=h.get_meta(s.shader.id);p=None
    if hasattr(shader,'soso_attrs'):
     ref=shader.soso_attrs.maps.diffuse_map
     if ref.id!=0xffffffff:
      b=h.get_meta(ref.id);h.meta_to_tag_data(b,'bitm',entries[ref.id&65535]);bn=name+'_'+str(si)
      extract_bitmaps(b,bn,out_dir=textures,bitmap_ext='png',halo_map=h)
      paths=sorted(textures.glob(bn+'*.png'))
      if paths:
       p=str(paths[0].resolve());im=Image.open(p).convert('RGB');im.thumbnail((64,64));im.save(p)
    tex.append(p)
   return {'vertices':[[v.pos_x/100,v.pos_y/100,v.pos_z/100] for v in a.verts],
    'uv':[[v.tex_u,1-v.tex_v] for v in a.verts],'weights':[[v.node_0,v.node_1,v.node_1_weight] for v in a.verts],
    'faces':[[t.v0,t.v1,t.v2] for t in a.tris],'materials':[t.shader for t in a.tris],
    'textures':tex,'nodes':[{'name':n.name,'parent':n.parent_index,'q':[n.rot_i,n.rot_j,n.rot_k,n.rot_w],
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
 (output/'firstperson-raw.json').write_text(json.dumps(result))
 print(json.dumps({k:{'triangles':len(v['gun']['faces']),'clips':{n:a['name'] for n,a in v['clips'].items()}} for k,v in result['weapons'].items()},indent=2))
if __name__=='__main__':extract(Path('build/n64/assets'))
