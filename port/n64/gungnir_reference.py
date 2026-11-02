"""Inspect the intact Reach customization before any semantic cuts or collapse."""
import sys,json,hashlib,argparse
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix,Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from demake_odst import components
from extract_gungnir import bone_globals
from jorge_workshop import setup,camera,point,VIEWS
from gungnir_assets import texture_path


def reference(source,output):
    source=Path(source);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    model=json.loads(source.read_text());parts=components(model)
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=True)
    scene=bpy.context.scene;scene.name='GUNGNIR / intact Reach customization';scene.render.fps=30
    bind=[Matrix(m) for m in bone_globals(model['nodes'])];axis=Matrix(((0,1,0),(-1,0,0),(0,0,1)))
    rig=bpy.data.objects.new('GUNGNIR / original 82-bone Reach rig',bpy.data.armatures.new('Intact Reach skeleton'));scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    for i,n in enumerate(model['nodes']):
        bone=rig.data.edit_bones.new(n['name']);bone.length=.035;m=(axis@bind[i].to_3x3()).to_4x4();m.translation=axis@bind[i].translation*3.048;bone.matrix=m
        if n['parent']>=0:bone.parent=rig.data.edit_bones[model['nodes'][n['parent']]['name']]
    bpy.ops.object.mode_set(mode='OBJECT');rig.hide_render=True;rig.hide_set(True)
    materials=[]
    for i,meta in enumerate(model['material_metadata']):
        mat=bpy.data.materials.new(meta['path'].split('\\')[-1]);mat.use_nodes=True;bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=.65
        if meta.get('diffuse'):
            im=bpy.data.images.load(str(texture_path(meta['diffuse'],source)),check_existing=True);im.alpha_mode='NONE';tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=im;color=tex.outputs['Color']
            if meta.get('cc') and i!=82:
                mask=mat.node_tree.nodes.new('ShaderNodeTexImage');mask.image=bpy.data.images.load(str(texture_path(meta['cc'],source)),check_existing=True);mask.image.colorspace_settings.name='Non-Color'
                sep=mat.node_tree.nodes.new('ShaderNodeSeparateColor');mat.node_tree.links.new(mask.outputs['Color'],sep.inputs['Color'])
                for channel,tint in [('Red',(.35,.39,.32,1)),('Green',(.5,.53,.43,1)),('Blue',(.2,.22,.2,1))]:
                    mix=mat.node_tree.nodes.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mat.node_tree.links.new(sep.outputs[channel],mix.inputs[0]);mat.node_tree.links.new(color,mix.inputs[1]);mix.inputs[2].default_value=tint;color=mix.outputs[0]
            mat.node_tree.links.new(color,bs.inputs['Base Color'])
        else:bs.inputs['Base Color'].default_value=(.035,.04,.04,1)
        if i==82:
            for link in list(bs.inputs['Base Color'].links):mat.node_tree.links.remove(link)
            bs.inputs['Base Color'].default_value=(.55,.23,.035,1);bs.inputs['Metallic'].default_value=.6;bs.inputs['Roughness'].default_value=.18
        materials.append(mat)
    ledger=[]
    for part in parts:
        ids=sorted({v for fi in part['faces'] for v in model['faces'][fi]});lookup={v:i for i,v in enumerate(ids)}
        me=bpy.data.meshes.new(part['id']);me.from_pydata([point(model['vertices'][i]) for i in ids],[],[[lookup[v] for v in model['faces'][fi]] for fi in part['faces']]);me.materials.append(materials[part['material']]);uv=me.uv_layers.new(name='Original UV')
        attribute=me.attributes.new(name='source_face',type='INT',domain='FACE')
        for face,fi in zip(me.polygons,part['faces']):
            attribute.data[face.index].value=fi
            for li,vi in zip(face.loop_indices,model['faces'][fi]):u,v=model['uv'][vi];uv.data[li].uv=(u,1-v)
        ob=bpy.data.objects.new(part['id'],me);scene.collection.objects.link(ob);ob.parent=rig;ob['source_component']=part['id'];ob['source_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
        va=me.attributes.new(name='source_vertex',type='INT',domain='POINT')
        for i,vi in enumerate(ids):va.data[i].value=vi
        for n in model['nodes']:ob.vertex_groups.new(name=n['name'])
        for i,vi in enumerate(ids):
            for bi,w in model['weights'][vi]:ob.vertex_groups[bi].add([i],w,'REPLACE')
        mod=ob.modifiers.new('Original Reach skin weights','ARMATURE');mod.object=rig
        bounds=[[min(model['vertices'][i][a] for i in ids),max(model['vertices'][i][a] for i in ids)] for a in range(3)]
        ledger.append(dict(**part,vertices=len(ids),triangles=len(part['faces']),bounds=bounds,material_path=model['material_metadata'][part['material']]['path'],bone_influences=sorted({model['nodes'][b]['name'] for i in ids for b,w in model['weights'][i]}),decision='intact source; no cuts'))
    setup(scene)
    for im in bpy.data.images:
        if im.filepath and im.has_data:im.pack()
    bpy.data.libraries.write(str(output/'gungnir-original.blend'),{scene},fake_user=True)
    (output/'component-inventory.json').write_text(json.dumps(ledger,indent=2)+'\n')
    (output/'reference-report.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),vertices=len(model['vertices']),triangles=len(model['faces']),bones=len(model['nodes']),components=len(parts),identity=['single-eye GUNGNIR helmet and recessed lens','HP/Parafoil chest attachment','paired UA/Base Security shoulder guards','UA/Buckler wrist plate','continuous Reach undersuit, leg and boot shapes'],render_note='Original diffuse/UV; approximate Reach team-mask presentation and gold visor reflection; no geometry edits'),indent=2)+'\n')
    for view in VIEWS:
        camera(scene,view);scene.render.filepath=str(output/(view+'.png'));bpy.ops.render.render(write_still=True)
    print('REFERENCE',len(parts),'components',len(model['faces']),'triangles',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('output');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);reference(a.source,a.output)
