"""Full-character surgical culling baseline; preserve original retained surfaces and rig."""
import bpy,bmesh,json,math,hashlib
from pathlib import Path
from collections import defaultdict,Counter
from mathutils import Vector
import jorge_shoulder_study as shoulder

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'halo64-assets/assets/jorge'
OUT=BASE/'full-cleanup'
pos=shoulder.pos
direction=shoulder.direction

def mesh_from_faces(raw,ids,name,scene):
    verts=sorted({v for fi in ids for v in raw['faces'][fi]});lookup={v:i for i,v in enumerate(verts)}
    me=bpy.data.meshes.new(name);me.from_pydata([pos(raw['vertices'][i]) for i in verts],[],[[lookup[v] for v in raw['faces'][fi]] for fi in ids])
    uv=me.uv_layers.new(name='Original UV')
    for f,fi in zip(me.polygons,ids):
        f.use_smooth=True
        for li,vi in zip(f.loop_indices,raw['faces'][fi]):uv.data[li].uv=(raw['uv'][vi][0],1-raw['uv'][vi][1])
    me.normals_split_custom_set_from_vertices([direction(raw['normals'][i]) for i in verts])
    original_normals=me.attributes.new('source_normal','FLOAT_VECTOR','POINT')
    original_normals.data.foreach_set('vector',[x for i in verts for x in direction(raw['normals'][i])])
    for attribute,domain,values in [('source_vertex','POINT',verts),('source_face','FACE',ids)]:
        a=me.attributes.new(attribute,'INT',domain);a.data.foreach_set('value',values)
    ob=bpy.data.objects.new(me.name,me);scene.collection.objects.link(ob)
    for n in raw['nodes']:ob.vertex_groups.new(name=n['name'])
    for local,vi in enumerate(verts):
        for bi,w in raw['weights'][vi]:ob.vertex_groups[bi].add([local],w,'REPLACE')
    return ob

def make_material(meta,index):
    mat=bpy.data.materials.new('Jorge / '+meta['path'].split('\\')[-1]);mat.use_nodes=True
    ns=mat.node_tree.nodes;ls=mat.node_tree.links;bs=next(n for n in ns if n.type=='BSDF_PRINCIPLED');bs.inputs['Roughness'].default_value=.73
    tex=ns.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(meta['diffuse'],check_existing=True);tex.image.alpha_mode='STRAIGHT' if index in (11,12,13) else 'NONE';color=tex.outputs['Color']
    if meta.get('cc') and index!=6:
        mask=ns.new('ShaderNodeTexImage');mask.image=bpy.data.images.load(meta['cc'],check_existing=True);mask.image.colorspace_settings.name='Non-Color';mask.image.alpha_mode='NONE'
        sep=ns.new('ShaderNodeSeparateColor');ls.new(mask.outputs['Color'],sep.inputs['Color'])
        for channel,tint in [('Red',(.42,.48,.22,1)),('Green',(.5,.52,.35,1)),('Blue',(.42,.08,.055,1))]:
            mix=ns.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';ls.new(sep.outputs[channel],mix.inputs[0]);ls.new(color,mix.inputs[1]);mix.inputs[2].default_value=tint;color=mix.outputs[0]
    ls.new(color,bs.inputs['Base Color'])
    if index==6:
        ls.remove(bs.inputs['Base Color'].links[0]);bs.inputs['Base Color'].default_value=(.48,.16,.035,1);bs.inputs['Metallic'].default_value=.7;bs.inputs['Roughness'].default_value=.22
    if index in (11,12,13):ls.new(tex.outputs['Alpha'],bs.inputs['Alpha'])
    if index==13:
        sep=ns.new('ShaderNodeSeparateColor');ls.new(tex.outputs['Color'],sep.inputs['Color']);ls.new(sep.outputs['Red'],bs.inputs['Base Color']);ls.new(sep.outputs['Green'],bs.inputs['Alpha'])
    if meta.get('normal_map') and index!=6:
        texn=ns.new('ShaderNodeTexImage');texn.image=bpy.data.images.load(meta['normal_map'],check_existing=True);texn.image.colorspace_settings.name='Non-Color'
        sep=ns.new('ShaderNodeSeparateColor');ls.new(texn.outputs['Color'],sep.inputs['Color'])
        inv=ns.new('ShaderNodeMath');inv.operation='SUBTRACT';inv.inputs[0].default_value=1;ls.new(sep.outputs['Green'],inv.inputs[1])
        combine=ns.new('ShaderNodeCombineColor');ls.new(sep.outputs['Red'],combine.inputs['Red']);ls.new(inv.outputs[0],combine.inputs['Green']);ls.new(sep.outputs['Blue'],combine.inputs['Blue'])
        nm=ns.new('ShaderNodeNormalMap');ls.new(combine.outputs[0],nm.inputs['Color']);ls.new(nm.outputs[0],bs.inputs['Normal'])
    mat['source_material']=index
    return mat

def inventory(ob,raw,group):
    bm=bmesh.new();bm.from_mesh(ob.data);faceid=bm.faces.layers.int.get('source_face')
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6);bm.normal_update()
    cs=shoulder.connected(bm);result=[]
    # Welding may discard coincident/degenerate faces. Classify ALL original faces
    # from their geometric vertices, not just surviving BMesh face records.
    vertex_components=defaultdict(set);exact_assignment={};key=lambda co:tuple(round(x,6) for x in co)
    for ci,faces in enumerate(cs):
        for f in faces:
            exact_assignment[f[faceid]]=ci
            for v in f.verts:vertex_components[key(v.co)].add(ci)
    complete_ids=defaultdict(list);unclassified=[]
    for entry in ob.data.attributes['source_face'].data:
        fi=entry.value
        if fi in exact_assignment:ci=exact_assignment[fi]
        else:
            candidates=[vertex_components[key(pos(raw['vertices'][v]))] for v in raw['faces'][fi]]
            common=set.intersection(*candidates)
            if not common:unclassified.append(fi);continue
            ci=min(common)
        complete_ids[ci].append(fi)
    assert not unclassified,(group,unclassified)
    for i,faces in enumerate(cs):
        ids=sorted(complete_ids[i]);vids={v for fi in ids for v in raw['faces'][fi]};vs=[pos(raw['vertices'][v]) for v in vids]
        bounds=[[min(v[k] for v in vs),max(v[k] for v in vs)] for k in range(3)];dims=[hi-lo for lo,hi in bounds]
        bone=Counter()
        for vi in vids:
            for bi,w in raw['weights'][vi]:bone[raw['nodes'][bi]['name']]+=w
        area=sum(f.calc_area() for f in faces)
        result.append({'id':f'{group}:{i:03d}','group':group,'local_id':i,'triangles':len(ids),'area_m2':area,'dimensions_m':dims,'center_m':[(lo+hi)/2 for lo,hi in bounds],
                       'bones':dict(bone.most_common(4)),'face_ids':ids,'zero_area_faces':sum(f.calc_area()<1e-12 for f in faces)})
    bm.free();return result

def inspect():
    raw=json.loads((OUT/'source-complete.json').read_text());scene=bpy.data.scenes.new('Jorge full - component inspection');bpy.context.window.scene=scene
    mats=[make_material(meta,i) for i,meta in enumerate(raw['material_metadata'])]
    groups=defaultdict(list)
    for fi,(r,m) in enumerate(zip(raw['regions'],raw['materials'])):groups[(r,m)].append(fi)
    components=[];objects=[]
    for (region,mi),ids in groups.items():
        name=f'{region}-{mi:02d}';ob=mesh_from_faces(raw,ids,'A / '+name,scene);ob.data.materials.append(mats[mi]);ob['group']=name;ob['source_material']=mi;ob['variant']='A';objects.append(ob)
        cs=inventory(ob,raw,name);components+=cs
        print(name,raw['material_metadata'][mi]['path'].split('\\')[-1],len(ids),'triangles',len(cs),'islands')
    (OUT/'component-inventory.json').write_text(json.dumps(components,indent=2))
    rig=shoulder.make_rig(scene,raw)
    for ob in objects:ob.parent=rig;mod=ob.modifiers.new('Original Reach deformation','ARMATURE');mod.object=rig
    rig.hide_set(True);studio(scene)
    for im in bpy.data.images:
        if im.filepath and 'jorge' in bpy.path.abspath(im.filepath):im.pack()
    bpy.data.libraries.write(str(OUT/'jorge-inspection.blend'),{scene},fake_user=True)
    print('COMPONENTS',len(components),'TRIANGLES',sum(c['triangles'] for c in components));return scene

VIEWS={'front':(0,-6,1.18),'back':(0,6,1.18),'left':(6,0,1.18),'right':(-6,0,1.18),'three_quarter':(4,-6,2.8)}
def studio(scene):
    scene.render.engine='CYCLES';scene.cycles.samples=24;scene.render.resolution_x=640;scene.render.resolution_y=800;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.film_transparent=True;scene.view_settings.view_transform='Standard';scene.view_settings.exposure=-.6
    scene.world=bpy.data.worlds.new('Full Jorge neutral studio');scene.world.use_nodes=True
    next(n for n in scene.world.node_tree.nodes if n.type=='BACKGROUND').inputs[0].default_value=(.28,.28,.28,1)
    for name,loc,power,size in [('Key',(3,-4,5),350,4),('Fill',(-4,-2,3),220,4),('Rim',(1,4,4),400,3)]:
        d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size;o=bpy.data.objects.new(name,d);scene.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,1.2))-o.location).to_track_quat('-Z','Y').to_euler()
    d=bpy.data.cameras.new('Full Jorge matched camera');d.type='ORTHO';d.ortho_scale=2.66;o=bpy.data.objects.new(d.name,d);scene.collection.objects.link(o);scene.camera=o;camera(scene,'three_quarter')

def camera(scene,view):
    scene.camera.location=VIEWS[view];scene.camera.rotation_euler=(Vector((0,0,1.15))-scene.camera.location).to_track_quat('-Z','Y').to_euler()

GROUP_NAMES={'arms-01':'Gauntlets','arms-04':'Large left shoulder','arms-05':'Right shoulder','arms-07':'Forearm and hand armor','arms-08':'Hands and gloves','arms-09':'Upper-arm armor','arms-10':'Elbow undersuit',
             'body-00':'Chest armor','body-02':'Calf gear and collar','body-03':'Helmet','body-06':'Visor','body-09':'Torso and leg armor','body-10':'Body undersuit','jorge_decals-11':'Scorch decals','jorge_decals-12':'UNSC markings','jorge_decals-13':'Shoulder damage','backpack-14':'Backpack'}
# Explicitly inspected component selections, not a global size threshold.
CULL_FROM={'arms-01':14,'arms-04':2,'body-00':7,'backpack-14':5}

def reduction_candidates(ob,raw,ids,protected_identity=False):
    key=lambda v:tuple(round(x,6) for x in pos(raw['vertices'][v]))
    edges=defaultdict(list);face_normals={};vids=sorted({v for fi in ids for v in raw['faces'][fi]})
    for fi in ids:
        vs=raw['faces'][fi];co=[pos(raw['vertices'][v]) for v in vs];face_normals[fi]=(co[1]-co[0]).cross(co[2]-co[0]).normalized()
        for j in range(3):
            i,k=vs[j],vs[(j+1)%3];a,b=key(i),key(k)
            edges[tuple(sorted((a,b)))].append((fi,{a:i,b:k}))
    sets={name:set() for name in ('boundary','uv_seam','normal_split','hard_edge','deformation','identity')}
    for (a,b),entries in edges.items():
        reasons=[]
        if len(entries)!=2:reasons.append('boundary')
        else:
            (fi,vi),(fj,vj)=entries
            if any((Vector(raw['uv'][vi[k]])-Vector(raw['uv'][vj[k]])).length>1e-4 for k in (a,b)):reasons.append('uv_seam')
            if any(direction(raw['normals'][vi[k]]).dot(direction(raw['normals'][vj[k]]))<math.cos(math.radians(28)) for k in (a,b)):reasons.append('normal_split')
            if face_normals[fi].dot(face_normals[fj])<math.cos(math.radians(30)):reasons.append('hard_edge')
        for reason in reasons:sets[reason].update((a,b))
    for vi in vids:
        if len(raw['weights'][vi])>1:sets['deformation'].add(key(vi))
        if protected_identity:sets['identity'].add(key(vi))
    all_locked=set.union(*sets.values());freedom=ob.vertex_groups.new(name='Reduction freedom - inspect before use')
    source_ids=[x.value for x in ob.data.attributes['source_vertex'].data]
    for name,locked in sets.items():
        attr=ob.data.attributes.new('candidate_'+name,'BOOLEAN','POINT')
        attr.data.foreach_set('value',[key(v) in locked for v in source_ids])
    for local,vi in enumerate(source_ids):freedom.add([local],0 if key(vi) in all_locked else 1,'REPLACE')
    ob['candidate_constraints_only']=True
    return {name:sum(key(vi) in locked for vi in source_ids) for name,locked in sets.items()}

def build():
    raw=json.loads((OUT/'source-complete.json').read_text());components=json.loads((OUT/'component-inventory.json').read_text())
    assert sum(c['triangles'] for c in components)==len(raw['faces'])
    scene=bpy.data.scenes.new('Jorge full - surgical baseline');bpy.context.window.scene=scene
    collections={}
    for label,name in [('A','A - preserved full source'),('B','B - surgical baseline'),('R','Removed fasteners - reference')]:
        co=bpy.data.collections.new(name);scene.collection.children.link(co);collections[label]=co
    mats=[make_material(meta,i) for i,meta in enumerate(raw['material_metadata'])]
    groups=defaultdict(list)
    for fi,(r,m) in enumerate(zip(raw['regions'],raw['materials'])):groups[f'{r}-{m:02d}'].append(fi)
    culled={c['id'] for c in components if c['group'] in CULL_FROM and c['local_id']>=CULL_FROM[c['group']]}
    removed_faces={fi for c in components if c['id'] in culled for fi in c['face_ids']}
    degenerates=set()
    for fi,f in enumerate(raw['faces']):
        a,b,c=(pos(raw['vertices'][i]) for i in f)
        if (b-a).cross(c-a).length/2<1e-12:degenerates.add(fi)
    zero_only=degenerates-removed_faces;keep=set(range(len(raw['faces'])))-removed_faces-degenerates
    report={'source_hashes':raw['source_hashes'],'source_complete_sha256':hashlib.sha256((OUT/'source-complete.json').read_bytes()).hexdigest(),
            'original_triangles':len(raw['faces']),'clean_triangles':len(keep),'fastener_components_removed':len(culled),'fastener_triangles_removed':len(removed_faces),
            'additional_degenerate_triangles_removed':len(zero_only),'original_bones':len(raw['nodes']),'groups':{},'components':[],
            'operations':['Remove 66 explicitly inspected disconnected fasteners','Remove four remaining zero-area chest faces','Retain every other source face, vertex position, UV, normal and skin weight','Partition retained components and annotate candidate reduction constraints'],
            'not_applied':['No global decimation','No primitive reconstruction','No undersuit or joint retopology','No blanket hidden-surface deletion']}
    # Share the original skeleton between reference and baseline for exact pose comparisons.
    rig=shoulder.make_rig(scene,raw);rig.name='Jorge original Reach skeleton - 85 bones'
    all_objects=[]
    def install(ob,label,group,mi):
        for co in list(ob.users_collection):co.objects.unlink(ob)
        collections[label].objects.link(ob);ob.data.materials.append(mats[mi]);ob['variant']=label;ob['group']=group;ob['source_material']=mi
        ob.parent=rig;mod=ob.modifiers.new('Original Reach skin weights','ARMATURE');mod.object=rig;all_objects.append(ob)
    for group,ids in groups.items():
        mi=raw['materials'][ids[0]];ob=mesh_from_faces(raw,ids,'A / '+GROUP_NAMES[group],scene);install(ob,'A',group,mi)
        report['groups'][group]={'name':GROUP_NAMES[group],'original':len(ids),'clean':sum(i in keep for i in ids),'removed_components':sum(c['group']==group and c['id'] in culled for c in components)}
    clean_json={k:raw[k] for k in ('tag','cache_build','nodes','material_metadata','backpack_attachment','source_hashes')};clean_json.update({'vertices':[],'normals':[],'uv':[],'weights':[],'faces':[],'materials':[],'regions':[],'component_ids':[],'source_vertex_ids':[],'source_face_ids':[]})
    used=sorted({vi for fi in keep for vi in raw['faces'][fi]});lookup={v:i for i,v in enumerate(used)}
    for key in ('vertices','normals','uv','weights'):clean_json[key]=[raw[key][v] for v in used]
    clean_json['source_vertex_ids']=used
    face_component={fi:c['id'] for c in components for fi in c['face_ids']}
    for fi in sorted(keep):
        clean_json['faces'].append([lookup[v] for v in raw['faces'][fi]]);clean_json['materials'].append(raw['materials'][fi]);clean_json['regions'].append(raw['regions'][fi]);clean_json['component_ids'].append(face_component[fi]);clean_json['source_face_ids'].append(fi)
    for c in components:
        mi=raw['materials'][c['face_ids'][0]];group=c['group'];remove=c['id'] in culled
        ids=c['face_ids'] if remove else [fi for fi in c['face_ids'] if fi in keep]
        dominant=next(iter(c['bones']));name=dominant.removeprefix('b_').replace('_',' ')
        ob=mesh_from_faces(raw,ids,f'{"R" if remove else "B"} / {GROUP_NAMES[group]} / {name} / {c["local_id"]:02d}',scene);install(ob,'R' if remove else 'B',group,mi)
        ob['source_component']=c['id'];ob['geometric_class']=('deforming undersuit' if mi in (8,10) else 'helmet or visor' if mi in (3,6) else 'decal' if mi in (11,12,13) else 'armor and equipment')
        constraints={} if remove else reduction_candidates(ob,raw,ids,mi in (3,6))
        report['components'].append({**{k:v for k,v in c.items() if k!='face_ids'},'action':'cull fastener' if remove else 'preserve original surface','clean_triangles':0 if remove else len(ids),'candidate_vertices':constraints})
    (OUT/'jorge-cleaned.json').write_text(json.dumps(clean_json,separators=(',',':')))
    (OUT/'cleanup-selection.json').write_text(json.dumps({'removed_component_ids':sorted(culled),'removed_fastener_face_ids':sorted(removed_faces),'removed_degenerate_face_ids':sorted(zero_only),'retained_face_ids':sorted(keep)},indent=2))
    validate_retained(raw,all_objects,rig,report)
    studio(scene)
    for ob in all_objects:ob.hide_set(ob['variant']!='B');ob.hide_render=ob['variant']!='B'
    rig.hide_set(True)
    for im in bpy.data.images:
        if im.filepath and 'jorge' in bpy.path.abspath(im.filepath):im.pack()
    (OUT/'cleanup-report.json').write_text(json.dumps(report,indent=2))
    bpy.data.libraries.write(str(OUT/'jorge-surgical-cleanup.blend'),{scene},fake_user=True)
    print(json.dumps({k:report[k] for k in ('original_triangles','clean_triangles','fastener_components_removed','fastener_triangles_removed','additional_degenerate_triangles_removed','validation')},indent=2));return scene

POSES={'rest':{},'aiming':{'b_l_upperarm':(-30,20,25),'b_r_upperarm':(-35,-25,-20),'b_l_forearm':(0,45,0),'b_r_forearm':(0,-45,0)},
       'stride':{'b_l_thigh':(25,0,0),'b_r_thigh':(-25,0,0),'b_l_calf':(-20,0,0),'b_r_calf':(20,0,0),'b_l_upperarm':(-15,0,0),'b_r_upperarm':(15,0,0)},
       'crouch_twist':{'b_pelvis':(8,0,0),'b_spine1':(10,0,10),'b_torso':(-5,0,12),'b_l_thigh':(40,0,0),'b_r_thigh':(40,0,0),'b_l_calf':(-55,0,0),'b_r_calf':(-55,0,0)},
       'hands_and_head':{'b_helmet':(0,0,20),'b_l_hand':(10,0,15),'b_r_hand':(-10,0,-15),'b_l_index1':(0,0,20),'b_r_index1':(0,0,-20)}}
def set_pose(rig,name):
    for p in rig.pose.bones:p.rotation_mode='XYZ';p.rotation_euler=(0,0,0)
    for bone,angles in POSES[name].items():
        assert bone in rig.pose.bones,bone
        rig.pose.bones[bone].rotation_euler=tuple(math.radians(x) for x in angles)
    bpy.context.view_layer.update()

def validate_retained(raw,objects,rig,report):
    max_position=max_uv=max_normal=max_weight=0.;source_faces=0;clean_faces=0
    for ob in objects:
        if ob['variant'] not in ('A','B'):continue
        me=ob.data;vis=[x.value for x in me.attributes['source_vertex'].data];fis=[x.value for x in me.attributes['source_face'].data]
        if ob['variant']=='A':source_faces+=len(fis)
        else:clean_faces+=len(fis)
        for i,vi in enumerate(vis):
            max_position=max(max_position,(me.vertices[i].co-pos(raw['vertices'][vi])).length)
            weights={ob.vertex_groups[g.group].name:g.weight for g in me.vertices[i].groups if ob.vertex_groups[g.group].name in rig.pose.bones}
            expected={raw['nodes'][bi]['name']:w for bi,w in raw['weights'][vi]}
            assert weights.keys()==expected.keys()
            max_weight=max(max_weight,max(abs(weights[k]-expected[k]) for k in weights))
        uv=me.uv_layers.active.data
        for f,fi in zip(me.polygons,fis):
            assert [vis[v] for v in f.vertices]==raw['faces'][fi]
            for li,vi in zip(f.loop_indices,raw['faces'][fi]):
                max_uv=max(max_uv,(uv[li].uv-Vector((raw['uv'][vi][0],1-raw['uv'][vi][1]))).length)
                if ob['variant']=='B':max_normal=max(max_normal,(me.corner_normals[li].vector-direction(raw['normals'][vi])).length)
                assert (me.attributes['source_normal'].data[me.loops[li].vertex_index].vector-direction(raw['normals'][vi])).length<1e-7
    assert source_faces==report['original_triangles'] and clean_faces==report['clean_triangles']
    # Blender encodes custom loop normals relative to each face fan. Preserve the
    # exact original vector separately; tolerate its finite-precision loop encoding.
    assert max_position<1e-7 and max_uv<2e-6 and max_weight<1e-6 and max_normal<.02,(max_position,max_uv,max_weight,max_normal)
    poses={}
    for name in POSES:
        set_pose(rig,name);dg=bpy.context.evaluated_depsgraph_get();expected={}
        for ob in objects:
            if ob['variant']!='A':continue
            ev=ob.evaluated_get(dg);me=ev.to_mesh()
            for v,vi in zip(me.vertices,ob.data.attributes['source_vertex'].data):expected[vi.value]=v.co.copy()
            ev.to_mesh_clear()
        error=0
        for ob in objects:
            if ob['variant']!='B':continue
            ev=ob.evaluated_get(dg);me=ev.to_mesh()
            for v,vi in zip(me.vertices,ob.data.attributes['source_vertex'].data):error=max(error,(v.co-expected[vi.value]).length)
            ev.to_mesh_clear()
        assert error<1e-6
        poses[name]=error
    set_pose(rig,'rest')
    report['validation']={'max_retained_position_error_m':max_position,'max_retained_uv_error':max_uv,'source_normal_attribute_exact':True,'blender_loop_normal_encoding_max_vector_error':max_normal,'max_skin_weight_error':max_weight,'pose_max_vertex_errors_m':poses,'original_faces_preserved':source_faces,'retained_faces_verified':clean_faces}

def export_all():
    scene=next(s for s in bpy.data.scenes if any(o.get('variant')=='B' for o in s.objects));bpy.context.window.scene=scene
    objects=[o for o in scene.objects if o.type=='MESH' and 'variant' in o];rig=next(o for o in scene.objects if o.type=='ARMATURE');set_pose(rig,'rest')
    mats={o['source_material']:o.data.materials[0] for o in objects}
    # A full-UV plane converts shader color masks and normal-map convention without
    # changing any model UVs or resampling through the character's geometry.
    me=bpy.data.meshes.new('Temporary full-UV bake plane');me.from_pydata([(-1,-1,0),(1,-1,0),(1,1,0),(-1,1,0)],[],[(0,1,2,3)])
    uv=me.uv_layers.new(name='UVMap')
    for li,co in enumerate([(0,0),(1,0),(1,1),(0,1)]):uv.data[li].uv=co
    plane=bpy.data.objects.new(me.name,me);scene.collection.objects.link(plane)
    for ob in objects:ob.hide_render=True
    for mi,mat in sorted(mats.items()):
        ns=mat.node_tree.nodes;ls=mat.node_tree.links;bs=next(n for n in ns if n.type=='BSDF_PRINCIPLED');out=next(n for n in ns if n.type=='OUTPUT_MATERIAL')
        me.materials.clear();me.materials.append(mat);targets=[]
        if mi not in (6,11,12,13):targets.append(('color',bs.inputs['Base Color'],False))
        nm=next((n for n in ns if n.type=='NORMAL_MAP'),None)
        if nm:targets.append(('normal',nm.inputs['Color'],True))
        for kind,socket,noncolor in targets:
            source=socket.links[0].from_socket
            images=[n.image for n in ns if n.type=='TEX_IMAGE' and n.image and (n.image.colorspace_settings.name=='Non-Color')==noncolor]
            w,h=max((tuple(im.size) for im in images),key=lambda dims:dims[0]*dims[1]) if images else (512,512)
            im=bpy.data.images.new(f'Jorge {mi:02d} portable {kind}',w,h,alpha=False);im.colorspace_settings.name='Non-Color' if noncolor else 'sRGB'
            target=ns.new('ShaderNodeTexImage');target.image=im
            for n in ns:n.select=False
            target.select=True;ns.active=target
            emit=ns.new('ShaderNodeEmission');ls.new(source,emit.inputs['Color']);ls.new(emit.outputs[0],out.inputs['Surface'])
            shoulder.select(plane);scene.cycles.samples=1
            bpy.ops.object.bake(type='EMIT',use_selected_to_active=False,margin=0,use_clear=True)
            im.filepath_raw=str(OUT/'textures'/f'{mi:02d}-{kind}.png');im.file_format='PNG';im.save();im.pack();ls.new(target.outputs[0],socket)
            ns.remove(emit);ls.new(bs.outputs[0],out.inputs['Surface'])
        if mi==13:
            # Retail damage decal packs grayscale color in R and opacity in G.
            from array import array
            source=next(n.image for n in ns if n.type=='TEX_IMAGE' and n.image and 'charred_hole_02.png' in n.image.filepath)
            pixels=array('f',[0])*(len(source.pixels));source.pixels.foreach_get(pixels)
            for at in range(0,len(pixels),4):r,g=pixels[at:at+2];pixels[at:at+4]=array('f',(r,r,r,g))
            im=bpy.data.images.new('Portable RG damage decal',*source.size,alpha=True);im.pixels.foreach_set(pixels);im.filepath_raw=str(OUT/'textures'/'13-color-alpha.png');im.file_format='PNG';im.save();im.pack()
            tex=ns.new('ShaderNodeTexImage');tex.image=im;ls.new(tex.outputs['Color'],bs.inputs['Base Color']);ls.new(tex.outputs['Alpha'],bs.inputs['Alpha'])
    bpy.data.objects.remove(plane,do_unlink=True);scene.cycles.samples=24
    for label,filename in [('A','jorge-source-reference.glb'),('B','jorge-cleaned.glb')]:
        bpy.ops.object.select_all(action='DESELECT')
        for ob in objects:
            ob.hide_set(False);ob.select_set(ob['variant']==label)
        rig.hide_set(False);rig.select_set(True);bpy.context.view_layer.objects.active=rig
        bpy.ops.export_scene.gltf(filepath=str(OUT/filename),export_format='GLB',use_selection=True,export_animations=False,export_skins=True)
    for ob in objects:ob.hide_set(ob['variant']!='B');ob.hide_render=ob['variant']!='B';ob.select_set(False)
    rig.select_set(False);rig.hide_set(True);camera(scene,'three_quarter')
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'jorge-surgical-cleanup.blend'))

def render_all():
    scene=next(s for s in bpy.data.scenes if any(o.get('variant')=='B' for o in s.objects));bpy.context.window.scene=scene
    objects=[o for o in scene.objects if o.type=='MESH' and 'variant' in o];rig=next(o for o in scene.objects if o.type=='ARMATURE');original={o.name:o.data.materials[0] for o in objects}
    clay=shoulder.simple_material('Full Jorge clay - no normal maps');wire=shoulder.simple_material('Full Jorge topology - no normal maps',True)
    folder=OUT/'renders';folder.mkdir(exist_ok=True)
    def visible(label,group=None):
        for ob in objects:ob.hide_render=not(ob['variant']==label and (group is None or ob['group']==group))
    def render(name):
        scene.render.filepath=str(folder/(name+'.png'));bpy.ops.render.render(write_still=True)
    for style,mat in [('textured',None),('clay',clay),('wire',wire)]:
        for ob in objects:ob.data.materials[0]=mat or original[ob.name]
        for label in ('A','B'):
            visible(label)
            for view in VIEWS:camera(scene,view);render(f'{label}-{style}-{view}')
    for ob in objects:ob.data.materials[0]=original[ob.name]
    scene.render.resolution_x=600;scene.render.resolution_y=600
    # Isolate every source material/region group; keep matching bounds for A and B.
    report=json.loads((OUT/'cleanup-report.json').read_text())
    for group,stats in report['groups'].items():
        source=[o for o in objects if o['variant']=='A' and o['group']==group]
        points=[v.co for o in source for v in o.data.vertices];lo=Vector([min(p[k] for p in points) for k in range(3)]);hi=Vector([max(p[k] for p in points) for k in range(3)]);center=(lo+hi)/2;dims=hi-lo
        view=Vector((1,-2,.6))
        if group=='backpack-14':view=Vector((1,2,.4))
        elif group=='arms-04':view=Vector((1,-.4,.2))
        elif group=='arms-05':view=Vector((-1,-.4,.2))
        elif group.startswith('jorge_decals-1') and group!='jorge_decals-12':view=Vector((1,1,.2))
        scene.camera.location=center+view*3;scene.camera.rotation_euler=(center-scene.camera.location).to_track_quat('-Z','Y').to_euler();scene.camera.data.ortho_scale=max(dims)*1.45
        for label in ('A','B'):visible(label,group);render(f'{label}-component-{group}')
    scene.camera.data.ortho_scale=2.9;scene.render.resolution_x=640;scene.render.resolution_y=800
    for pose in POSES:
        set_pose(rig,pose);camera(scene,'three_quarter')
        for label in ('A','B'):visible(label);render(f'{label}-pose-{pose}')
    set_pose(rig,'rest');scene.camera.data.ortho_scale=2.66
    # Color original fastener faces directly, avoiding coplanar overlay artifacts.
    selection=json.loads((OUT/'cleanup-selection.json').read_text());removed=set(selection['removed_fastener_face_ids'])
    red=bpy.data.materials.new('Removed fastener highlight');red.use_nodes=True;bs=next(n for n in red.node_tree.nodes if n.type=='BSDF_PRINCIPLED');bs.inputs['Base Color'].default_value=(.85,.025,.012,1);bs.inputs['Emission Color'].default_value=(.6,.008,.002,1);bs.inputs['Emission Strength'].default_value=.3
    visible('A')
    for ob in objects:
        if ob['variant']!='A':continue
        ob.data.materials[0]=clay;ob.data.materials.append(red)
        for face,fi in zip(ob.data.polygons,ob.data.attributes['source_face'].data):face.material_index=1 if fi.value in removed else 0
    for view in ('front','back','three_quarter'):camera(scene,view);render('removed-highlight-'+view)
    for ob in objects:
        for face in ob.data.polygons:face.material_index=0
        ob.data.materials.clear();ob.data.materials.append(original[ob.name])
    visible('B');camera(scene,'three_quarter')

def render_gauntlet_details():
    scene=next(s for s in bpy.data.scenes if any(o.get('variant')=='B' for o in s.objects));bpy.context.window.scene=scene
    objects=[o for o in scene.objects if o.type=='MESH' and 'variant' in o];scene.render.resolution_x=600;scene.render.resolution_y=600
    for side,sign in [('left',1),('right',-1)]:
        source=[o for o in objects if o['variant']=='A' and o['group']=='arms-01'];points=[v.co for o in source for v in o.data.vertices if v.co.x*sign>0]
        lo=Vector([min(p[k] for p in points) for k in range(3)]);hi=Vector([max(p[k] for p in points) for k in range(3)]);center=(lo+hi)/2
        scene.camera.location=center+Vector((sign*.7,-2,.5))*3;scene.camera.rotation_euler=(center-scene.camera.location).to_track_quat('-Z','Y').to_euler();scene.camera.data.ortho_scale=max(hi-lo)*1.45
        for label in ('A','B'):
            for o in objects:o.hide_render=not(o['variant']==label and o['group']=='arms-01')
            scene.render.filepath=str(OUT/'renders'/f'{label}-detail-{side}-gauntlet.png');bpy.ops.render.render(write_still=True)
            if side=='left':
                import shutil
                shutil.copyfile(scene.render.filepath,OUT/'renders'/f'{label}-component-arms-01.png')

if __name__=='__main__':
    import sys
    if '--inspect' in sys.argv:inspect()
    if '--build' in sys.argv:build()
    if '--export' in sys.argv:export_all()
    if '--render' in sys.argv:render_all()
    if '--details' in sys.argv:render_gauntlet_details()
