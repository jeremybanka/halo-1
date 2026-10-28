"""Compare packed-precision grip occlusion with the original skinned hand.

This is an independent nearest-surface test of the camera-facing grip, not an
RDP emulator. Native four-player captures remain the rendering acceptance gate.
The old generic hand makes the shaft win hundreds of source-hand pixels.
"""
import json
from pathlib import Path
import numpy as np
from pack_objectives import FLAG_FP_SCALE
from pack_animation import compact_clip
from pack_assets import position

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'halo64-assets/assets/objectives'

def matrices(nodes,states):
    result=[None]*len(nodes)
    def visit(i):
        if result[i] is not None:return result[i]
        n=states[i];x,y,z,w=n['q']
        m=np.array([[1-2*(y*y+z*z),2*(x*y+z*w),2*(x*z-y*w),n['p'][0]],
                    [2*(x*y-z*w),1-2*(x*x+z*z),2*(y*z+x*w),n['p'][1]],
                    [2*(x*z+y*w),2*(y*z-x*w),1-2*(x*x+y*y),n['p'][2]],
                    [0,0,0,1]])
        parent=nodes[i]['parent']
        result[i]=visit(parent)@m if parent>=0 and parent!=i else m
        return result[i]
    return np.array([visit(i) for i in range(len(nodes))])

def source_hand(raw,frame):
    hands=raw['hands'];weapon=raw['weapons']['flag']
    lookup={n['name']:i for i,n in enumerate(weapon['nodes'])}
    inv=np.linalg.inv(matrices(hands['nodes'],hands['nodes']))
    pose=matrices(weapon['nodes'],frame)
    skin=np.array([pose[lookup[n['name']]]@inv[i] for i,n in enumerate(hands['nodes'])])
    points=np.c_[hands['vertices'],np.ones(len(hands['vertices']))]
    weighted=np.zeros_like(points)
    for i,(a,b,t) in enumerate(hands['weights']):
        weighted[i]=(skin[a]@points[i])*(1-t)
        if b>=0 and t>0:weighted[i]+=(skin[b]@points[i])*t
    return weighted[np.array(hands['faces']).reshape(-1),:3]

def nearest(points,hand_triangles,rays):
    triangles=np.round(np.asarray(points).reshape(-1,3,3)*FLAG_FP_SCALE)/FLAG_FP_SCALE
    a=triangles[:,0];e1=triangles[:,1]-a;e2=triangles[:,2]-a
    answers=[]
    for first in range(0,len(rays),128):
        r=rays[first:first+128]
        h=np.cross(r[:,None,:],e2[None,:,:]);d=np.einsum('tij,ij->ti',h,e1)
        safe=np.where(abs(d)>1e-10,d,1)
        u=np.einsum('tij,ij->ti',h,-a)/safe;q=np.cross(-a,e1)
        v=np.einsum('ij,tj->ti',q,r)/safe;t=np.einsum('ij,ij->i',q,e2)[None,:]/safe
        valid=(abs(d)>1e-10)&(u>=0)&(v>=0)&(u+v<=1)&(t>0)
        depth=np.where(valid,t,np.inf);chosen=np.argmin(depth,axis=1)
        answers.extend(np.where(np.isfinite(depth.min(axis=1)),np.where(chosen<hand_triangles,1,2),0))
    return np.array(answers)

def main():
    raw=json.loads((SOURCE/'firstperson-raw.json').read_text())
    reduced=json.loads((SOURCE/'firstperson-reduced.json').read_text())['weapons']['flag']
    surface_results=[]
    for name,clip in reduced['clips'].items():
        packed=compact_clip(clip,FLAG_FP_SCALE,16)
        for f,frame in enumerate(clip['frames']):
            triangles=np.asarray(frame).reshape(-1,3,3)[:reduced['hand_triangle_count']]
            original=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
            snapped=np.round(triangles*FLAG_FP_SCALE)
            normal=np.cross(snapped[:,1]-snapped[:,0],snapped[:,2]-snapped[:,0])
            assert np.all(np.sum(normal*original,axis=1)>0),(name,f,'collapsed or reversed hand face')
            # Decode the actual stored stream independently, including duplicate
            # corners, to catch a precision or trajectory-aliasing regression.
            for v,point in enumerate(frame):
                at=(f*packed['tracks']+packed['indices'][v])*3
                decoded=[packed['values'][at+a]+packed['origin'][a] for a in range(3)]
                assert decoded==[round(x*FLAG_FP_SCALE) for x in position(point,(0,0,0))]
        surface_results.append({'clip':name,'poses':len(clip['frames']),'collapsed_or_reversed_faces':0})
    # Production four-player projection: fov=1.08, 160x120, safe-window aim
    # point=(91,68). The source-space +X axis points into the screen.
    x,y=np.meshgrid(np.arange(118,158)+.5,np.arange(65,112)+.5)
    rays=np.stack([np.ones_like(x),-(x-91)*2/120*np.tan(.54),
                   -(y-68)*2/120*np.tan(.54)],axis=-1).reshape(-1,3)
    clip=reduced['clips']['idle'];original=raw['weapons']['flag']['clips']['idle']['frames']
    count=reduced['hand_triangle_count'];total=0;results=[]
    for i,frame in enumerate(clip['frames']):
        sample=round(i*(len(original)-1)/max(1,len(clip['frames'])-1))
        hand=source_hand(raw,original[sample]);reference=np.concatenate([hand,frame[count*3:]])
        expected=nearest(reference,len(hand)//3,rays);actual=nearest(frame,count,rays)
        wrong=int(np.count_nonzero((expected==1)&(actual!=1)))
        hand_pixels=int(np.count_nonzero(expected==1));total+=hand_pixels
        assert hand_pixels>1000,(i,'invalid grip fixture')
        assert wrong<=2,(i,'source grip lost behind shaft/background',wrong)
        results.append({'frame':i,'source_hand_pixels':hand_pixels,'wrongly_occluded_pixels':wrong})
    print(json.dumps({'poses':results,'compared_hand_pixels':total,
                     'surface_checks':surface_results,'position_scale':FLAG_FP_SCALE,'status':'pass'},indent=2))

if __name__=='__main__':main()
