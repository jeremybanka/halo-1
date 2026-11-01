"""Preserve Jorge's armor; restore matte pack colors and prepare first-person coverage."""
import bpy, bmesh, json, shutil, hashlib
import numpy as np
from mathutils import Vector, Matrix, geometry
from mathutils.bvhtree import BVHTree
import refine_jorge as previous
import jorge_playable_reduce as task

ROOT=task.ROOT;BASE=task.BASE;SOURCE=previous.OUT
OUT=BASE/'playable-personal';NAME='jorge-playable-personal'
SCENE='Jorge - personal arms and matte pack'

def configure():
    task.OUT=OUT;task.NAME=NAME;task.SCENE=SCENE

def cap_thighs(scene,rig):
    """Cloth backing beneath the authored thigh rims, visible only from above."""
    by={o['source_component']:o for o in task.body(scene)}
    for side,key,part in [('l','body-09:004',11),('r','body-09:005',12)]:
        source=by[key];p=np.array([v.co[:] for v in source.data.vertices]);high=p[p[:,2]>np.quantile(p[:,2],.62)]
        # Monotone convex outline of the actual upper plate, inset under its rim.
        points=sorted(set(tuple(v[:2]) for v in high))
        cross=lambda a,b,c:(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
        lower=[];upper=[]
        for point in points:
            while len(lower)>=2 and cross(lower[-2],lower[-1],point)<=0:lower.pop()
            lower.append(point)
        for point in points[::-1]:
            while len(upper)>=2 and cross(upper[-2],upper[-1],point)<=0:upper.pop()
            upper.append(point)
        hull=np.array(lower[:-1]+upper[:-1]);center=hull.mean(0);hull=center+(hull-center)*.97
        z=float(np.quantile(p[:,2],.7))-.018
        me=bpy.data.meshes.new('Upper thigh cloth backing '+side);me.from_pydata([(x,y,z) for x,y in hull],[],[list(range(len(hull)))])
        bm=bmesh.new();bm.from_mesh(me);bmesh.ops.triangulate(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
        ob=source.copy();ob.data=me;ob.name='Personal / thigh backing '+side;scene.collection.objects.link(ob)
        ob['source_component']=f'body-10:{part:03d}';ob['group']='body-10';ob['ce_tile']=10
        ob.vertex_groups.clear();g=ob.vertex_groups.new(name=f'b_{side}_upperleg_jiggle');g.add(list(range(len(hull))),1,'REPLACE')
        uv=me.uv_layers.new(name='CE Atlas UV')
        for c in uv.data:c.uv=(.625,.375)
        ca=me.color_attributes.new(name=previous.COLOR,type='FLOAT_COLOR',domain='CORNER');me.color_attributes.active_color=ca
        for c in ca.data:c.color_srgb=(.15,.17,.15,1)
        mat=previous.material('Jorge cloth thigh backing '+side);bs=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');bs.inputs['Metallic'].default_value=0;bs.inputs['Roughness'].default_value=1
        me.materials.append(mat);ob['color_source']='Dark undersuit closure under original upper thigh rim'

def run():
    previous.configure();scene,rig=task.proof_scene();scene.name=SCENE;configure()
    cap_thighs(scene,rig)
    OUT.mkdir(exist_ok=True);(OUT/'textures').mkdir(exist_ok=True)
    for name in ('ce-motion-source.json','gameplay-poses.json','component-budgets.csv'):
        shutil.copy2(SOURCE/name,OUT/name)
    shutil.copy2(SOURCE/'textures/jorge-ce-atlas-256.png',OUT/'textures/jorge-ce-atlas-256.png')
    raw=json.loads((BASE/'backpack-original.json').read_text())
    xf=Matrix(json.loads((BASE/'backpack-attachment.json').read_text())['matrix'])
    points=[]
    for p in raw['vertices']:
        v=xf@Vector((*p,1));points.append(Vector((v.y,-v.x,v.z))*3.048)
    tree=BVHTree.FromPolygons(points,raw['faces'],all_triangles=True)
    image=bpy.data.images.load(raw['material_metadata'][0]['diffuse'],check_existing=False)
    image.name='Jorge original gear - 64 pixel reference';image.scale(64,64)
    image.filepath_raw=str(OUT/'textures/jorge-gear-64.png');image.file_format='PNG';image.save();image.pack()
    pixels=np.array(image.pixels[:]).reshape(64,64,4)
    matte=previous.material('Jorge matte field pack')
    bs=next(n for n in matte.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    bs.inputs['Metallic'].default_value=0;bs.inputs['Roughness'].default_value=.95
    obs=sorted(task.body(scene),key=lambda o:o['source_component']);arms=[];changes=[]
    for ob in obs:
        me=ob.data;key=ob['source_component'];ca=me.color_attributes[previous.COLOR]
        if key.startswith('backpack-'):
            layer=me.uv_layers.get('Reach pack UV') or me.uv_layers.new(name='Reach pack UV')
            for loop,c in zip(me.loops,ca.data):
                co=me.vertices[loop.vertex_index].co;near,normal,fi,distance=tree.find_nearest(co)
                ids=raw['faces'][fi];a,b,d=[points[i] for i in ids]
                uv=geometry.barycentric_transform(near,a,b,d,*[Vector((*raw['uv'][i],0)) for i in ids])
                layer.data[loop.index].uv=(uv.x,1-uv.y)
                x=int(np.clip(uv.x*64,0,63));y=int(np.clip((1-uv.y)*64,0,63))
                # Retain the authored strap/panel tones, compress tiny grime and
                # color shifts. No specular band or bright upward reflection.
                rgb=pixels[y,x,:3]
                c.color_srgb=(*np.clip(.65*rgb+.35*np.array((.35,.32,.26)),.07,.52),1)
            me.materials.clear();me.materials.append(matte)
            for p in me.polygons:p.material_index=0
            ob['color_source']='64px original Reach gear, matte gray-brown; retained original UV projection'
            changes.append(key)
        elif ob['ce_tile']==5:
            for c in ca.data:
                luminance=float(np.array(c.color_srgb[:3])@np.array((.3,.59,.11)))
                gain=.5+.5*np.clip((luminance-.15)/.7,0,1)
                c.color_srgb=(*(np.array((.68,.57,.37))*gain),1)
            ob['color_source']='Muted warm ochre armor; restrained metallic ramp distinct from olive'
            changes.append(key)
        if key.startswith(('arms-01:','arms-07:')):
            arms.append({'component':key,'vertices':[list(v.co) for v in me.vertices],
                'faces':[list(p.vertices) for p in me.polygons],
                'weights':[[[ob.vertex_groups[g.group].name,g.weight] for g in v.groups] for v in me.vertices],
                'colors':[list(c.color_srgb[:3]) for c in ca.data]})
    bones={b.name:np.array(b.matrix_local).tolist() for b in rig.data.bones}
    (OUT/'firstperson-plates.json').write_text(json.dumps({'components':arms,'bones':bones,'coordinate_units':'Blender meters; same bind pose as accepted body'})+'\n')
    report={'source_sha256':hashlib.sha256((SOURCE/(previous.NAME+'.blend')).read_bytes()).hexdigest(),
            'accepted_geometry_unchanged':True,'added_geometry':'Two inset cloth thigh caps for downward visibility','changed_colors':changes,
            'backpack_texture_size':[64,64],'native_vertices':sum(len(o.data.vertices) for o in obs),
            'triangles':sum(len(o.data.polygons) for o in obs)}
    (OUT/'personalization-report.json').write_text(json.dumps(report,indent=2)+'\n')
    bpy.data.libraries.write(str(OUT/(NAME+'.blend')),{scene,*bpy.data.actions},fake_user=True,compress=True)
    import bake_jorge_playable as bake
    bake.OUT=OUT;bake.run()
    task.export();print('PERSONALIZED',report,flush=True)

if __name__=='__main__':run()
