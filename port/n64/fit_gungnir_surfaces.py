"""Bounded source-surface fitting across the native gameplay poses.

Keep the reduced topology and its source skin channels. Fit local surface
samples toward the intact source in pose space; no primitive armor replacement,
new vertices, animation clock or donor motion is introduced. Independent raster
coverage and plate-depth checks still decide whether the result is acceptable.
"""
import argparse,copy,hashlib,json,sys
from collections import defaultdict
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector,interpolate
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from demake_gungnir import bake,groups
from extract_gungnir import bone_globals

BASIS=np.array(((1,0,0),(0,0,1),(0,-1,0)),dtype=float)

def key(p,ws):return tuple(round(v,7) for v in p),tuple(sorted((b,round(w,7)) for b,w in ws))

def solve(indices,gradient,rhs,delta,free,limit,iterations):
    indices=np.array(indices,dtype=int);gradient=np.array(gradient,dtype=float);rhs=np.array(rhs,dtype=float)
    norm=np.maximum(1e-12,(gradient*gradient).sum((1,2)))
    counts=np.zeros(len(delta));np.add.at(counts,indices.ravel(),((gradient*gradient).sum(2)>1e-16).ravel());counts=np.maximum(1,counts)
    for iteration in range(iterations):
        value=(gradient*delta[indices]).sum((1,2));violation=np.maximum(0,rhs-value);correction=np.zeros_like(delta)
        np.add.at(correction,indices.ravel(),(gradient*(violation/norm)[:,None,None]).reshape(-1,3))
        delta+=correction/counts[:,None]*.9;delta[~free]=0
        length=np.linalg.norm(delta,axis=1);delta*=np.minimum(1,limit/np.maximum(length,1e-12))[:,None]
        if violation.max(initial=0)<.0001:break
    residual=np.maximum(0,rhs-(gradient*delta[indices]).sum((1,2)))
    return dict(constraints=len(rhs),iterations=iteration+1,maximum_residual_m=float(residual.max(initial=0)*3.048),residuals_over_one_mm=int((residual>.001/3.048).sum()))

def run(source,candidate,motion,output,limit_mm,passes,iterations,armor_only=False):
    source,candidate,motion,output=map(Path,(source,candidate,motion,output));output.mkdir(parents=True,exist_ok=True)
    original=json.loads(source.read_text());original['skin_weights']=original['weights'];data=json.loads((candidate/'solid.json').read_text());plan={g['id']:g for g in groups(original,True)[0]};meta=json.loads((motion/'motion-report.json').read_text());poses=np.load(motion/'native-poses.npz');inverse=np.linalg.inv(np.array(bone_globals(original['nodes'])));report=[]
    original_p=np.c_[original['vertices'],np.ones(len(original['vertices']))];original_w=np.zeros((len(original_p),len(original['nodes'])))
    for i,ws in enumerate(original['weights']):
        for b,w in ws:original_w[i,b]=w
    bind=bone_globals(original['nodes']);names={n['name']:i for i,n in enumerate(original['nodes'])};pairs=[('b_pelvis','b_spine1'),('b_spine1','b_spine2'),('b_spine2','b_spine3'),('b_spine3','b_neck0'),('b_neck0','b_neck1'),('b_neck1','b_head')]
    for side in ('l','r'):pairs.extend([('b_pelvis',f'b_{side}_thigh'),(f'b_{side}_thigh',f'b_{side}_calf'),(f'b_{side}_calf',f'b_{side}_foot'),(f'b_{side}_foot',f'b_{side}_toe'),(f'b_{side}_clav',f'b_{side}_upperarm'),(f'b_{side}_upperarm',f'b_{side}_forearm'),(f'b_{side}_forearm',f'b_{side}_hand')])
    segments=[(bind[names[a]][:3,3],bind[names[b]][:3,3]-bind[names[a]][:3,3]) for a,b in pairs if a in names and b in names]
    exterior=set()
    for fi,face in enumerate(original['faces']):
        tri=original_p[face,:3];center=tri.mean(0);normal=np.cross(tri[1]-tri[0],tri[2]-tri[0]);closest=min((a+d*np.clip((center-a)@d/max(d@d,1e-12),0,1) for a,d in segments),key=lambda p:np.linalg.norm(p-center));radial=center-closest
        if normal@radial>np.linalg.norm(normal)*np.linalg.norm(radial)*.05:exterior.add(fi)
    for lod,model in enumerate(data['lods']):
        points=[];weights=[];lookup={};corners=[];by_part=defaultdict(list)
        for ti,t in enumerate(model['triangles']):
            face=[]
            for p,ws in zip(t['p'],t['weights']):
                k=key(p,ws)
                if k not in lookup:lookup[k]=len(points);points.append(p);weights.append(ws)
                face.append(lookup[k])
            corners.append(face);by_part[t['component']].append(ti)
        p=np.array(points);faces=np.array(corners);w=np.zeros((len(p),len(original['nodes'])))
        for i,ws in enumerate(weights):
            for b,amount in ws:w[i,b]=amount
        delta=np.zeros_like(p);free=np.ones(len(p),dtype=bool)
        for name,ids in by_part.items():
            if name.endswith('-glove') or name=='helmet-lens':free[np.unique(faces[ids])]=False
            if armor_only and name.startswith(('helmet-','garment-')):free[np.unique(faces[ids])]=False
            if name.endswith('-boot'):
                ids=np.unique(faces[ids]);free[ids[p[ids,2]<.018]]=False
        # Use the exact source/input pose clocks used by the independent audit.
        samples=[]
        for ci,clip in enumerate(meta['clips']):
            if clip['name'] not in ('idle','run','reload','passenger'):continue
            for fraction in (0,.45,.9):
                fi=round(fraction*(len(poses['matrices_'+str(ci)])-1));skin=poses['matrices_'+str(ci)][fi]@inverse
                native=np.einsum('gb,bij->gij',w,skin[:,:3,:3]);matrix=np.einsum('ij,gjk->gik',BASIS,native)
                body=np.zeros((len(original_p),3))
                for b in np.flatnonzero(original_w.sum(0)):body+=(original_p@skin[b].T)[:,:3]*original_w[:,b,None]
                source_pos=body@BASIS.T;posed=np.c_[p,np.ones(len(p))]
                base=np.einsum('gb,bij,gj->gi',w,skin[:,:3,:],posed)@BASIS.T
                samples.append((clip['name'],fi,source_pos,base,matrix))
        for attempt in range(passes):
            indices=[];gradients=[];rhs=[];counts=defaultdict(int)
            for clip,fi,source_pos,base,matrix in samples:
                current=base+np.einsum('gij,gj->gi',matrix,delta)
                for name,ids in by_part.items():
                    if name not in plan or name.endswith('-glove') or name=='helmet-lens':continue
                    if armor_only and name.startswith(('helmet-','garment-')):continue
                    source_faces=plan[name]['faces'];removed=next((set(r.get('omitted_inner_source_faces',[])) for r in data['ledger'] if r['lod']==lod and r['id']==name),set());source_faces=[f for f in source_faces if f not in removed and f in exterior]
                    tree=BVHTree.FromPolygons([Vector(q) for q in current],faces[ids].tolist(),all_triangles=True)
                    part_points=current[faces[ids]];plane_normals=np.cross(part_points[:,1]-part_points[:,0],part_points[:,2]-part_points[:,0]);plane_normals/=np.maximum(1e-12,np.linalg.norm(plane_normals,axis=1))[:,None];plane_d=(plane_normals*part_points[:,0]).sum(1);unique=np.unique(faces[ids]);convex=bool(np.all(current[unique]@plane_normals.T<=plane_d+1e-7))
                    for source_face in source_faces:
                        tri=source_pos[np.array(original['faces'][source_face])];n=np.cross(tri[1]-tri[0],tri[2]-tri[0]);length=np.linalg.norm(n)
                        if length<1e-10:continue
                        n/=length
                        for q in (*tri,tri.mean(0)):
                            if convex and np.all(plane_normals@q<=plane_d+1e-7):continue
                            nearest=tree.find_nearest(Vector(q))
                            if nearest[0] is None or nearest[3]>.025:continue
                            options=[x for x in tree.find_nearest_range(Vector(q),min(.025,nearest[3]+.006)) if n@np.array(x[1])>.2 and (q-np.array(x[0]))@np.array(x[1])>=-1e-7 and (q-np.array(x[0]))@n>=-1e-7]
                            if not options:continue
                            hit,normal,local,distance=min(options,key=lambda x:x[3])
                            if distance<.00015:continue
                            direction=q-np.array(hit)
                            if direction@n<-.0001:continue
                            direction/=distance;face=faces[ids[local]];bary=np.maximum(0,interpolate.poly_3d_calc([Vector(current[i]) for i in face],hit));bary/=max(1e-12,bary.sum())
                            gradient=np.array([matrix[i].T@direction*b for i,b in zip(face,bary)])
                            gradient[~free[face]]=0
                            if (gradient*gradient).sum()<1e-12:continue
                            margin=0 if name.startswith('garment-') else 1/512
                            indices.append(face);gradients.append(gradient);rhs.append(distance+margin+float((gradient*delta[face]).sum()));counts[name]+=1
                print('CONSTRAINTS',lod,attempt,clip,fi,len(rhs),flush=True)
            if not rhs:break
            result=solve(indices,gradients,rhs,delta,free,limit_mm/3048,iterations);report.append(dict(lod=lod,pass_index=attempt,by_component=dict(counts),**result));print('FIT',report[-1],flush=True)
        fitted=p+delta
        for t,face in zip(model['triangles'],faces):
            for i,vi in enumerate(face):
                t['p'][i]=fitted[vi].tolist();t['source_faces'][i]={**t['source_faces'][i],'local_surface_fit_delta_m':(delta[vi]*3.048).tolist(),'preserved_native_skin_channels':True}
        # The original off-center optic stays outside its newly fitted shell.
        shell=[t for t in model['triangles'] if t['component']=='helmet-shell'];lens=[t for t in model['triangles'] if t['component']=='helmet-lens']
        if shell and lens and not armor_only:
            eye=np.array([q for t in lens for q in t['p']]);center=eye.mean(0);tree=BVHTree.FromPolygons([Vector(q) for t in shell for q in t['p']],np.arange(len(shell)*3).reshape(-1,3).tolist(),all_triangles=True);hit,_,_,_=tree.ray_cast(Vector((.2,center[1],center[2])),Vector((-1,0,0)));shift=max(0,float(hit.x)+1/512-float(eye[:,0].min())) if hit else 0;assert shift*3.048<.016
            for t in lens:
                for i,q in enumerate(t['p']):q[0]+=shift;t['source_faces'][i]['surface_fit_optic_clearance_m']=shift*3.048
        baked,clips=bake(original,model['triangles'],motion);np.savez_compressed(output/f'poses-{lod}.npz',**baked);model['animations']=clips
        report.append(dict(lod=lod,vertices=len(p),maximum_displacement_m=float(np.linalg.norm(delta,axis=1).max()*3.048),triangles=len(faces)))
    data['surface_fit_parent_sha256']=hashlib.sha256((candidate/'solid.json').read_bytes()).hexdigest();data['surface_fit']=report;data['publication_approved']=False
    (output/'solid.json').write_text(json.dumps(data,separators=(',',':'))+'\n');(output/'surface-fit.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('candidate');p.add_argument('motion');p.add_argument('output');p.add_argument('--limit-mm',type=float,default=16);p.add_argument('--passes',type=int,default=2);p.add_argument('--iterations',type=int,default=300);p.add_argument('--armor-only',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run(a.source,a.candidate,a.motion,a.output,a.limit_mm,a.passes,a.iterations,a.armor_only)
