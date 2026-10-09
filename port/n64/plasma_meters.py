"""Small opaque geometry proxies for the Xbox transparent plasma meters.

Applied in bind space, then skinned with the original face/gun bones. Only
the meter surfaces change; the weapon shells and hand geometry are retained.
"""
from copy import deepcopy
import numpy as np

def globals_for(states,nodes):
    # JMS stores the inverse quaternion convention used by the source skin.
    result=[None]*len(nodes)
    def visit(i):
        if result[i] is not None:return result[i]
        x,y,z,w=states[i]['q'];x,y,z=-x,-y,-z
        m=np.array(((1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w),0),
                    (2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w),0),
                    (2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y),0),(0,0,0,1)),dtype=float)
        m[:3,3]=states[i]['p'];parent=nodes[i]['parent']
        result[i]=visit(parent)@m if parent>=0 and parent!=i else m
        return result[i]
    for i in range(len(nodes)):visit(i)
    return np.array(result)



def meter_geometry(name, gun):
    material=next(i for i,n in enumerate(gun['material_types']) if n=='shader_transparent_meter')
    if name=='plasma_pistol':
        # The source alpha is a horseshoe open at the far end. An angular U
        # retains its opening at the 160x120 split-screen footprint.
        source_faces=[f for f,m in zip(gun['faces'],gun['materials']) if m==material]
        assert len(source_faces)==2
        p=np.array([gun['vertices'][i] for i in source_faces[0]])
        base=p[0];forward=p[1]-p[0];across=p[2]-p[0]
        normal=np.cross(forward,across);normal/=np.linalg.norm(normal)
        base=base+normal*(2/256)
        # Three joined quads, no coplanar overlap at the bottom corners.
        uv=[(0,0),(1,0),(1,1),(.68,1),(.68,.34),(.32,.34),(.32,1),(0,1)]
        points=[base+across*u+forward*v for u,v in uv]
        faces=[(0,1,4),(0,4,5),(1,2,3),(1,3,4),(0,5,6),(0,6,7)]
        # above faces are across/forward order; retain source winding.
        faces=[(a,c,b) for a,b,c in faces]
        bone=3
    else:
        # A narrow vertical luminous strip sits in the original left-side
        # gauge recess, beneath the purple upper shell. It does not cover the
        # broad curved transparent-meter sheet with an opaque green surface.
        points=[np.array(p) for p in [(-.024,.018,.032),(.040,.018,.032),
                                      (.040,.018,.039),(-.024,.018,.039)]]
        faces=[(0,3,2),(0,2,1)];bone=0
    return material,points,faces,bone


def repair_meters(data, raw):
    report={}
    for name in ('plasma_pistol','plasma_rifle'):
        w=data['weapons'][name];original=raw['weapons'][name];gun=original['gun']
        material,points,faces,bone=meter_geometry(name,gun)
        material+=len(raw['hands']['textures'])
        keep=[i for i,t in enumerate(w['triangles']) if t['material']!=material]
        triangles=[deepcopy(w['triangles'][i]) for i in keep]
        lookup={n['name']:i for i,n in enumerate(original['nodes'])}
        inverse=np.linalg.inv(globals_for(gun['nodes'],gun['nodes'])[bone])
        node=lookup[gun['nodes'][bone]['name']]
        added=[{'p':[points[j].tolist() for j in face], 'uv':[[0,0]]*3,
                'weights':[[[bone,1.0]] for _ in face], 'material':material,
                'part':-1,'plasma_meter':True} for face in faces]
        for cname,clip in w['clips'].items():
            source=original['clips'][cname]['frames'];count=len(clip['frames'])
            for fi,frame in enumerate(clip['frames']):
                states=source[round(fi*(len(source)-1)/max(1,count-1))]
                mat=globals_for(states,original['nodes'])[node]@inverse
                posed=[(mat@np.array([*p,1]))[:3].tolist() for p in points]
                clip['frames'][fi]=[p for i in keep for p in frame[i*3:i*3+3]]+[posed[j] for f in faces for j in f]
        w['triangles']=triangles+added
        for ti,t in enumerate(w['triangles']):t['p']=deepcopy(w['clips']['idle']['frames'][0][ti*3:ti*3+3])
        w['gun_triangle_count']=len(w['triangles'])-w['hand_triangle_count']
        report[name]={'meter_triangles':len(added),
                      'bone':gun['nodes'][bone]['name'], 'shape':'raised U' if name=='plasma_pistol' else 'recessed strip'}
    data['plasma_meter_repairs']=report
    return report


def blender_review(data, scene):
    """Inspect the final, posed models beside their isolated meter geometry."""
    import bpy
    for row,name in enumerate(('plasma_pistol','plasma_rifle')):
        w=data['weapons'][name]
        mesh=bpy.data.meshes.new(name+' repaired meter')
        mesh.from_pydata([p for t in w['triangles'] for p in t['p']],[],
                         [[i*3+j for j in range(3)] for i in range(len(w['triangles']))])
        for i,label in enumerate(w['material_names']):
            material=bpy.data.materials.new(label+' geometry review')
            rgb=w['material_overrides'][i] or ([38,40,72] if i>=2 else [80,100,80])
            material.diffuse_color=(*[c/255 for c in rgb],1)
            mesh.materials.append(material)
        for polygon,t in zip(mesh.polygons,w['triangles']):polygon.material_index=t['material']
        obj=bpy.data.objects.new(name+' final first person',mesh);scene.collection.objects.link(obj)
        obj.location=(0,row*.3,0)


if __name__=='__main__':
    import argparse,json
    from pathlib import Path
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=Path('build/n64/assets/firstperson-reduced.json'))
    p.add_argument('--raw',type=Path,default=Path('build/n64/assets/firstperson-raw.json'))
    a=p.parse_args();data=json.loads(a.source.read_text())
    print(json.dumps(repair_meters(data,json.loads(a.raw.read_text())),indent=2))
    a.source.write_text(json.dumps(data))
