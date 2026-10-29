"""Author a small-screen third tier in Blender; original near/far stay intact."""
import collections,itertools,json,math
from pathlib import Path
import bpy

def reduce(source,colors_path,output,blend):
    data=json.loads(Path(source).read_text());colors=json.loads(Path(colors_path).read_text());report={}
    scene=bpy.data.scenes.new('Covenant crunchy miniatures');bpy.context.window.scene=scene
    for row,(name,ratio) in enumerate((('grunt',.25),('elite',.48),('jackal',.44),('hunter',.23))):
        model=data['models'][name];lods=model.get('n64_lods') or ['base00 low','base00 superlow'];original=model['source_geometry_lods'][lods[1]]
        verts=[];weights=[];ids={};remap=[]
        for i,p in enumerate(original['vertices']):
            if 'skin_weights' in original:skin=tuple((int(b),float(w)) for b,w in original['skin_weights'][i])
            else:
                a,b,w=original['weights'][i];skin=tuple((int(j),float(v)) for j,v in ((a,1-w if b>=0 else 1),(b,w)) if j>=0 and v>1e-7)
            key=(*[round(x,7) for x in p],skin)
            if key not in ids:ids[key]=len(verts);verts.append(p);weights.append(skin)
            remap.append(ids[key])
        faces=[[remap[v] for v in face] for face in original['faces']]
        mesh=bpy.data.meshes.new(name+' crunchy');mesh.from_pydata(verts,[],faces);mesh.update()
        obj=bpy.data.objects.new(name+' crunch',mesh);scene.collection.objects.link(obj)
        for mi,meta in enumerate(model['material_metadata']):
            mat=bpy.data.materials.new(name+' '+str(mi));mat.diffuse_color=(.25,.4,.6,1);mesh.materials.append(mat)
        uv=mesh.uv_layers.new(name='Source UV');color=mesh.color_attributes.new(name='Source colors',type='FLOAT_COLOR',domain='CORNER')
        for pi,(poly,face,mi) in enumerate(zip(mesh.polygons,original['faces'],original['materials'])):
            poly.material_index=mi
            for corner,(li,v) in enumerate(zip(poly.loop_indices,face)):
                uv.data[li].uv=original['uv'][v];color.data[li].color=[c/255 for c in colors[name][pi][corner]]
        groups=[obj.vertex_groups.new(name=n['name']) for n in model['nodes']]
        for i,skin in enumerate(weights):
            for bone,w in skin:groups[bone].add([i],w,'REPLACE')
        # Keep whole silhouette supports and tips of characteristic distal parts.
        # Softer joint weights preserve articulation without locking every seam.
        directions=[d for d in itertools.product((-1,0,1),repeat=3) if any(d)]
        locked={max(range(len(verts)),key=lambda i:sum(a*b for a,b in zip(verts[i],d))) for d in directions}
        dominant=lambda i:max(weights[i],key=lambda x:x[1])[0]
        for bone,node in enumerate(model['nodes']):
            domain=[i for i in range(len(verts)) if dominant(i)==bone]
            if not domain:continue
            if any(word in node['name'] for word in ('spike','head','hand','foot','forearm')):
                for d in ((0,0,1),(1,0,0),(-1,0,0)):
                    locked.add(max(domain,key=lambda i:sum(a*b for a,b in zip(verts[i],d))))
        allow=obj.vertex_groups.new(name='Allow crunch');allow.add([i for i in range(len(verts)) if i not in locked],1,'REPLACE')
        bpy.context.view_layer.objects.active=obj;obj.select_set(True)
        mod=obj.modifiers.new('Crunch at small screen size','DECIMATE');mod.decimate_type='COLLAPSE';mod.ratio=ratio;mod.use_collapse_triangulate=True;mod.vertex_group=allow.name;mod.vertex_group_factor=1
        bpy.ops.object.modifier_apply(modifier=mod.name);mesh=obj.data;mesh.calc_loop_triangles();uv=mesh.uv_layers.active;color=mesh.color_attributes['Source colors']
        skins=[]
        for v in mesh.vertices:
            skin=[(g.group,g.weight) for g in v.groups if g.group<len(groups) and g.weight>1e-7];total=sum(w for _,w in skin);assert total>0;skins.append([[b,w/total] for b,w in skin])
        points=[];uvs=[];skin_weights=[];out_faces=[];materials=[];rgb=[];tints=[];lookup={}
        for tri in mesh.loop_triangles:
            face=[]
            for li in tri.loops:
                vi=mesh.loops[li].vertex_index;tex=list(uv.data[li].uv);key=(vi,*tex)
                if key not in lookup:lookup[key]=len(points);points.append(list(mesh.vertices[vi].co));uvs.append(tex);skin_weights.append(skins[vi])
                face.append(lookup[key])
            out_faces.append(face);materials.append(tri.material_index)
            rgba=[[min(255,max(0,round(v*255))) for v in color.data[li].color] for li in tri.loops]
            rgb.append([q[:3] for q in rgba]);tints.append([q[3] for q in rgba])
        geom=dict(nodes=original['nodes'],vertices=points,uv=uvs,faces=out_faces,materials=materials,skin_weights=skin_weights,corner_colors=rgb,corner_tints=tints)
        model['source_geometry_lods']['n64 crunch']=geom;model['n64_lods']=[*lods,'n64 crunch']
        report[name]=dict(input_triangles=len(faces),triangles=len(out_faces),vertices=len(points),protected=len(locked),ratio=ratio,materials=dict(collections.Counter(materials)))
        obj.location=(0,row*3,0);obj.select_set(False)
    # Spirit keeps its previously appraised hull; third tier aliases that far mesh.
    data['models']['spirit']['n64_lods']=['n64 near','n64 far','n64 far']
    Path(output).write_text(json.dumps(data,separators=(',',':'))+'\n');Path(output).with_suffix('.report.json').write_text(json.dumps(report,indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(blend).resolve()));print(json.dumps(report,indent=2))
