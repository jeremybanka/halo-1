"""Replace the ODST head; retain the body and restore local source junction faces."""
import copy,hashlib,json,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from demake_odst import paint_source,bake
from odst_helmet import build_head,is_old_head
from reduce_odst_game import fit_overlap

def run(folder,output,candidate='game-scale'):
    folder=Path(folder);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    source=folder/candidate/'solid.json';data=json.loads(source.read_text())
    raw=json.loads((folder/'source/odst-ce-raw.json').read_text());model=paint_source(raw['models']['spartan'])
    clips=dict(raw['animations']);clips.update(json.loads((folder.parent/'jorge/playable-half/ce-motion-source.json').read_text()))
    head,report=build_head(model);report['overlap_fit']=fit_overlap(head)
    # Make paired coordinates bit-identical after fitting, including the midline.
    for i in range(0,len(head),2):
        for p in head[i]['p']:
            if abs(p[1])<1e-7:p[1]=0
        head[i+1]['p']=[[p[0],-p[1],p[2]] for p in [head[i]['p'][j] for j in (0,2,1)]]
    bone=next(i for i,n in enumerate(model['nodes']) if n['name']=='bip01 head')
    changes=[]
    for lod,l in enumerate(data['lods']):
        kept=[t for t in l['triangles'] if not is_old_head(t,bone)]
        immutable=json.dumps(kept,sort_keys=True).encode();removed=len(l['triangles'])-len(kept)
        # Restoring the source head encloses three former open junction gaps
        # during melee. Add only their audited original shoulder/pack faces;
        # never move or re-reduce the accepted garment and armor.
        seams=[]
        for fi in ((8550,),(4126,4150,8550))[lod]:
            ids=model['faces'][fi]
            seams.append(dict(p=[model['vertices'][i] for i in ids],uv=[model['uv'][i] for i in ids],
                weights=[model['skin_weights'][i] for i in ids],material=model['materials'][fi],
                component='helmet-junction-seam',helmet_junction_repair=fi,
                source_faces=[dict(face=fi,barycentric=[int(a==b) for a in range(3)]) for b in range(3)]))
        l['triangles']=[*kept,*seams,*copy.deepcopy(head)];animations=bake(model,l['triangles'],clips);arrays={}
        for i,c in enumerate(animations):
            arrays['frames_'+str(i)]=np.array(c.pop('frames'),np.float32);arrays['grips_'+str(i)]=np.array(c.pop('grips'),np.float32);c['frames']=len(arrays['frames_'+str(i)])
        np.savez_compressed(output/f'poses-{lod}.npz',**arrays);l['animations']=animations
        changes.append(dict(lod=lod,removed_head_triangles=removed,new_head_triangles=len(head),unchanged_body_triangles=len(kept),restored_source_junction_faces=[t['helmet_junction_repair'] for t in seams],unchanged_body_sha256=hashlib.sha256(immutable).hexdigest()))
    data['helmet_symmetry']=report;data['helmet_refinement']=changes
    data['helmet_parent_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
    (output/'solid.json').write_text(json.dumps(data));(output/'helmet-refinement.json').write_text(json.dumps(dict(report=report,changes=changes),indent=2)+'\n')
    print('SYMMETRIC HELMET',report,changes,flush=True)

if __name__=='__main__':run(*sys.argv[sys.argv.index('--')+1:])
