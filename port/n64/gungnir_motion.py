"""Calibrate CE gameplay motion on GUNGNIR's own intact 82-bone Reach rig.

Shares Jorge's length-preserving support-arm solver and explicit helper/finger
approximations. Bind frames, proportions, skinning, ground correction and weapon
socket are measured again from this source; Jorge vertex/socket tracks are not used.
"""
import sys,json,argparse,math,hashlib
from pathlib import Path
import bpy,numpy as np
from mathutils import Quaternion,Vector,Matrix
sys.path.insert(0,str(Path(__file__).resolve().parent))
import jorge_animation_proof as motion

ROOT=Path(__file__).resolve().parents[2]


class GungnirRetarget(motion.Retarget):
    def __init__(self,source):
        self.raw=json.loads(Path(source).read_text());self.ce=json.loads((ROOT/'halo64-assets/assets/extended-raw.json').read_text())
        self.ce['animations'].update(json.loads((ROOT/'halo64-assets/assets/jorge/playable-half/ce-motion-source.json').read_text()))
        self.cn=self.ce['models']['spartan']['nodes'];self.jn=self.raw['nodes'];self.cb=motion.globals_for(self.cn,True);self.jb=motion.globals_for(self.jn)
        self.ci={n['name'].removeprefix('bip01 '):i for i,n in enumerate(self.cn)};self.ji={n['name']:i for i,n in enumerate(self.jn)}
        ids=[i for i,v in enumerate(self.raw['vertices']) if v[2]<.13]
        self.boot_vertices=np.array([self.raw['vertices'][i]+[1] for i in ids]);self.bind_inverse=np.linalg.inv(np.array(self.jb));self.boot_weights=np.zeros((len(ids),len(self.jn)))
        for i,vi in enumerate(ids):
            for bi,w in self.raw['weights'][vi]:self.boot_weights[i,bi]=w
        core={'pelvis':'pelvis','spine':'spine1','spine1':'spine3','neck':'neck0','head':'head'}
        for side in ('l','r'):
            for a,b in [('thigh','thigh'),('calf','calf'),('foot','foot'),('clavicle','clav'),('upperarm','upperarm'),('forearm','forearm'),('hand','hand')]:core[side+' '+a]=side+'_'+b
        self.mapping={self.ji['b_'+core[n['name'].removeprefix('bip01 ')]]:i for i,n in enumerate(self.cn)}
        self.height_scale=(max(v[2] for v in self.raw['vertices'])-min(v[2] for v in self.raw['vertices']))/(max(v[2] for v in self.ce['models']['spartan']['vertices'])-min(v[2] for v in self.ce['models']['spartan']['vertices']))
        self.correction={};self.calibration=[]
        ends={'b_spine1':('b_spine3','spine1'),'b_spine3':('b_neck0','neck'),'b_neck0':('b_head','head')}
        for side in ('l','r'):
            for a,b,c in [('clav','upperarm','upperarm'),('upperarm','forearm','forearm'),('forearm','hand','hand'),('thigh','calf','calf'),('calf','foot','foot')]:ends[f'b_{side}_{a}']=(f'b_{side}_{b}',f'{side} {c}')
        for ji,ci in self.mapping.items():
            name=self.jn[ji]['name'];align=Quaternion()
            if name in ends:
                jend,cend=ends[name];jvec=self.jb[self.ji[jend]].translation-self.jb[ji].translation;cvec=self.cb[self.ci[cend]].translation-self.cb[ci].translation;align=jvec.rotation_difference(cvec)
            elif name.endswith('_hand'):
                side=name[2];align=(self.jb[ji].translation-self.jb[self.ji[f'b_{side}_forearm']].translation).rotation_difference(self.cb[ci].translation-self.cb[self.ci[f'{side} forearm']].translation)
            self.correction[ji]=self.cb[ci].to_3x3().inverted()@(align.to_matrix()@self.jb[ji].to_3x3())
            self.calibration.append(dict(reach=name,ce=self.cn[ci]['name'],bind_alignment_degrees=math.degrees(align.angle)))
        self.ce_right_marker=motion.local_matrix(self.ce['models']['spartan']['markers']['right hand'][0],True);self.ce_left_marker=motion.local_matrix(self.ce['models']['spartan']['markers']['left hand'][0],True)
        self.ar_left=Vector(self.ce['models']['ar']['markers']['left hand cyborg'][0]['p']);idle=self.ce_globals('idle',0);weapon=idle[self.ci['r hand']]@self.ce_right_marker;self.base_left=(weapon.inverted()@idle[self.ci['l hand']]@self.ce_left_marker).translation
        self.finger_axes={};self.finger_sign={}
        for side in ('l','r'):
            width=(self.jb[self.ji[f'b_{side}_index1']].translation-self.jb[self.ji[f'b_{side}_pinky1']].translation).normalized()
            for digit in ('index','middle','ring','pinky','thumb'):
                for joint in (1,2,3):
                    ji=self.ji[f'b_{side}_{digit}{joint}'];self.finger_axes[ji]=self.jb[ji].to_3x3().inverted()@width
            root=self.ji[f'b_{side}_middle1'];tip=self.ji[f'b_{side}_middle3'];center=self.jb[self.ji[f'b_{side}_grip']].translation;lever=self.jb[tip].translation-self.jb[root].translation
            self.finger_sign[side]=min((-1,1),key=lambda sign:(self.jb[root].translation+Quaternion(width,sign*.7)@lever-center).length)


def run(source,reference,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True);rt=GungnirRetarget(source);motion.RT=rt
    bpy.ops.wm.open_mainfile(filepath=str(Path(reference)/'gungnir-original.blend'));scene=bpy.context.scene;rig=next(o for o in scene.objects if o.type=='ARMATURE');rig.hide_set(False);rig.animation_data_create()
    bpy.context.preferences.edit.keyframe_new_interpolation_type='LINEAR'
    poses={};clips=[];maximum=0.;samples=0;metrics=[];worst={}
    # Independently compare Blender's actual armature modifier with numerical
    # source-weight skinning on each core clip before reducing any geometry.
    objects=[o for o in scene.objects if o.type=='MESH'];deps=bpy.context.evaluated_depsgraph_get()
    for ci,(name,clip) in enumerate(rt.ce['animations'].items()):
        action=bpy.data.actions.new('GUNGNIR / '+name);action.use_fake_user=True;action['source_clip']=name;action['duration_seconds']=clip['duration'];rig.animation_data.action=action;previous={};matrices=[]
        indices=np.rint(np.linspace(0,len(clip['frames'])-1,min(12,len(clip['frames'])))).astype(int)
        for sample,fi in enumerate(indices):
            frame=sample*clip['duration']*30/max(1,len(indices)-1);scene.frame_set(int(frame),subframe=frame-int(frame))
            seated=ci>=18 or name in ('drive','passenger','gunner');armed=(not seated or 'rifle' in name or name=='passenger') and name not in ('death','melee','throw')
            pose,metric=rt.pose(name,int(fi),support_weapon=armed,ground=not seated and name!='death',root_scale=1 if seated else None);motion.apply_pose(rig,pose);metrics.append(metric);matrices.append(np.array(pose))
            for pb in rig.pose.bones:
                q=pb.rotation_quaternion.copy()
                if pb.name in previous and q.dot(previous[pb.name])<0:q.negate();pb.rotation_quaternion=q
                previous[pb.name]=q.copy()
                for path in ('location','rotation_quaternion'):pb.keyframe_insert(path,frame=frame,group=pb.name)
            if name in ('idle','run','fire','reload'):
                bpy.context.view_layer.update();skin=np.array(pose)@rt.bind_inverse
                for ob in objects:
                    ev=ob.evaluated_get(deps);me=ev.to_mesh()
                    ids=[v.value for v in ob.data.attributes['source_vertex'].data]
                    for vi in range(0,len(ids),max(1,len(ids)//7)):
                        original=ids[vi];point=np.array([*rt.raw['vertices'][original],1]);p=sum(((skin[b]@point)[:3]*w for b,w in rt.raw['weights'][original]),np.zeros(3));expected=motion.AXIS@Vector(p)*motion.SCALE
                        error=(me.vertices[vi].co-expected).length
                        if error>maximum:maximum=error;worst=dict(clip=name,frame=int(fi),object=ob.name,vertex=vi,error_m=error)
                        samples+=1
                    ev.to_mesh_clear()
        poses['matrices_'+str(ci)]=np.array(matrices,dtype=np.float32);clips.append(dict(name=name,frames=len(indices),duration=clip['duration'],source_frames=indices.tolist()))
        print('MOTION',name,len(indices),flush=True)
    assert maximum<1e-4,worst
    np.savez_compressed(output/'native-poses.npz',**poses)
    report=dict(source_sha256=hashlib.sha256(Path(source).read_bytes()).hexdigest(),calibration=rt.calibration,clips=clips,bones=len(rt.jn),skin_comparisons=samples,max_blender_skin_error_m=maximum,maximum_support_grip_error_m=max(m['support_grip_error_m'] for m in metrics),limitations='CE motion adaptation; explicit helper/finger approximation and length-preserving support-arm solve; no Reach procedural jiggle or terrain IK')
    (output/'motion-report.json').write_text(json.dumps(report,indent=2)+'\n');rig.animation_data.action=None;rig.hide_set(True)
    bpy.data.libraries.write(str(output/'gungnir-motion.blend'),{scene,*[a for a in bpy.data.actions if a.get('source_clip')]},fake_user=True,compress=True)
    print('PASS MOTION',samples,maximum,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('reference');p.add_argument('output');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run(a.source,a.reference,a.output)
