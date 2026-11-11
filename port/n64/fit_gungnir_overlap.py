"""Measured local armor overlap on retained source surfaces, without new tracks.

Offset existing plate contours by a bounded distance to meet adjacent source
garment. Preserve component topology, then transfer correspondence and skin
again from that component's original triangles. Coverage/depth remain separate
acceptance gates; an offset alone never approves a candidate.
"""
import argparse,copy,hashlib,json,sys
from collections import defaultdict
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector,interpolate
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from demake_gungnir import bake

def run(source,inventory,candidate,motion,output,overlap_mm,repair=None):
    source,inventory,candidate,motion,output=map(Path,(source,inventory,candidate,motion,output));output.mkdir(parents=True,exist_ok=True)
    assert 0<=overlap_mm<=16
    original=json.loads(source.read_text());parts={p['id']:p for p in json.loads(inventory.read_text())};data=json.loads((candidate/'solid.json').read_text());report=[]
    for lod,model in enumerate(data['lods']):
        by_part=defaultdict(list)
        for t in model['triangles']:
            name=t['component']
            if name.startswith(('garment-','helmet-','chest-')) or name.endswith('-glove'):continue
            by_part[name].append(t)
        if not overlap_mm:by_part={}
        for name,triangles in by_part.items():
            normals=defaultdict(lambda:np.zeros(3));points={}
            def key(p,ws):return tuple(p),tuple(map(tuple,ws))
            for t in triangles:
                p=np.array(t['p']);n=np.cross(p[1]-p[0],p[2]-p[0])
                for p,ws in zip(t['p'],t['weights']):
                    k=key(p,ws);normals[k]+=n;points[k]=np.array(p)
            source_ids={c.split(' / ')[0] for t in triangles for c in t['source_components']};faces=sorted({fi for c in source_ids for fi in parts[c]['faces']});tree=BVHTree.FromPolygons([Vector(p) for p in original['vertices']],[original['faces'][fi] for fi in faces],all_triangles=True)
            changes={};maximum=0
            for k,p in points.items():
                n=normals[k];length=np.linalg.norm(n)
                amount=overlap_mm/3048 if length>1e-10 else 0
                if name.endswith('-boot') and p[2]<.035:amount=0
                q=Vector(p+n/max(length,1e-12)*amount);hit,_,fi,distance=tree.find_nearest(q);ids=original['faces'][faces[fi]];bary=np.maximum(0,interpolate.poly_3d_calc([Vector(original['vertices'][vi]) for vi in ids],hit));bary/=max(1e-12,bary.sum());weights=defaultdict(float)
                for vi,value in zip(ids,bary):
                    for bi,w in original['weights'][vi]:weights[bi]+=value*w
                ws=sorted(((bi,w) for bi,w in weights.items() if w>1e-7),key=lambda x:-x[1])[:4];total=sum(w for bi,w in ws);ws=[(bi,w/total) for bi,w in ws]
                uv=(bary@np.array([original['uv'][vi] for vi in ids])).tolist();record=dict(face=faces[fi],barycentric=bary.tolist(),surface_distance=distance,coverage_overlap_displacement_m=(np.array(q)-p).tolist(),changed_topology=True)
                record['coverage_overlap_displacement_m']=[v*3.048 for v in record['coverage_overlap_displacement_m']]
                changes[k]=(list(q),ws,uv,record);maximum=max(maximum,distance*3.048)
            for t in triangles:
                for i,(p,ws) in enumerate(zip(t['p'],t['weights'])):
                    q,new_ws,uv,record=changes[key(p,ws)];t['p'][i]=q;t['weights'][i]=new_ws;t['uv'][i]=uv;t['source_faces'][i]=copy.deepcopy(record)
                t['construction']+='; bounded local plate overlap with renewed original source correspondence'
            report.append(dict(lod=lod,component=name,overlap_mm=overlap_mm,maximum_final_source_point_distance_m=maximum,triangles=len(triangles)))
        if repair:
            from gungnir_seams import source_seams
            patches,ledger=source_seams(original,json.loads(Path(repair).read_text())['repair_source_faces'][lod],lod,model['triangles']);model['triangles'].extend(patches);data.setdefault('seam_repairs',[]).extend(ledger)
        poses,clips=bake(original,model['triangles'],motion);np.savez_compressed(output/f'poses-{lod}.npz',**poses);model['animations']=clips
    data['overlap_parent_sha256']=hashlib.sha256((candidate/'solid.json').read_bytes()).hexdigest();data.setdefault('overlap_repairs',[]).extend(report);data['publication_approved']=False
    if repair:data['seam_review_sha256']=hashlib.sha256(Path(repair).read_bytes()).hexdigest()
    (output/'solid.json').write_text(json.dumps(data,separators=(',',':'))+'\n');(output/'overlap-report.json').write_text(json.dumps(report,indent=2)+'\n');print('FITTED',overlap_mm,'mm',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('inventory');p.add_argument('candidate');p.add_argument('motion');p.add_argument('output');p.add_argument('--overlap-mm',type=float,default=6);p.add_argument('--repair-report');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run(a.source,a.inventory,a.candidate,a.motion,a.output,a.overlap_mm,a.repair_report)
