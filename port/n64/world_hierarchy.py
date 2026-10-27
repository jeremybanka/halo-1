"""Bake a conservative spatial hierarchy without modifying a map byte."""
import hashlib, json, struct
from pathlib import Path

NONE=65535
LEAF=0x8000
LOD=0x4000

def bake(sidecar, bank, destination):
    sidecar=Path(sidecar);bank=Path(bank);destination=Path(destination)
    meta=json.loads(sidecar.read_text());raw=bank.read_bytes()
    digest=hashlib.sha256(raw).hexdigest()
    assert digest==meta['map_sha256']
    offset,count,stride=struct.unpack_from('>III',raw,16+12)
    assert stride==24
    chunks=list(struct.iter_unpack('>IHH6hHH',raw[offset:offset+count*stride]))
    assert len(chunks)==len(meta['lod_chunks'])<16384
    assert len(meta['lod_groups'])<=128
    assert all(0<=c<=2*len(meta['lod_groups']) for c in meta['lod_chunks'])
    def union(items):
        return [min(n['bounds'][a] for n in items) for a in range(3)]+[max(n['bounds'][a+3] for n in items) for a in range(3)]
    def spatial(items):
        if not items:return None
        if len(items)==1:return items[0]
        # Median split along the widest centroid axis, with stable tie breaks.
        axis=max(range(3),key=lambda a:max(n['bounds'][a]+n['bounds'][a+3] for n in items)-min(n['bounds'][a]+n['bounds'][a+3] for n in items))
        items=sorted(items,key=lambda n:(n['bounds'][axis]+n['bounds'][axis+3],n['order']))
        mid=len(items)//2
        return dict(bounds=union(items),children=[spatial(items[:mid]),spatial(items[mid:])],code=0,order=min(n['order'] for n in items))
    units=[];groups={}
    for b,c in enumerate(chunks):
        item=dict(bounds=list(c[3:9]),children=[],code=LEAF|b,order=b)
        code=meta['lod_chunks'][b]
        if not code:units.append(item)
        else:groups.setdefault((code-1)//2,[[],[]])[(code-1)%2].append(item)
    for g,levels in sorted(groups.items()):
        all_items=levels[0]+levels[1]
        units.append(dict(bounds=union(all_items),children=[spatial(levels[0]),spatial(levels[1])],code=LOD|g,order=min(n['order'] for n in all_items)))
    tree=spatial(units);nodes=[];max_depth=0
    def flatten(n,depth=1):
        nonlocal max_depth
        if n is None:return NONE
        index=len(nodes);nodes.append(None);max_depth=max(max_depth,depth)
        children=[flatten(c,depth+1) for c in n['children']]
        nodes[index]=dict(bounds=n['bounds'],first=children[0] if children else NONE,second=children[1] if children else NONE,code=n['code'])
        return index
    assert flatten(tree)==0 and max_depth<64 and len(nodes)<NONE
    seen=[]
    for i,n in enumerate(nodes):
        if n['code']&LEAF:
            b=n['code']&0x3fff;seen.append(b);assert n['bounds']==list(chunks[b][3:9])
        for child in (n['first'],n['second']):
            if child!=NONE:
                assert child>i
                c=nodes[child]
                assert all(n['bounds'][a]<=c['bounds'][a]<=c['bounds'][a+3]<=n['bounds'][a+3] for a in range(3))
    assert sorted(seen)==list(range(len(chunks)))
    lines=['#include "render_world_hierarchy.h"','static const bg_hierarchy_node hierarchy_nodes[]={']
    lines += ['{{'+','.join(map(str,n['bounds']))+'},'+f'{n["first"]},{n["second"]},{n["code"]}'+'},' for n in nodes]
    lines += ['};',f'const bg_hierarchy_data bg_world_hierarchy={{hierarchy_nodes,{len(nodes)},{len(chunks)},{len(meta["lod_groups"])},{meta["map_id"]},{max_depth}}};']
    destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text('\n'.join(lines)+'\n')
    result=dict(map_sha256=digest,sidecar_sha256=hashlib.sha256(sidecar.read_bytes()).hexdigest(),nodes=len(nodes),chunks=len(chunks),used_lod_groups=len(groups),groups=len(meta['lod_groups']),depth=max_depth,node_bytes=len(nodes)*18,source_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),header_sha256=hashlib.sha256(Path(__file__).with_name('render_world_hierarchy.h').read_bytes()).hexdigest(),every_chunk_once=True,parent_enclosure=True,geometry_unchanged=True)
    destination.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    import sys
    print(json.dumps(bake(*sys.argv[1:]),indent=2))
