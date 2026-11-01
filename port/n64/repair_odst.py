"""Restore original source triangles only where game-scale coverage found gaps."""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from demake_odst import bake

def repair(folder,faces_path,output):
    folder,output=Path(folder),Path(output);output.mkdir(parents=True,exist_ok=True)
    source=folder/'runtime/solid.json'
    data=json.loads(source.read_text())
    raw=json.loads((folder/'source/odst-ce-raw.json').read_text());model=raw['models']['spartan']
    clips=dict(raw['animations']);clips.update(json.loads((folder.parent/'jorge/playable-half/ce-motion-source.json').read_text()))
    selected=json.loads(Path(faces_path).read_text());changes=[]
    for lod,indices in enumerate(selected):
        tris=data['lods'][lod]['triangles'];existing={(t['material'],tuple(sorted(tuple(p) for p in t['p']))) for t in tris}
        added=[]
        for fi in indices:
            face=model['faces'][fi];material=model['materials'][fi]
            if fi in data['stripe_source_faces']:material=len(data['materials'])-1
            points=[model['vertices'][i] for i in face]
            key=(material,tuple(sorted(tuple(p) for p in points)))
            if key in existing:continue
            existing.add(key);added.append(fi)
            tris.append(dict(p=points,uv=[model['uv'][i] for i in face],weights=[model['skin_weights'][i] for i in face],
                material=material,component=f'original-seam:{fi}',continuity_repair=True,
                source_faces=[dict(face=fi,barycentric=[int(a==b) for a in range(3)]) for b in range(3)]))
        animations=bake(model,tris,clips);arrays={}
        for i,c in enumerate(animations):
            arrays['frames_'+str(i)]=np.array(c.pop('frames'),dtype=np.float32)
            arrays['grips_'+str(i)]=np.array(c.pop('grips'),dtype=np.float32);c['frames']=len(arrays['frames_'+str(i)])
        np.savez_compressed(output/f'poses-{lod}.npz',**arrays)
        data['lods'][lod]['animations']=animations
        changes.append(dict(lod=lod,restored_original_faces=added,triangles=len(tris)))
    data['coverage_repairs']=changes
    (output/'solid.json').write_text(json.dumps(data))
    (output/'coverage-repairs.json').write_text(json.dumps(changes,indent=2)+'\n')
    print('SOURCE SEAM REPAIRS',changes,flush=True)

if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:];repair(*args)
