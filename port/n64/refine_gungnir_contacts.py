"""Local source-measured hip continuity and original back-panel returns.

The hip rings use the intact garment/plate cross-sections and native source
weights. They are recessed against the retained thigh contour, rather than
forming a convex volume across both legs. All added geometry is recorded.
"""
import argparse,copy,hashlib,json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector,interpolate
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from demake_gungnir import bake,envelope
from extract_gungnir import bone_globals

def run(source,motion,candidate,inventory,clearance,output):
    source,motion,candidate,inventory,clearance,output=map(Path,(source,motion,candidate,inventory,clearance,output));output.mkdir(parents=True,exist_ok=True)
    original=json.loads(source.read_text());data=json.loads((candidate/'solid.json').read_text());parts=json.loads(inventory.read_text());part_for_face={f:p['id'] for p in parts for f in p['faces']};bind=bone_globals(original['nodes']);names={n['name']:i for i,n in enumerate(original['nodes'])};ledger=[]
    vertices=[Vector(p) for p in original['vertices']];cloth_faces=[i for i,(region,mat) in enumerate(zip(original['regions'],original['materials'])) if region=='body' and mat==87];cloth=BVHTree.FromPolygons(vertices,[original['faces'][i] for i in cloth_faces],all_triangles=True)
    donor=json.loads(clearance.read_text())['restore_original_faces']
    def transfer(p):
        hit,_,fi,distance=cloth.find_nearest(Vector(p));face=cloth_faces[fi];vs=original['faces'][face];bary=np.maximum(0,interpolate.poly_3d_calc([vertices[i] for i in vs],hit));bary/=bary.sum();ws={}
        for vi,amount in zip(vs,bary):
            for b,w in original['weights'][vi]:ws[b]=ws.get(b,0)+w*amount
        ws=sorted(ws.items(),key=lambda x:-x[1])[:4];total=sum(w for b,w in ws)
        return [(b,w/total) for b,w in ws],(bary@np.array([original['uv'][i] for i in vs])).tolist(),dict(face=face,barycentric=bary.tolist(),continuity_distance=distance,changed_topology=True)
    for lod,model in enumerate(data['lods']):
        triangles=model['triangles']
        # Close only the small isolated upper-back panel through its exact
        # retained contours. The main torso's authored curved exterior stays.
        back=[t for t in triangles if t['component']=='torso-back'];corners=[];lookup={}
        for t in back:
            for i,p in enumerate(t['p']):
                k=tuple(p)
                if k not in lookup:lookup[k]=len(corners);corners.append((t,i))
        points,faces=envelope([t['p'][i] for t,i in corners]);new=[]
        for f in faces:
            row=copy.deepcopy(back[0]);donors=[min(corners,key=lambda c:np.linalg.norm(np.subtract(c[0]['p'][c[1]],points[i]))) for i in f]
            for field in ('p','uv','weights','source_faces'):row[field]=[copy.deepcopy(t[field][i]) for t,i in donors]
            row['construction']='closed return through the retained original upper-back contour';new.append(row)
        triangles[:]=[t for t in triangles if t['component']!='torso-back']+new
        ledger.append(dict(lod=lod,component='torso-back',parent_triangles=len(back),triangles=len(new),new_tracks=0))
        for side,short in [('left','l'),('right','r')]:
            thigh=bind[names[f'b_{short}_thigh']][:3,3];knee=bind[names[f'b_{short}_calf']][:3,3];axis=knee-thigh;length=np.linalg.norm(axis);axis/=length;u=np.array((1.,0,0));u-=axis*(axis@u);u/=np.linalg.norm(u);v=np.cross(axis,u)
            ts=[t for t in triangles if t['component']==side+'-thigh'];hull_points,hull_faces=envelope([p for t in ts for p in t['p']]);plate=BVHTree.FromPolygons(hull_points,hull_faces,all_triangles=True)
            source_faces=[f for p in parts if p['id'] in ('body-87:004','body-06:'+('024' if side=='left' else '023')) for f in p['faces']];reference=BVHTree.FromPolygons(vertices,[original['faces'][f] for f in source_faces],all_triangles=True)
            count=5 if lod==0 else 4;levels=(-.020,.025,.080) if lod==0 else (-.020,.080);points=[];weights=[];uvs=[];records=[];ring_records=[]
            for along in levels:
                center=thigh+axis*along;radii=[]
                for a in np.arange(count)*2*np.pi/count:
                    direction=u*np.cos(a)+v*np.sin(a);hit,_,_,radius=reference.ray_cast(Vector(center),Vector(direction),.12)
                    if hit is None:
                        cloud=np.array([original['vertices'][vi] for f in source_faces for vi in original['faces'][f]]);delta=cloud-center;projection=delta@direction;axial=delta@axis;keep=(abs(axial)<.025)&(projection>.004)
                        assert keep.any(),(side,along,a);radius=float(np.percentile(projection[keep],60))
                    radius=max(.012,min(.060,radius-.001));plate_hit,_,_,plate_radius=plate.ray_cast(Vector(center),Vector(direction),.12)
                    if along>=0 and plate_hit is not None:radius=min(radius,max(.007,plate_radius-.001))
                    p=center+direction*radius;ws,uv,record=transfer(p);points.append(p.tolist());weights.append(ws);uvs.append(uv);records.append(record);radii.append(radius)
                ring_records.append(dict(center=center.tolist(),radii=radii))
            faces=[]
            for r in range(len(levels)-1):
                for j in range(count):
                    k=(j+1)%count;a=r*count+j;b=r*count+k;c=(r+1)*count+k;d=(r+1)*count+j;faces.extend(([a,b,c],[a,c,d]))
            for offset in (0,(len(levels)-1)*count):faces.extend([offset,offset+i,offset+i+1] for i in range(1,count-1))
            for f in faces:
                p=np.array([points[i] for i in f]);center=thigh+axis*((p.mean(0)-thigh)@axis)
                radial=p.mean(0)-center
                if len({i//count for i in f})==1:radial=axis*(-1 if f[0]//count==0 else 1)
                if np.dot(np.cross(p[1]-p[0],p[2]-p[0]),radial)<0:f.reverse()
                triangles.append(dict(p=[points[i] for i in f],uv=[uvs[i] for i in f],weights=[weights[i] for i in f],source_faces=[records[i] for i in f],source_components=['original pelvis garment and '+side+' thigh cross-sections'],material=87,component='garment-hip-return-'+side,color_override=[44,49,51],construction='local source-measured hip return recessed inside the retained thigh; native garment skin channels'))
            ledger.append(dict(lod=lod,component='garment-hip-return-'+side,triangles=len(faces),vertices=len(points),rings=ring_records))
        for fi in donor[lod]:
            vs=original['faces'][fi];name=part_for_face[fi];component='left-calf' if name=='body-06:020' else 'restored-original-'+name
            triangles.append(dict(p=[original['vertices'][i] for i in vs],uv=[original['uv'][i] for i in vs],weights=[original['weights'][i] for i in vs],source_faces=[dict(face=fi,barycentric=[int(j==k) for j in range(3)],unchanged_original_corner=True) for k in range(3)],source_components=[name],material=original['materials'][fi],component=component,construction='restore original plate triangle identified by the independent depth audit'))
        frames,clips=bake(original,triangles,motion);np.savez_compressed(output/f'poses-{lod}.npz',**frames);model['animations']=clips
    data['contact_parent_sha256']=hashlib.sha256((candidate/'solid.json').read_bytes()).hexdigest();data['contact_refinement']=ledger;data['publication_approved']=False
    (output/'solid.json').write_text(json.dumps(data,separators=(',',':'))+'\n');(output/'contact-refinement.json').write_text(json.dumps(ledger,indent=2)+'\n');print('CONTACTS',[len(m['triangles']) for m in data['lods']],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('motion');p.add_argument('candidate');p.add_argument('inventory');p.add_argument('clearance');p.add_argument('output');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run(a.source,a.motion,a.candidate,a.inventory,a.clearance,a.output)
