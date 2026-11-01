"""Actual near/far N64 Spartans, native scale, packed colors and shared clips.

Reference bodies use quantized runtime animation samples, rather than another
retarget. Nothing in the port's generated banks is modified.
"""
import bpy, json, sys, math, hashlib
import numpy as np
from mathutils import Vector, Matrix, Quaternion
import jorge_playable_reduce as task
import jorge_half_budget as half
import jorge_animation_proof as animation
import jorge_surgical_cleanup as cleanup

OUT=task.OUT/'standard'; DATA=task.ROOT/'halo64-assets/assets/extended-reduced.json'
PACK=task.ROOT/'halo64-assets/generated/extended-report.json'
# Packed N64 (Halo X, Halo Z, -Halo Y) -> Blender (Halo Y, -Halo X, Halo Z).
AXIS=Matrix(((0,0,-1),(-1,0,0),(0,1,0)))
LOCAL=Matrix(((1,0,0),(0,0,1),(0,-1,0)))
GREEN=(57,183,69)  # scene.c's actual green player profile

def setup(name):
    raw=json.loads(DATA.read_text());preview=json.loads(half.AR_SOURCE.read_text())[name]
    packed=json.loads(PACK.read_text());scene=bpy.data.scenes.new('Standard N64 '+name);bpy.context.window.scene=scene
    scene.render.fps=30;cleanup.studio(scene);scene.camera.data.ortho_scale=2.95
    points=[AXIS@Vector(p)*animation.SCALE for p in preview['positions']]
    mesh=bpy.data.meshes.new(name+' packed reference');mesh.from_pydata(points,[],[(i,i+1,i+2) for i in range(0,len(points),3)])
    color=mesh.color_attributes.new(name='Runtime green profile',type='FLOAT_COLOR',domain='CORNER')
    for c,rgb,mask in zip(color.data,preview['colors'],preview['team_mask']):
        m=round(mask*255);tinted=[(v*(65025-m*(255-t))+32512)//65025 for v,t in zip(rgb,GREEN)]
        c.color_srgb=(*[v/255 for v in tinted],1)
    mat=bpy.data.materials.new(name+' original packed unlit color');mat.use_nodes=True;ns=mat.node_tree.nodes;ns.clear()
    vertex=ns.new('ShaderNodeVertexColor');vertex.layer_name=color.name;output=ns.new('ShaderNodeOutputMaterial');mat.node_tree.links.new(vertex.outputs['Color'],output.inputs['Surface'])
    mesh.materials.append(mat);ob=bpy.data.objects.new(name+' / actual N64 reference',mesh);scene.collection.objects.link(ob)
    weapon=bpy.data.objects.new('AR reference',bpy.data.meshes.new('placeholder'));scene.collection.objects.link(weapon);half.port_ar(weapon)
    ob['reference_only']=True;weapon['reference_only']=True
    report={'model':name,'runtime_vertices':packed['vertices'][name],'triangles':preview['triangle_count'],
            'scale_m_per_halo_unit':animation.SCALE,'team_color':list(GREEN),'shading':'Original packed vertex RGB, unlit',
            'sources':{str(p.relative_to(task.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (DATA,PACK,half.AR_SOURCE)}}
    order=packed['triangle_order'][name];corners=[i*3+c for i in order for c in range(3)]
    model=raw['models'][name] if name=='spartan' else raw['spartan_lod']
    packed_rest=np.round(np.array([p for t in model['triangles'] for p in t['p']])*128)/128
    expected=np.array([(p[0],p[2],-p[1]) for p in packed_rest[corners]])
    assert np.array_equal(expected,np.array(preview['positions']))
    report['packed_rest_positions_exact']=True
    clips=raw['animations' if name=='spartan' else 'animations_lod']
    return scene,ob,weapon,clips,raw['weapon_attachment'],corners,report

def pose(state,name,fraction):
    scene,ob,weapon,clips,attachments,corners,report=state;bpy.context.window.scene=scene
    clip=clips[name];frames=clip['frames'];f=min(len(frames)-1,max(0,fraction*(len(frames)-1)))
    i=int(f);j=min(i+1,len(frames)-1);t=f-i
    # Quantization precedes interpolation, exactly as in pack_animation/scene.c.
    a=np.round(np.array(frames[i])*128)/128;b=np.round(np.array(frames[j])*128)/128
    raw=(a*(1-t)+b*t)[corners];coords=np.column_stack((raw[:,1],-raw[:,0],raw[:,2]))*animation.SCALE
    ob.data.vertices.foreach_set('co',coords.ravel());ob.data.update()
    poses=attachments[name]['poses'];a=poses[i];b=poses[j]
    qa=Quaternion((a['quat'][3],*a['quat'][:3]));qb=Quaternion((b['quat'][3],*b['quat'][:3]))
    if qa.dot(qb)<0:qb.negate()
    q=Quaternion([x*(1-t)+y*t for x,y in zip(qa,qb)]);q.normalize()
    m=(AXIS@q.to_matrix()@LOCAL).to_4x4();m.translation=AXIS@(Vector(a['pos']).lerp(Vector(b['pos']),t))*animation.SCALE
    weapon.matrix_world=m;scene.frame_set(round(fraction*clip['duration']*30))

def render(name,motion=False):
    OUT.mkdir(exist_ok=True);folder=OUT/name;folder.mkdir(exist_ok=True);(folder/'renders').mkdir(exist_ok=True)
    state=setup(name);scene=state[0];scene.render.resolution_x=600;scene.render.resolution_y=750;scene.cycles.samples=8
    for clip,fraction in [('idle',0),('run',.25),('run',.5),('reload',.4),('reload',.8)]:
        pose(state,clip,fraction)
        for view in (('front','back','left','right','three_quarter') if clip=='idle' else ('three_quarter',)):
            cleanup.camera(scene,view);scene.render.filepath=str(folder/'renders'/f'ce-{clip}-{round(fraction*100):03d}-{view}.png');bpy.ops.render.render(write_still=True)
    (folder/'reference-report.json').write_text(json.dumps(state[-1],indent=2)+'\n')
    if motion:
        scene.render.resolution_x=420;scene.render.resolution_y=520;scene.cycles.samples=4;scene.render.film_transparent=False
        bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.002));floor=bpy.context.object;floor.name='Reference ground'
        mat=bpy.data.materials.new('Reference ground');mat.diffuse_color=(.08,.095,.1,1);floor.data.materials.append(mat)
        scene.camera.location=(3,-5,2.4);scene.camera.rotation_euler=(Vector((0,-.15,1.15))-scene.camera.location).to_track_quat('-Z','Y').to_euler()
        for clip in animation.CLIPS:
            count=round(state[3][clip]['duration']*30);frames=folder/'frames'/clip;frames.mkdir(parents=True,exist_ok=True)
            for f in range(count):
                pose(state,clip,f/count);scene.render.filepath=str(frames/f'{f:04d}.png');bpy.ops.render.render(write_still=True)
    pose(state,'idle',0);cleanup.camera(scene,'three_quarter')
    bpy.data.libraries.write(str(folder/(name+'-reference.blend')),{scene},fake_user=True)
    print('STANDARD COMPLETE',name,flush=True)

if __name__=='__main__':
    for name in ('spartan','spartan_lod'):
        if '--'+name in sys.argv:render(name,'--motion' in sys.argv)
