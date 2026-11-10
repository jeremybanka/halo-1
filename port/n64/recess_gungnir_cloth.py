"""Bounded, pose-aware local cloth recess behind retained source armor fronts.

Only original source-visible plate interiors create constraints. The native
skin weights and topology stay fixed; the displacement is shared by every
compatible corner, and independently checked by the existing depth audit.
"""
import argparse, hashlib, json, math
from collections import defaultdict
from pathlib import Path
import numpy as np
from extract_gungnir import bone_globals
from audit_models import engine
from audit_jorge_armor_clearance import depth

BASIS=np.array(((1,0,0),(0,0,1),(0,-1,0)),dtype=float)

def layers(points, triangles, center, scale, direction, size=80):
    direction=np.array(direction,dtype=float); direction/=np.linalg.norm(direction)
    right=np.cross(direction,[0,1,0]);right/=np.linalg.norm(right);up=np.cross(right,direction)
    local=(points-center)@np.array([right,up,direction]).T;local[:,:2]=local[:,:2]/scale*size+size/2
    zbuf=np.full((size,size),-np.inf);ids=np.full((size,size),-1,dtype=int);bary=np.zeros((size,size,3))
    for fi,face in enumerate(triangles):
        tri=local[face];lo=np.maximum(0,np.floor(tri[:,:2].min(0)).astype(int));hi=np.minimum(size-1,np.ceil(tri[:,:2].max(0)).astype(int))
        if np.any(lo>hi):continue
        x,y=np.meshgrid(np.arange(lo[0],hi[0]+1)+.5,np.arange(lo[1],hi[1]+1)+.5);a,b,c=tri
        den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(den)<1e-10:continue
        u=((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/den;v=((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/den;w=1-u-v
        z=u*a[2]+v*b[2]+w*c[2];valid=(u>=-1e-8)&(v>=-1e-8)&(w>=-1e-8)
        sub=zbuf[lo[1]:hi[1]+1,lo[0]:hi[0]+1];hit=valid&(z>sub);sub[hit]=z[hit]
        ids[lo[1]:hi[1]+1,lo[0]:hi[0]+1][hit]=fi;bary[lo[1]:hi[1]+1,lo[0]:hi[0]+1][hit]=np.stack((u,v,w),axis=-1)[hit]
    return zbuf,ids,bary

def solve(indices,gradient,rhs,count,limit,initial):
    ids=np.array(indices);g=np.array(gradient);rhs=np.array(rhs);delta=initial.copy();norm=np.maximum(1e-12,(g*g).sum((1,2)))
    degree=np.zeros(count);np.add.at(degree,ids.ravel(),np.ones(ids.size));degree=np.maximum(1,degree)
    for _ in range(400):
        violation=np.maximum(0,rhs-(g*delta[ids]).sum((1,2)));correction=np.zeros_like(delta)
        np.add.at(correction,ids.ravel(),(g*(violation/norm)[:,None,None]).reshape(-1,3));delta+=correction/degree[:,None]
        length=np.linalg.norm(delta,axis=1);delta*=np.minimum(1,limit/np.maximum(1e-12,length))[:,None]
    return delta

def run(candidate,source,motion,inventory,output,passes=5,limit_mm=20,back_only=False,only_region=None):
    candidate,source,motion,inventory,output=map(Path,(candidate,source,motion,inventory,output));output.mkdir(parents=True,exist_ok=True)
    data=json.loads((candidate/'solid.json').read_text());original=json.loads(source.read_text());parts={p['id']:p for p in json.loads(inventory.read_text())};inverse=np.linalg.inv(np.array(bone_globals(original['nodes'])));native=np.load(motion/'native-poses.npz');report=[]
    groups=[('chest',('torso','chest-parafoil','chest-lower'),('b_torso','b_spine1','b_spine2','b_spine3','b_belt'),0,1)]
    groups.append(('back',('torso','torso-back'),('b_torso','b_spine1','b_spine2','b_spine3','b_belt','b_neck0'),0,-1))
    groups.append(('codpiece',('belt',),('b_pelvis','b_belt','b_l_hip_fixup','b_r_hip_fixup'),0,1))
    for side,short,sign in [('left','l',-1),('right','r',1)]:
        groups.extend([(side+' shoulder',('shoulder-'+side,),(f'b_{short}_clav',f'b_{short}_upperarm',f'b_{short}_upperarm_fixup',f'b_{short}_shoulder'),2,sign),
                       (side+' forearm',(side+'-forearm',*(['wrist-buckler'] if side=='left' else [])),tuple(f'b_{short}_{b}' for b in ('forearm','forearm_fixup','elbow_fixup','hand')),0,1),
                       (side+' thigh',(side+'-thigh',),(f'b_{short}_thigh',f'b_{short}_upperleg_jiggle',f'b_{short}_hip_fixup','b_pelvis'),0,1),
                       (side+' calf',(side+'-calf',),tuple(f'b_{short}_{b}' for b in ('calf','calf_jiggle','knee_fixup','foot')),0,1)])
    if back_only:groups=[g for g in groups if g[0]=='back']
    if only_region:
        groups=[g for g in groups if g[0]==only_region]
        assert groups,only_region
    original_points=np.c_[original['vertices'],np.ones(len(original['vertices']))];ow=np.zeros((len(original_points),len(original['nodes'])))
    for i,ws in enumerate(original['weights']):
        for b,w in ws:ow[i,b]=w
    for lod,model in enumerate(data['lods']):
        points=[];weights=[];lookup={};faces=[]
        for tri in model['triangles']:
            face=[]
            for p,ws in zip(tri['p'],tri['weights']):
                key=tuple(p),tuple(map(tuple,ws))
                if key not in lookup:lookup[key]=len(points);points.append(p);weights.append(ws)
                face.append(lookup[key])
            faces.append(face)
        points=np.array(points);faces=np.array(faces);skinweights=np.zeros((len(points),len(original['nodes'])))
        for i,ws in enumerate(weights):
            for b,w in ws:skinweights[i,b]=w
        rest=engine(points);delta=np.zeros_like(points);poses=np.load(candidate/f'poses-{lod}.npz');samples=[];specs=[]
        for region,names,bones,axis,sign in groups:
            armor_ids=[i for i,t in enumerate(model['triangles']) if t['component'] in names];armor=faces[armor_ids];allowed={i for i,n in enumerate(data['nodes']) if n['name'] in bones}
            under=faces[[i for i,t in enumerate(model['triangles']) if t['component'].startswith('garment-') and sum(w for ws in t['weights'] for b,w in ws if b in allowed)>1.4]]
            if not len(under):continue
            ps=rest[armor];center=(ps.min((0,1))+ps.max((0,1)))/2;normal=np.cross(ps[:,1]-ps[:,0],ps[:,2]-ps[:,0]);length=np.linalg.norm(normal,axis=1);front=armor[(normal[:,axis]*sign>.55*length)&(sign*(ps[:,:,axis].mean(1)-center[axis])>=-.001)]
            source_components={c for t in model['triangles'] if t['component'] in names for c in t['source_components']};source_armor=np.array(original['faces'])[sorted({f for c in source_components if c in parts for f in parts[c]['faces']})]
            source_under=np.array(original['faces'])[[i for i,(mat,face) in enumerate(zip(original['materials'],original['faces'])) if mat in (5,87) and sum(w for vi in face for b,w in original['weights'][vi] if b in allowed)>1.4]]
            scale=max(np.ptp(ps[:,:,a]) for a in range(3))*1.4;ids=np.unique(armor);basis=np.c_[rest[ids],np.ones(len(ids))]
            for clip,fraction in [('idle',0),('run',.4),('reload',.45),('passenger',.5)]:
                ci=next(i for i,c in enumerate(model['animations']) if c['name']==clip);fi=round(fraction*(len(poses['frames_'+str(ci)])-1));skin=native['matrices_'+str(ci)][fi]@inverse
                current=np.rint(poses['frames_'+str(ci)][fi]*512)/512
                # Expanded baked corners and native registry use different indexing.
                expanded=faces.ravel();base=np.zeros_like(rest)
                for vi,corner in enumerate(expanded):base[corner]=current[vi]
                transform=np.linalg.lstsq(basis,base[ids],rcond=None)[0];inv=np.linalg.inv(transform[:3]);local=(base-transform[3])@inv
                matrix=np.einsum('ij,gjk->gik',BASIS,np.einsum('gb,bij->gij',skinweights,skin[:,:3,:3]));local_matrix=np.einsum('ij,gjk->gik',inv.T,matrix)
                op=np.einsum('gb,bij,gj->gi',ow,skin[:,:3,:],original_points);source_local=(np.rint(engine(op)*512)/512-transform[3])@inv
                for angle in (-25,0,25):
                    theta=math.radians(angle);direction=np.array((sign*math.cos(theta),0,math.sin(theta)) if axis==0 else (math.sin(theta),0,sign*math.cos(theta)))
                    def facing(points, faces):
                        ps=points[faces]
                        return faces[np.cross(ps[:,1]-ps[:,0],ps[:,2]-ps[:,0])@direction>0]
                    if region=='back':
                        plate=depth(local,facing(local,armor),center,scale,direction)
                        sp=depth(source_local,facing(source_local,source_armor),center,scale,direction)
                        su=depth(source_local,facing(source_local,source_under),center,scale,direction)
                    else:
                        plate=depth(local,front,center,scale,direction);sp=depth(source_local,source_armor,center,scale,direction);su=depth(source_local,source_under,center,scale,direction)
                    visible=np.isfinite(sp)&(su<=sp+1/512);interior=visible.copy()
                    for dy,dx in ((0,1),(0,-1),(1,0),(-1,0)):interior&=np.roll(visible,(dy,dx),(0,1))
                    specs.append((region,under,local,local_matrix,center,scale,direction,plate,interior))
        for attempt in range(passes):
            indices=[];gradients=[];rhs=[];counts=defaultdict(int)
            for region,under,base,matrix,center,scale,direction,plate,interior in specs:
                local=base+np.einsum('gij,gj->gi',matrix,delta);lining,ids,bary=layers(local,under,center,scale,direction)
                lost=interior&np.isfinite(plate)&(lining>plate-.0005)
                for y,x in np.argwhere(lost):
                    face=under[ids[y,x]];g=np.array([-matrix[i].T@direction*b for i,b in zip(face,bary[y,x])]);required=lining[y,x]-plate[y,x]+.0025
                    indices.append(face);gradients.append(g);rhs.append(required+float((g*delta[face]).sum()));counts[region]+=1
            if not rhs:break
            # Absolute displacement constraints retain the same bind origin across passes.
            delta=solve(indices,gradients,rhs,len(points),limit_mm/3048,delta)
            row=dict(lod=lod,pass_index=attempt,constraints=len(rhs),regions=dict(counts),maximum_displacement_m=float(np.linalg.norm(delta,axis=1).max()*3.048));report.append(row);print('RECESS',row,flush=True)
        for tri,face in zip(model['triangles'],faces):
            for i,v in enumerate(face):
                tri['p'][i]=(points[v]+delta[v]).tolist()
                prior=tri['source_faces'][i]
                shift=delta[v]*3.048
                tri['source_faces'][i]={**prior,'cloth_recess_delta_m':(np.array(prior.get('cloth_recess_delta_m',[0,0,0]))+shift).tolist(),'cloth_recess_latest_delta_m':shift.tolist(),'preserved_native_skin_channels':True}
        baked={k:poses[k].copy() for k in poses.files}
        for ci,clip in enumerate(model['animations']):
            allskin=native['matrices_'+str(ci)]@inverse
            for fi,skin in enumerate(allskin):
                shift=np.einsum('gb,bij,gj->gi',skinweights,skin[:,:3,:3],delta)@BASIS.T;baked['frames_'+str(ci)][fi]+=shift[faces.ravel()]
        np.savez_compressed(output/f'poses-{lod}.npz',**baked)
    data['cloth_recess_parent_sha256']=hashlib.sha256((candidate/'solid.json').read_bytes()).hexdigest();data['cloth_recess']=report;data['publication_approved']=False
    (output/'solid.json').write_text(json.dumps(data,separators=(',',':'))+'\n');(output/'cloth-recess.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('candidate');p.add_argument('source');p.add_argument('motion');p.add_argument('inventory');p.add_argument('output');p.add_argument('--passes',type=int,default=5);p.add_argument('--limit-mm',type=float,default=20);p.add_argument('--back-only',action='store_true');p.add_argument('--only-region');a=p.parse_args();run(a.candidate,a.source,a.motion,a.inventory,a.output,a.passes,a.limit_mm,a.back_only,a.only_region)
