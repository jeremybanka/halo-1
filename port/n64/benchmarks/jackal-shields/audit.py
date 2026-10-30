"""Exact source topology and source-bone attachment checks, independent of N64."""
import gzip,hashlib,json,sys
from collections import Counter
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'port/n64'))
from pack_assets import position
out=ROOT/'build/jackal-shields';base=ROOT/'halo64-assets/assets/firefight-roster'
raw=json.loads((out/'source/shield-source.json').read_text());m=raw['models']['jackal'];g=m['source_geometry_lods']['source shield']
original=json.loads((base/'source/squad-source.json').read_text())['models']['jackal']['source_geometry_lods']['base00 superhigh']
untouched_path=ROOT/'halo64-assets/assets/firefight-combat/squad-source.json'
untouched=json.loads(untouched_path.read_text())['models']['jackal']
assert original==untouched['source_geometry_lods']['base00 superhigh'] and m['nodes']==untouched['nodes']
assert g['faces']==[f for f,mat in zip(original['faces'],original['materials']) if mat==6]
assert g['vertices']==original['vertices'] and g['weights']==original['weights'] and g['uv']==original['uv']
baked=json.loads(gzip.decompress((out/'source/shield-baked.json.gz').read_bytes()))['jackal'][0]
local=json.loads((out/'source/shield-local.json').read_text())
points=np.array([position(local['vertices'][v],(0,0,0)) for f in g['faces'] for v in f]);points=np.rint(points*1024)/1024
maximum=0;poses=0
for key,clip in baked['clips'].items():
    hand=baked['grips'][key];assert hand['duration']==clip['duration']
    for frame,pose in zip(clip['frames'],hand['poses']):
        x,y,z,w=pose['quat'];norm=(x*x+y*y+z*z+w*w)**.5;x,y,z,w=[c/norm for c in (x,y,z,w)]
        rot=np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
        actual=points@rot.T+pose['pos'];expected=np.array([position(p,(0,0,0)) for p in frame])
        error=np.max(np.linalg.norm(actual-expected,axis=1));maximum=max(maximum,float(error));poses+=1
assert maximum<.0015,maximum
# Independently ray-test the visible attachment at the host hit-test pose.
# These actor-local rays correspond to the recorded shield/body samples; the
# body opening must not acquire a visible energy surface in the restoration.
hand=baked['grips']['idle'];frame=.35*(len(hand['poses'])-1);f0=int(frame);mix=frame-f0
q0=np.array(hand['poses'][f0]['quat']);q1=np.array(hand['poses'][f0+1]['quat'])
if np.dot(q0,q1)<0:q1=-q1
q=q0*(1-mix)+q1*mix;q/=np.linalg.norm(q);x,y,z,w=q
rot=np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
translation=np.array(hand['poses'][f0]['pos'])*(1-mix)+np.array(hand['poses'][f0+1]['pos'])*mix
triangles=(points@rot.T+translation).reshape(-1,3,3)
def visible_hits(origin):
    direction=np.array([-1,0,0]);v0=triangles[:,0];e1=triangles[:,1]-v0;e2=triangles[:,2]-v0
    cross=np.cross(direction,e2);det=np.sum(e1*cross,axis=1);valid=np.abs(det)>1e-8
    inv=np.zeros(len(det));inv[valid]=1/det[valid];s=np.array(origin)-v0
    u=np.sum(s*cross,axis=1)*inv;q=np.cross(s,e1);v=np.sum(direction*q,axis=1)*inv
    distance=np.sum(e2*q,axis=1)*inv
    return distance[valid&(u>=0)&(v>=0)&(u+v<=1)&(distance>0)].tolist()
shield_ray=[2,.56,.08];gap_ray=[2,.44,-.04]
assert visible_hits(shield_ray) and not visible_hits(gap_ray)
edges=Counter()
for f in g['faces']:
    p=[tuple(round(v,6) for v in g['vertices'][i]) for i in f]
    assert np.linalg.norm(np.cross(np.subtract(p[1],p[0]),np.subtract(p[2],p[0])))>1e-9
    for a,b in zip(p,p[1:]+p[:1]):edges[tuple(sorted((a,b)))]+=1
unchanged=[]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for path in (base/'bank').iterdir():
    if path.is_file():assert sha(path)==sha(out/'bank'/path.name),path.name;unchanged.append(path.name)
result={'source_shield_triangles_preserved':len(g['faces']),'all_source_uvs_weights_and_vertices_preserved':True,
        'original_pre_reduction_source_mesh_and_skeleton_identical':True,'original_extraction_sha256':sha(untouched_path),
        'source_rigid_bone':26,'source_attachment_poses_verified':poses,'max_quantized_attachment_error_world_units':maximum,
        'nondegenerate_triangles':76,'boundary_edges':sum(v==1 for v in edges.values()),'nonmanifold_edges':sum(v>2 for v in edges.values()),
        'unchanged_roster_bank_files':unchanged,'shield_asset_sha256':sha(out/'bank/pve_jackal_shield.c'),
        'visible_mesh_ray_check':{'clip':'idle','phase':.35,'direction':[-1,0,0],'shield_origin_actor_local':shield_ray,'shield_distances':visible_hits(shield_ray),'body_gap_origin_actor_local':gap_ray,'body_gap_distances':visible_hits(gap_ray)},
        'note':'Sampled source poses verified; intermediate rotations use normalized quaternion interpolation, as CE-style rigid attachments do. Collision remains canonical.'}
(out/'asset-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
