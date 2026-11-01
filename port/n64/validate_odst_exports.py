"""Round-trip both body-only GLBs against the independent editable library."""
import json,sys,hashlib,re
from pathlib import Path
import bpy
from mathutils.kdtree import KDTree

def points(ob):
    ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
    result=[ev.matrix_world@v.co for v in mesh.vertices];ev.to_mesh_clear();return result

def distance(a,b):
    tree=KDTree(len(a))
    for i,p in enumerate(a):tree.insert(p,i)
    tree.balance();return max(tree.find(p)[2] for p in b)

def run(folder):
    folder=Path(folder).resolve();bpy.ops.wm.open_mainfile(filepath=str(folder/'library/odst.blend'))
    scene=bpy.context.scene;scene.render.fps=30;scene.unit_settings.scale_length=1
    native=next(o for o in scene.objects if o.name=='ODST / CE gameplay rig')
    actions={a['source_clip']:a for a in bpy.data.actions if a.get('source_clip')}
    metadata=json.loads((folder/'covered/solid.json').read_text())
    report=[]
    for lod,name in enumerate(('ODST near','ODST far')):
        original=scene.objects[name];original.hide_set(False);original.hide_render=False
        before=set(bpy.data.objects);old_actions=set(bpy.data.actions)
        bpy.ops.import_scene.gltf(filepath=str(folder/f'library/odst-{lod}.glb'))
        imported=set(bpy.data.objects)-before;rig=next(o for o in imported if o.type=='ARMATURE');ob=next(o for o in imported if o.type=='MESH' and o.name.startswith(name))
        exported={re.sub(r'\.\d+$','',a.name):a for a in set(bpy.data.actions)-old_actions}
        assert len(exported)==39 and len(rig.data.bones)==19
        native.animation_data.use_nla=False;rig.animation_data.use_nla=False
        clips=[]
        for clip,action in actions.items():
            native.animation_data.action=action;rig.animation_data.action=exported['CE / '+clip]
            duration=action['duration_seconds'];maximum=reverse=0.
            for i in range(10):
                count=next(c['frames'] for c in metadata['lods'][lod]['animations'] if c['name']==clip)
                frame=(round(i*(count-1)/4)/max(1,count-1) if i<5 else (i-5)/4)*duration*30;scene.frame_set(int(frame),subframe=frame-int(frame));bpy.context.view_layer.update()
                a=[p*3.048 for p in points(original)];b=points(ob)
                maximum=max(maximum,distance(a,b));reverse=max(reverse,distance(b,a))
            assert maximum<1e-3 and reverse<1e-3,(lod,clip,maximum,reverse)
            clips.append(dict(name=clip,authored_key_samples=5,interpolated_samples=5,export_to_native_error_m=maximum,native_to_export_error_m=reverse))
        report.append(dict(lod=lod,sha256=hashlib.sha256((folder/f'library/odst-{lod}.glb').read_bytes()).hexdigest(),triangles=len(ob.data.polygons),bones=19,clips=clips))
        for item in imported:bpy.data.objects.remove(item,do_unlink=True)
        original.hide_set(bool(lod))
    (folder/'library/export-validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS: 780 GLB round-trip samples (390 authored keys + 390 clock samples), 39 clips / two LODs, <1 mm error',flush=True)

if __name__=='__main__':run(sys.argv[sys.argv.index('--')+1])
