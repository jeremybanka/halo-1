"""Matched equal-cost shoulder pilot: clay, source diffuse, BLEND and GLBs."""
import argparse,json,sys,hashlib
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector,interpolate
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from jorge_workshop import point
from gungnir_assets import texture_path


def run(source,pilot,output):
    source,pilot,output=map(Path,(source,pilot,output));output.mkdir(parents=True,exist_ok=True);raw=json.loads(source.read_text());study=json.loads(pilot.read_text())
    faces=[fi for p in study['source_components'] for fi in p['faces']];tree=BVHTree.FromPolygons([Vector(v) for v in raw['vertices']],[raw['faces'][i] for i in faces],all_triangles=True);texture=bpy.data.images.load(str(texture_path(raw['material_metadata'][96]['diffuse'],source)),check_existing=True);tw,th=texture.size;pixels=np.array(texture.pixels[:]).reshape(th,tw,4); bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=True);objects=[];meshes=[]
    for key,label in [('source','A Original'),('cleaned','B Fasteners removed'),('constrained','C Component collapse'),('direct','D Direct same count')]:
        tris=study[key];positions=[];uvs=[];colors=[]
        for t in tris:
            for p in t['p']:
                hit,_,fi,_=tree.find_nearest(Vector(p));ids=raw['faces'][faces[fi]];bary=np.maximum(0,interpolate.poly_3d_calc([Vector(raw['vertices'][i]) for i in ids],hit));bary/=bary.sum();uv=bary@np.array([raw['uv'][i] for i in ids]);uvs.append(uv);colors.append((pixels[th-1-int(uv[1]%1*th),int(uv[0]%1*tw),:3]*255).tolist());positions.append(p)
        me=bpy.data.meshes.new(label);me.from_pydata([point(p) for p in positions],[],[[i*3+j for j in range(3)] for i in range(len(tris))]);uv=me.uv_layers.new(name='Source shoulder UV')
        for i in range(len(me.loops)):uv.data[i].uv=(uvs[i][0],1-uvs[i][1])
        mat=bpy.data.materials.new('Original Reach shoulder diffuse');mat.use_nodes=True;bs=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=texture;tex.image.pack();mat.node_tree.links.new(tex.outputs['Color'],bs.inputs['Base Color']);me.materials.append(mat)
        ob=bpy.data.objects.new(label,me);bpy.context.scene.collection.objects.link(ob);ob['triangles']=len(tris);ob['source_sha256']=study['source_sha256'];objects.append(ob);meshes.append(dict(positions=(np.array(positions)@np.array(((1,0,0),(0,0,-1),(0,1,0)))).reshape(-1,3,3).tolist(),colors=np.array(colors).reshape(-1,3,3).tolist()))
        bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob;bpy.ops.export_scene.gltf(filepath=str(output/(key+'.glb')),use_selection=True,export_animations=False)
    bpy.data.libraries.write(str(output/'shoulder-pilot.blend'),{bpy.context.scene},fake_user=True,compress=True)
    (output/'pilot-render.json').write_text(json.dumps([dict(label=ob.name,**mesh) for ob,mesh in zip(objects,meshes)]))
    import subprocess
    subprocess.run([str(Path('build/n64-python/bin/python').absolute()),str(Path(__file__).with_name('gungnir_pilot_images.py')),str(output)],check=True)
    (output/'pilot-review.json').write_text(json.dumps(dict(source_sha256=study['source_sha256'],pilot_sha256=hashlib.sha256(pilot.read_bytes()).hexdigest(),equal_count=len(study['constrained'])==len(study['direct']),counts={k:len(study[k]) for k in ('source','cleaned','constrained','direct')},retained_surface_error_m=study['reduction']['maximum_sampled_surface_error']*3.048),indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('pilot');p.add_argument('output');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run(a.source,a.pilot,a.output)
