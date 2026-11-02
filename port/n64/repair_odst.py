"""Restore original source triangles only where game-scale coverage found gaps."""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from demake_odst import bake

def repair(folder,faces_path,output,candidate='runtime',reorder=False):
    folder,output=Path(folder),Path(output);output.mkdir(parents=True,exist_ok=True)
    source=folder/candidate/'solid.json'
    data=json.loads(source.read_text())
    raw=json.loads((folder/'source/odst-ce-raw.json').read_text());model=raw['models']['spartan']
    components=json.loads((folder/'source/components.json').read_text())
    source_components={fi:p['id'] for p in components for fi in p['faces']}
    clips=dict(raw['animations']);clips.update(json.loads((folder.parent/'jorge/playable-half/ce-motion-source.json').read_text()))
    selected=json.loads(Path(faces_path).read_text());changes=[]
    for lod,indices in enumerate(selected):
        tris=data['lods'][lod]['triangles'];existing={(t['material'],tuple(sorted(tuple(p) for p in t['p']))) for t in tris}
        added=[]
        for fi in indices:
            face=model['faces'][fi];material=model['materials'][fi]
            if fi in data['stripe_source_faces']:material=len(data['materials'])-1
            points=[model['vertices'][i] for i in face]
            weights=[model['skin_weights'][i] for i in face]
            key=(material,tuple(sorted(tuple(p) for p in points)))
            if key in existing:continue
            existing.add(key);added.append(fi)
            tris.append(dict(p=points,uv=[model['uv'][i] for i in face],weights=weights,
                material=material,component='original-seam' if reorder else f'original-seam:{fi}',continuity_repair=True,
                source_component=source_components[fi],
                source_faces=[dict(face=fi,barycentric=[int(a==b) for a in range(3)]) for b in range(3)]))
        if reorder:
            from reduce_odst_game import cache_order
            for t in tris:
                if t.get('continuity_repair'):t['component']='original-seam'
            tris=cache_order(tris);data['lods'][lod]['triangles']=tris
        animations=bake(model,tris,clips);arrays={}
        for i,c in enumerate(animations):
            arrays['frames_'+str(i)]=np.array(c.pop('frames'),dtype=np.float32)
            arrays['grips_'+str(i)]=np.array(c.pop('grips'),dtype=np.float32);c['frames']=len(arrays['frames_'+str(i)])
        np.savez_compressed(output/f'poses-{lod}.npz',**arrays)
        data['lods'][lod]['animations']=animations
        changes.append(dict(lod=lod,restored_original_faces=added,triangles=len(tris)))
    import hashlib
    data['repair_parent_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
    data['coverage_repairs']=changes
    if reorder:data['opaque_motion_reorder']=True
    (output/'solid.json').write_text(json.dumps(data))
    (output/'coverage-repairs.json').write_text(json.dumps(changes,indent=2)+'\n')
    print('SOURCE SEAM REPAIRS',changes,flush=True)

if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:];repair(*args)
