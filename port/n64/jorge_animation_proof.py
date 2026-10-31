"""Retarget core CE motion onto the preserved Reach Jorge rig.

All geometry/weights remain the accepted surgical baseline. Work in isolated
Blender scenes; write only animation-proof outputs. No game bank is replaced.
"""
import bpy,json,math,hashlib,sys
from pathlib import Path
import numpy as np
from mathutils import Vector,Matrix,Quaternion
import jorge_surgical_cleanup as cleanup

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'halo64-assets/assets/jorge'
OUT=BASE/'animation-proof'
CLIPS=('idle','run','fire','reload')
SCALE=3.048
AXIS=Matrix(((0,1,0),(-1,0,0),(0,0,1)))

def local_matrix(n,ce=False):
    x,y,z,w=n['q'];q=Quaternion((w,-x,-y,-z) if ce else (w,x,y,z));q.normalize();m=q.to_matrix().to_4x4();m.translation=Vector(n['p']);return m

def globals_for(nodes,ce=False):
    result=[]
    for n in nodes:
        m=local_matrix(n,ce);result.append(result[n['parent']]@m if n['parent']>=0 else m)
    return result

def to_blender(m):
    r=(AXIS@m.to_3x3()).to_4x4();r.translation=AXIS@m.translation*SCALE;return r

class Retarget:
    def __init__(self):
        self.ce=json.loads((ROOT/'halo64-assets/assets/extended-raw.json').read_text());self.raw=json.loads((BASE/'full-cleanup/jorge-cleaned.json').read_text())
        self.cn=self.ce['models']['spartan']['nodes'];self.jn=self.raw['nodes'];self.cb=globals_for(self.cn,True);self.jb=globals_for(self.jn)
        self.ci={n['name'].removeprefix('bip01 '):i for i,n in enumerate(self.cn)};self.ji={n['name']:i for i,n in enumerate(self.jn)}
        # A root-only ground correction for the larger Reach boots. Preserve
        # airborne motion; never stretch a leg or rewrite foot rotations.
        ids=[i for i,v in enumerate(self.raw['vertices']) if v[2]<.13]
        self.boot_vertices=np.array([self.raw['vertices'][i]+[1] for i in ids]);self.bind_inverse=np.linalg.inv(np.array(self.jb));self.boot_weights=np.zeros((len(ids),len(self.jn)))
        for i,vi in enumerate(ids):
            for bi,w in self.raw['weights'][vi]:self.boot_weights[i,bi]=w
        plan=json.loads((BASE/'animation-preflight/rig-and-reduction-plan.json').read_text());self.mapping={self.ji[r['reach_bone']]:r['ce_index'] for r in plan['core_correspondence']}
        self.height_scale=(max(v[2] for v in self.raw['vertices'])-min(v[2] for v in self.raw['vertices']))/(max(v[2] for v in self.ce['models']['spartan']['vertices'])-min(v[2] for v in self.ce['models']['spartan']['vertices']))
        self.correction={};self.calibration=[]
        ends={'b_spine1':('b_spine3','spine1'),'b_spine3':('b_neck0','neck'),'b_neck0':('b_head','head')}
        for side in ('l','r'):
            for a,b,cb in [('clav','upperarm','upperarm'),('upperarm','forearm','forearm'),('forearm','hand','hand'),('thigh','calf','calf'),('calf','foot','foot')]:ends[f'b_{side}_{a}']=(f'b_{side}_{b}',f'{side} {cb}')
        for ji,ci in self.mapping.items():
            name=self.jn[ji]['name'];align=Quaternion()
            if name in ends:
                jend,cend=ends[name];jvec=self.jb[self.ji[jend]].translation-self.jb[ji].translation;cvec=self.cb[self.ci[cend]].translation-self.cb[ci].translation
                align=jvec.rotation_difference(cvec)
            elif name.endswith('_hand'):
                side=name[2];jfore=self.ji[f'b_{side}_forearm'];cfore=self.ci[f'{side} forearm']
                align=(self.jb[ji].translation-self.jb[jfore].translation).rotation_difference(self.cb[ci].translation-self.cb[cfore].translation)
            canonical=align.to_matrix()@self.jb[ji].to_3x3();self.correction[ji]=self.cb[ci].to_3x3().inverted()@canonical
            self.calibration.append({'reach':name,'ce':self.cn[ci]['name'],'bind_direction_alignment_degrees':math.degrees(align.angle)})
        marker=self.ce['models']['spartan']['markers']['right hand'][0];self.ce_right_marker=local_matrix(marker,True)
        self.ce_left_marker=local_matrix(self.ce['models']['spartan']['markers']['left hand'][0],True)
        self.ar_left=Vector(self.ce['models']['ar']['markers']['left hand cyborg'][0]['p'])
        idle=self.ce_globals('idle',0);w=idle[self.ci['r hand']]@self.ce_right_marker;self.base_left=(w.inverted()@idle[self.ci['l hand']]@self.ce_left_marker).translation
        self.finger_axes={};self.finger_sign={}
        for side in ('l','r'):
            width=(self.jb[self.ji[f'b_{side}_index1']].translation-self.jb[self.ji[f'b_{side}_pinky1']].translation).normalized()
            for digit in ('index','middle','ring','pinky','thumb'):
                for joint in (1,2,3):
                    name=f'b_{side}_{digit}{joint}';ji=self.ji[name];self.finger_axes[ji]=self.jb[ji].to_3x3().inverted()@width
            # Determine curl sign geometrically in the authored bind frame.
            root=self.ji[f'b_{side}_middle1'];tip=self.ji[f'b_{side}_middle3'];center=self.jb[self.ji[f'b_{side}_grip']].translation
            lever=self.jb[tip].translation-self.jb[root].translation
            scores={sign:(self.jb[root].translation+Quaternion(width,sign*.7)@lever-center).length for sign in (-1,1)}
            self.finger_sign[side]=min(scores,key=scores.get)

    def ce_globals(self,name,fi):
        clip=self.ce['animations'][name];states=clip['frames'][fi]
        if clip['type']=='overlay':
            combined=[];idle=self.ce['animations']['idle']['frames'][0]
            for i,(a,b) in enumerate(zip(idle,states)):
                ax,ay,az,aw=a['q'];bx,by,bz,bw=b['q'];q=Quaternion((bw,bx,by,bz))@Quaternion((aw,ax,ay,az)) if clip['rot_flags']&(1<<i) else Quaternion((aw,ax,ay,az))
                combined.append({'p':[a['p'][k]+(b['p'][k] if clip['trans_flags']&(1<<i) else 0) for k in range(3)],'q':[q.x,q.y,q.z,q.w]})
            states=combined
        return globals_for([{**n,**s} for n,s in zip(self.cn,states)],True)

    def forward(self,rotations,root_position,grip_amount=1):
        result=[]
        for i,n in enumerate(self.jn):
            parent=n['parent'];local=local_matrix(n);m=result[parent]@local if parent>=0 else local
            if i in rotations:m=rotations[i].to_4x4();m.translation=result[parent]@local.translation if parent>=0 else local.translation
            if n['name']=='b_pelvis':m.translation=root_position
            if i in self.finger_axes:
                side=n['name'][2];digit=n['name'][4:-1];joint=int(n['name'][-1]);amount=grip_amount if side=='l' else 1
                angle=([24,46,34][joint-1] if digit!='thumb' else [8,20,18][joint-1])*amount
                if digit=='index':angle*=.65
                m=m@Quaternion(self.finger_axes[i],math.radians(angle)*self.finger_sign[side]).to_matrix().to_4x4()
            result.append(m)
        return result

    def helper_rotations(self,rot):
        def skin(name):
            i=self.ji[name];return rot.get(i,self.jb[i].to_3x3())@self.jb[i].to_3x3().inverted()
        for side in ('l','r'):
            for helper,a,b,weight in [('elbow_fixup','upperarm','forearm',.5),('shoulder_fixup','clav','upperarm',.5),('hip_fixup',None,'thigh',.5),('knee_fixup','thigh','calf',.5),('wrist_fixup','forearm','hand',.5)]:
                name=f'b_{side}_{helper}';aname=f'b_{side}_{a}' if a else 'b_pelvis';bname=f'b_{side}_{b}';i=self.ji[name]
                blended=skin(aname).to_quaternion().slerp(skin(bname).to_quaternion(),weight).to_matrix();rot[i]=blended@self.jb[i].to_3x3()

    def pose(self,name,fi):
        cp=self.ce_globals(name,fi);rot={ji:cp[ci].to_3x3()@self.correction[ji] for ji,ci in self.mapping.items()}
        jmid=self.ji['b_spine2'];low=self.ji['b_spine1'];high=self.ji['b_spine3']
        a=(rot[low]@self.jb[low].to_3x3().inverted()).to_quaternion();b=(rot[high]@self.jb[high].to_3x3().inverted()).to_quaternion();rot[jmid]=a.slerp(b,.45).to_matrix()@self.jb[jmid].to_3x3()
        jp=self.ji['b_pelvis'];root=self.jb[jp].translation+(cp[0].translation-self.cb[0].translation)*self.height_scale
        grip_amount=.65 if name=='reload' and .12<fi/max(1,len(self.ce['animations'][name]['frames'])-1)<.85 else 1
        self.helper_rotations(rot);pose=self.forward(rot,root,grip_amount)
        jr=self.ji['b_r_hand'];rg=self.ji['b_r_grip'];jl=self.ji['b_l_hand'];lg=self.ji['b_l_grip']
        weapon=(pose[jr].to_3x3()@self.correction[jr].inverted()@self.ce_right_marker.to_3x3()).to_4x4();weapon.translation=pose[rg].translation
        ce_weapon=cp[self.ci['r hand']]@self.ce_right_marker;relative=(ce_weapon.inverted()@cp[self.ci['l hand']]@self.ce_left_marker).translation
        desired_grip=weapon@(self.ar_left+relative-self.base_left)
        desired_wrist=desired_grip-rot[jl]@Vector(self.jn[lg]['p'])
        # Two-link IK changes joint rotations only; bone lengths and source mesh stay fixed.
        upper=self.ji['b_l_upperarm'];lower=self.ji['b_l_forearm'];a0=pose[upper].translation;b0=pose[lower].translation;c0=pose[jl].translation
        l1=(b0-a0).length;l2=(c0-b0).length;v=desired_wrist-a0;distance=v.length;axis=v.normalized();d=max(abs(l1-l2)+1e-5,min(distance,l1+l2-1e-5))
        along=(l1*l1-l2*l2+d*d)/(2*d);height=max(0,l1*l1-along*along)**.5
        pole=b0-a0-axis*(b0-a0).dot(axis)
        if pole.length<1e-6:pole=Vector((0,1,0))-axis*axis.y
        elbow=a0+axis*along+pole.normalized()*height;wrist=a0+axis*d
        rot[upper]=(b0-a0).rotation_difference(elbow-a0).to_matrix()@rot[upper]
        rot[lower]=(c0-b0).rotation_difference(wrist-elbow).to_matrix()@rot[lower]
        self.helper_rotations(rot);pose=self.forward(rot,root,grip_amount)
        # The existing unweighted Reach grip node is the animated weapon socket.
        pose[rg]=weapon
        metrics={'support_reach_clamp_m':abs(distance-d)*SCALE,'support_grip_error_m':(pose[lg].translation-desired_grip).length*SCALE}
        skin=np.array(pose)@self.bind_inverse;boot=np.zeros((len(self.boot_vertices),3))
        for bi in np.flatnonzero(self.boot_weights.sum(axis=0)):
            boot+=(self.boot_vertices@skin[bi].T)[:,:3]*self.boot_weights[:,bi,None]
        lift=max(0.,-float(boot[:,2].min()))
        for m in pose:m.translation.z+=lift
        metrics['root_ground_lift_m']=lift*SCALE
        return pose,metrics

def clone_baseline():
    source=next(s for s in bpy.data.scenes if any(o.get('variant')=='B' for o in s.objects) and 'Jorge full' in s.name)
    scene=bpy.data.scenes.new('Jorge - CE animation proof');bpy.context.window.scene=scene
    original=next(o for o in source.objects if o.type=='ARMATURE');rig=original.copy();rig.data=original.data.copy();rig.animation_data_clear();rig.name='Jorge - retained Reach rig';scene.collection.objects.link(rig);rig.hide_set(False)
    objects=[]
    for ob in source.objects:
        if ob.get('variant')!='B':continue
        new=ob.copy();new.name=ob.name.replace('B /','Jorge /');scene.collection.objects.link(new);new.parent=rig;new.hide_render=False;new.hide_set(False)
        for mod in new.modifiers:
            if mod.type=='ARMATURE':mod.object=rig
        objects.append(new)
    cleanup.studio(scene);scene.render.fps=30;scene.camera.data.ortho_scale=2.85;return scene,rig,objects

def add_weapon(scene,rig,rt):
    raw=rt.ce['models']['ar'];me=bpy.data.meshes.new('Original CE assault rifle');me.from_pydata([Vector(p)*SCALE for p in raw['vertices']],[],raw['faces']);uv=me.uv_layers.new(name='Original CE UV')
    for mi,path in enumerate(raw.get('textures_fullres',raw['textures'])):
        mat=bpy.data.materials.new(f'CE rifle / {mi}');mat.use_nodes=True;bs=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');bs.inputs['Roughness'].default_value=.7
        if path:
            tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(path,check_existing=True);tex.image.alpha_mode='NONE';mat.node_tree.links.new(tex.outputs['Color'],bs.inputs['Base Color'])
        else:bs.inputs['Base Color'].default_value=(.14,.17,.16,1)
        me.materials.append(mat)
    for face,mi in zip(me.polygons,raw['materials']):
        face.material_index=mi
        for li,vi in zip(face.loop_indices,face.vertices):uv.data[li].uv=(raw['uv'][vi][0],1-raw['uv'][vi][1])
    ob=bpy.data.objects.new('CE rifle - shared weapon attachment',me);scene.collection.objects.link(ob);ob.parent=rig;ob.parent_type='BONE';ob.parent_bone='b_r_grip';ob.matrix_basis=Matrix.Translation((0,-rig.data.bones['b_r_grip'].length,0));return ob

def apply_pose(rig,pose):
    # Convert desired armature-space matrices to local bases in hierarchy order.
    rest={b.name:b.matrix_local.copy() for b in rig.data.bones}
    for i,n in enumerate(RT.jn):
        name=n['name'];parent=n['parent'];world=to_blender(pose[i])
        basis=rest[name].inverted()@world if parent<0 else rest[name].inverted()@rest[RT.jn[parent]['name']]@to_blender(pose[parent]).inverted()@world
        p=rig.pose.bones[name];p.rotation_mode='QUATERNION';p.matrix_basis=basis
    bpy.context.view_layer.update()

def pilot():
    global RT
    OUT.mkdir(exist_ok=True);RT=Retarget();scene,rig,objects=clone_baseline();weapon=add_weapon(scene,rig,RT)
    pose,metrics=RT.pose('idle',0);apply_pose(rig,pose);rig.hide_set(True)
    for image in bpy.data.images:
        if image.filepath and image.has_data:image.pack()
    bpy.data.libraries.write(str(OUT/'jorge-animation-pilot.blend'),{scene},fake_user=True)
    (OUT/'calibration.json').write_text(json.dumps({'calibration':RT.calibration,'finger_curl_signs':RT.finger_sign,'idle_metrics':metrics},indent=2))
    print('PILOT',metrics);return scene

def source_hashes():
    paths=[BASE/'jorge-original.json',BASE/'backpack-original.json',BASE/'full-cleanup/jorge-cleaned.json',BASE/'full-cleanup/jorge-surgical-cleanup.blend',ROOT/'halo64-assets/assets/extended-raw.json']
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}

def ground_between_keys(scene,rig,action,rt,source_frames):
    """Clamp boot penetration between sparse rotation keys at 120 Hz.

    Retain every authored key and all rotations. Only add a small vertical root
    correction; collecting before inserting avoids accumulating corrections.
    """
    rig.animation_data.action=action;end=action['duration_seconds']*30
    times=sorted(set(source_frames+[i/4 for i in range(round(end*4)+1)]))
    rest=np.array([to_blender(m) for m in rt.jb]);inverse=np.linalg.inv(rest)
    verts=rt.boot_vertices.copy();verts[:,:3]=verts[:,:3]@np.array(AXIS).T*SCALE
    records=[];maximum=0.;root=rig.pose.bones['b_pedestal'];world_to_local=root.bone.matrix_local.to_3x3().inverted()
    for frame in times:
        scene.frame_set(int(frame),subframe=frame-int(frame));bpy.context.view_layer.update();skin=np.array([rig.pose.bones[n['name']].matrix for n in rt.jn])@inverse;points=np.zeros((len(verts),3))
        for bi in np.flatnonzero(rt.boot_weights.sum(axis=0)):points+=(verts@skin[bi].T)[:,:3]*rt.boot_weights[:,bi,None]
        lift=max(0.,-float(points[:,2].min()));maximum=max(maximum,lift)
        records.append((frame,root.location.copy()+world_to_local@Vector((0,0,lift))))
    for frame,location in records:
        root.location=location;root.keyframe_insert('location',frame=frame,group=root.name)
    return {'sampling_hz':120,'root_translation_keys':len(records),'max_added_lift_between_source_keys_m':maximum}

def build():
    """Bake editable local TRS actions; independently verify full-mesh skinning."""
    global RT
    OUT.mkdir(exist_ok=True);before=source_hashes();RT=Retarget();scene,rig,objects=clone_baseline();weapon=add_weapon(scene,rig,RT)
    rig.animation_data_create();raw=RT.raw;original=json.loads((BASE/'full-cleanup/source-complete.json').read_text())
    old_interpolation=bpy.context.preferences.edit.keyframe_new_interpolation_type
    bpy.context.preferences.edit.keyframe_new_interpolation_type='LINEAR'
    source_lookup={vi:i for i,vi in enumerate(raw['source_vertex_ids'])}
    object_ids={ob.name:np.array([source_lookup[v.value] for v in ob.data.attributes['source_vertex'].data]) for ob in objects}
    # Audit unchanged source coordinates, weights, topology, UVs and constraint attributes.
    geometry={'triangles':0,'components':len(objects),'max_position_error_m':0.,'max_uv_error':0.,'max_weight_error':0.}
    for ob in objects:
        me=ob.data;vis=[x.value for x in me.attributes['source_vertex'].data];fis=[x.value for x in me.attributes['source_face'].data]
        geometry['triangles']+=len(me.polygons)
        for v,vi in zip(me.vertices,vis):
            geometry['max_position_error_m']=max(geometry['max_position_error_m'],(v.co-cleanup.pos(original['vertices'][vi])).length)
            actual={ob.vertex_groups[g.group].name:g.weight for g in v.groups if ob.vertex_groups[g.group].name in rig.data.bones}
            expected={raw['nodes'][bi]['name']:w for bi,w in original['weights'][vi]}
            assert actual.keys()==expected.keys()
            geometry['max_weight_error']=max(geometry['max_weight_error'],max(abs(actual[k]-expected[k]) for k in actual))
        for f,fi in zip(me.polygons,fis):
            assert [vis[v] for v in f.vertices]==original['faces'][fi]
            for li,vi in zip(f.loop_indices,original['faces'][fi]):
                geometry['max_uv_error']=max(geometry['max_uv_error'],(me.uv_layers.active.data[li].uv-Vector((original['uv'][vi][0],1-original['uv'][vi][1]))).length)
        assert 'source_normal' in me.attributes
    assert geometry['triangles']==26076 and geometry['components']==110
    assert geometry['max_position_error_m']<1e-7 and geometry['max_uv_error']<2e-6 and geometry['max_weight_error']<1e-6
    rest=np.array([to_blender(m) for m in RT.jb]);inverse=np.linalg.inv(rest)
    vertices=np.array([list(cleanup.pos(p))+[1] for p in raw['vertices']])
    influences=[]
    for bi in range(len(RT.jn)):
        selected=[(vi,w) for vi,weights in enumerate(raw['weights']) for bone,w in weights if bone==bi]
        influences.append((np.array([v for v,w in selected],dtype=int),np.array([w for v,w in selected])))
    actions={};reports={};cache={};motion_bounds={ob.name:{'component':ob.get('source_component'),'group':ob.get('group'),'min':[float('inf')]*3,'max':[-float('inf')]*3} for ob in objects}
    for name in CLIPS:
        clip=RT.ce['animations'][name];action=bpy.data.actions.new('Jorge / '+name);action.use_fake_user=True;action['source_clip']=name;action['duration_seconds']=clip['duration'];action['source_type']=clip['type'];rig.animation_data.action=action;actions[name]=action
        previous={};frames=[];mats=[];metrics=[];max_skin=max_pose=max_socket=max_length=max_scale=0.;mins=[];maxs=[]
        for fi in range(len(clip['frames'])):
            frame=fi*clip['duration']*30/max(1,len(clip['frames'])-1);scene.frame_set(int(frame),subframe=frame-int(frame))
            pose,metric=RT.pose(name,fi);apply_pose(rig,pose)
            for pb in rig.pose.bones:
                q=pb.rotation_quaternion.copy()
                if pb.name in previous and q.dot(previous[pb.name])<0:q.negate();pb.rotation_quaternion=q
                previous[pb.name]=q.copy()
                for path in ('location','rotation_quaternion','scale'):pb.keyframe_insert(path,frame=frame,group=pb.name)
                max_scale=max(max_scale,max(abs(v-1) for v in pb.scale))
            bpy.context.view_layer.update();desired=np.array([to_blender(m) for m in pose]);frames.append(frame);mats.append(desired);metrics.append(metric)
            actual=np.array([rig.pose.bones[n['name']].matrix for n in RT.jn]);max_pose=max(max_pose,float(np.max(np.abs(actual-desired))))
            max_socket=max(max_socket,float(np.max(np.abs(np.array(weapon.matrix_world)-desired[RT.ji['b_r_grip']]))))
            for bi,n in enumerate(RT.jn):
                if n['parent']<0 or n['name'] in ('b_pelvis','b_r_grip'):continue
                length=(pose[bi].translation-pose[n['parent']].translation).length
                max_length=max(max_length,abs(length-Vector(n['p']).length)*SCALE)
            skin=desired@inverse;expected=np.zeros((len(vertices),3))
            for bi,(ids,w) in enumerate(influences):
                if len(ids):expected[ids]+=(vertices[ids]@skin[bi].T)[:,:3]*w[:,None]
            assert np.isfinite(expected).all();mins.append(expected.min(axis=0).tolist());maxs.append(expected.max(axis=0).tolist())
            graph=bpy.context.evaluated_depsgraph_get()
            for ob in objects:
                ev=ob.evaluated_get(graph);me=ev.to_mesh();actual_vertices=np.array([v.co for v in me.vertices]);ev.to_mesh_clear();points=expected[object_ids[ob.name]]
                max_skin=max(max_skin,float(np.max(np.linalg.norm(actual_vertices-points,axis=1))))
                bound=motion_bounds[ob.name];bound['min']=np.minimum(bound['min'],points.min(axis=0)).tolist();bound['max']=np.maximum(bound['max'],points.max(axis=0)).tolist()
        assert max_pose<2e-5 and max_skin<3e-5 and max_socket<2e-5 and max_length<2e-5 and max_scale<1e-5,(name,max_pose,max_skin,max_socket,max_length,max_scale)
        cache[name+'_matrices']=np.array(mats,dtype=np.float32);cache[name+'_seconds']=np.array(frames,dtype=np.float32)/30
        reports[name]={'source_frames':len(frames),'duration_seconds':clip['duration'],'source_type':clip['type'],'max_blender_pose_matrix_error':max_pose,'max_independent_skinning_error_m':max_skin,'max_weapon_socket_matrix_error':max_socket,'max_bone_length_error_m':max_length,'max_scale_error':max_scale,'max_support_reach_clamp_m':max(m['support_reach_clamp_m'] for m in metrics),'max_support_grip_error_m':max(m['support_grip_error_m'] for m in metrics),'max_root_ground_lift_m':max(m['root_ground_lift_m'] for m in metrics),'bounds_min':np.min(mins,axis=0).tolist(),'bounds_max':np.max(maxs,axis=0).tolist(),'per_frame_bounds_min':mins,'per_frame_bounds_max':maxs}
        reports[name]['interpolated_ground_correction']=ground_between_keys(scene,rig,action,RT,frames)
        playback=[];playback_floor=100.
        for frame in range(round(clip['duration']*30)+1):
            scene.frame_set(frame);bpy.context.view_layer.update();desired=np.array([rig.pose.bones[n['name']].matrix for n in RT.jn]);playback.append(desired);skin=desired@inverse;points=np.zeros((len(vertices),3))
            for bi,(ids,w) in enumerate(influences):
                if len(ids):points[ids]+=(vertices[ids]@skin[bi].T)[:,:3]*w[:,None]
            playback_floor=min(playback_floor,float(points[:,2].min()))
            for ob in objects:
                p=points[object_ids[ob.name]];bound=motion_bounds[ob.name];bound['min']=np.minimum(bound['min'],p.min(axis=0)).tolist();bound['max']=np.maximum(bound['max'],p.max(axis=0)).tolist()
        cache[name+'_playback_matrices']=np.array(playback,dtype=np.float32);cache[name+'_playback_seconds']=np.arange(len(playback),dtype=np.float32)/30
        reports[name]['final_playback_samples']=len(playback);reports[name]['final_playback_min_z_m']=playback_floor
        assert playback_floor>-.0001,(name,playback_floor)
        print('CLIP',name,{k:v for k,v in reports[name].items() if not k.startswith('per_frame')},flush=True)
    bpy.context.preferences.edit.keyframe_new_interpolation_type=old_interpolation
    cache['bind_matrices']=rest.astype(np.float32);cache['source_vertex_ids']=np.array(raw['source_vertex_ids'],dtype=np.int32);np.savez_compressed(OUT/'motion-proof.npz',**cache)
    rig.animation_data.action=actions['idle'];scene.frame_start=0;scene.frame_end=60;scene.frame_set(0);rig.hide_set(True)
    for ob in scene.objects:ob.select_set(False)
    rig.select_set(True);bpy.context.view_layer.objects.active=rig
    for im in bpy.data.images:
        if im.filepath and im.has_data:im.pack()
    report={'status':'Four-clip offline animation proof; not a game-runtime integration','source_hashes':before,'source_files_unchanged':source_hashes()==before,'geometry':geometry,'weapon_triangles':len(weapon.data.polygons),'reach_bones':85,'ce_motion_bones':19,'calibration':RT.calibration,'finger_curl_signs':RT.finger_sign,'clips':reports,'node_order':[n['name'] for n in RT.jn],'motion_cache_space':'Blender armature-space matrices in meters; skin = pose @ inverse(bind); seconds use existing runtime clip-duration convention','limitations':['Remaining seven shared clips are untested','Grip curls and fixup bones use explicit approximations, not Reach runtime controllers','Reload is body motion with a rigid attached rifle; magazine and bolt animation are not implemented','Motion bounds are evidence for later reduction, not permission to delete geometry','No further geometry reduction or runtime bank replacement in this proof']}
    assert report['source_files_unchanged']
    (OUT/'animation-report.json').write_text(json.dumps(report,indent=2)+'\n');(OUT/'component-motion-bounds.json').write_text(json.dumps(motion_bounds,indent=2)+'\n')
    bpy.data.libraries.write(str(OUT/'jorge-animation-proof.blend'),{scene,*actions.values()},fake_user=True)
    print('BUILT',str(OUT/'jorge-animation-proof.blend'),flush=True)

def proof_scene():
    scene=next(s for s in bpy.data.scenes if s.name.startswith('Jorge - CE animation proof'));bpy.context.window.scene=scene
    rig=next(o for o in scene.objects if o.type=='ARMATURE');return scene,rig

def select_clip(scene,rig,name,seconds=0):
    rig.animation_data.use_nla=False
    rig.animation_data.action=next(a for a in bpy.data.actions if a.get('source_clip')==name)
    scene.frame_start=0;scene.frame_end=round(rig.animation_data.action['duration_seconds']*30)
    f=seconds*30;scene.frame_set(int(f),subframe=f-int(f));bpy.context.view_layer.update()

def render_checks():
    scene,rig=proof_scene();folder=OUT/'renders';folder.mkdir(exist_ok=True)
    scene.render.resolution_x=480;scene.render.resolution_y=600;scene.cycles.samples=12;scene.cycles.use_denoising=True
    for name,fractions in [('idle',[0]),('run',[0,.25,.5,.75]),('fire',[0,.5,1]),('reload',[0,.2,.4,.6,.8,1])]:
        for fraction in fractions:
            duration=next(a['duration_seconds'] for a in bpy.data.actions if a.get('source_clip')==name);select_clip(scene,rig,name,duration*fraction)
            cleanup.camera(scene,'three_quarter');scene.camera.data.ortho_scale=2.85
            scene.render.filepath=str(folder/f'{name}-{round(fraction*100):03d}.png');bpy.ops.render.render(write_still=True)
    print('CHECK RENDERS COMPLETE',flush=True)

def export_proof():
    scene,rig=proof_scene();select_clip(scene,rig,'idle');rig.hide_set(False)
    for ob in scene.objects:ob.select_set(ob.type in ('ARMATURE','MESH'))
    bpy.context.view_layer.objects.active=rig
    bpy.ops.export_scene.gltf(filepath=str(OUT/'jorge-animation-proof.glb'),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='ACTIONS',export_force_sampling=True,export_frame_range=False,export_frame_step=1,export_skins=True,export_yup=True,export_materials='EXPORT',export_extras=True)
    # Make Space/Play immediately demonstrate all four clips in the saved file.
    rig.animation_data.action=None;rig.animation_data.use_nla=True
    for track in list(rig.animation_data.nla_tracks):
        if track.name.startswith('Proof sequence'):rig.animation_data.nla_tracks.remove(track)
    for marker in list(scene.timeline_markers):
        if marker.name in {n.upper() for n in CLIPS}:scene.timeline_markers.remove(marker)
    track=rig.animation_data.nla_tracks.new();track.name='Proof sequence - shared CE motion';cursor=0
    for name,repeat in [('idle',1),('run',3),('fire',4),('reload',1)]:
        action=next(a for a in bpy.data.actions if a.get('source_clip')==name);strip=track.strips.new(name,cursor,action);strip.repeat=repeat;strip.extrapolation='NOTHING';strip.blend_type='REPLACE';strip.blend_in=0;strip.blend_out=0
        scene.timeline_markers.new(name.upper(),frame=cursor);cursor=round(strip.frame_end)
    scene.frame_start=0;scene.frame_end=cursor-1;scene.frame_set(0)
    rig.hide_set(True)
    for ob in scene.objects:ob.select_set(False)
    # This command runs only in the isolated background process, never live MCP.
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'jorge-animation-proof.blend'))
    print('EXPORTED ANIMATED GLB AND BLEND',flush=True)

def render_motion():
    scene,rig=proof_scene();scene.render.resolution_x=420;scene.render.resolution_y=520;scene.cycles.samples=8;scene.cycles.use_denoising=True
    scene.render.film_transparent=False
    # A restrained floor makes ground contact visible in the animation review.
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.002));floor=bpy.context.object;floor.name='Preview ground (not exported)'
    mat=bpy.data.materials.new('Preview ground');mat.diffuse_color=(.08,.095,.1,1);floor.data.materials.append(mat)
    cleanup.camera(scene,'three_quarter');scene.camera.data.ortho_scale=2.95
    scene.camera.location=(3,-5,2.4);scene.camera.rotation_euler=(Vector((0,-.15,1.15))-scene.camera.location).to_track_quat('-Z','Y').to_euler()
    for name in CLIPS:
        select_clip(scene,rig,name);folder=OUT/'frames'/name;folder.mkdir(parents=True,exist_ok=True)
        for frame in range(scene.frame_end):
            scene.frame_set(frame);scene.render.filepath=str(folder/f'{frame:04d}.png');bpy.ops.render.render(write_still=True)
        print('RENDERED MOTION',name,flush=True)
    floor.hide_render=True
    for name,fraction in [('idle',0),('run',.25),('run',.75),('reload',.4),('reload',.8)]:
        action=next(a for a in bpy.data.actions if a.get('source_clip')==name);select_clip(scene,rig,name,action['duration_seconds']*fraction)
        for view in ('front','left','back'):
            cleanup.camera(scene,view);scene.camera.data.ortho_scale=2.95;scene.render.filepath=str(OUT/'renders'/f'{name}-{round(fraction*100):03d}-{view}.png');bpy.ops.render.render(write_still=True)
    print('MOTION RENDERS COMPLETE',flush=True)

if __name__=='__main__':
    if '--pilot' in sys.argv:pilot()
    if '--build' in sys.argv:build()
    if '--checks' in sys.argv:render_checks()
    if '--export' in sys.argv:export_proof()
    if '--motion' in sys.argv:render_motion()
