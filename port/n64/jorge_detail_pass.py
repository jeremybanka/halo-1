"""Restore Jorge's graphic identity, quiet the CE atlas, cull reviewed fittings.

No collapse/decimation: retained surface topology and skinning stay exact.
The original helmet paint mask restores the black band, shaded with CE pixels.
"""
import bpy,json,sys,hashlib
from pathlib import Path
from mathutils import Vector
import jorge_ce_materials as ce
import jorge_animation_proof as animation
import jorge_surgical_cleanup as cleanup

ROOT=ce.ROOT;BASE=ce.BASE;OUT=BASE/'detail-pass';SOURCE=BASE/'ce-materials/jorge-ce-materials.blend'
HELMET_SOURCE=BASE/'tactical-5000/jorge-tactical-5000.blend'
HELMET_MASK=BASE/'textures/4170_helmet_cc.png'
NAME='jorge-detail-pass';SCENE='Jorge - colors and surgical detail pass'
# Reviewed components, not a global area/triangle threshold.
CULL={}
for group,parts,reason in [
    ('arms-01',range(6,14),'Small buckle blocks on retained gauntlet straps'),
    ('arms-07',range(4,12),'Small forearm fasteners on retained armor plates'),
    ('arms-09',(2,3),'Small upper-arm mounting tabs beneath the shoulders'),
    ('body-00',range(3,7),'Small hinge ribs on retained chest couplings'),
    ('body-02',range(5,9),'Small calf fasteners on retained calf armor'),
    ('body-03',(3,4),'Paired small chin fittings; helmet shell and brow retained'),
    ('body-09',range(20,24),'Small plugs on retained spine mechanisms'),
    ('backpack-14',(2,3,4),'Shallow circular side caps; backpack body and lower connector retained'),
]:
    for part in parts:CULL[f'{group}:{part:03d}']=reason

ORIGINAL_DONOR=ce.donor_material
def quiet_donor(index,diffuse,mask,atlas):
    mat=ORIGINAL_DONOR(index,diffuse,mask,atlas);ns=mat.node_tree.nodes;ls=mat.node_tree.links
    em=next(n for n in ns if n.type=='EMISSION');source=next(n for n in ns if n.type=='TEX_IMAGE' and n.image==diffuse)
    bw=ns.new('ShaderNodeRGBToBW');ls.new(source.outputs['Color'],bw.inputs[0]);name,rect,tint,kind=ce.PATCHES[index]
    # Keep a restrained amount of real CE shading; eliminate printed undersuit
    # shapes and high-contrast panel motifs from the broad armor surfaces.
    if kind=='armor':floor,contrast=.58,.12
    elif kind=='visor':floor,contrast=.76,.035
    elif kind=='glove':floor,contrast=.19,.08
    else:floor,contrast=.14,.08
    level=ce.math_node(ns,ls,'ADD',ce.math_node(ns,ls,'MULTIPLY',bw.outputs[0],contrast),floor)
    color=ns.new('ShaderNodeMixRGB');color.blend_type='MULTIPLY';color.inputs[0].default_value=1;color.inputs[1].default_value=(*tint,1);ls.new(level,color.inputs[2]);result=color.outputs[0]
    if index==2:
        uv=ns.new('ShaderNodeUVMap');uv.uv_map='Donor UV';scale=ns.new('ShaderNodeVectorMath');scale.operation='SCALE';scale.inputs['Scale'].default_value=1/(1-6/64);ls.new(uv.outputs[0],scale.inputs[0])
        offset=ns.new('ShaderNodeVectorMath');offset.operation='ADD';ls.new(scale.outputs[0],offset.inputs[0]);offset.inputs[1].default_value=(-3/58,-3/58,0)
        tex=ns.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(HELMET_MASK),check_existing=True);tex.image.colorspace_settings.name='Non-Color';tex.extension='EXTEND';ls.new(offset.outputs[0],tex.inputs['Vector'])
        separate=ns.new('ShaderNodeSeparateColor');ls.new(tex.outputs['Color'],separate.inputs[0]);mix=ns.new('ShaderNodeMixRGB');ls.new(separate.outputs['Red'],mix.inputs[0]);mix.inputs[1].default_value=(.028,.032,.034,1);ls.new(result,mix.inputs[2]);result=mix.outputs[0]
    for link in list(em.inputs['Color'].links):ls.remove(link)
    ls.new(result,em.inputs['Color']);return mat

def atlas():
    ce.OUT=OUT;ce.PATCHES=list(ce.PATCHES)
    ce.PATCHES[2]=('helmet_original_paint_layout',(0,0,512,512),ce.OLIVE,'armor')
    ce.PATCHES[12]=('gray_brown_backpack',(387,95,507,216),(.30,.265,.22),'armor')
    ce.donor_material=quiet_donor
    image=ce.bake_atlas();image.name='Jorge quiet CE atlas - 256'
    return image

def body(scene):return [o for o in scene.objects if o.get('texture_variant')=='ce_spartan']

def proof_scene():
    scene=next(s for s in bpy.data.scenes if s.name.startswith(SCENE));bpy.context.window.scene=scene
    return scene,next(o for o in scene.objects if o.type=='ARMATURE')

def build():
    OUT.mkdir(exist_ok=True);source,old_rig=ce.proof_scene();texture=atlas()
    with bpy.data.libraries.load(str(HELMET_SOURCE),link=False) as (src,dst):dst.objects=[n for n in src.objects if '/ Helmet /' in n]
    helmets={o['source_component']:o for o in dst.objects if o and o.get('source_component')}
    scene=bpy.data.scenes.new(SCENE);bpy.context.window.scene=scene;scene.render.fps=30
    rig=old_rig.copy();rig.data=old_rig.data.copy();rig.name='Jorge detail pass - preserved CE animation rig';scene.collection.objects.link(rig);rig.hide_set(True)
    mats=[ce.material(texture),ce.material(texture,True)];removed=[];retained=[]
    for ob in source.objects:
        if ob.type!='MESH':continue
        key=ob.get('source_component')
        if key in CULL:
            removed.append({'component':key,'reason':CULL[key],'triangles':len(ob.data.polygons),'vertices':len(ob.data.vertices)});continue
        new=ob.copy();new.data=ob.data.copy();scene.collection.objects.link(new);new.parent=rig;new.hide_set(False);new.hide_render=False
        for mod in new.modifiers:
            if mod.type=='ARMATURE':mod.object=rig
        if key:
            new.name='Detail pass / '+key;new['detail_variant']='surgical_fittings';new.data.materials.clear();new.data.materials.append(mats[int(ob['group']=='body-06')])
            for f in new.data.polygons:f.material_index=0
            if key in helmets:
                src=helmets[key];assert len(new.data.loops)==len(src.data.loops)
                for a,b in zip(new.data.uv_layers.active.data,src.data.uv_layers.active.data):a.uv=((2+3/64+b.uv.x*(1-6/64))/4,(3+3/64+b.uv.y*(1-6/64))/4)
                new['ce_tile']=2;new['ce_donor']='CE shading with original helmet paint mask'
            new['next_reduction_priority']='protect identity' if ob['group'] in ('body-03','body-06','arms-04','arms-05','body-02','backpack-14') else ('deformation-sensitive' if ob['group'] in ('body-10','arms-08','arms-10') else 'armor surface')
            retained.append({'component':key,'triangles':len(new.data.polygons),'vertices':len(new.data.vertices),'priority':new['next_reduction_priority']})
        else:new.name='CE rifle - unchanged preview attachment'
    cleanup.studio(scene);scene.camera.data.ortho_scale=2.95;scene.frame_start=0;scene.frame_end=230;scene.frame_set(0)
    report={'source_blend_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'helmet_uv_source_sha256':hashlib.sha256(HELMET_SOURCE.read_bytes()).hexdigest(),'source_images':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ce.DIFFUSE,ce.MASK,HELMET_MASK)},'method':'Exact retained meshes; explicit detail component removal; low-contrast CE atlas; original helmet paint mask and UV layout restore black band','before':{'components':len(body(source)),'triangles':sum(len(o.data.polygons) for o in body(source)),'vertices':sum(len(o.data.vertices) for o in body(source))},'after':{'components':len(retained),'triangles':sum(r['triangles'] for r in retained),'vertices':sum(r['vertices'] for r in retained)},'removed':removed,'retained':retained,'atlas':{'resolution':[256,256],'materials':2,'normal_maps':0,'armor_luminance':'0.58 + 0.12 * CE diffuse luminance','backpack_linear_tint':[.30,.265,.22],'helmet_dark_linear_rgb':[.028,.032,.034]},'global_decimation':False}
    assert set(CULL)=={r['component'] for r in removed}
    actions={strip.action for track in rig.animation_data.nla_tracks for strip in track.strips if strip.action}
    (OUT/'detail-report.json').write_text(json.dumps(report,indent=2)+'\n');bpy.data.libraries.write(str(OUT/(NAME+'.blend')),{scene,*actions},fake_user=True)
    print('DETAIL PASS BUILT',report['before'],report['after'],flush=True)

def render():
    ce.OUT=OUT;ce.proof_scene=proof_scene;ce.render()

def export():
    scene,rig=proof_scene();animation.select_clip(scene,rig,'idle');rig.hide_set(False)
    for ob in scene.objects:ob.select_set(ob.type in ('MESH','ARMATURE'))
    bpy.context.view_layer.objects.active=rig
    options=dict(export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIONS',export_force_sampling=True,export_frame_range=False,export_frame_step=1,export_skins=True,export_extras=True)
    bpy.ops.export_scene.gltf(filepath=str(OUT/(NAME+'-with-rifle.glb')),**options)
    for ob in scene.objects:
        if ob.type=='MESH' and not ob.get('detail_variant'):ob.select_set(False)
    bpy.ops.export_scene.gltf(filepath=str(OUT/(NAME+'.glb')),**options)
    rig.animation_data.action=None;rig.animation_data.use_nla=True;scene.frame_start=0;scene.frame_end=230;scene.frame_set(0);rig.hide_set(True)
    for name,frame in [('IDLE',0),('RUN',60),('FIRE',123),('RELOAD',143)]:scene.timeline_markers.new(name,frame=frame)
    for ob in scene.objects:ob.select_set(False)
    cleanup.camera(scene,'three_quarter');ce.prepare_viewport();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(NAME+'.blend')))
    print('DETAIL EXPORT COMPLETE',flush=True)

if __name__=='__main__':
    if '--build' in sys.argv:build()
    if '--render' in sys.argv:render()
    if '--export' in sys.argv:export()
    if '--motion' in sys.argv:animation.OUT=OUT;animation.proof_scene=proof_scene;animation.render_motion()
