"""Independent source fit, topology and quantization observations for both LODs."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from demake_gungnir import groups

def run(source,candidate,output):
    source,candidate,output=map(Path,(source,candidate,output));output.mkdir(parents=True,exist_ok=True);original=json.loads(source.read_text());data=json.loads((candidate/'solid.json').read_text());plan={g['id']:g for g in groups(original,True)[0]};rows=[];valid=[]
    for lod,model in enumerate(data['lods']):
        parts={}
        for t in model['triangles']:parts.setdefault(t['component'],[]).append(t)
        for name,ts in parts.items():
            p=np.array([t['p'] for t in ts]);assert np.isfinite(p).all();n=np.linalg.norm(np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]),axis=1)
            assert n.min()>1e-12,(lod,name,'float-degenerate triangle')
            for t in ts:
                for ws in t['weights']:assert 1<=len(ws)<=4 and any(w>0 for b,w in ws) and all(0<=b<len(data['nodes']) and w>=0 for b,w in ws) and abs(sum(w for b,w in ws)-1)<1e-5
            source_ids=plan[name]['faces'] if name in plan else sorted({r['face'] for t in ts for r in t['source_faces']})
            tree=BVHTree.FromPolygons([Vector(v) for v in original['vertices']],[original['faces'][i] for i in source_ids],all_triangles=True)
            distances=np.array([tree.find_nearest(Vector(v))[3]*3.048 for v in p.reshape(-1,3)])
            rows.append(dict(lod=lod,component=name,triangles=len(ts),source_faces=len(source_ids),sampled_retained_corner_error_m=dict(maximum=float(distances.max()),p95=float(np.percentile(distances,95)),mean=float(distances.mean()))))
        poses=np.load(candidate/f'poses-{lod}.npz');degenerate=total=0;maximum=0
        for ci in range(39):
            frames=np.rint(poses['frames_'+str(ci)]*512).astype(np.int64).reshape(-1,len(model['triangles']),3,3)
            cross=np.cross(frames[:,:,1]-frames[:,:,0],frames[:,:,2]-frames[:,:,0]);area=np.linalg.norm(cross,axis=-1);degenerate+=int((area==0).sum());total+=area.size;maximum=max(maximum,int(np.abs(frames).max()))
        valid.append(dict(lod=lod,authoring_triangle_pose_samples=total,quantized_degenerate_triangle_samples=degenerate,maximum_quantized_coordinate=maximum,normalized_four_influence_weights=True))
    report=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),candidate_sha256=hashlib.sha256((candidate/'solid.json').read_bytes()).hexdigest(),parts=rows,geometry=valid,scope='Retained-corner distances to component-local source triangles; sampled values, not an exhaustive surface bound. Quantized zero-area triangles are reported without silently deleting them; appearance acceptance is separate.')
    (output/'shape-validation.json').write_text(json.dumps(report,indent=2)+'\n');print('SHAPE',valid,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('candidate');p.add_argument('output');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run(a.source,a.candidate,a.output)
