"""Fit real CE Spartan texture regions to the reduced Jorge, then bake one atlas.

The supplied source rasters stay unchanged. Recoloring/resizing/extension are
Blender material/UV operations baked through emission, not generated imagery.
"""
import bpy,json,math,hashlib,sys
import numpy as np
from pathlib import Path
from mathutils import Vector
import jorge_tactical_reduce as tactical
import jorge_animation_proof as animation
import jorge_surgical_cleanup as cleanup

ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'halo64-assets/assets/jorge';OUT=BASE/'ce-materials'
SOURCE=BASE/'tactical-5000/jorge-tactical-5000.blend'
DIFFUSE=ROOT/'build/n64/assets/model-textures-reference/spartan_2_diffuse.png'
MASK=ROOT/'build/n64/assets/model-textures-reference/spartan_2_multipurpose.png'
# Rectangles are actual CE atlas pixels, with top-left image origin.
OLIVE=(.29,.36,.13);PALE=(.49,.49,.32);RED=(.40,.095,.055);OCHRE=(.65,.38,.075)
PATCHES=[
 ('olive_plate',(130,274,166,341),OLIVE,'armor'),
 ('olive_shoulder',(7,4,137,114),OLIVE,'armor'),
 ('helmet',(211,50,364,121),OLIVE,'armor'),
 ('ochre_chest',(387,95,507,216),OCHRE,'armor'),
 ('red_shoulder_collar',(7,4,137,114),RED,'armor'),
 ('pale_heavy_shoulder',(7,4,137,114),PALE,'armor'),
 ('forearm',(7,126,182,212),OLIVE,'armor'),
 ('shin',(6,435,211,508),OLIVE,'armor'),
 ('thigh',(10,247,227,379),OLIVE,'armor'),
 ('mechanical',(18,389,117,424),(.14,.16,.17),'rubber'),
 ('undersuit',(15,387,151,425),(.16,.18,.20),'rubber'),
 ('gloves',(254,202,401,275),(.23,.25,.22),'glove'),
 ('backpack',(387,95,507,216),(.25,.30,.12),'armor'),
 ('vent',(144,1,278,17),(.14,.16,.17),'rubber'),
 ('visor',(298,110,353,146),(.95,.59,.09),'visor'),
 ('plain_dark',(39,407,115,423),(.14,.16,.17),'rubber'),
]

def math_node(ns,ls,operation,a,b=None):
    n=ns.new('ShaderNodeMath');n.operation=operation
    for i,value in enumerate((a,b)):
        if value is None:continue
        if isinstance(value,(float,int)):n.inputs[i].default_value=value
        else:ls.new(value,n.inputs[i])
    return n.outputs[0]

def donor_material(index,diffuse,mask,atlas):
    name,rect,tint,kind=PATCHES[index];mat=bpy.data.materials.new('CE donor / '+name);mat.use_nodes=True;ns=mat.node_tree.nodes;ls=mat.node_tree.links;ns.clear()
    uv=ns.new('ShaderNodeUVMap');uv.uv_map='Donor UV';tex=ns.new('ShaderNodeTexImage');tex.image=diffuse;tex.interpolation='Linear';ls.new(uv.outputs[0],tex.inputs['Vector'])
    m=ns.new('ShaderNodeTexImage');m.image=mask;m.interpolation='Linear';ls.new(uv.outputs[0],m.inputs['Vector']);sep=ns.new('ShaderNodeSeparateColor');ls.new(m.outputs['Color'],sep.inputs[0]);rgb=ns.new('ShaderNodeSeparateColor');ls.new(tex.outputs['Color'],rgb.inputs[0])
    gr=math_node(ns,ls,'SUBTRACT',rgb.outputs['Green'],rgb.outputs['Red']);gb=math_node(ns,ls,'SUBTRACT',rgb.outputs['Green'],rgb.outputs['Blue'])
    green=math_node(ns,ls,'MULTIPLY',math_node(ns,ls,'GREATER_THAN',gr,.012),math_node(ns,ls,'GREATER_THAN',gb,.006))
    clean=ns.new('ShaderNodeMixRGB');ls.new(green,clean.inputs[0]);ls.new(tex.outputs['Color'],clean.inputs[1]);clean.inputs[2].default_value=(.60,.60,.60,1)
    if kind=='armor':
        paint=ns.new('ShaderNodeMixRGB');ls.new(math_node(ns,ls,'MAXIMUM',sep.outputs['Blue'],green),paint.inputs[0]);paint.inputs[1].default_value=(1,1,1,1);paint.inputs[2].default_value=(*tint,1)
        color=ns.new('ShaderNodeMixRGB');color.blend_type='MULTIPLY';color.inputs[0].default_value=1;ls.new(clean.outputs[0],color.inputs[1]);ls.new(paint.outputs[0],color.inputs[2]);result=color.outputs[0]
    elif kind=='visor':
        bw=ns.new('ShaderNodeRGBToBW');ls.new(tex.outputs['Color'],bw.inputs[0]);level=math_node(ns,ls,'ADD',math_node(ns,ls,'MULTIPLY',bw.outputs[0],.25),.72)
        color=ns.new('ShaderNodeMixRGB');color.blend_type='MULTIPLY';color.inputs[0].default_value=1;color.inputs[1].default_value=(*tint,1);ls.new(level,color.inputs[2]);result=color.outputs[0]
    else:
        # Keep the CE rubber pattern, lifting only its nearly black floor.
        bw=ns.new('ShaderNodeRGBToBW');ls.new(tex.outputs['Color'],bw.inputs[0]);level=math_node(ns,ls,'ADD',math_node(ns,ls,'MULTIPLY',bw.outputs[0],1.7),.12 if kind=='rubber' else .08)
        color=ns.new('ShaderNodeMixRGB');color.blend_type='MULTIPLY';color.inputs[0].default_value=1;color.inputs[1].default_value=(*tint,1);ls.new(level,color.inputs[2]);result=color.outputs[0]
    em=ns.new('ShaderNodeEmission');ls.new(result,em.inputs['Color']);out=ns.new('ShaderNodeOutputMaterial');ls.new(em.outputs[0],out.inputs['Surface'])
    target=ns.new('ShaderNodeTexImage');target.image=atlas
    for n in ns:n.select=False
    target.select=True;ns.active=target;return mat

def bake_atlas():
    OUT.mkdir(exist_ok=True);(OUT/'textures').mkdir(exist_ok=True);scene=bpy.data.scenes.new('CE donor atlas bake');bpy.context.window.scene=scene;scene.render.engine='CYCLES';scene.cycles.samples=1
    diffuse=bpy.data.images.load(str(DIFFUSE),check_existing=True);diffuse.alpha_mode='NONE';mask=bpy.data.images.load(str(MASK),check_existing=True);mask.colorspace_settings.name='Non-Color';mask.alpha_mode='NONE'
    atlas=bpy.data.images.new('Jorge CE atlas - 256',256,256,alpha=False);atlas.colorspace_settings.name='sRGB'
    verts=[];faces=[]
    for i in range(16):
        x=i%4;y=3-i//4;at=len(verts);verts.extend([(x,y,0),(x+1,y,0),(x+1,y+1,0),(x,y+1,0)]);faces.append(tuple(range(at,at+4)))
    me=bpy.data.meshes.new('CE atlas bake tiles');me.from_pydata(verts,[],faces);uv=me.uv_layers.new(name='Donor UV');dest=me.uv_layers.new(name='CE Atlas UV')
    for i,face in enumerate(me.polygons):
        mat=donor_material(i,diffuse,mask,atlas);me.materials.append(mat);face.material_index=i;x0,y0,x1,y1=PATCHES[i][1]
        coords=[(x0/512,1-y1/512),(x1/512,1-y1/512),(x1/512,1-y0/512),(x0/512,1-y0/512)]
        for li,co in zip(face.loop_indices,coords):uv.data[li].uv=co;v=me.vertices[me.loops[li].vertex_index].co;dest.data[li].uv=(v.x/4,v.y/4)
    me.uv_layers.active=dest;ob=bpy.data.objects.new('CE atlas bake plane',me);scene.collection.objects.link(ob);ob.select_set(True);bpy.context.view_layer.objects.active=ob
    bpy.ops.object.bake(type='EMIT',margin=0,use_clear=True);atlas.filepath_raw=str(OUT/'textures/jorge-ce-atlas-256.png');atlas.file_format='PNG';atlas.save();atlas.pack()
    print('BAKED CE ATLAS',atlas.filepath_raw,flush=True);return atlas

def material(atlas,visor=False):
    mat=bpy.data.materials.new('CE Jorge / '+('visor' if visor else 'armor and undersuit'));mat.use_nodes=True;ns=mat.node_tree.nodes;ls=mat.node_tree.links;bs=next(n for n in ns if n.type=='BSDF_PRINCIPLED')
    tex=ns.new('ShaderNodeTexImage');tex.image=atlas;tex.interpolation='Linear';ls.new(tex.outputs['Color'],bs.inputs['Base Color']);bs.inputs['Roughness'].default_value=.3 if visor else .82;bs.inputs['Metallic'].default_value=.28 if visor else 0
    mat['source']='Halo CE Spartan cyborg diffuse + original multipurpose blue armor mask';return mat

def slot_for(ob):
    group=ob['group'];part=int(ob['source_component'].split(':')[-1])
    if group=='body-06':return 14
    if group=='body-03':return 2 if part==0 else (0 if part==1 else 15)
    if group=='body-00':return 3 if part==0 else 9
    if group=='body-02':return 4 if part==2 else (7 if part<2 else (0 if part<5 else 13))
    if group=='arms-04':return 5 if part==0 else 9
    if group=='arms-05':return 4
    if group=='arms-01':return 6 if part<2 else (0 if part<6 else 9)
    if group=='arms-07':return 6 if part<2 else (5 if part<4 else 9)
    if group=='arms-08':return 11
    if group=='arms-09':return 1 if part<2 else 9
    if group=='arms-10':return 10
    if group=='body-10':return 10 if part<7 else 9
    if group=='body-09':
        if part==0:return 0
        if part==1:return 0
        if part in (2,3):return 7
        if part in (4,5):return 8
        if 6<=part<=11:return 0 if part<8 else 7
        return 9 if part in (15,16,17,20,21,22,23) else 0
    if group=='backpack-14':return 12 if part==0 else 9
    raise ValueError(group)

def remap_uv(ob,slot):
    vertices=np.array([v.co for v in ob.data.vertices]);center=vertices.mean(axis=0);cov=(vertices-center).T@(vertices-center);values,axes=np.linalg.eigh(cov);axes=axes[:,np.argsort(values)[::-1]]
    a,b=axes[:,0],axes[:,1]
    # Keep vertical motifs upright where possible; otherwise follow the plate.
    if abs(a[2])>abs(b[2]):u,v=b,a
    else:u,v=a,b
    if v[2]<0:v=-v
    if u[0]<0:u=-u
    coordinates=np.stack(((vertices-center)@u,(vertices-center)@v),axis=1);lo=coordinates.min(axis=0);span=np.maximum(coordinates.max(axis=0)-lo,1e-6);normalized=(coordinates-lo)/span
    x=slot%4;y=3-slot//4;uv=ob.data.uv_layers.active;uv.name='CE Atlas UV';pad=3/64
    for loop in ob.data.loops:
        a,b=normalized[loop.vertex_index];uv.data[loop.index].uv=((x+pad+a*(1-2*pad))/4,(y+pad+b*(1-2*pad))/4)
    return {'projection_u':u.tolist(),'projection_v':v.tolist(),'center_m':center.tolist(),'span_m':span.tolist(),'donor':PATCHES[slot][0],'tile':slot}

def build():
    atlas=bake_atlas();source,original_rig=tactical.proof_scene();scene=bpy.data.scenes.new('Jorge - CE texture simplification');bpy.context.window.scene=scene;scene.render.fps=30
    rig=original_rig.copy();rig.data=original_rig.data.copy();rig.name='Jorge CE materials - shared rig';scene.collection.objects.link(rig);rig.hide_set(True)
    body_mat=material(atlas);visor_mat=material(atlas,True);records=[];omitted=[];body=[]
    for ob in source.objects:
        if ob.type!='MESH':continue
        if ob.get('group','').startswith('jorge_decals'):
            omitted.append({'component':ob['source_component'],'triangles':len(ob.data.polygons),'reason':'Retired Reach-specific alpha decal overlay during CE material simplification'});continue
        new=ob.copy();new.data=ob.data.copy();scene.collection.objects.link(new);new.parent=rig;new.hide_set(False);new.hide_render=False
        for mod in new.modifiers:
            if mod.type=='ARMATURE':mod.object=rig
        if ob.get('reduction_variant')=='tactical_5000':
            new.name='CE / '+ob.name;new['texture_variant']='ce_spartan';slot=slot_for(ob);info=remap_uv(new,slot);new['ce_donor']=PATCHES[slot][0];new['ce_tile']=slot;new.data.materials.clear();new.data.materials.append(visor_mat if slot==14 else body_mat)
            for f in new.data.polygons:f.material_index=0
            assert all(tuple(a.co)==tuple(b.co) for a,b in zip(ob.data.vertices,new.data.vertices));assert [tuple(f.vertices) for f in ob.data.polygons]==[tuple(f.vertices) for f in new.data.polygons]
            records.append({'component':ob['source_component'],'triangles':len(new.data.polygons),**info});body.append(new)
        else:new.name='CE rifle - unchanged preview attachment'
    cleanup.studio(scene);scene.camera.data.ortho_scale=2.95;scene.frame_start=0;scene.frame_end=230;scene.frame_set(0)
    report={'source_blend_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'donor_images':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (DIFFUSE,MASK)},'atlas_resolution':[256,256],'body_materials':2,'body_images':1,'normal_maps':0,'retained_geometry_unchanged':True,'bones':len(rig.data.bones),'components':records,'retired_decal_overlays':omitted,'body_triangles':sum(len(o.data.polygons) for o in body),'body_mesh_vertices':sum(len(o.data.vertices) for o in body),'patches':[{'name':n,'source_rectangle_pixels':r,'linear_tint':t,'kind':k} for n,r,t,k in PATCHES]}
    (OUT/'material-report.json').write_text(json.dumps(report,indent=2)+'\n');bpy.data.libraries.write(str(OUT/'jorge-ce-materials.blend'),{scene,*bpy.data.actions},fake_user=True)
    print('BUILT CE JORGE',{k:v for k,v in report.items() if k in ('body_triangles','body_mesh_vertices','body_materials','body_images','bones')},flush=True)

def proof_scene():
    scene=next(s for s in bpy.data.scenes if s.name.startswith('Jorge - CE texture simplification'));bpy.context.window.scene=scene;rig=next(o for o in scene.objects if o.type=='ARMATURE');return scene,rig

def render():
    scene,rig=proof_scene();folder=OUT/'renders';folder.mkdir(exist_ok=True);scene.render.resolution_x=600;scene.render.resolution_y=750;scene.cycles.samples=16;scene.cycles.use_denoising=True
    for name,fraction in [('idle',0),('run',.25),('run',.5),('reload',.4),('reload',.8)]:
        action=next(a for a in bpy.data.actions if a.get('source_clip')==name);animation.select_clip(scene,rig,name,action['duration_seconds']*fraction)
        for view in (('front','back','left','right','three_quarter') if name=='idle' else ('three_quarter',)):
            cleanup.camera(scene,view);scene.render.filepath=str(folder/f'ce-{name}-{round(fraction*100):03d}-{view}.png');bpy.ops.render.render(write_still=True)
    print('CE MATERIAL RENDERS COMPLETE',flush=True)

def export():
    # Background-only: preserve the live user's current .blend and older assets.
    scene,rig=proof_scene();animation.select_clip(scene,rig,'idle');rig.hide_set(False)
    for ob in scene.objects:ob.select_set(ob.type in ('MESH','ARMATURE'))
    bpy.context.view_layer.objects.active=rig
    options=dict(export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIONS',export_force_sampling=True,export_frame_range=False,export_frame_step=1,export_skins=True,export_extras=True)
    bpy.ops.export_scene.gltf(filepath=str(OUT/'jorge-ce-materials-with-rifle.glb'),**options)
    for ob in scene.objects:
        if ob.type=='MESH' and ob.get('texture_variant')!='ce_spartan':ob.select_set(False)
    bpy.ops.export_scene.gltf(filepath=str(OUT/'jorge-ce-materials.glb'),**options)
    rig.animation_data.action=None;rig.animation_data.use_nla=True;scene.frame_start=0;scene.frame_end=230;scene.frame_set(0);rig.hide_set(True)
    for marker in list(scene.timeline_markers):scene.timeline_markers.remove(marker)
    for name,frame in [('IDLE',0),('RUN',60),('FIRE',123),('RELOAD',143)]:scene.timeline_markers.new(name,frame=frame)
    cleanup.camera(scene,'three_quarter');scene.camera.data.ortho_scale=2.95
    for ob in scene.objects:ob.select_set(False)
    prepare_viewport()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'jorge-ce-materials.blend'))
    print('CE MATERIAL EXPORT COMPLETE',flush=True)

def prepare_viewport():
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type!='VIEW_3D':continue
            space=area.spaces.active
            modes=[i.identifier for i in space.shading.bl_rna.properties['type'].enum_items]
            if 'MATERIAL' in modes:space.shading.type='MATERIAL'
            space.overlay.show_overlays=False;space.region_3d.view_location=(0,-.05,1.15);space.region_3d.view_distance=3.7;space.region_3d.view_rotation=Vector((4,-6,2.3)).to_track_quat('Z','Y')

if __name__=='__main__':
    if '--build' in sys.argv:build()
    if '--export' in sys.argv:export()
    if '--render' in sys.argv:render()
    if '--motion' in sys.argv:
        animation.OUT=OUT;animation.proof_scene=proof_scene;animation.render_motion()
    if '--presentation' in sys.argv:
        proof_scene();prepare_viewport();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'jorge-ce-materials.blend'))
