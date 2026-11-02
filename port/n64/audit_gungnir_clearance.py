"""Broad armor-front depth versus the independent source-fitted undersuit.

Use each plate's own posed affine frame. Exclude garment branches belonging to
other limbs: a hand crossing the chest is ordinary occlusion, not swollen cloth.
"""
import argparse,json,math,hashlib
from pathlib import Path
import numpy as np
from audit_jorge_armor_clearance import depth
from pack_assets import position


def run(candidate,output,source,motion,inventory):
    from PIL import Image
    from extract_gungnir import bone_globals
    from audit_models import engine
    output.mkdir(parents=True,exist_ok=True)
    data=json.loads((candidate/'solid.json').read_text());rows=[];restore=[set(),set()]
    original=json.loads(source.read_text());parts={p['id']:p for p in json.loads(inventory.read_text())}
    original_rest=engine(original['vertices']);original_faces=np.array(original['faces']);original_points=np.c_[original['vertices'],np.ones(len(original['vertices']))]
    inverse=np.linalg.inv(np.array(bone_globals(original['nodes'])));native=np.load(motion/'native-poses.npz');original_poses={}
    for ci in (0,1,3,10):
        if 'matrices_'+str(ci) not in native:continue
    def original_pose(ci,fi):
        key=ci,fi
        if key not in original_poses:
            skin=native['matrices_'+str(ci)][fi]@inverse;posed=np.zeros((len(original_points),3))
            for vi,ws in enumerate(original['weights']):
                for b,w in ws:posed[vi]+=(skin[b]@original_points[vi])[:3]*w
            original_poses[key]=np.rint(engine(posed)*512)/512
        return original_poses[key]
    groups=[('chest',lambda n:n in ('torso','chest-parafoil','chest-lower'),('b_torso','b_spine1','b_spine2','b_spine3','b_belt'),0,1),
        ('back',lambda n:n=='torso' or n.startswith('torso-back'),('b_torso','b_spine1','b_spine2','b_spine3','b_belt','b_neck0'),0,-1),
        ('codpiece',lambda n:n=='belt',('b_pelvis','b_belt','b_l_hip_fixup','b_r_hip_fixup'),0,1),
        ('left shoulder',lambda n:n=='shoulder-left',('b_l_clav','b_l_upperarm','b_l_upperarm_fixup','b_l_shoulder'),2,-1),('right shoulder',lambda n:n=='shoulder-right',('b_r_clav','b_r_upperarm','b_r_upperarm_fixup','b_r_shoulder'),2,1),
        ('left forearm',lambda n:n in ('left-forearm','wrist-buckler'),('b_l_forearm','b_l_forearm_fixup','b_l_elbow_fixup','b_l_hand'),0,1),('right forearm',lambda n:n=='right-forearm',('b_r_forearm','b_r_forearm_fixup','b_r_elbow_fixup','b_r_hand'),0,1),
        ('left thigh',lambda n:n=='left-thigh',('b_l_thigh','b_l_upperleg_jiggle','b_l_hip_fixup','b_pelvis'),0,1),('right thigh',lambda n:n=='right-thigh',('b_r_thigh','b_r_upperleg_jiggle','b_r_hip_fixup','b_pelvis'),0,1),
        ('left calf',lambda n:n=='left-calf',('b_l_calf','b_l_calf_jiggle','b_l_knee_fixup','b_l_foot'),0,1),('right calf',lambda n:n=='right-calf',('b_r_calf','b_r_calf_jiggle','b_r_knee_fixup','b_r_foot'),0,1)]
    for lod,model in enumerate(data['lods']):
        triangles=model['triangles'];rest=np.array([position(p,(0,0,0)) for t in triangles for p in t['p']]);faces=np.arange(len(rest)).reshape(-1,3);poses=np.load(candidate/f'poses-{lod}.npz')
        for region,select,bones,axis,sign in groups:
            armor=faces[[select(t['component']) for t in triangles]];allowed={i for i,n in enumerate(data['nodes']) if n['name'] in bones};under=[]
            for i,t in enumerate(triangles):
                if t['component'].startswith('garment-') and sum(w for ws in t['weights'] for b,w in ws if b in allowed)>1.4:under.append(faces[i])
            under=np.array(under,dtype=int).reshape(-1,3);assert len(armor),(lod,region)
            source_components={c for t in triangles if select(t['component']) for c in t['source_components']}
            source_face_ids=sorted({f for c in source_components if c in parts for f in parts[c]['faces']});source_armor=original_faces[source_face_ids]
            source_under=original_faces[[i for i,(mat,face) in enumerate(zip(original['materials'],original['faces'])) if mat in (5,87) and sum(w for vi in face for b,w in original['weights'][vi] if b in allowed)>1.4]]
            assert len(source_armor) and len(source_under),(lod,region,'source baseline missing')
            points=rest[armor];center=(points.min((0,1))+points.max((0,1)))/2;normal=np.cross(points[:,1]-points[:,0],points[:,2]-points[:,0]);length=np.linalg.norm(normal,axis=1)
            broad=(normal[:,axis]*sign>.55*length)&(sign*(points[:,:,axis].mean(1)-center[axis])>=-.001);front=armor[broad];assert len(front),(lod,region,'no broad front')
            ids=np.unique(armor);basis=np.c_[rest[ids],np.ones(len(ids))];scale=max(np.ptp(points[:,:,a]) for a in range(3))*1.4
            worst=None
            for name,fraction in [('idle',0),('run',.4),('reload',.45),('passenger',.5)]:
                ci=next(i for i,c in enumerate(model['animations']) if c['name']==name);frames=poses['frames_'+str(ci)];posed=np.rint(frames[round(fraction*(len(frames)-1))]*512)/512;transform=np.linalg.lstsq(basis,posed[ids],rcond=None)[0];local=(posed-transform[3])@np.linalg.inv(transform[:3])
                fi=round(fraction*(len(frames)-1));source_local=(original_pose(ci,fi)-transform[3])@np.linalg.inv(transform[:3])
                for angle in (-25,0,25):
                    theta=math.radians(angle);direction=(sign*math.cos(theta),0,math.sin(theta)) if axis==0 else (math.sin(theta),0,sign*math.cos(theta))
                    def facing_faces(points,faces):
                        ps=points[faces];return faces[np.cross(ps[:,1]-ps[:,0],ps[:,2]-ps[:,0])@np.array(direction)>0]
                    plate=depth(local,front,center,scale,direction);raw_lining=depth(local,under,center,scale,direction);lining=depth(local,facing_faces(local,under),center,scale,direction);visible=np.isfinite(plate)
                    # Broad faces define the inspected region, but the whole
                    # visible plate can occlude cloth there. An angled original
                    # bevel in front of both is real armor, not a cloth loss.
                    ap=local[armor];facing=np.cross(ap[:,1]-ap[:,0],ap[:,2]-ap[:,0])@np.array(direction)>0
                    whole_plate=depth(local,armor[facing],center,scale,direction)
                    raw_covered=visible&(raw_lining>plate+1/512)
                    covered=visible&(lining>whole_plate+1/512)
                    visible_source_armor=facing_faces(source_local,source_armor)
                    original_plate=depth(source_local,visible_source_armor,center,scale,direction);original_lining=depth(source_local,facing_faces(source_local,source_under),center,scale,direction)
                    original_visible=np.isfinite(original_plate)&(original_lining<=original_plate+1/512)
                    # A one-pixel rim is not a broad plate front. Compare the
                    # same camera against the intact source; its inward shell
                    # returns can legitimately lie behind exposed fabric.
                    interior=original_visible.copy()
                    for dy,dx in ((0,1),(0,-1),(1,0),(-1,0)):interior&=np.roll(original_visible,(dy,dx),(0,1))
                    lost=(interior&np.isfinite(lining)&(lining>whole_plate+1/512)) if region=='back' else covered&interior
                    lost_backing=[]
                    if lost.any():
                        from recess_gungnir_cloth import layers
                        donor_depth,donor_ids,_=layers(source_local,visible_source_armor,center,scale,direction)
                        assert np.array_equal(np.isfinite(donor_depth),np.isfinite(original_plate)) and np.allclose(donor_depth[np.isfinite(donor_depth)],original_plate[np.isfinite(original_plate)])
                        source_lookup={tuple(face):fi for face,fi in zip(source_armor,source_face_ids)}
                        restore[lod].update(source_lookup[tuple(visible_source_armor[int(i)])] for i in np.unique(donor_ids[lost]) if i>=0)
                        visible_under=facing_faces(local,under);_,cloth_ids,_=layers(local,visible_under,center,scale,direction)
                        for index in np.unique(cloth_ids[lost]):
                            if index>=0:
                                ti=int(visible_under[int(index),0]//3);lost_backing.append(dict(component=triangles[ti]['component'],triangle=ti,bind_points=triangles[ti]['p']))
                    row=dict(lod=lod,region=region,clip=name,angle=angle,plate_pixels=int(visible.sum()),source_visible_plate_pixels=int(original_visible.sum()),source_broad_plate_pixels=int(interior.sum()),isolated_broad_subset_overlap_pixels=int(raw_covered.sum()),backing_in_front_pixels=int(covered.sum()),new_broad_plate_occlusion_pixels=int(lost.sum()),source_plate_missing_pixels=int((interior&~np.isfinite(whole_plate)).sum()),retained_plate_hidden_pixels=int((interior&np.isfinite(whole_plate)&(lining>whole_plate+1/512)).sum()),lost_backing=lost_backing,fraction=float(lost.sum()/max(1,interior.sum())))
                    rows.append(row)
                    if worst is None or row['fraction']>worst[0]['fraction']:
                        rgb=np.full((*visible.shape,3),35,dtype=np.uint8);rgb[original_visible]=[60,160,150];rgb[covered]=[150,110,45];rgb[lost]=[255,30,30];worst=row,rgb
            Image.fromarray(np.flipud(worst[1])).resize((400,400),Image.Resampling.NEAREST).save(output/f'{lod}-{region.replace(" ","-")}.png')
    report=dict(samples=len(rows),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),candidate_sha256=hashlib.sha256((candidate/'solid.json').read_bytes()).hexdigest(),method='Candidate broad fronts against intact source-visible plate interiors, one-pixel rim excluded; source and candidate use front-face culling; whole front-facing plate resolves depth, isolated uncullled broad-subset overlaps also retained',rows=rows,restore_original_faces=[sorted(v) for v in restore],maximum_new_broad_plate_occlusion_pixels=max(r['new_broad_plate_occlusion_pixels'] for r in rows))
    (output/'clearance.json').write_text(json.dumps(report,indent=2)+'\n');print('CLEARANCE',len(rows),'maximum',report['maximum_new_broad_plate_occlusion_pixels'],flush=True)
    assert not any(r['new_broad_plate_occlusion_pixels'] for r in rows),'Backing newly crosses a broad source-visible armor front'


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('candidate',type=Path);p.add_argument('output',type=Path);p.add_argument('--source',type=Path,required=True);p.add_argument('--motion',type=Path,required=True);p.add_argument('--inventory',type=Path,required=True);a=p.parse_args();run(a.candidate,a.output,a.source,a.motion,a.inventory)
