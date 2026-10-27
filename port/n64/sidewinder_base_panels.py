"""Authored west-base detail replacement: six recessed lights to baked panels.

Only the selected six assemblies change. Their original rectangular ceiling
rim coordinates define the new panels. Main architecture is copied exactly;
source frames and light patterns are baked into three full-resolution tiles.
Four lower lights share one source pattern, with individual color modulation.
"""
import collections
import csv
import json
import math
from pathlib import Path
import re
import struct
import sys
import numpy as np
from sidewinder_structures import ROOT,PREVIOUS,sha

OUT=ROOT/'build/n64-sidewinder-west-base'
FIXTURES=[
    dict(name='Lower rear left',bounds=[-8431,-8259,10647,10913,-635,-615],tile=[0,0,8,16]),
    dict(name='Lower rear right',bounds=[-8148,-7980,10647,10913,-635,-615],tile=[8,0,8,16]),
    dict(name='Lower front left',bounds=[-8431,-8261,8332,8599,-635,-615],tile=[16,0,8,16]),
    dict(name='Lower front right',bounds=[-8150,-7980,8332,8599,-635,-615],tile=[24,0,8,16]),
    dict(name='Upper front',bounds=[-8461,-7949,8599,8906,491,512],tile=[0,16,24,12]),
    dict(name='Upper rear',bounds=[-8333,-8084,9634,9798,491,512],tile=[24,16,8,16]),
]


def prepare():
    from PIL import Image
    from photo_sidewinder_structures import load_bank,render
    OUT.mkdir(exist_ok=True);raw=(ROOT/'build/n64-sidewinder-structures/source.json').read_bytes();source=json.loads(raw)
    assert sha((PREVIOUS/'candidate-maps/sidewinder.map64').read_bytes())==source['bank_sha256']
    (OUT/'source.json').write_bytes(raw);bank=load_bank(PREVIOUS/'candidate-maps/sidewinder.map64');owners=bank[2]
    source_by_owner=collections.defaultdict(list)
    for i,r in enumerate(source['triangles']):source_by_owner[r['batch']].append((i,r))
    # The bank decoder and source census enumerate faces in the same order.
    assert len(bank[0])==len(source['triangles'])
    plans=[];refs=set();images=[]
    for fixture in FIXTURES:
        x0,x1,z0,z1,y0,y1=fixture['bounds'];selected=[]
        for i,r in enumerate(source['triangles']):
            if r['category']!='structures' or r['material'] not in (1,13):continue
            p=np.array([v[:3] for v in r['triangle']])
            if np.all(p[:,0]>=x0)&np.all(p[:,0]<=x1)&np.all(p[:,1]>=y0)&np.all(p[:,1]<=y1)&np.all(p[:,2]>=z0)&np.all(p[:,2]<=z1):selected.append(i)
        assert len(selected)>=12,(fixture['name'],len(selected))
        for i in selected:
            ref=source['triangles'][i]['batch'],source['triangles'][i]['face'];assert ref not in refs;refs.add(ref)
        matrix=np.zeros((4,4));matrix[0,0]=16/(x1-x0);matrix[3,0]=-(x1+x0)/(x1-x0);matrix[2,1]=16/(z1-z0);matrix[3,1]=-(z1+z0)/(z1-z0)
        near,far=y0-32,y1+32;matrix[1,2]=16/(far-near);matrix[3,2]=-(far+near)/(far-near);matrix[3,3]=1
        selected=np.array(selected);subset=(bank[0][selected],bank[1][selected],bank[2][selected],bank[3],bank[4]);image=render(subset,matrix,width=32,height=32);images.append(image)
        plans.append({**fixture,'source_refs':[[source['triangles'][i]['batch'],source['triangles'][i]['face']] for i in selected],'source_triangles':len(selected),'bake_matrix_columns':matrix.tolist()})
    # Three full-resolution textures fit the existing 32-material capacity.
    # The four lower fixtures use the same source pattern, tinted individually.
    atlas_bytes=bytearray();texture_hashes=[]
    for mi,index in [(29,2),(30,4),(31,5)]:
        atlas=images[index];five=np.clip(np.round(atlas.astype(float)*31/255),0,31).astype(np.uint16)
        rgba=(five[:,:,0]<<11)|(five[:,:,1]<<6)|(five[:,:,2]<<1)|1
        decoded=np.stack((((rgba>>11)&31)*255//31,((rgba>>6)&31)*255//31,((rgba>>1)&31)*255//31),axis=-1).astype(np.uint8)
        Image.fromarray(decoded).save(OUT/f'panel-{mi}.png');raw_texture=rgba.astype('>u2').tobytes();atlas_bytes.extend(raw_texture);texture_hashes.append(sha(raw_texture))
    (OUT/'panel-atlas.rgba16').write_bytes(atlas_bytes)
    for index,fixture in enumerate(plans):
        fixture['material']=29 if index<4 else 30+index-4
        fixture['tile']=[0,0,32,32]
        fixture['rgb']=[int(v) for v in np.clip(np.round(images[index].mean((0,1))/images[2].mean((0,1))*255),0,255)] if index<4 else [255,255,255]
    plan={'source_sha256':sha(raw),'source_bank_sha256':source['bank_sha256'],'atlas_sha256':sha(bytes(atlas_bytes)),'new_materials':[29,30,31],'texture_sha256':texture_hashes,'fixtures':plans,'source_faces_removed':len(refs),'source':__doc__}
    (OUT/'design.json').write_text(json.dumps(plan,indent=2)+'\n');print(json.dumps({'source_faces':len(refs),'new_faces':len(plans)*2,'new_texture_bytes':6144,'fixtures':[(p['name'],p['source_triangles']) for p in plans]}))


def remodel():
    import bpy
    source=json.loads((OUT/'source.json').read_text());plan=json.loads((OUT/'design.json').read_text());assert plan['source_sha256']==sha((OUT/'source.json').read_bytes())
    removed={tuple(ref) for f in plan['fixtures'] for ref in f['source_refs']};replacements=[]
    scene=bpy.data.scenes.new('West base - authored light panels');bpy.context.window.scene=scene;scene.view_settings.view_transform='Standard'
    materials=[];texture_dir=ROOT/'build/n64-visibility-rollout/sidewinder/data/sidewinder-textures'
    for mi in range(32):
        material=bpy.data.materials.new('West base detail '+str(mi));material.use_nodes=True;n=material.node_tree.nodes;n.clear();output=n.new('ShaderNodeOutputMaterial');em=n.new('ShaderNodeEmission');tex=n.new('ShaderNodeTexImage')
        if mi<17:tex.image=bpy.data.images.load(str(texture_dir/f'packed-{mi}.png'),check_existing=True)
        elif mi>=29:tex.image=bpy.data.images.load(str(OUT/f'panel-{mi}.png'),check_existing=True)
        tex.interpolation='Closest';color=n.new('ShaderNodeVertexColor');color.layer_name='Source lightmap';mix=n.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=1;l=material.node_tree.links;l.new(tex.outputs['Color'],mix.inputs[1]);l.new(color.outputs['Color'],mix.inputs[2]);l.new(mix.outputs[0],em.inputs['Color']);l.new(em.outputs[0],output.inputs['Surface']);materials.append(material)
    for f in plan['fixtures']:
        x0,x1,z0,z1,y0,y1=f['bounds'];tx,ty,w,h=f['tile']
        # Preserve the original lower rim, including its exact ceiling height.
        vertices=[(x0,y0,z0),(x0,y0,z1),(x1,y0,z1),(x1,y0,z0)]
        attrs=[]
        for x,y,z in vertices:
            u=tx+(x-x0)/(x1-x0)*w;v=ty+(z1-z)/(z1-z0)*h
            # Stay within the baked tile by half a texel at its rim.
            u=min(tx+w-.5,max(tx+.5,u));v=min(ty+h-.5,max(ty+.5,v))
            attrs.append([x,y,z,*f['rgb'],round(u*32),round(v*32)])
        for indices in ((0,1,2),(0,2,3)):replacements.append({'material':f['material'],'triangle':[attrs[i] for i in indices],'mask':(1<<35)-1,'fixture':f['name']})
    def west(r):
        p=np.mean([v[:3] for v in r['triangle']],axis=0)/256
        return r['category']=='structures' and p[0]<-24 and p[2]>15
    original=[r for r in source['triangles'] if west(r)];after=[r for r in original if (r['batch'],r['face']) not in removed]+replacements
    points=np.array([v[:3] for r in original for v in r['triangle']],float)/256;center=(points.min(0)+points.max(0))/2
    for name,rows,hidden in [('Original west base',original,True),('Authored west base',after,False)]:
        ps=[];faces=[]
        for r in rows:
            at=len(ps)
            for v in r['triangle']:
                p=np.array(v[:3],float)/256-center;ps.append((p[0],-p[2],p[1]))
            faces.append((at,at+1,at+2))
        mesh=bpy.data.meshes.new(name);mesh.from_pydata(ps,[],faces)
        for mat in materials:mesh.materials.append(mat)
        uv=mesh.uv_layers.new(name='Diffuse');color=mesh.color_attributes.new(name='Source lightmap',type='FLOAT_COLOR',domain='CORNER')
        for poly,r in zip(mesh.polygons,rows):
            poly.material_index=r['material']
            for li,v in zip(poly.loop_indices,r['triangle']):uv.data[li].uv=(v[6]/1024,1-v[7]/1024);color.data[li].color=tuple(c/255 for c in v[3:6])+(1,)
        mesh.update();obj=bpy.data.objects.new(name,mesh);scene.collection.objects.link(obj);obj.hide_set(hidden);obj.hide_render=hidden;obj.select_set(not hidden)
    candidate={'source_sha256':plan['source_sha256'],'design_sha256':sha((OUT/'design.json').read_bytes()),'atlas_sha256':plan['atlas_sha256'],'removed_source_refs':sorted(removed),'replacement_triangles':replacements,'before_base_triangles':len(original),'after_base_triangles':len(after),'method':__doc__}
    (OUT/'candidate.json').write_text(json.dumps(candidate,indent=2)+'\n')
    for area in bpy.context.screen.areas:
        if area.type=='VIEW_3D':
            region=next(r for r in area.regions if r.type=='WINDOW')
            with bpy.context.temp_override(area=area,region=region):bpy.ops.view3d.view_selected()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'west-base-appraisal.blend'));print(json.dumps({k:candidate[k] for k in ['before_base_triangles','after_base_triangles']}))


def pack():
    from remap_sidewinder_visibility import sections,batches
    from pack_maps import packed,bank,uv_safe_triangles
    from pack_terrain import indexed_terrain
    source=json.loads((OUT/'source.json').read_text());candidate=json.loads((OUT/'candidate.json').read_text());assert candidate['source_sha256']==sha((OUT/'source.json').read_bytes()) and candidate['atlas_sha256']==sha((OUT/'panel-atlas.rgba16').read_bytes())
    original=(PREVIOUS/'candidate-maps/sidewinder.map64').read_bytes();assert sha(original)==source['bank_sha256'];ss=sections(original);visibility=json.loads((PREVIOUS/'data/visibility.json').read_text());removed={tuple(ref) for ref in candidate['removed_source_refs']};affected={b for b,f in removed};remaining=collections.defaultdict(list)
    for r in source['triangles']:
        if r['batch'] in affected and (r['batch'],r['face']) not in removed:remaining[r['batch']].append(r['triangle'])
    vertex=bytearray();indices=bytearray();chunks=[];proof=[];masks=[]
    def add(tris,material,mask,old_batch=None):
        for batch in indexed_terrain(uv_safe_triangles(tris),color_delta=0,uv_period=1024):
            vs=batch['vertices'];ix=batch['indices'];first=len(vertex)//16;start=len(indices)//2;padded=vs+([vs[-1]] if len(vs)%2 else []);pairs=[];rgba=lambda v:(v[3]<<24)|(v[4]<<16)|(v[5]<<8)|255
            for a,b in zip(padded[::2],padded[1::2]):pairs.append((*a[:3],0,*b[:3],0,rgba(a),rgba(b),*a[6:],*b[6:]))
            vertex.extend(packed('3hH3hHII4h',pairs));indices.extend(packed('H',[(i,) for i in ix]))
            while len(indices)%8:indices.extend(b'\0\0')
            bounds=[math.floor(min(v[a] for v in vs)/8) for a in range(3)]+[math.ceil(max(v[a] for v in vs)/8) for a in range(3)]
            chunks.append((first,len(vs),material,*bounds,start,len(ix)));proof.append({'unchanged':False,'old_batch':old_batch,'material':material,'retained_source_faces':old_batch is not None});masks.append(mask)
    for b,c in enumerate(struct.iter_unpack('>IHH6hHH',ss[1])):
        first,count,material,*rest=c;at,n=rest[-2:]
        if b in affected:
            if remaining[b]:add(remaining[b],material,visibility['chunk_masks'][b],b)
        else:
            bv=len(vertex)//16;bi=len(indices)//2;vertex.extend(ss[0][first//2*32:(first+((count+1)&~1))//2*32]);indices.extend(ss[2][at*2:(at+((n+3)&~3))*2]);chunks.append((bv,count,material,*rest[:6],bi,n));proof.append({'unchanged':True,'old_batch':b});masks.append(visibility['chunk_masks'][b])
    for mi in (29,30,31):add([r['triangle'] for r in candidate['replacement_triangles'] if r['material']==mi],mi,(1<<35)-1)
    assert len(chunks)<=512 and len(indices)//2<65536
    ss[0]=bytes(vertex);ss[1]=packed('IHH6hHH',chunks);ss[2]=bytes(indices);ss[3]+=(OUT/'panel-atlas.rgba16').read_bytes();ss[4]+=bytes([32]*3);ss[5]+=bytes([0]*3);ss[6]+=bytes([0]*3)
    destination=OUT/'candidate-maps';destination.mkdir(exist_ok=True)
    for p in (PREVIOUS/'candidate-maps').iterdir():
        if p.name!='sidewinder.map64' and not (destination/p.name).exists():(destination/p.name).symlink_to(p.resolve())
    result=bank(destination/'sidewinder.map64',1,ss);payload=(destination/'sidewinder.map64').read_bytes();before=sections(original);after=sections(payload);assert before[7:]==after[7:]
    for s in range(3,7):assert after[s].startswith(before[s])
    a=list(batches(original));b=list(batches(payload))
    for i,e in enumerate(proof):
        if e['unchanged']:assert a[e['old_batch']][1]==b[i][1]
    result.update(source_bank_sha256=sha(original),candidate_bank_sha256=sha(payload),candidate_sha256=sha(payload),batches=proof,chunk_masks=masks,vertices=len(vertex)//16,chunks=len(chunks),triangles=sum(c[-1]//3 for c in chunks),unchanged_batches=sum(e['unchanged'] for e in proof),affected_source_batches=sorted(affected),original_textures_preserved=True,added_texture_bytes=6144,collision_gameplay_sections_identical=True)
    (OUT/'packing-report.json').write_text(json.dumps(result,indent=2)+'\n')
    c=(PREVIOUS/'cameras/visibility-data.c').read_text();c,n=re.subn(r'static const uint64_t chunks\[\]=\{[^}]+\};','static const uint64_t chunks[]={'+','.join('UINT64_C('+str(m)+')' for m in masks)+'};',c);assert n==1
    c,n=re.subn(r'(bg_world_pvs=\{nodes,planes,leaves,rows,chunks,\d+,\d+,\d+,35,)478,',lambda m:m[1]+str(len(chunks))+',',c);assert n==1;(OUT/'visibility-data.c').write_text(c)
    print(json.dumps({k:result[k] for k in ['vertices','chunks','triangles','unchanged_batches','affected_source_batches']}))


if __name__=='__main__':
    if sys.argv[1:] and sys.argv[1]=='pack':pack()
    else:prepare()
