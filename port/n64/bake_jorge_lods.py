"""Sample the accepted 39 actions on each reduced rig; do not retarget again."""
from pathlib import Path
import sys,json,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
import numpy as np
from mathutils import Matrix
import jorge_lods as task
import jorge_animation_proof as anim

BASIS=np.array(((0,-1,0),(0,0,1),(-1,0,0)),dtype=float)/anim.SCALE
RUNTIME=Matrix(((1,0,0),(0,0,1),(0,-1,0)))

def run(lod):
    folder=task.OUT/lod;name='jorge-'+lod
    bpy.ops.wm.open_mainfile(filepath=str(folder/(name+'.blend')))
    scene=next(s for s in bpy.data.scenes if s.name.startswith('Jorge - '+lod+' body LOD'))
    bpy.context.window.scene=scene;rig=next(o for o in scene.objects if o.type=='ARMATURE')
    objects=sorted(task.task.body(scene),key=lambda o:o['source_component'])
    bones=[b.name for b in rig.data.bones];indices={n:i for i,n in enumerate(bones)}
    points=[];weights=[];faces=[];uv=[];colors=[];components=[];component_vertices={};rigid={}
    for ob in objects:
        start=len(points);group={g.index:indices.get(g.name) for g in ob.vertex_groups}
        for v in ob.data.vertices:
            points.append([*v.co,1]);w=np.zeros(len(bones))
            for g in v.groups:
                if group[g.group] is not None:w[group[g.group]]=g.weight
            assert abs(w.sum()-1)<1e-5 and np.count_nonzero(w)<=4
            weights.append(w)
        component_vertices[ob['source_component']]=[start,len(ob.data.vertices)]
        unique=set(tuple(np.flatnonzero(w)) for w in weights[start:])
        if len(unique)==1 and len(next(iter(unique)))==1:
            rigid[ob['source_component']]=bones[next(iter(unique))[0]]
        for p in ob.data.polygons:
            assert len(p.vertices)==3
            faces.append([start+i for i in p.vertices])
            for li in p.loop_indices:
                uv.append(list(ob.data.uv_layers.active.data[li].uv))
                colors.append(list(ob.data.color_attributes[task.COLOR].data[li].color_srgb[:3]))
                components.append(ob['source_component'])
    points=np.array(points);weights=np.array(weights)
    inv=np.linalg.inv(np.array([rig.data.bones[n].matrix_local for n in bones]))
    data=dict(rest=points[:,:3]@BASIS.T,triangles=np.array(faces),uv=np.array(uv),
              colors=np.rint(np.clip(colors,0,1)*255).astype(np.uint8))
    meta=json.loads((task.SOURCE/'gameplay-poses.json').read_text())
    source=np.load(task.SOURCE/'gameplay-poses.npz')
    actions={a['source_clip']:a for a in bpy.data.actions if a.get('source_clip')}
    report=dict(components=components,component_vertices=component_vertices,rigid_components=rigid,clips=meta['clips'],
                native_vertices=len(points),triangles=len(faces),bones=bones)
    rig.data.pose_position='POSE';rig.animation_data.use_nla=False
    socket_error=0.
    for ci,clip in enumerate(meta['clips']):
        rig.animation_data.action=actions[clip['name']];frames=[]
        for fi in range(clip['frames']):
            time=fi*clip['duration']*30/max(1,clip['frames']-1)
            scene.frame_set(int(time),subframe=time-int(time));bpy.context.view_layer.update()
            skin=np.array([rig.pose.bones[n].matrix for n in bones])@inv
            pos=np.zeros((len(points),3))
            for bi in np.flatnonzero(weights.sum(0)):
                pos+=(points@skin[bi].T)[:,:3]*weights[:,bi,None]
            frames.append(pos@BASIS.T)
            hand=rig.pose.bones['b_r_grip'].matrix
            socket_error=max(socket_error,float(np.linalg.norm(BASIS@np.array(hand.translation)-source['grips_'+str(ci)][fi,:3])))
        data['frames_'+str(ci)]=np.array(frames,dtype=np.float32)
        # Attachments and durations are exactly the accepted game's bank.
        data['grips_'+str(ci)]=source['grips_'+str(ci)]
        assert np.isfinite(frames).all()
        print('BAKED',lod,ci,clip['name'],len(frames),flush=True)
    assert socket_error<1e-5,socket_error
    report['maximum_socket_translation_error_halo_units']=socket_error
    np.savez_compressed(folder/'gameplay-poses.npz',**data)
    (folder/'gameplay-poses.json').write_text(json.dumps(report,indent=2)+'\n')
    rig.animation_data.action=None;rig.animation_data.use_nla=True;scene.frame_set(0)
    bpy.data.libraries.write(str(folder/(name+'.blend')),{scene,*actions.values()},fake_user=True,compress=True)
    print('BAKE COMPLETE',lod,len(points),len(faces),socket_error,flush=True)

if __name__=='__main__':
    for lod in ('near','far'):
        if '--lod' not in sys.argv or sys.argv[sys.argv.index('--lod')+1]==lod:run(lod)
