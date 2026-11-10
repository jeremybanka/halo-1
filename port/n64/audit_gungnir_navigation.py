"""Independently decode GNV3 and bind its 13 maps to gameplay evidence."""
import argparse,hashlib,json,re,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def run(bank,gameplay,output):
    output.mkdir(parents=True,exist_ok=True);text=gameplay.read_text();assert 'PASS: GUNGNIR gameplay and all-map movement autopilot' in text
    coverage={int(m[0]):dict(covered=int(m[1]),starts=int(m[2]),runtime_allocation_bytes=int(m[3])) for m in re.findall(r'PASS map(\d+): (\d+)/(\d+) starts have nearby graph nodes; follow walked certified route, navigation RAM (\d+)',text)}
    assert set(coverage)==set(range(13))
    from asset_ids import map_ids
    ids={v:k for k,v in map_ids().items()};rows=[]
    for i in range(13):
        path=bank/f'autonav-{i}.bin';raw=path.read_bytes();magic,nx,nz,layers,reserved,step,ox,oz,oy,nodes,pad=struct.unpack_from('>4s4H4f2H',raw)
        assert magic==b'GNV3' and 1<=layers<=6 and 2<=nx<=104 and 2<=nz<=104 and not reserved and not pad
        count=nx*nz*layers;grid=[];offset=32;live=walk=jump=0
        while len(grid)<count:
            code=struct.unpack_from('>H',raw,offset)[0];offset+=2;length=code&32767;assert length and len(grid)+length<=count
            if code&32768:grid.extend([None]*length)
            else:
                for j in range(length):
                    height,edges,jumps=struct.unpack_from('>hBB',raw,offset);offset+=4;assert edges and height!=-32768 and not jumps&~edges
                    grid.append((height,edges,jumps));live+=1;walk+=(edges&~jumps).bit_count();jump+=jumps.bit_count()
        assert offset==len(raw) and live==nodes
        report=coverage[i];assert report['covered']==report['starts']>0 and report['runtime_allocation_bytes']==16*live+2*count
        map_path=ROOT/'halo64-assets/generated/maps'/f'{ids[i]}.map64'
        rows.append(dict(map=i,name=ids[i],sha256=sha(path),map_sha256=sha(map_path),bytes=len(raw),grid=[nx,nz,layers],step=step,origin=[ox,oy,oz],live_nodes=live,walk_edges=walk,jump_drop_edges=jump,**report))
    inputs=[ROOT/'port/n64'/name for name in ('bake_autopilot_nav.c','autopilot_nav.c','gungnir_movement.c','autopilot_strategy.c','prepare_gungnir_strategy.py','game.c','map.c','terrain.c','movement.c','test_gungnir.c')]
    result=dict(schema=1,format='GNV3',maps=rows,inputs={str(p.relative_to(ROOT)):sha(p) for p in inputs},gameplay_log_sha256=sha(gameplay),maximum_runtime_allocation_bytes=max(r['runtime_allocation_bytes'] for r in rows),per_tick_expansion_limit=256,scope='Production floor/capsule bake and one simulated reachable follow route per map; full Slayer start proximity; directed original portals loaded from the selected map. No claim that every spawn pair or jump edge was simulated.')
    (output/'navigation-validation.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS: independent GNV3 decode, 13 production-map hashes and all eligible Slayer starts, maximum RAM',result['maximum_runtime_allocation_bytes'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('bank',type=Path);p.add_argument('gameplay',type=Path);p.add_argument('output',type=Path);a=p.parse_args();run(a.bank,a.gameplay,a.output)
