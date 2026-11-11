"""Review-located returns sharing existing native trajectories and RGB corners.

Keep raw body-union measurements. Do not bridge air between opposite legs or
between a hand/forearm and the head/torso just to improve a silhouette metric.
Those projection changes remain separately reviewable in the original report.
"""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
import bpy,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from demake_gungnir import bake
from gungnir_seams import source_seams

def projection_gap(components):
    c=set(components)
    left=any('left' in n and any(s in n for s in ('thigh','knee','calf','boot')) for n in c)
    right=any('right' in n and any(s in n for s in ('thigh','knee','calf','boot')) for n in c)
    if left and right:return 'opposite legs'
    distal=any(n.endswith(('-forearm','-glove')) or n=='wrist-buckler' for n in c)
    body=any(n in ('helmet-shell','torso','torso-back','belt') or n.startswith('chest-') for n in c)
    if distal and body:return 'hand/forearm crossing head or torso'
    if 'helmet-shell' in c and any(n.endswith('-upperarm') or n.startswith('shoulder-') for n in c):return 'head/upper-arm projection'
    return None

def run(source,motion,candidate,review,output):
    source,motion,candidate,review,output=map(Path,(source,motion,candidate,review,output));output.mkdir(parents=True,exist_ok=True)
    original=json.loads(source.read_text());data=json.loads((candidate/'solid.json').read_text());audit=json.loads(review.read_text());assert audit['candidate_sha256']==hashlib.sha256((candidate/'solid.json').read_bytes()).hexdigest()
    subprocess.run([str(Path('build/n64-python/bin/python').absolute()),str(Path(__file__).with_name('gungnir_library_colors.py')),str(candidate/'solid.json'),str(output/'donor-colors.json')],check=True);colors=json.loads((output/'donor-colors.json').read_text());ledger=[]
    for lod,model in enumerate(data['lods']):
        faces=set();decisions=[]
        for view in audit['views']:
            if view['lod']!=lod:continue
            for gap in view['gap_boundaries']:
                reason=projection_gap(gap['boundary_components']);decisions.append(dict(clip=view['clip'],frame=view['frame'],angle=view['angle'],size=view['size'],gap=gap,projection_change=reason))
                if not reason:faces.update(gap['source_faces'])
        patches,records=source_seams(original,sorted(faces),lod,model['triangles'],colors[lod])
        kept=[]
        for tri in patches:
            if np.ptp(np.array(tri['p']),axis=0).max()>.075:continue
            tri['component']='garment-local-return-'+tri['component'];tri['construction']+='; exact donor RGB and team-mask corners retained'
            kept.append(tri)
        model['triangles'].extend(kept);frames,clips=bake(original,model['triangles'],motion);np.savez_compressed(output/f'poses-{lod}.npz',**frames);model['animations']=clips
        ledger.append(dict(lod=lod,source_locator_faces=sorted(faces),added_triangles=len(kept),new_trajectories=0,donor_records=records,review_decisions=decisions))
    data['gap_parent_sha256']=hashlib.sha256((candidate/'solid.json').read_bytes()).hexdigest();data['gap_review_sha256']=hashlib.sha256(review.read_bytes()).hexdigest();data['gap_returns']=ledger;data['publication_approved']=False
    (output/'solid.json').write_text(json.dumps(data,separators=(',',':'))+'\n');(output/'gap-returns.json').write_text(json.dumps(ledger,indent=2)+'\n');print('GAP RETURNS',[(r['added_triangles'],r['new_trajectories']) for r in ledger],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('motion');p.add_argument('candidate');p.add_argument('review');p.add_argument('output');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run(a.source,a.motion,a.candidate,a.review,a.output)
