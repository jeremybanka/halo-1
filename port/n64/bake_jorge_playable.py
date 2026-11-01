"""Bake Jorge's retained rig into all CE gameplay states, without a runtime skeleton."""
import bpy,json,sys,math
import numpy as np
from mathutils import Matrix
import jorge_playable_reduce as task
import jorge_animation_proof as anim
from validate_jorge_ce_materials import actions_for
OUT=task.OUT
CORE=('idle','run','fire','reload','death','jump','melee','throw','drive','passenger','gunner')
BASIS=np.array(((0,-1,0),(0,0,1),(-1,0,0)),dtype=float)/anim.SCALE
HALO_RUNTIME=Matrix(((1,0,0),(0,0,1),(0,-1,0)))
def run():
    scene,rig=task.proof_scene();rt=anim.Retarget();anim.RT=rt
    extra=json.loads((OUT/'ce-motion-source.json').read_text());rt.ce['animations'].update(extra)
    names=list(CORE)+list(extra);obs=sorted(task.body(scene),key=lambda o:o['source_component']);old=actions_for(rig)
    rig.animation_data.action=None
    for action in list(bpy.data.actions):
        if action not in old.values():bpy.data.actions.remove(action)
    points=[];weights=[];uv=[];triangles=[];components=[];colors=[]
    has_colors=all(o.data.color_attributes.get('CE metallic armor') for o in obs)
    for ob in obs:
        start=len(points);group={g.index:rt.ji.get(g.name) for g in ob.vertex_groups}
        for v in ob.data.vertices:
            points.append([*v.co,1]);w=np.zeros(len(rt.jn))
            for g in v.groups:
                if group[g.group] is not None:w[group[g.group]]=g.weight
            assert abs(w.sum()-1)<1e-5
            weights.append(w)
        for p in ob.data.polygons:
            assert len(p.vertices)==3
            triangles.append([i+start for i in p.vertices]);uv.extend([list(ob.data.uv_layers.active.data[l].uv) for l in p.loop_indices]);components.extend([ob['source_component']]*3)
            if has_colors:colors.extend([list(ob.data.color_attributes['CE metallic armor'].data[l].color_srgb[:3]) for l in p.loop_indices])
    points=np.array(points);weights=np.array(weights);rest=np.array([rig.data.bones[n['name']].matrix_local for n in rt.jn]);inv=np.linalg.inv(rest)
    data={'rest':points[:,:3]@BASIS.T,'triangles':np.array(triangles),'uv':np.array(uv)};report={'components':components,'clips':[],'native_vertices':len(points),'triangles':len(triangles)}
    if has_colors:data['colors']=np.rint(np.array(colors)*255).astype(np.uint8)
    rig.animation_data.use_nla=False
    bpy.context.preferences.edit.keyframe_new_interpolation_type='LINEAR'
    allactions=set(old.values())
    for index,name in enumerate(names):
        source=rt.ce['animations'][name];duration=source['duration'];frames=[];grips=[];metrics=[];action=None
        if name not in old:
            action=bpy.data.actions.new('Jorge / '+name);action.use_fake_user=True;action['source_clip']=name;action['duration_seconds']=duration;action['source_type']=source['type'];rig.animation_data.action=action;allactions.add(action)
        else:rig.animation_data.action=old[name]
        previous={}
        for fi in range(len(source['frames'])):
            frame=fi*duration*30/max(1,len(source['frames'])-1);scene.frame_set(int(frame),subframe=frame-int(frame))
            if action:
                seated=index>=18 or name in ('drive','passenger','gunner')
                armed=(not seated or 'rifle' in name or name=='passenger') and name not in ('death','melee','throw')
                pose,metric=rt.pose(name,fi,support_weapon=armed,ground=not seated and name!='death',root_scale=1 if seated else None)
                anim.apply_pose(rig,pose);metrics.append(metric)
                for pb in rig.pose.bones:
                    q=pb.rotation_quaternion.copy()
                    if pb.name in previous and q.dot(previous[pb.name])<0:q.negate();pb.rotation_quaternion=q
                    previous[pb.name]=q.copy()
                    for path in ('location','rotation_quaternion'):pb.keyframe_insert(path,frame=frame,group=pb.name)
            mats=np.array([rig.pose.bones[n['name']].matrix for n in rt.jn]);skin=mats@inv;pos=np.zeros((len(points),3))
            for bi in np.flatnonzero(weights.sum(axis=0)):pos+=(points@skin[bi].T)[:,:3]*weights[:,bi,None]
            frames.append(pos@BASIS.T)
            hand=rig.pose.bones['b_r_grip'].matrix
            # Grip axes are authored in Halo weapon-local coordinates.
            r=(anim.AXIS.inverted()@hand.to_3x3());r=HALO_RUNTIME@r@HALO_RUNTIME.transposed()
            q=r.to_quaternion();q.normalize();grips.append([*(BASIS@np.array(hand.translation)),q.x,q.y,q.z,q.w])
        data['frames_'+str(index)]=np.array(frames,dtype=np.float32);data['grips_'+str(index)]=np.array(grips,dtype=np.float32)
        report['clips'].append({'name':name,'duration':duration,'frames':len(frames),'max_support_error_m':max((r['support_grip_error_m'] for r in metrics),default=0)})
        assert np.isfinite(frames).all() and np.isfinite(grips).all()
        print('BAKED',index,name,len(frames),flush=True)
    np.savez_compressed(OUT/'gameplay-poses.npz',**data);(OUT/'gameplay-poses.json').write_text(json.dumps(report,indent=2)+'\n')
    rig.animation_data.action=None;rig.animation_data.use_nla=True;scene.frame_set(0)
    bpy.data.libraries.write(str(OUT/(task.NAME+'.blend')),{scene,*allactions},fake_user=True,compress=True)
if __name__=='__main__':run()
