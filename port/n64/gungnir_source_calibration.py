"""Intact-source control for coverage/depth audits, never a playable asset."""
import argparse,copy,hashlib,json
from pathlib import Path
import numpy as np
from extract_gungnir import bone_globals
from audit_models import engine

def run(source,inventory,motion,donor,output):
    output.mkdir(parents=True,exist_ok=True);m=json.loads(source.read_text());meta=json.loads((motion/'motion-report.json').read_text());poses=np.load(motion/'native-poses.npz');parts=json.loads(inventory.read_text());part_for_face={f:p['id'] for p in parts for f in p['faces']};donor=json.loads((donor/'solid.json').read_text());roles={}
    for t in donor['lods'][0]['triangles']:
        for component in t['source_components']:
            component=component.split(' / ')[0]
            if component in part_for_face.values():roles[component]=t['component']
    triangles=[]
    for fi,face in enumerate(m['faces']):
        part=part_for_face[fi];material=m['materials'][fi];component=roles.get(part,('garment-' if material in (5,87) else 'source-')+part)
        if part=='body-06:005':
            p=np.array([m['vertices'][i] for i in face]);component='torso-back' if p[:,0].mean()<-.062 and p[:,2].mean()>.505 else 'torso'
        triangles.append(dict(p=[m['vertices'][i] for i in face],uv=[m['uv'][i] for i in face],weights=[m['weights'][i] for i in face],material=material,component=component,source_components=[part],source_faces=[dict(face=fi,barycentric=[int(i==j) for i in range(3)],unchanged_source_vertex=vi) for j,vi in enumerate(face)],construction='intact source calibration; no reduction'))
    points=np.c_[m['vertices'],np.ones(len(m['vertices']))];weights=np.zeros((len(points),len(m['nodes'])))
    for i,ws in enumerate(m['weights']):
        for b,w in ws:weights[i,b]=w
    inverse=np.linalg.inv(np.array(bone_globals(m['nodes'])));frames={};clips=[]
    for ci,clip in enumerate(meta['clips']):
        matrices=poses['matrices_'+str(ci)];clips.append(dict(name=clip['name'],duration=clip['duration'],frames=len(matrices)))
        if clip['name'] not in ('idle','run','reload','passenger'):continue
        values=[]
        for matrix in matrices:
            skin=matrix@inverse;vertices=np.zeros((len(points),3))
            for b in np.flatnonzero(weights.sum(0)):vertices+=(points@skin[b].T)[:,:3]*weights[:,b,None]
            values.append(engine(vertices)[np.array(m['faces'])].reshape(-1,3).astype(np.float32))
        frames['frames_'+str(ci)]=np.array(values)
    for lod in range(2):np.savez_compressed(output/f'poses-{lod}.npz',**frames)
    data=dict(quality_state='intact source audit control; not a playable candidate',publication_approved=False,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),nodes=m['nodes'],materials=m['material_metadata'],textures=[t.get('diffuse') for t in m['material_metadata']],lods=[dict(triangles=triangles,animations=clips),dict(triangles=triangles,animations=clips)],ledger=[],omitted_components=[])
    (output/'solid.json').write_text(json.dumps(data,separators=(',',':'))+'\n');print('SOURCE CONTROL',len(triangles),'triangles',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('inventory',type=Path);p.add_argument('motion',type=Path);p.add_argument('donor',type=Path);p.add_argument('output',type=Path);a=p.parse_args();run(a.source,a.inventory,a.motion,a.donor,a.output)
