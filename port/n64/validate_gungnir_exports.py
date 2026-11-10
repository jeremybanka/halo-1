"""Reimport both colored body-only GLBs against the independent native rig."""
import argparse,hashlib,json,re,struct,sys
from pathlib import Path
import bpy
from mathutils.kdtree import KDTree

def points(ob):
    ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh();result=[ev.matrix_world@v.co for v in mesh.vertices];ev.to_mesh_clear();return result

def distance(a,b):
    tree=KDTree(len(a))
    for i,p in enumerate(a):tree.insert(p,i)
    tree.balance();return max(tree.find(p)[2] for p in b)

def run(candidate,library,output):
    candidate,library,output=map(Path,(candidate,library,output));output.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(library/'gungnir.blend'));scene=bpy.context.scene;scene.render.fps=30
    native=scene.objects['GUNGNIR / native Reach gameplay rig'];actions={a['source_clip']:a for a in bpy.data.actions if a.get('source_clip')};metadata=json.loads((candidate/'solid.json').read_text());report=[]
    assert len(actions)==39 and len(native.data.bones)==82
    for lod,name in enumerate(('GUNGNIR near','GUNGNIR far')):
        path=library/f'gungnir-{lod}.glb';raw=path.read_bytes();length,kind=struct.unpack_from('<II',raw,12);assert kind==0x4e4f534a;gltf=json.loads(raw[20:20+length])
        assert all('COLOR_0' in p['attributes'] for m in gltf['meshes'] for p in m['primitives'])
        assert all('KHR_materials_unlit' in m.get('extensions',{}) for m in gltf['materials'])
        original=scene.objects[name];original.hide_set(False);before=set(bpy.data.objects);old_actions=set(bpy.data.actions);bpy.ops.import_scene.gltf(filepath=str(path));imported=set(bpy.data.objects)-before;rig=next(o for o in imported if o.type=='ARMATURE');ob=next(o for o in imported if o.type=='MESH' and o.name.startswith(name));exported={re.sub(r'\.\d+$','',a.name):a for a in set(bpy.data.actions)-old_actions}
        assert len(exported)==39 and len(rig.data.bones)==82
        native.animation_data.use_nla=rig.animation_data.use_nla=False;clips=[]
        for clip,action in actions.items():
            native.animation_data.action=action;rig.animation_data.action=exported['GUNGNIR / '+clip];duration=action['duration_seconds'];count=next(c['frames'] for c in metadata['lods'][lod]['animations'] if c['name']==clip);maximum=reverse=0
            for i in range(10):
                frame=(round(i*(count-1)/4)/max(1,count-1) if i<5 else (i-5)/4)*duration*30;scene.frame_set(int(frame),subframe=frame-int(frame));bpy.context.view_layer.update();a=points(original);b=points(ob);maximum=max(maximum,distance(a,b));reverse=max(reverse,distance(b,a))
            assert max(maximum,reverse)<.001,(lod,clip,maximum,reverse)
            clips.append(dict(name=clip,authored_key_samples=5,interpolated_samples=5,export_to_native_error_m=maximum,native_to_export_error_m=reverse))
        report.append(dict(lod=lod,candidate_sha256=hashlib.sha256((candidate/'solid.json').read_bytes()).hexdigest(),blend_sha256=hashlib.sha256((library/'gungnir.blend').read_bytes()).hexdigest(),sha256=hashlib.sha256(raw).hexdigest(),vertices=len(ob.data.vertices),triangles=len(ob.data.polygons),bones=82,vertex_colors=True,unlit_materials=True,clips=clips))
        for item in imported:bpy.data.objects.remove(item,do_unlink=True)
        original.hide_set(bool(lod))
    (output/'export-validation.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS: 780 GLB samples, native 82-bone rig, 39 clips, two colored body-only LODs, <1 mm error',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('candidate');p.add_argument('library');p.add_argument('output');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run(a.candidate,a.library,a.output)
