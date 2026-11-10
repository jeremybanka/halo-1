"""Identify redundant construction across every adapted clip, not only the bind pose.

This is a finite visibility sample. Its face ledger is a candidate semantic cut,
not a proof of invisibility in every pose; independent assembled coverage and
plate-depth gates remain mandatory after reduction and N64 quantization.
"""
import sys,json,argparse,hashlib
from pathlib import Path
import numpy as np
from audit_models import Mesh,engine,matching_bounds,ANGLES
from demake_raster import Raster
from extract_gungnir import bone_globals


def run(source,motion,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True);m=json.loads(Path(source).read_text());meta=json.loads((Path(motion)/'motion-report.json').read_text());poses=np.load(Path(motion)/'native-poses.npz')
    points=np.c_[m['vertices'],np.ones(len(m['vertices']))];weights=np.zeros((len(points),len(m['nodes'])))
    for i,values in enumerate(m['weights']):
        for b,w in values:weights[i,b]=w
    inverse=np.linalg.inv(np.array(bone_globals(m['nodes'])));faces=np.array(m['faces']);seen=np.zeros(len(faces),bool);raster=Raster(output);rows=[];calibration=[]
    directions=[d for name,d in ANGLES]+[(.001,-1,.001),(-1,-.25,1)]
    for ci,clip in enumerate(meta['clips']):
        frames=poses['matrices_'+str(ci)];indices=sorted(set(round(f*(len(frames)-1)) for f in (0,.2,.4,.6,.8,1)))
        for fi in indices:
            skin=frames[fi]@inverse;vertices=np.zeros((len(points),3))
            for b in np.flatnonzero(weights.sum(0)):vertices+=(points@skin[b].T)[:,:3]*weights[:,b,None]
            mesh=Mesh(engine(vertices)[faces],rgb=np.full((len(faces),3,3),160.))
            for vi,direction in enumerate(directions):
                bounds=matching_bounds([mesh],direction)
                if ci==0 and fi==0 and vi<3:calibration.append(raster.calibrate(mesh,bounds,direction))
                _,ids,_=raster.render(mesh,bounds,direction,width=160,height=160);visible=np.unique(ids[ids>=0]);seen[visible]=True
                rows.append(dict(clip=clip['name'],frame=fi,direction=vi,visible_faces=len(visible)))
        print('VISIBILITY',clip['name'],int(seen.sum()),flush=True)
    report=dict(source_sha256=hashlib.sha256(Path(source).read_bytes()).hexdigest(),motion_sha256=hashlib.sha256((Path(motion)/'motion-report.json').read_bytes()).hexdigest(),samples=len(rows),image_size=160,calibration=calibration,visible_source_faces=np.flatnonzero(seen).tolist(),unseen_source_faces=np.flatnonzero(~seen).tolist(),views=rows,scope=__doc__)
    (output/'visibility.json').write_text(json.dumps(report,indent=2)+'\n');print('VISIBLE',int(seen.sum()),'of',len(seen),'faces across',len(rows),'images',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('motion');p.add_argument('output');a=p.parse_args();run(a.source,a.motion,a.output)
