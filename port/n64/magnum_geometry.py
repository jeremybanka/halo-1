"""Box-built M6D proxy, authored against owned Xbox bind-space geometry.

Closed planar pieces retain the source moving-part bones. Blender triangulates
and checks each piece; the same recipe supplies FP and world weapon geometry.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from copy import deepcopy
import numpy as np
from plasma_meters import globals_for
COLORS=[(102,102,102),(38,43,49),(193,142,63),(77,77,77),(12,17,22)]

def build_magnum(scene):
    import bpy,bmesh
    materials=[]
    for name,rgb in zip(('silver slide','black grip','brass','receiver gray','muzzle recess'),COLORS):
        mat=bpy.data.materials.new('M6D '+name);mat.diffuse_color=(*[v/255 for v in rgb],1);mat.use_nodes=True
        node=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');node.inputs['Base Color'].default_value=mat.diffuse_color
        materials.append(mat)
    triangles=[];objects=[]
    def part(name,points,faces,bone,material):
        mesh=bpy.data.meshes.new('M6D '+name);mesh.from_pydata(points,[],faces);mesh.update()
        bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bmesh.ops.triangulate(bm,faces=list(bm.faces))
        assert all(e.is_manifold for e in bm.edges),name
        bm.to_mesh(mesh);bm.free();mesh.update()
        obj=bpy.data.objects.new('M6D '+name,mesh);scene.collection.objects.link(obj);mesh.materials.append(materials[material]);objects.append(obj)
        obj['source_bone']=bone
        for f in mesh.polygons:
            triangles.append(dict(p=[list(mesh.vertices[i].co) for i in f.vertices],uv=[[0,0]]*3,weights=[[[bone,1.0]]]*3,material=material,part=name,magnum_proxy=True))
    def prism(name,profile,width,bone,material):
        n=len(profile);points=[(x,y,z) for y in (-width,width) for x,z in profile]
        faces=[list(range(n-1,-1,-1)),list(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
        part(name,points,faces,bone,material)
    def box(name,x0,x1,z0,z1,width,bone,material):prism(name,[(x0,z0),(x1,z0),(x1,z1),(x0,z1)],width,bone,material)
    # Keep broad, parallel planes; spend corners on silhouette breaks, not
    # fragmented texture/material islands. Dimensions are source Halo units.
    prism('slide',[(-.037,.020),(-.034,.0188),(.026,.0188),(.026,.029),(.021,.0325),(-.033,.0325),(-.037,.029)],.0068,2,0)
    prism('barrel housing',[(.025,.018),(.0505,.018),(.0505,.033),(.045,.0375),(.032,.0375),(.025,.034)],.0073,0,0)
    prism('lower receiver',[(-.035,.011),(.050,.011),(.050,.0176),(-.033,.0176),(-.0365,.015)],.0068,0,3)
    prism('grip',[(-.014,.011),(.010,.011),(.004,-.0245),(-.012,-.0245),(-.015,-.019),(-.009,.001)],.0054,0,1)
    prism('magazine',[(-.007,.017),(.009,.017),(-.003,-.048),(-.017,-.048)],.0048,1,0)
    prism('magazine base',[(-.0185,-.047),(.001,-.050),(.001,-.053),(-.0185,-.050)],.0058,1,1)
    # Thick enough for the N64 grid, with the original open trigger guard.
    outer=[(.008,.011),(.038,.011),(.032,-.020),(.026,-.024),(.003,-.024)]
    inner=[(.012,.007),(.034,.007),(.028,-.017),(.024,-.020),(.008,-.020)]
    n=len(outer);points=[(x,y,z) for y in (-.003,.003) for ring in (outer,inner) for x,z in ring];faces=[]
    for i in range(n):
        j=(i+1)%n
        faces += [(i,j,j+n,i+n),(i+2*n,i+3*n,j+3*n,j+2*n),(i,i+2*n,j+2*n,j),(i+n,j+n,j+3*n,i+3*n)]
    part('trigger guard',points,faces,0,3)
    prism('trigger',[(.017,.010),(.021,.010),(.018,.001),(.021,-.002),(.016,0),(.015,.004)],.0018,4,1)
    box('rear sight',-.033,-.027,.0328,.0358,.0053,2,1)
    box('front sight',.044,.049,.0378,.0402,.0020,0,1)
    # The muzzle is a shallow dark closed box in front of the silver housing,
    # rather than an open backface or a coplanar black decal.
    box('muzzle',.0508,.0515,.022,.029,.0037,0,4)
    box('chamber port',.008,.020,.0327,.0337,.0038,2,1)
    box('chamber button',-.038,-.0372,.0235,.0275,.0018,6,3)
    box('cartridge',.016,.029,.022,.026,.0025,5,2)
    return triangles,objects

def install_firstperson(data,raw,triangles):
    w=data['weapons']['pistol'];src=raw['weapons']['pistol'];gun=src['gun'];hc=w['hand_triangle_count'];hands=deepcopy(w['triangles'][:hc]);offset=len(raw['hands']['textures'])
    bind=globals_for(gun['nodes'],gun['nodes']);inv=np.linalg.inv(bind);lookup={n['name']:i for i,n in enumerate(src['nodes'])}
    for name,clip in w['clips'].items():
        original=src['clips'][name]['frames'];count=len(clip['frames'])
        for fi,frame in enumerate(clip['frames']):
            pose=globals_for(original[round(fi*(len(original)-1)/max(1,count-1))],src['nodes']);points=[]
            for t in triangles:
                bone=t['weights'][0][0][0];mat=pose[lookup[gun['nodes'][bone]['name']]]@inv[bone]
                points.extend([(mat@np.array([*p,1]))[:3].tolist() for p in t['p']])
            clip['frames'][fi]=frame[:hc*3]+points
    w['triangles']=hands+deepcopy(triangles)
    for t in w['triangles'][hc:]:t['material']+=offset
    for i,t in enumerate(w['triangles']):t['p']=deepcopy(w['clips']['idle']['frames'][0][i*3:i*3+3])
    for key in ('textures','material_names','material_types','material_colors','material_overrides','texture_sources','material_multipurpose','material_change_source'):
        suffix=[None]*len(COLORS)
        if key=='material_names':suffix=['M6D proxy '+str(i) for i in range(len(COLORS))]
        if key=='material_types':suffix=['shader_model']*len(COLORS)
        if key=='material_colors':suffix=[list(c) for c in COLORS]
        if key=='textures':suffix=[triangles[0]['texture_path']]*len(COLORS)
        w[key]=w.get(key,[None]*offset)[:offset]+suffix
    w['gun_triangle_count']=len(triangles);w['magnum_proxy']='closed rectangular source-bone proxy'

def install_world(data,raw,fpraw,triangles):
    w=data['models']['pistol'];nodes=raw['models']['pistol']['nodes'];fpgun=fpraw['weapons']['pistol']['gun'];bind=globals_for(nodes,nodes);inverse=np.linalg.inv(globals_for(fpgun['nodes'],fpgun['nodes']));lookup={n['name']:i for i,n in enumerate(nodes)}
    # The cartridge is visible only during the first-person reload.
    converted=[deepcopy(t) for t in triangles if t["part"]!="cartridge"]
    for t in converted:
        bone=t['weights'][0][0][0];worldbone=lookup[fpgun['nodes'][bone]['name']];mat=bind[worldbone]@inverse[bone]
        t['p']=[(mat@np.array([*p,1]))[:3].tolist() for p in t['p']];t['weights']=[[[worldbone,1.0]]]*3
    w['triangles']=converted
    for key in ('textures','textures_fullres','multipurpose_fullres','team_masks','team_mask_channels','material_metadata'):
        w[key]=[{} if key=='material_metadata' else None for _ in COLORS]
    w['material_colors']=[list(c) for c in COLORS];w['material_overrides']=[None]*len(COLORS)
    w['textures']=[triangles[0]['texture_path']]*len(COLORS)
    w['magnum_proxy']='closed rectangular source-bone proxy'

def refine(root):
    """Reapply only this weapon after either general-purpose reduction pass."""
    import bpy,json,hashlib
    from pathlib import Path
    root=Path(root);assets=root/'build/n64/assets'
    raw=json.loads((assets/'firstperson-raw.json').read_text())
    worldraw=json.loads((assets/'extended-raw.json').read_text())
    fp=json.loads((assets/'firstperson-reduced.json').read_text())
    world=json.loads((assets/'extended-reduced.json').read_text())
    scene=bpy.data.scenes.new('M6D rectangular refinement')
    triangles,objects=build_magnum(scene)
    texture_magnum(triangles,objects,raw['weapons']['pistol']['gun'],assets)
    install_firstperson(fp,raw,triangles);install_world(world,worldraw,raw,triangles)
    for name,data in [('firstperson',fp),('extended',world)]:
        (assets/(name+'-reduced.json')).write_text(json.dumps(data))
    for layer in scene.view_layers:layer.update()
    bpy.data.libraries.write(str(assets/'magnum-refined.blend'),{scene})
    (assets/'magnum-refinement.json').write_text(json.dumps({'triangles':len(triangles),'closed_parts':len(objects),
        'recipe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'source':'owned Xbox pistol first-person bind geometry and original moving-part bones',
        'distant_lod':'unchanged source-derived pickup LOD'},indent=2)+'\n')
    return scene

def texture_magnum(triangles,objects,gun,assets):
    """Transfer source UV planes to the closed proxy; retain source surface detail.

    The RGB atlas is baked to 64x32, with one white row for the existing hands
    and dark solid details. Source silver is attenuated before N64 lighting.
    """
    import bpy
    # Read the owned diffuse pixels through Blender; box-average in NumPy.
    src=bpy.data.images.load(gun['textures'][0],check_existing=True)
    src.colorspace_settings.name='Non-Color' # Preserve source byte values during the reduction.
    pixels=np.array(src.pixels[:]).reshape(src.size[1],src.size[0],4)[::-1]
    atlas=np.ones((32,64,4),dtype=np.float32)
    for y in range(31):
        for x in range(64):
            patch=pixels[y*src.size[1]//31:(y+1)*src.size[1]//31,x*src.size[0]//64:(x+1)*src.size[0]//64,:3]
            atlas[y,x,:3]=patch.mean(axis=(0,1))*.45
    result=bpy.data.images.new('M6D source atlas',width=64,height=32,alpha=True)
    result.colorspace_settings.name='Non-Color'
    result.pixels=atlas[::-1].reshape(-1).tolist()
    path=assets/'magnum-texture.png';result.filepath_raw=str(path);result.file_format='PNG';result.save()
    points=np.asarray(gun['vertices'])[gun['faces']];uv=np.asarray(gun['uv'])[gun['faces']]
    centers=points.mean(axis=1);normals=np.cross(points[:,1]-points[:,0],points[:,2]-points[:,0]);normals/=np.maximum(1e-12,np.linalg.norm(normals,axis=1))[:,None]
    bones=np.array([gun['weights'][f[0]][0] for f in gun['faces']])
    # One UV plane per planar proxy face, rather than a fresh source island
    # per triangle. Shared corners then remain shared in every animation pose.
    groups={}
    for t in triangles:
        p=np.array(t['p']);n=np.cross(p[1]-p[0],p[2]-p[0]);n/=max(1e-12,np.linalg.norm(n))
        key=(t['part'],tuple(np.round(n,3)))
        groups.setdefault(key,[]).append(t)
    sources={}
    for key,faces in groups.items():
        center=np.array([p for t in faces for p in t['p']]).mean(axis=0)
        bone=faces[0]['weights'][0][0][0]
        sources[key]=int(np.argmin(np.linalg.norm(centers-center,axis=1)+(1-normals@np.array(key[1]))*.06+(bones!=bone)*10))
    for t in triangles:
        p=np.array(t['p']);normal=np.cross(p[1]-p[0],p[2]-p[0]);normal/=max(1e-12,np.linalg.norm(normal));bone=t['weights'][0][0][0]
        i=sources[(t['part'],tuple(np.round(normal,3)))];basis=np.stack((points[i,1]-points[i,0],points[i,2]-points[i,0]),axis=1)
        weights=np.linalg.lstsq(basis,(p-points[i,0]).T,rcond=None)[0].T
        mapped=uv[i,0]+weights@(uv[i,1:]-uv[i,0])
        t['uv']=[[float(np.clip(u,0,63/64)),min(float(np.clip(v,0,.999))*31,30)/32] for u,v in mapped]
        t['texture_path']=str(path);t['magnum_textured']=True
        # Sights and muzzle keep a clean silhouette. All broad surfaces use
        # the original artwork, including its darker sidewalls and grip.
        if t['part'] in ('front sight','rear sight','muzzle','chamber port','cartridge'):
            t['uv']=[[.5/64,31.5/32]]*3;t['texture_shade']=list(COLORS[t['material']])
    # Store the same UV layout on the review meshes in Blender.
    source=bpy.data.images.load(str(path),check_existing=False)
    offset=0
    for obj in objects:
        first=triangles[offset]
        layer=obj.data.uv_layers.new(name='Source M6D atlas')
        for f in obj.data.polygons:
            t=triangles[offset];offset+=1
            for loop,(u,v) in zip(f.loop_indices,t['uv']):layer.data[loop].uv=(u,1-v)
        mat=obj.data.materials[0].copy();obj.data.materials[0]=mat
        node=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
        if 'texture_shade' in first:
            # Match the runtime's solid-detail vertex modulation in the review.
            rgb=[v/255 for v in first['texture_shade']]
            node.inputs['Base Color'].default_value=(*[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb],1)
            continue
        tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=source;tex.interpolation='Closest'
        mat.node_tree.links.new(tex.outputs['Color'],node.inputs['Base Color'])
    assert offset==len(triangles)

if __name__=='__main__':
    from pathlib import Path
    refine(Path(__file__).resolve().parents[2])
