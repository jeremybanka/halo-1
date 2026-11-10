"""Refine the accepted low-poly Jorge without another global reduction.

Central shells get mirrored topology; the backpack recovers its authored upper
shoulders. CE-derived broad metallic color ramps survive as GLB vertex colors
and exactly the same RGB samples in the N64 bank. Old checkpoints stay intact.
"""
import bpy, bmesh, json, sys, shutil, hashlib
import numpy as np
from mathutils import Vector
import jorge_playable_reduce as task
import jorge_solid_reduce as solid
import jorge_half_budget as half
import jorge_surgical_cleanup as cleanup

ROOT=task.ROOT; SOURCE=task.OUT/(task.NAME+'.blend')
OUT=task.BASE/'playable-refined'; NAME='jorge-playable-refined'
SCENE='Jorge - metallic armor and restored forms'; COLOR='CE metallic armor'
# Small source faces exposed by game-grid coverage checks, reflected as pairs.
SEAMS={'body-00:000':[27],'backpack-14:000':[10,13,15,32,48],'body-09:000':[64]}

def configure():
    task.OUT=OUT; task.NAME=NAME; task.SCENE=SCENE
    return task

def mirror_shell(ob, positive=True):
    """Bisect one existing shell and mirror its UVs/weights across the midline."""
    bm=bmesh.new();bm.from_mesh(ob.data)
    bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=1e-6,
        plane_co=(0,0,0),plane_no=(1,0,0),clear_inner=positive,clear_outer=not positive)
    # Center-plane closing faces would otherwise become doubled internal faces.
    bmesh.ops.delete(bm,geom=[f for f in bm.faces if all(abs(v.co.x)<1e-6 for v in f.verts)],context='FACES')
    bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
    bmesh.ops.triangulate(bm,faces=list(bm.faces));bm.to_mesh(ob.data);bm.free()
    for o in bpy.context.selected_objects:o.select_set(False)
    ob.select_set(True);bpy.context.view_layer.objects.active=ob
    mod=ob.modifiers.new('Matched center shell','MIRROR');mod.use_mirror_merge=True;mod.merge_threshold=.00001
    # Explicit Halo bone names are not Blender's .L/.R convention.
    mod.use_mirror_vertex_groups=False
    bpy.ops.object.modifier_move_up(modifier=mod.name);bpy.ops.object.modifier_apply(modifier=mod.name)
    names={g.index:g.name for g in ob.vertex_groups}
    for v in ob.data.vertices:
        if (v.co.x<0)==positive:
            weights=[(names[g.group],g.weight) for g in v.groups]
            for g in ob.vertex_groups:g.remove([v.index])
            for name,w in weights:
                name=name.replace('b_l_','b_SWAP_').replace('b_r_','b_l_').replace('b_SWAP_','b_r_')
                (ob.vertex_groups.get(name) or ob.vertex_groups.new(name=name)).add([v.index],w,'REPLACE')
    half.clean_geometry(ob)
    return len(ob.data.vertices)

def material(name, visor=False):
    m=bpy.data.materials.new(name);m.use_nodes=True
    bs=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    c=m.node_tree.nodes.new('ShaderNodeVertexColor');c.layer_name=COLOR
    m.node_tree.links.new(c.outputs['Color'],bs.inputs['Base Color'])
    bs.inputs['Metallic'].default_value=.65 if visor else .35
    bs.inputs['Roughness'].default_value=.3 if visor else .48
    return m

def retain_seams(ob,source,names,indices):
    old=ob.data;verts=[v.co.copy() for v in old.vertices];faces=[tuple(p.vertices) for p in old.polygons]
    uv=[u.uv.copy() for u in old.uv_layers.active.data]
    weights=[[(ob.vertex_groups[g.group].name,g.weight) for g in v.groups] for v in old.vertices]
    for sign in (1,-1):
        mapped={}
        for fi in indices:
            p=source.polygons[fi];face=[];coords=[]
            for li,vi in zip(p.loop_indices,p.vertices):
                if vi not in mapped:
                    mapped[vi]=len(verts);v=source.vertices[vi];verts.append(Vector((v.co.x*sign,v.co.y,v.co.z)))
                    ws=[]
                    for g in v.groups:
                        name=names[g.group]
                        if sign<0:name=name.replace('b_l_','b_SWAP_').replace('b_r_','b_l_').replace('b_SWAP_','b_r_')
                        ws.append((name,g.weight))
                    weights.append(ws)
                face.append(mapped[vi]);coords.append(source.uv_layers.active.data[li].uv.copy())
            if sign<0:face.reverse();coords.reverse()
            faces.append(face);uv.extend(coords)
    me=bpy.data.meshes.new(old.name+' / paired seam backing');me.from_pydata(verts,[],faces)
    for m in old.materials:me.materials.append(m)
    layer=me.uv_layers.new(name=old.uv_layers.active.name)
    for a,b in zip(layer.data,uv):a.uv=b
    ob.data=me
    for g in ob.vertex_groups:g.remove(list(range(len(verts))))
    for i,ws in enumerate(weights):
        for name,w in ws:(ob.vertex_groups.get(name) or ob.vertex_groups.new(name=name)).add([i],w,'REPLACE')
    return len(verts)-len(old.vertices)

def paint(obs):
    image=bpy.data.images.load(str(OUT/'textures/jorge-ce-atlas-256.png'),check_existing=True)
    pixels=np.array(image.pixels[:]).reshape(image.size[1],image.size[0],4)
    # Loaded PNG pixel samples are sRGB. Assign through color_srgb so Blender
    # stores linear vertex colors and the ROM retrieves the original RGB scale.
    mats=[material('Jorge CE metallic plates'),material('Jorge gold visor',True)]
    rows=[]
    for ob in obs:
        me=ob.data;key=ob['source_component'];tile=ob['ce_tile']
        is_armor=tile in (0,1,2,3,4,5,6,7,8,12)
        lo=np.min([v.co[:] for v in me.vertices],axis=0);hi=np.max([v.co[:] for v in me.vertices],axis=0)
        spans=np.maximum(hi-lo,.001)
        ca=me.color_attributes.get(COLOR) or me.color_attributes.new(name=COLOR,type='FLOAT_COLOR',domain='CORNER')
        me.color_attributes.active_color=ca
        for loop,c in zip(me.loops,ca.data):
            u,v=me.uv_layers.active.data[loop.index].uv
            x=np.clip(u*image.size[0]-.5,0,image.size[0]-1);y=np.clip(v*image.size[1]-.5,0,image.size[1]-1)
            ix,iy=int(x),int(y);fx,fy=x-ix,y-iy
            rgb=(pixels[iy,ix,:3]*(1-fx)+pixels[iy,min(ix+1,image.size[0]-1),:3]*fx)*(1-fy)+(pixels[min(iy+1,image.size[1]-1),ix,:3]*(1-fx)+pixels[min(iy+1,image.size[1]-1),min(ix+1,image.size[0]-1),:3]*fx)*fy
            p=me.vertices[loop.vertex_index].co;t=(p.z-lo[2])/spans[2]
            if tile==14:rgb=np.array((1,224/255,18/255))
            elif is_armor and not(tile==2 and max(rgb)-min(rgb)<.025):
                # Broad, restrained reflection band, anchored to each plate.
                # Normal response is symmetric, avoiding one bright/one dull side.
                n=me.vertices[loop.vertex_index].normal
                facing=max(0,-n.y)*.35+max(0,n.z)*.2
                band=np.exp(-((t-.72)/.24)**2)
                gain=.36+.56*t+.85*band+facing
                rgb=rgb*gain
                rgb+=np.array((.12,.135,.15))*band*max(0,facing)*.55
            c.color_srgb=(*np.clip(rgb,0,1),1)
        me.materials.clear();me.materials.append(mats[int(tile==14)])
        for p in me.polygons:p.material_index=0
        ob['color_source']='CE donor atlas with broad per-plate metallic gradient'
        rows.append({'component':key,'armor_gradient':is_armor,'min_rgb':np.min([c.color_srgb[:3] for c in ca.data],axis=0).tolist(),'max_rgb':np.max([c.color_srgb[:3] for c in ca.data],axis=0).tolist()})
    return rows

def build():
    OUT.mkdir(exist_ok=True);(OUT/'textures').mkdir(exist_ok=True)
    shutil.copy2(SOURCE.parent/'textures/jorge-ce-atlas-256.png',OUT/'textures/jorge-ce-atlas-256.png')
    shutil.copy2(SOURCE.parent/'ce-motion-source.json',OUT/'ce-motion-source.json')
    scene,rig=task.proof_scene();scene.name=SCENE;configure();obs=task.body(scene);by={o['source_component']:o for o in obs}
    old_surfaces={k:(by[k].data.copy(),{g.index:g.name for g in by[k].vertex_groups}) for k in SEAMS}
    report={'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'source':str(SOURCE.relative_to(ROOT)),'changes':[]}
    for key in ('body-00:000','body-09:001','body-09:000','body-09:013'):
        ob=by[key];before=len(ob.data.vertices);mirror_shell(ob)
        report['changes'].append({'component':key,'method':'Mirror original positive half with matched center seam','before_vertices':before,'vertices':len(ob.data.vertices)})
    # Go back before either destructive reduction: the 199-vertex shell keeps
    # the broad shoulder volume and recessed center of the original backpack.
    backpack_source=task.BASE/'detail-pass/jorge-detail-pass.blend'
    with bpy.data.libraries.load(str(backpack_source),link=False) as (src,dst):
        dst.objects=['Detail pass / backpack-14:000']
    original=dst.objects[0]
    ob=by['backpack-14:000'];before=len(ob.data.vertices);ob.data=original.data.copy()
    # This plate is rigid; source datablock group indices belong to its old
    # object. Rebind explicitly instead of inheriting those numeric indices.
    ob.vertex_groups.clear();group=ob.vertex_groups.new(name='b_backpack')
    bm=bmesh.new();bm.from_mesh(ob.data);deform=bm.verts.layers.deform.verify()
    for v in bm.verts:v[deform].clear();v[deform][group.index]=1.
    bm.to_mesh(ob.data);bm.free()
    # Preserve the upper shoulder outline; only broad lower faces can collapse.
    freedom=ob.vertex_groups.new(name='Backpack lower surface freedom')
    for v in ob.data.vertices:freedom.add([v.index],1. if v.co.z<1.92 else .15,'REPLACE')
    for o in bpy.context.selected_objects:o.select_set(False)
    ob.select_set(True);bpy.context.view_layer.objects.active=ob
    mod=ob.modifiers.new('Lower backpack economy','DECIMATE');mod.ratio=.4;mod.use_collapse_triangulate=True;mod.vertex_group=freedom.name;mod.vertex_group_factor=100
    bpy.ops.object.modifier_move_up(modifier=mod.name);bpy.ops.object.modifier_apply(modifier=mod.name)
    ob.vertex_groups.remove(ob.vertex_groups['Backpack lower surface freedom']);mirror_shell(ob)
    report['changes'].append({'component':'backpack-14:000','method':'Restore authored upper volume from detail-pass; protected top, reduced lower faces, mirrored shell','before_vertices':before,'vertices':len(ob.data.vertices),'source_sha256':hashlib.sha256(backpack_source.read_bytes()).hexdigest()})
    # Keep the accepted overlapping coverage after restoring smaller source
    # surfaces. A symmetric fit avoids tiny animated armor-to-fabric cracks.
    for key,factor,cap in [('backpack-14:000',.05,.016),('body-00:000',.025,.008),('body-09:001',.025,.008)]:
        ob=by[key];center=sum((v.co for v in ob.data.vertices),Vector())/len(ob.data.vertices);center.x=0
        for v in ob.data.vertices:
            delta=(v.co-center)*factor
            if delta.length>cap:delta=delta.normalized()*cap
            v.co+=delta
    report['paired_seam_backings']=[]
    for key,indices in SEAMS.items():
        added=retain_seams(by[key],*old_surfaces[key],indices)
        report['paired_seam_backings'].append({'component':key,'source_faces':indices,'vertices_added':added,'triangles_added':len(indices)*2})
    for ob in obs:
        # Clear old custom normals after editing, retain intended broad curvature.
        if ob['source_component'] in {r['component'] for r in report['changes']}:
            ob.data.normals_split_custom_set([(0,0,0)]*len(ob.data.loops))
            for p in ob.data.polygons:p.use_smooth=True
            ob.data.update()
        assert all(abs(sum(g.weight for g in v.groups)-1)<1e-5 for v in ob.data.vertices),ob.name
    report['paint']=paint(obs);report['native_vertices']=sum(len(o.data.vertices) for o in obs);report['triangles']=sum(len(o.data.polygons) for o in obs)
    (OUT/'refinement-report.json').write_text(json.dumps(report,indent=2)+'\n')
    rig.animation_data.action=None;rig.animation_data.use_nla=True;scene.frame_set(0)
    bpy.data.libraries.write(str(OUT/(NAME+'.blend')),{scene,*bpy.data.actions},fake_user=True,compress=True)
    print('REFINED',report['native_vertices'],report['triangles'],report['changes'],flush=True)

if __name__=='__main__':
    if '--build' in sys.argv:build()
    else:configure()
    if '--bake' in sys.argv:
        import bake_jorge_playable as bake
        bake.OUT=OUT;bake.run()
    if '--export' in sys.argv:task.export()
    if '--render' in sys.argv:
        import preview_jorge_playable as preview
        preview.OUT=OUT;preview.run()
