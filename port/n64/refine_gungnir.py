"""Local restoration from preserved source-derived component checkpoints.

Visible plates come from the authored-surface candidate. Joint backing comes
from the earlier, more complete source-fitted continuity checkpoint. Coverage
hints locate small source-contour returns; they never stand in for acceptance.
"""
import argparse,copy,hashlib,json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector,interpolate
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from demake_gungnir import bake

def recess_backing(model,triangles,lod):
    """Recess hidden backing against the retained plate side planes.

    End caps are excluded: the garment must continue through elbow/knee
    openings. Rigid plate regions use that plate's original native bone.
    Shared corners are edited once so a repair cannot split the undersuit.
    """
    from extract_gungnir import bone_globals
    bind=bone_globals(model['nodes']);names={n['name']:i for i,n in enumerate(model['nodes'])};regions=[];records=[]
    for side,short in (('left','l'),('right','r')):
        for part,start,end,bone in [('calf','calf','foot','calf_jiggle'),('forearm','forearm','hand','forearm_fixup')]:
            component=side+'-'+part;ts=[t for t in triangles if t['component']==component];ps=np.array([t['p'] for t in ts]);center=ps.mean((0,1));a=bind[names[f'b_{short}_{start}']][:3,3];b=bind[names[f'b_{short}_{end}']][:3,3];axis=b-a;axis/=np.linalg.norm(axis);extent=(ps-a)@axis;planes=[]
            for p in ps:
                n=np.cross(p[1]-p[0],p[2]-p[0]);length=np.linalg.norm(n)
                if length<1e-10:continue
                n/=length
                if n@(p.mean(0)-center)<0:n=-n
                if abs(n@axis)<.75:planes.append((n,float(n@p[0])-.0015))
            regions.append((component,a,axis,float(extent.min()),float(extent.max()),planes,names[f'b_{short}_{bone}']))
    cache={}
    for t in triangles:
        if not t['component'].startswith('garment-'):continue
        for ci,(p,ws) in enumerate(zip(t['p'],t['weights'])):
            key=tuple(p),tuple(map(tuple,ws))
            if key not in cache:
                q=np.array(p);new_ws=ws;changed=[]
                for name,a,axis,lo,hi,planes,bone in regions:
                    delta=q-a;along=delta@axis;radial=np.linalg.norm(delta-along*axis)
                    if not lo-.04<=along<=hi+.035 or radial>.055:continue
                    before=q.copy()
                    for iteration in range(8):
                        for n,d in planes:
                            # Evaluate an end ring at the nearest plate
                            # cross-section, and recess radially only. Plane
                            # extrapolation above a tapered knee can otherwise
                            # drag the joint along the limb.
                            along_now=(q-a)@axis;evaluate=np.clip(along_now,lo+.003,hi-.003);radial_normal=n-axis*(n@axis)
                            distance=q@n+(evaluate-along_now)*(n@axis)-d
                            if distance>0:q-=radial_normal*(distance/max(1e-8,radial_normal@radial_normal))
                    displacement=float(np.linalg.norm(q-before))
                    changed.append(name);new_ws=[(bone,1.)]
                if .44<q[2]<.585 and abs(q[1])<.075 and q[0]>.042:
                    q[0]=.042;changed.append('recessed torso backing')
                displacement=float(np.linalg.norm(q-p));assert displacement*3.048<.10,('excessive backing repair',p,displacement)
                cache[key]=(q.tolist(),new_ws,dict(plate_regions=changed,recess_displacement_m=displacement*3.048,changed_topology=True,skinning='original rigid plate region where recessed'))
                if changed:records.append(dict(lod=lod,point=p,**cache[key][2]))
            q,new_ws,record=cache[key];t['p'][ci]=q;t['weights'][ci]=new_ws;t['source_faces'][ci]={**t['source_faces'][ci],**record}
    return records

def run(source,motion,armor,backing,output,repair=None):
    source,motion,armor,backing,output=map(Path,(source,motion,armor,backing,output));output.mkdir(parents=True,exist_ok=True)
    model=json.loads(source.read_text());data=json.loads((armor/'solid.json').read_text());old=json.loads((backing/'solid.json').read_text())
    records=[]
    for lod in range(2):
        triangles=[copy.deepcopy(t) for t in data['lods'][lod]['triangles'] if not t['component'].startswith('garment-')]
        triangles.extend(copy.deepcopy(t) for t in old['lods'][lod]['triangles'] if t['component'].startswith('garment-') and t['component'] not in ('garment-torso','garment-pelvis','garment-ankle-left','garment-ankle-right') and not t['component'].startswith(('garment-continuity-l-','garment-continuity-r-')))
        from demake_gungnir import collapse,groups
        model['skin_weights']=model['weights'];pelvis=next(g for g in groups(model,True)[0] if g['id']=='garment-pelvis');pelvis_tris,pelvis_report=collapse(model,pelvis,lod,True);triangles.extend(pelvis_tris);records.append(dict(lod=lod,component='garment-pelvis',**pelvis_report))
        from gungnir_continuity import limb_backing
        limbs,limb_records=limb_backing(model,lod,triangles);triangles.extend(limbs);records.extend(dict(lod=lod,**r) for r in limb_records)
        for t in triangles:
            if not t['component'].startswith('garment-'):continue
            for i,p in enumerate(t['p']):
                if .44<p[2]<.585 and abs(p[1])<.075 and p[0]>.042:
                    offset=.042-p[0];p[0]=.042;t['source_faces'][i]={**t['source_faces'][i],'hidden_front_recess_m':offset*3.048,'changed_topology':True}
        if repair:
            hints=json.loads(Path(repair).read_text())['repair_samples'][lod]
            groups=[]
            # Bound clusters in bind space; never join opposite limbs or
            # bridge a large natural opening between the arms and torso.
            for hint in hints:
                p=np.array(hint['point']);fi=hint['face'];ws={b for vi in model['faces'][fi] for b,w in model['weights'][vi] if w>.25}
                choices=[g for g in groups if g['bones']&ws and np.linalg.norm(p-g['center'])<.018 and np.ptp(np.array(g['points']+[p]),axis=0).max()<.036]
                if choices:
                    g=min(choices,key=lambda g:np.linalg.norm(p-g['center']));g['points'].append(p);g['faces'].add(fi);g['center']=np.mean(g['points'],axis=0)
                else:groups.append(dict(points=[p],faces={fi},bones=ws,center=p))
            verts=[Vector(p) for p in model['vertices']]
            for gi,g in enumerate(groups):
                face_ids=sorted(g['faces']);fs=[model['faces'][i] for i in face_ids];tree=BVHTree.FromPolygons(verts,fs,all_triangles=True)
                pts=np.array(g['points']);source_tri=np.array([[model['vertices'][i] for i in f] for f in fs]);normal=np.cross(source_tri[:,1]-source_tri[:,0],source_tri[:,2]-source_tri[:,0]).sum(0)
                if np.linalg.norm(normal)<1e-10:continue
                normal/=np.linalg.norm(normal);u=np.cross(normal,np.eye(3)[np.argmin(abs(normal))]);u/=np.linalg.norm(u);v=np.cross(normal,u);c=g['center'];uv=np.c_[(pts-c)@u,(pts-c)@v];lo=uv.min(0)-.006;hi=uv.max(0)+.006
                ps=[];skin=[];correspondence=[]
                for a,b in ((lo[0],lo[1]),(hi[0],lo[1]),(hi[0],hi[1]),(lo[0],hi[1])):
                    p=Vector(c+u*a+v*b);hit,_,fi,distance=tree.find_nearest(p);ids=fs[fi];bary=np.maximum(0,interpolate.poly_3d_calc([verts[i] for i in ids],hit));bary/=max(1e-12,bary.sum());weights={}
                    for vi,amount in zip(ids,bary):
                        for bone,w in model['weights'][vi]:weights[bone]=weights.get(bone,0)+amount*w
                    ws=sorted(weights.items(),key=lambda x:-x[1])[:4];total=sum(w for b,w in ws);skin.append([(b,w/total) for b,w in ws]);ps.append(list(p));correspondence.append(dict(face=face_ids[fi],barycentric=bary.tolist(),local_return_offset=list(p-hit),changed_topology=True))
                material=87;component=f'garment-local-return-{gi}'
                for f in ((0,1,2),(0,2,3),(2,1,0),(3,2,0)):
                    triangles.append(dict(p=[ps[i] for i in f],weights=[skin[i] for i in f],source_faces=[correspondence[i] for i in f],uv=[[0,0]]*3,component=component,material=material,color_override=[44,49,51],source_components=['source-located local coverage return'],construction='small source-contour return at a measured coverage gap'))
                records.append(dict(lod=lod,component=component,source_faces=face_ids,vertices=4,triangles=4,overlap_halo_units=.006))
        data['lods'][lod]['triangles']=triangles
        poses,clips=bake(model,triangles,motion);np.savez_compressed(output/f'poses-{lod}.npz',**poses);data['lods'][lod]['animations']=clips
    data['restoration_inputs']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (source,armor/'solid.json',backing/'solid.json',*([Path(repair)] if repair else []))}
    data['local_returns']=records;data['publication_approved']=False
    (output/'solid.json').write_text(json.dumps(data,separators=(',',':'))+'\n');(output/'restoration.json').write_text(json.dumps(dict(inputs=data['restoration_inputs'],returns=records),indent=2)+'\n')
    print('RESTORED',[len(l['triangles']) for l in data['lods']],len(records),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('motion');p.add_argument('armor');p.add_argument('backing');p.add_argument('output');p.add_argument('--repair');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run(a.source,a.motion,a.armor,a.backing,a.output,a.repair)
