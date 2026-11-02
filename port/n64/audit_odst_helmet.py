"""Acceptance checks for independent symmetric ODST helmet LODs and palettes."""
import argparse,hashlib,json
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
from odst_colors import TEAM_AMOUNT,team_amount


def triangle_key(points):return tuple(sorted(map(tuple,points)))


def check_helmet(data,old):
    bone=next(i for i,n in enumerate(data['nodes']) if n['name']=='bip01 head');helmets=[];reports=[]
    def old_head(t):
        return (t['component'].startswith('helmet') or t.get('source_component','').startswith('helmet')) and all(b==bone for ws in t['weights'] for b,w in ws if w>1e-5)
    for lod,l in enumerate(data['lods']):
        helmet=[t for t in l['triangles'] if t['component']=='helmet-head'];helmets.append(helmet)
        body=[t for t in l['triangles'] if t['component']!='helmet-head' and 'helmet_junction_repair' not in t]
        seams=[t for t in l['triangles'] if 'helmet_junction_repair' in t]
        assert [t['helmet_junction_repair'] for t in seams]==[[8550,2800],[4126,4150,8550]][lod]
        assert body==[t for t in old['lods'][lod]['triangles'] if not old_head(t)],'Accepted body/neck data changed'
        points=np.array([t['p'] for t in helmet]);assert len(helmet)%2==0
        error=float(np.abs(points[::2]-points[1::2][:,[0,2,1]]*[1,-1,1]).max());assert error<1e-10
        q=np.rint(points*512).astype(int);assert np.array_equal(q[::2],q[1::2][:,[0,2,1]]*[1,-1,1])
        for a,b in zip(helmet[::2],helmet[1::2]):
            assert a['material']==b['material'] and a['helmet_region']==b['helmet_region']
            assert a['uv']==[b['uv'][i] for i in (0,2,1)]
            assert a['corner_color_override']==[b['corner_color_override'][i] for i in (0,2,1)]
            assert all(ws==[[bone,1]] for t in (a,b) for ws in t['weights'])
        stripe=[t for t in helmet if t['helmet_region']=='stripe'];assert len(stripe)>=6
        points=np.array([t['p'] for t in stripe]);assert abs(float(points[:,:,1].mean()))<1e-10
        assert np.abs(points[:,:,1]).max()<.012 and np.ptp(points[:,:,0])>.10
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
        assert components==1,'Quantized grey crown stripe is broken'
        reports.append(dict(lod=lod,head_triangles=len(helmet),native_head_vertices=len(np.unique(np.round(np.array([t['p'] for t in helmet]).reshape(-1,3),7),axis=0)),stripe_triangles=len(stripe),stripe_components=components,maximum_mirror_error_halo=error,quantized_bind_symmetric=True,colors_symmetric=True,body_sha256=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()))
    assert helmets[0]!=helmets[1] and reports[1]['head_triangles']<reports[0]['head_triangles']
    assert reports[1]['native_head_vertices']<reports[0]['native_head_vertices']
    return dict(independent_helmet_lods=True,lods=reports)


def check_packed(data,packed):
    from audit_models import engine
    from pack_odst import palette
    reports=[]
    for lod,l in enumerate(data['lods']):
        p=np.load(packed/f'odst-{lod}-preview.npz');ts=l['triangles'];head=[t for t in ts if t['component']=='helmet-head']
        keys={triangle_key(t) for t in np.rint(engine([t['p'] for t in head])*512).astype(int)}
        faces=p['triangles'][[triangle_key(t) in keys for t in np.rint(p['positions'][p['triangles']]*512).astype(int)]]
        xyz=np.rint(p['positions'][faces]*512).astype(int);assert len(faces)==len(head)
        assert Counter(triangle_key(v) for v in xyz)==Counter(triangle_key(v*[1,1,-1]) for v in xyz)
        colored=lambda v,c:tuple(sorted((*q,*rgb) for q,rgb in zip(v,c)))
        colors=p['colors'][faces]
        assert Counter(colored(v,c) for v,c in zip(xyz,colors))==Counter(colored(v*[1,1,-1],c) for v,c in zip(xyz,colors))
        ids=np.unique(faces);assert not np.any(p['mask'][ids])
        for profile in range(4):assert np.array_equal(palette(p['colors'],p['mask'],profile)[ids],p['colors'][ids])
        expected=np.array([team_amount(ts[i//3]) for i in p['sources']]);assert np.array_equal(p['mask'],expected)
        assert set(map(int,p['mask']))=={0,TEAM_AMOUNT}
        reports.append(dict(lod=lod,head_triangles=len(faces),packed_head_vertices=len(ids),quantized_geometry_symmetric=True,packed_colors_symmetric=True,helmet_palette_invariant=True,team_mask_amount=TEAM_AMOUNT,team_tint_limited_to_chest_and_shoulders=True))
    assert reports[0]['packed_head_vertices']<=85 and reports[1]['packed_head_vertices']<=70
    assert reports[1]['packed_head_vertices']<reports[0]['packed_head_vertices']
    return reports


def run(folder,parent,output,packed=None):
    data=json.loads((folder/'solid.json').read_text());old=json.loads((parent/'solid.json').read_text());result=check_helmet(data,old)
    if packed:result['packed']=check_packed(data,packed)
    output.write_text(json.dumps(result,indent=2)+'\n');print('PASS: independent reduced helmets, symmetry, grey stripe and muted plate palettes',result)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('folder',type=Path);p.add_argument('parent',type=Path);p.add_argument('output',type=Path);p.add_argument('--packed',type=Path);a=p.parse_args();run(a.folder,a.parent,a.output,a.packed)
