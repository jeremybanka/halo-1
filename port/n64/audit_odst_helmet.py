"""Blender-independent acceptance checks for the original-source helmet refinement."""
from collections import Counter,defaultdict
import hashlib,json
import numpy as np

def check_helmet(data,old):
    head=next(i for i,n in enumerate(data['nodes']) if n['name']=='bip01 head')
    helmets=[];reports=[]
    def old_head(t):
        return (t['component'].startswith('helmet') or t.get('source_component','').startswith('helmet')) and all(b==head for ws in t['weights'] for b,w in ws if w>1e-5)
    for lod,l in enumerate(data['lods']):
        helmet=[t for t in l['triangles'] if t['component']=='helmet-head'];helmets.append(helmet)
        body=[t for t in l['triangles'] if t['component']!='helmet-head' and 'helmet_junction_repair' not in t]
        seams=[t for t in l['triangles'] if 'helmet_junction_repair' in t]
        assert [t['helmet_junction_repair'] for t in seams]==[[8550],[4126,4150,8550]][lod]
        reference=[t for t in old['lods'][lod]['triangles'] if not old_head(t)]
        assert body==reference,'Helmet refinement changed accepted body data'
        points=np.array([t['p'] for t in helmet]);assert len(helmet)%2==0
        mirrored=points[1::2][:,[0,2,1]]*[1,-1,1]
        error=float(np.abs(points[::2]-mirrored).max());assert error<1e-10
        quantized=np.rint(points*512).astype(int)
        assert np.array_equal(quantized[::2],quantized[1::2][:,[0,2,1]]*[1,-1,1])
        for a,b in zip(helmet[::2],helmet[1::2]):
            assert a['material']==b['material'] and a['helmet_region']==b['helmet_region']
            assert a['uv']==[b['uv'][i] for i in (0,2,1)]
            if 'corner_color_override' in a:assert a['corner_color_override']==[b['corner_color_override'][i] for i in (0,2,1)]
            assert all(ws==[[head,1]] for t in (a,b) for ws in t['weights'])
        stripe=[t for t in helmet if t['helmet_region']=='stripe'];assert len(stripe)==42
        assert all(r['maximum_protected_movement']<1e-7 for r in data['helmet_symmetry']['regions'])
        points=np.array([t['p'] for t in stripe]);assert abs(float(points[:,:,1].mean()))<1e-10
        assert np.abs(points[:,:,1]).max()<.012,'Crown paint expanded into a helmet cap'
        assert np.ptp(points[:,:,0])>.10,'Stripe no longer runs front to back'
        # Connectivity after the actual game's bind-coordinate quantization.
        adjacency=defaultdict(set)
        for i,t in enumerate(stripe):
            for p in np.rint(np.array(t['p'])*512).astype(int):adjacency[tuple(p)].add(i)
        remaining=set(range(len(stripe)));components=0
        while remaining:
            todo=[remaining.pop()];components+=1
            while todo:
                for p in np.rint(np.array(stripe[todo.pop()]['p'])*512).astype(int):
                    for j in adjacency[tuple(p)]:
                        if j in remaining:remaining.remove(j);todo.append(j)
        assert components==1,'Quantized crown stripe is broken'
        reports.append(dict(lod=lod,head_triangles=len(helmet),stripe_triangles=len(stripe),stripe_components=components,maximum_mirror_error_halo=error,quantized_bind_symmetric=True,colors_symmetric=True,body_sha256=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()))
    assert helmets[0]==helmets[1],'Near/far helmets must share the protected head'
    return dict(shared_head_between_lods=True,lods=reports)

import argparse
from pathlib import Path

def check_packed(data,packed):
    reports=[]
    for lod,l in enumerate(data['lods']):
        p=np.load(packed/f'odst-{lod}-preview.npz')
        head=np.array([t['component']=='helmet-head' for t in l['triangles']])
        faces=p['triangles'][np.all(head[p['sources'][p['triangles']]//3],axis=1)]
        xyz=np.rint(p['positions'][faces]*512).astype(int)
        key=lambda v:tuple(sorted(tuple(q) for q in v))
        assert len(faces)==216
        assert Counter(key(v) for v in xyz)==Counter(key(v*[1,1,-1]) for v in xyz)
        colored=lambda v,c,m:tuple(sorted((*q,*rgb,int(mask)) for q,rgb,mask in zip(v,c,m)))
        colors=p['colors'][faces];masks=p['mask'][faces]
        assert Counter(colored(v,c,m) for v,c,m in zip(xyz,colors,masks))==Counter(colored(v*[1,1,-1],c,m) for v,c,m in zip(xyz,colors,masks))
        stripe=faces[np.all(p['mask'][faces]==255,axis=1)]
        assert len(stripe)==42,'Production palette lost the original crown stripe'
        reports.append(dict(lod=lod,head_triangles=len(faces),stripe_triangles=len(stripe),quantized_geometry_symmetric=True,packed_colors_symmetric=True))
    return reports

def run(folder,parent,output,packed=None):
    data=json.loads((folder/'solid.json').read_text());old=json.loads((parent/'solid.json').read_text())
    result=check_helmet(data,old)
    if packed:result['packed']=check_packed(data,packed)
    output.write_text(json.dumps(result,indent=2)+'\n');print('PASS: symmetric near/far head, continuous centered stripe, accepted body retained',result)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('folder',type=Path);p.add_argument('parent',type=Path);p.add_argument('output',type=Path);p.add_argument('--packed',type=Path);a=p.parse_args();run(a.folder,a.parent,a.output,a.packed)
