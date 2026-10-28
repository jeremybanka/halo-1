"""Author Hunter/Spirit distance meshes in Blender; retain source skin and UVs.

Run with Blender --background --python SCRIPT -- SOURCE OUTPUT BLEND.
The source cache and approved baseline payload are never overwritten.
"""
import argparse, collections, itertools, json, math, sys
from pathlib import Path
import bpy

def reduce(source, output, blend, colors):
    data=json.loads(Path(source).read_text());report={}
    source_colors=json.loads(Path(colors).read_text())
    scene=bpy.data.scenes.new('Covenant LOD appraisal')
    bpy.context.window.scene=scene
    for name,ratios in [('hunter',(.40,.20)),('spirit',(.32,.16))]:
        model=data['models'][name];original=model['source_geometry_lods'][model['source_lod']]
        # Weld UV splits only when position AND skinning agree. UVs remain on
        # loops; articulated seams and different bone weights stay separate.
        verts=[];weights=[];lookup={};remap=[]
        for p,(a,b,w) in zip(original['vertices'],original['weights']):
            skin=tuple((i,v) for i,v in [(a,1-w if b>=0 else 1),(b,w)] if i>=0 and v>1e-7)
            key=(*[round(x,7) for x in p],skin)
            if key not in lookup:lookup[key]=len(verts);verts.append(p);weights.append(skin)
            remap.append(lookup[key])
        report[name]=[]
        for lod,ratio in enumerate(ratios):
            mesh=bpy.data.meshes.new(f'{name} {lod} source');mesh.from_pydata(verts,[],[[remap[v] for v in f] for f in original['faces']]);mesh.update()
            obj=bpy.data.objects.new(f'{name} {"near" if lod==0 else "far"}',mesh);scene.collection.objects.link(obj)
            for mi,meta in enumerate(model['material_metadata']):
                mat=bpy.data.materials.new(f'{name} {mi}');mat.diffuse_color=(.2,.3,.6,1)
                mesh.materials.append(mat)
            uv=mesh.uv_layers.new(name='Source UV')
            color=mesh.color_attributes.new(name='Source diffuse and tint',type='FLOAT_COLOR',domain='CORNER')
            for pi,(poly,face,mi) in enumerate(zip(mesh.polygons,original['faces'],original['materials'])):
                poly.material_index=mi
                for corner,(loop,source_vertex) in enumerate(zip(poly.loop_indices,face)):
                    uv.data[loop].uv=original['uv'][source_vertex];color.data[loop].color=[v/255 for v in source_colors[name][pi][corner]]
            groups=[obj.vertex_groups.new(name=n['name']) for n in model['nodes']]
            for i,skin in enumerate(weights):
                for bone,w in skin:groups[bone].add([i],w,'REPLACE')
            edges=collections.Counter(tuple(sorted((f[i],f[(i+1)%3]))) for f in [[remap[v] for v in face] for face in original['faces']] for i in range(3))
            locked={v for edge,count in edges.items() if count!=2 for v in edge}
            edge_materials=collections.defaultdict(set)
            for face,mi in zip(original['faces'],original['materials']):
                f=[remap[v] for v in face]
                for i in range(3):edge_materials[tuple(sorted((f[i],f[(i+1)%3])))].add(mi)
            for edge,materials in edge_materials.items():
                a,b=edge
                dominant=lambda skin:max(skin,key=lambda item:item[1])[0]
                if (len(materials)>1 and (lod==0 or name=='spirit')) or dominant(weights[a])!=dominant(weights[b]):locked.update(edge)
            # Retain each semantic/articulated part's supporting outline in
            # 26 directions, not merely the whole model's bounding box. This
            # keeps broad shields, barrel ends, feet and the Spirit's booms.
            domains=collections.defaultdict(set)
            for face,mi in zip(original['faces'],original['materials']):
                for source_vertex in face:
                    vi=remap[source_vertex];domains[(mi,dominant(weights[vi]))].add(vi)
            directions=[d for d in itertools.product((-1,0,1),repeat=3) if any(d)]
            for domain in domains.values():
                for direction in directions:
                    locked.add(max(domain,key=lambda i:sum(a*b for a,b in zip(verts[i],direction))))
            if name=='hunter':
                head={remap[v] for face,mi in zip(original['faces'],original['materials']) if mi==2 for v in face}
                spikes={i for i,skin in enumerate(weights) if any('spike' in model['nodes'][bone]['name'] for bone,w in skin)}
                if lod==0:locked.update(head|spikes)
                else:
                    # At distance retain the face's extrema and each spine's
                    # endpoints, allowing its intermediate rings to collapse.
                    domains=[head]+[{i for i in spikes if any(b==bone for b,w in weights[i])} for bone,n in enumerate(model['nodes']) if 'spike' in n['name']]
                    for domain in domains:
                        if domain:
                            for axis in range(3):
                                locked.add(min(domain,key=lambda i:verts[i][axis]));locked.add(max(domain,key=lambda i:verts[i][axis]))
            # Zero-weight endpoints are excluded by Blender's collapse tool.
            # Keep open/attachment seams, the Hunter face and six back spines.
            reduce_group=obj.vertex_groups.new(name='Allow reduction')
            reduce_group.add([i for i in range(len(verts)) if i not in locked],1,'REPLACE')
            bpy.context.view_layer.objects.active=obj;obj.select_set(True)
            mod=obj.modifiers.new('Distance geometry','DECIMATE');mod.decimate_type='COLLAPSE';mod.ratio=ratio;mod.use_collapse_triangulate=True
            mod.vertex_group=reduce_group.name;mod.vertex_group_factor=1
            bpy.ops.object.modifier_apply(modifier=mod.name)
            mesh=obj.data;mesh.calc_loop_triangles();uv=mesh.uv_layers.active
            # Keep all interpolated weights: pre-baking supports these without
            # adding runtime skinning work or forcing a two-bone approximation.
            skins=[]
            for v in mesh.vertices:
                skin=[(g.group,g.weight) for g in v.groups if g.group<len(groups) and g.weight>1e-7];total=sum(w for _,w in skin);assert total>0
                skins.append([[b,w/total] for b,w in skin])
            points=[];uvs=[];skin_weights=[];faces=[];materials=[];corner_colors=[];corner_tints=[];ids={}
            color=mesh.color_attributes['Source diffuse and tint']
            for tri in mesh.loop_triangles:
                face=[]
                for li in tri.loops:
                    vi=mesh.loops[li].vertex_index;coord=list(mesh.vertices[vi].co);tex=list(uv.data[li].uv)
                    key=(vi,*tex)
                    if key not in ids:ids[key]=len(points);points.append(coord);uvs.append(tex);skin_weights.append(skins[vi])
                    face.append(ids[key])
                faces.append(face);materials.append(tri.material_index)
                rgba=[[min(255,max(0,round(v*255))) for v in color.data[li].color] for li in tri.loops]
                corner_colors.append([c[:3] for c in rgba]);corner_tints.append([c[3] for c in rgba])
            geom={'nodes':original['nodes'],'vertices':points,'uv':uvs,'faces':faces,'materials':materials,'skin_weights':skin_weights,'corner_colors':corner_colors,'corner_tints':corner_tints}
            assert set(materials)==set(original['materials']),'A character-defining material region disappeared'
            assert max(map(len,skins))<=4,'Collapse crossed too many skinning boundaries'
            key=f'n64 {"near" if lod==0 else "far"}';model['source_geometry_lods'][key]=geom
            report[name].append({'lod':key,'input_triangles':len(original['faces']),'triangles':len(faces),'ratio':ratio,'vertices':len(points),'protected_vertices':len(locked),'materials':dict(collections.Counter(materials)),'max_bones':max(map(len,skins))})
            obj.location.x=lod*12;obj.location.y=0 if name=='hunter' else 12;obj.select_set(False)
        model['n64_lods']=['n64 near','n64 far']
    Path(output).write_text(json.dumps(data,separators=(',',':'))+'\n')
    Path(output).with_suffix('.report.json').write_text(json.dumps(report,indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(blend).resolve()))
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source');p.add_argument('output');p.add_argument('blend');p.add_argument('--colors',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);reduce(a.source,a.output,a.blend,a.colors)
