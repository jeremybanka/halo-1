"""Export an opt-in PVS sidecar bound to the unchanged accepted Chiron bank.

Original surface IDs follow UV subdivisions and ordered batching. Scenery and
unassigned surfaces fail open. No private payload is written outside build/.
"""
import argparse
import contextlib
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
from pack_maps import ROOT
from chiron_provenance import instrument


def export(out):
    from reclaimer.meta.wrappers.halo1_map import Halo1Map
    out = out.resolve();out.mkdir(parents=True, exist_ok=True)
    original=ROOT/'port/n64/pack_maps.py'
    annotated=instrument(original.read_text())
    (out/'provenance_exporter.py').write_text(annotated)
    namespace={'__file__':str(original),'__name__':'chiron_provenance_exporter'}
    exec(compile(annotated,str(out/'provenance_exporter.py'),'exec'),namespace)
    accepted = ROOT / 'halo64-assets/generated/maps'
    for name in ('spawn-clearance.json', 'scenery-reduced.json'):
        if (accepted/name).exists():shutil.copyfile(accepted/name, out/name)
    report=json.loads((accepted/'maps-report.json').read_text())['maps']
    bg=(accepted/'bloodgulch.map64').read_bytes()
    offset,count,stride=report['bloodgulch']['sections'][20]
    sources=[]
    namespace['arena'](out,bg[offset:offset+count*stride],'putput',
          tuple(json.loads((accepted/'map-bins.json').read_text())['putput']),sources)
    bank=(accepted/'putput.map64').read_bytes()
    assert (out/'putput.map64').read_bytes()==bank, 'Provenance export changed accepted Chiron bank'
    path=ROOT/'build/n64-map-survey/putput-decompressed.map'
    with (out/'pvs-extract.log').open('w') as log, contextlib.redirect_stdout(log):
        halo=Halo1Map();halo.load_map(path)
        bsp=halo.get_meta(next(i for i,e in enumerate(halo.tag_index.tag_index)
                              if e.class_1.enum_name=='scenario_structure_bsp'))
    leaves=list(struct.iter_unpack('<6BHhhi',bytes(bsp.leaves.STEPTREE)))
    refs=list(struct.iter_unpack('<ii',bytes(bsp.leaf_surfaces.STEPTREE)))
    triangles=len(bytes(bsp.surface.STEPTREE))//6
    clusters=len(bsp.clusters.STEPTREE);assert 0<clusters<=16
    memberships=[0]*triangles
    for leaf in leaves:
        cluster,length,first=leaf[-3:]
        if cluster<0:continue
        assert cluster<clusters and 0<=first<=len(refs)-length
        for surface,_ in refs[first:first+length]:
            assert 0<=surface<triangles
            memberships[surface]|=1<<cluster
    all_mask=(1<<clusters)-1
    masks=[];unknown=[];covered=set()
    for chunk,ids in enumerate(sources):
        mask=0;uncertain=False
        for i in ids:
            if i<0 or not memberships[i]:uncertain=True
            else:mask|=memberships[i]
            if i>=0:covered.add(i)
        masks.append(all_mask if uncertain else mask)
        if uncertain:unknown.append(chunk)
    assert covered==set(range(triangles)), 'Original surface provenance omitted'
    assert len(masks)==report['putput']['chunks']
    raw=bytes(bsp.cluster_data.STEPTREE);stride=((clusters+31)//32)*4
    assert len(raw)==stride*clusters
    rows=[int.from_bytes(raw[i*stride:(i+1)*stride],'little')&all_mask for i in range(clusters)]
    assert all(row&(1<<i) for i,row in enumerate(rows))
    collision=bsp.collision_bsp.STEPTREE[0]
    nodes=list(struct.iter_unpack('<3i',bytes(collision.bsp3d_nodes.STEPTREE)))
    planes=list(struct.iter_unpack('<4f',bytes(collision.planes.STEPTREE)))
    leaf_clusters=[leaf[-3] for leaf in leaves]
    # structure_visibility_find_camera uses these collision BSP nodes to index
    # the render leaves. Keep exact plane values and source child designators.
    for plane,back,front in nodes:
        assert 0<=plane<len(planes)
        for child in (back,front):
            assert child==-1 or (child>=0 and child<len(nodes)) or (child<0 and (child&0x7fffffff)<len(leaves))
    reachable=set();active=set()
    def visit(i):
        if i<0:return 0
        assert i not in active,'Cyclic source BSP'
        if i in reachable:return 0
        active.add(i);depth=1+max(visit(nodes[i][1]),visit(nodes[i][2]));active.remove(i);reachable.add(i);return depth
    depth=visit(0);assert depth<128
    result=dict(schema=1,map_id=11,map_sha256=hashlib.sha256(bank).hexdigest(),
                source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                exporter_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
                annotated_exporter_sha256=hashlib.sha256(annotated.encode()).hexdigest(),
                clusters=clusters,rows=rows,chunk_masks=masks,chunk_source_ids=sources,
                fail_open_chunks=unknown,nodes=nodes,planes=planes,leaf_clusters=leaf_clusters,
                bsp_depth=depth,static_bytes=len(nodes)*12+len(planes)*16+len(leaves)*2+len(masks)*2+clusters*2,
                normal_limit=max(math.sqrt(sum(v*v for v in p[:3])) for p in planes)*1.0001,
                source_reference='source/structures/structure_visibility.c:structure_visibility_find_camera; source/structures/structure_bsp_definitions.c:structure_bsp_get_cluster_pvs')
    (out/'visibility.json').write_text(json.dumps(result,separators=(',',':'))+'\n')
    print(json.dumps({k:result[k] for k in ('clusters','fail_open_chunks','bsp_depth','static_bytes','map_sha256')}))
    return result


def emit_c(data, destination):
    assert data['schema']==1 and data['map_id']==11 and 0<data['clusters']<=16
    bank=ROOT/'halo64-assets/generated/maps/putput.map64'
    assert hashlib.sha256(bank.read_bytes()).hexdigest()==data['map_sha256'],'PVS/accepted map identity mismatch'
    def array(name,kind,rows,convert=str):
        return 'static const '+kind+' '+name+'[]={'+','.join(convert(x) for x in rows)+'};\n'
    text='#include "render_pvs.h"\n'
    text+=array('nodes','bg_pvs_node',data['nodes'],lambda r:'{'+','.join(map(str,r))+'}')
    text+=array('planes','bg_pvs_plane',data['planes'],lambda r:'{{'+','.join(float(x).hex()+'f' for x in r)+'}}')
    text+=array('leaves','int16_t',data['leaf_clusters'])
    text+=array('rows','uint16_t',data['rows'])
    text+=array('chunks','uint16_t',data['chunk_masks'])
    limit=data.get('normal_limit',max(math.sqrt(sum(v*v for v in p[:3])) for p in data['planes'])*1.0001)
    text+='const bg_pvs_data bg_chiron_pvs={nodes,planes,leaves,rows,chunks,'+','.join(map(str,[len(data['nodes']),len(data['planes']),len(data['leaf_clusters']),data['clusters'],len(data['chunk_masks'])]))+','+float(limit).hex()+'f};\n'
    destination.write_text(text)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'build/n64-chiron-visibility/data')
    export(parser.parse_args().output_dir)
