"""Candidate cull of exact cloth triangles identified by a posed depth audit.

This does not establish hidden-surface status. Full independent assembled
coverage must compare the result to its parent before the cull is accepted.
"""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from demake_gungnir import bake

def run(source,motion,candidate,audit,output):
    source,motion,candidate,audit,output=map(Path,(source,motion,candidate,audit,output));output.mkdir(parents=True,exist_ok=True);data=json.loads((candidate/'solid.json').read_text());original=json.loads(source.read_text());report=json.loads(audit.read_text());ledger=[]
    for lod,model in enumerate(data['lods']):
        targets={(p['component'],json.dumps(p['bind_points'],separators=(',',':'))) for row in report['rows'] if row['lod']==lod for p in row.get('lost_backing',[])};kept=[]
        for ti,t in enumerate(model['triangles']):
            if (t['component'],json.dumps(t['p'],separators=(',',':'))) in targets:
                ledger.append(dict(lod=lod,index=ti,component=t['component'],source_faces=t['source_faces'],decision='candidate cull of cloth crossing the source-visible calf; all-pose parent coverage required'))
            else:kept.append(t)
        model['triangles']=kept;frames,clips=bake(original,kept,motion);np.savez_compressed(output/f'poses-{lod}.npz',**frames);model['animations']=clips
    data['intersection_cull_parent_sha256']=hashlib.sha256((candidate/'solid.json').read_bytes()).hexdigest();data['intersection_culls']=ledger;data['publication_approved']=False
    (output/'solid.json').write_text(json.dumps(data,separators=(',',':'))+'\n');(output/'intersection-culls.json').write_text(json.dumps(ledger,indent=2)+'\n');print('CULLS',len(ledger),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('motion');p.add_argument('candidate');p.add_argument('audit');p.add_argument('output');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run(a.source,a.motion,a.candidate,a.audit,a.output)
