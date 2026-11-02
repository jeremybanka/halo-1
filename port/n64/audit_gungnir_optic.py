"""Optic shape, intact convex shell, stable art placement and clean albedo."""
import argparse,copy,hashlib,json
from collections import Counter
from pathlib import Path
import numpy as np
from PIL import Image
from pack_gungnir import prepare_broad_colors,corner_colors
from gungnir_assets import texture_path
from gungnir_faces import face_uv
from audit_models import engine

def run(parent,candidate,output):
    output.mkdir(parents=True,exist_ok=True);before=json.loads((parent/'solid.json').read_text());data=json.loads((candidate/'solid.json').read_text());rows=[]
    textures={i:Image.open(texture_path(p,candidate/'solid.json')).convert('RGB') for i,p in enumerate(data['textures']) if p}
    prepared=copy.deepcopy(data);prepare_broad_colors(prepared,textures)
    for lod,model in enumerate(data['lods']):
        unrelated=lambda d:[t for t in d['lods'][lod]['triangles'] if t['component'] not in ('helmet-lens','helmet-optic-frame')]
        assert unrelated(before)==unrelated(data),'A requested optic change moved another component'
        shell=[t for t in model['triangles'] if t['component']=='helmet-shell'];points=np.array([t['p'] for t in shell]);normals=np.cross(points[:,1]-points[:,0],points[:,2]-points[:,0]);unique=np.unique(points.reshape(-1,3),axis=0)
        error=np.max(np.einsum('fvi,fi->fv',unique[None,:,:]-points[:,0,None,:],normals));assert error<1e-9,('Non-convex helmet',lod,error)
        edges=Counter()
        for tri in points:
            keys=[tuple(np.round(p,8)) for p in tri]
            for a,b in zip(keys,keys[1:]+keys[:1]):edges[tuple(sorted((a,b)))]+=1
        assert all(v==2 for v in edges.values()),'Helmet acquired an open seam'
        old_uv=face_uv(before,engine(points.reshape(-1,3)));new_uv=face_uv(data,engine(points.reshape(-1,3)));assert np.allclose(old_uv,new_uv,rtol=0,atol=1e-12),'Original drawings shifted'
        eye=[t for t in model['triangles'] if t['component']=='helmet-lens'];frame=[t for t in model['triangles'] if t['component']=='helmet-optic-frame'];ep=np.unique(np.array([t['p'] for t in eye]).reshape(-1,3),axis=0);fp=np.unique(np.array([t['p'] for t in frame]).reshape(-1,3),axis=0)
        assert len(eye)==4 and len(ep)==6 and len(frame)==2 and len(fp)==4
        assert np.ptp(ep[:,0])==np.ptp(fp[:,0])==0 and ep[0,0]>fp[0,0]
        assert sum(np.isclose(ep[:,2],ep[:,2].max()))==2 and sum(np.isclose(ep[:,2],ep[:,2].min()))==2,'Hex must have flat top and bottom'
        assert all(t['color_override']==[255,149,25] for t in eye) and all(t['color_override']==[76,76,76] for t in frame)
        assert all(t['weights']==before['lods'][lod]['triangles'][next(i for i,t in enumerate(before['lods'][lod]['triangles']) if t['component']=='helmet-lens')]['weights'] for t in [*eye,*frame])
        new_colors=[corner_colors(t,data['materials'],textures)[0] for t in prepared['lods'][lod]['triangles'] if t['component']=='helmet-shell']
        shuffled=copy.deepcopy(data);ts=[t for t in shuffled['lods'][lod]['triangles'] if t['component']=='helmet-shell'];uvs=[uv for t in ts for uv in t['uv']][::-1]
        for i,t in enumerate(ts):t['uv']=uvs[i*3:i*3+3]
        prepare_broad_colors(shuffled,textures);other_colors=[corner_colors(t,data['materials'],textures)[0] for t in ts]
        assert np.array_equal(new_colors,other_colors),'Source UV stains still affect the helmet'
        ps=np.load(candidate/f'poses-{lod}.npz');eye_ids=[i for i,t in enumerate(model['triangles']) if t['component']=='helmet-lens'];samples=degenerate=0
        for ci in range(39):
            f=np.rint(ps['frames_'+str(ci)]*512).astype(np.int64).reshape(-1,len(model['triangles']),3,3)[:,eye_ids];n=np.cross(f[:,:,1]-f[:,:,0],f[:,:,2]-f[:,:,0]);degenerate+=int((np.linalg.norm(n,axis=-1)==0).sum());samples+=f.shape[0]
            assert all(len(np.unique(p.reshape(-1,3),axis=0))==6 for p in f),'A quantized pose lost a hex corner'
        rows.append(dict(lod=lod,helmet_shell_geometry_unchanged=True,closed_convex_shell=True,flat_topped_hex_corners=6,orange_rgb=[255,149,25],housing_rgb=[76,76,76],source_art_uv_unchanged=True,source_uv_stains_removed=True,quantized_pose_samples=samples,quantized_optic_degenerate_triangles=degenerate,width_increase_ratio=float(np.ptp(ep[:,1])/np.ptp(np.array([t['p'] for t in before['lods'][lod]['triangles'] if t['component']=='helmet-lens'])[:,:,1]))))
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();result=dict(schema=1,passed=True,candidate_sha256=sha(candidate/'solid.json'),parent_sha256=sha(parent/'solid.json'),lods=rows,scope='All unrelated geometry and original scrawls retain their coordinates. Helmet remains closed/convex. Albedo is independent of source UV stains; all 39 clips retain six quantized optic corners. Native appearance and rendering are separate.')
    (output/'optic-validation.json').write_text(json.dumps(result,indent=2)+'\n');print('OPTIC VALIDATION',rows,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('parent','candidate','output'):p.add_argument(name,type=Path)
    a=p.parse_args();run(a.parent,a.candidate,a.output)
