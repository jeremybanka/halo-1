"""Export an opt-in PVS sidecar bound to the unchanged accepted map bank.

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
from asset_ids import map_ids
from chiron_provenance import instrument

SIDEWINDER_PIXEL_GUARDS = {
    'map_sha256':'200a3e01cd0c29a4f3f6f2ab71a1737c81342d2d3950bf763e3e9417606f7948',
    'chunks':[7,21,59,60,117,118,119,120,121,122],
}


def export(out, name="putput", pixel_guards=None):
    from reclaimer.meta.wrappers.halo1_map import Halo1Map
    out = out.resolve();out.mkdir(parents=True, exist_ok=True)
    original=ROOT/'port/n64/pack_maps.py'
    annotated=instrument(original.read_text())
    (out/'provenance_exporter.py').write_text(annotated)
    namespace={'__file__':str(original),'__name__':'chiron_provenance_exporter'}
    exec(compile(annotated,str(out/'provenance_exporter.py'),'exec'),namespace)
    accepted = ROOT / 'halo64-assets/generated/maps'
    for config in ('spawn-clearance.json', 'scenery-reduced.json'):
        if (accepted/config).exists():shutil.copyfile(accepted/config, out/config)
    report=json.loads((accepted/'maps-report.json').read_text())['maps']
    bg=(accepted/'bloodgulch.map64').read_bytes()
    offset,count,stride=report['bloodgulch']['sections'][20]
    sources=[]
    namespace['arena'](out,bg[offset:offset+count*stride],name,
          tuple(json.loads((accepted/'map-bins.json').read_text()).get(name,(8,8,4))),sources)
    bank=(accepted/(name+'.map64')).read_bytes()
    assert (out/(name+'.map64')).read_bytes()==bank, 'Provenance export changed accepted map bank'
    path=ROOT/'build/n64-map-survey'/(name+'-decompressed.map')
    with (out/'pvs-extract.log').open('w') as log, contextlib.redirect_stdout(log):
        halo=Halo1Map();halo.load_map(path)
        bsp=halo.get_meta(next(i for i,e in enumerate(halo.tag_index.tag_index)
                              if e.class_1.enum_name=='scenario_structure_bsp'))
    leaves=list(struct.iter_unpack('<6BHhhi',bytes(bsp.leaves.STEPTREE)))
    refs=list(struct.iter_unpack('<ii',bytes(bsp.leaf_surfaces.STEPTREE)))
    triangles=len(bytes(bsp.surface.STEPTREE))//6
    clusters=len(bsp.clusters.STEPTREE);assert 0<clusters<=64
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
    chunk_offset,chunk_count,chunk_stride=report[name]['sections'][1]
    flag_offset,flag_count,flag_stride=report[name]['sections'][6]
    material_flags=bank[flag_offset:flag_offset+flag_count*flag_stride]
    nonopaque=[]
    for chunk,ids in enumerate(sources):
        mask=0;uncertain=False
        material=struct.unpack_from('>H',bank,chunk_offset+chunk*chunk_stride+6)[0]
        # N64 overlay/cutout/two-sided treatment differs from the original
        # renderer's occlusion assumptions. Retain these batches explicitly.
        if material_flags[material]:uncertain=True;nonopaque.append(chunk)
        for i in ids:
            if i<0 or not memberships[i]:uncertain=True
            else:mask|=memberships[i]
            if i>=0:covered.add(i)
        masks.append(all_mask if uncertain else mask)
        if uncertain:unknown.append(chunk)
    assert covered==set(range(triangles)), 'Original surface provenance omitted'
    assert len(masks)==report[name]['chunks']
    guarded=[]
    if pixel_guards or name=='sidewinder':
        guards=json.loads(Path(pixel_guards).read_text()) if pixel_guards else SIDEWINDER_PIXEL_GUARDS
        assert guards['map_sha256']==hashlib.sha256(bank).hexdigest(),'Pixel guard/map identity mismatch'
        guarded=guards['chunks']
        for chunk in guarded:
            assert isinstance(chunk,int) and 0<=chunk<len(masks)
            masks[chunk]=all_mask
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
    # Deterministic interior points exercise rare clusters that uniform random
    # sampling can miss on large maps. Render-face centers are only probe seeds;
    # the original collision BSP must classify each offset into the claimed leaf.
    def point_cluster(p):
        i=0
        for _ in range(len(nodes)+1):
            if i<0:return -1 if i==-1 else leaf_clusters[i&0x7fffffff]
            plane,back,front=nodes[i];q=planes[plane]
            i=front if sum(q[a]*p[a] for a in range(3))-q[3]>=0 else back
        raise ValueError('Cyclic source BSP')
    probes=[None]*clusters
    faces=list(struct.iter_unpack('<3H',bytes(bsp.surface.STEPTREE)))
    for light in bsp.lightmaps.STEPTREE:
        for material in light.materials.STEPTREE:
            raw=bytes(material.compressed_vertices.STEPTREE)
            positions=[struct.unpack_from('<3f',raw,i*32) for i in range(material.vertices_count)]
            for at,face in enumerate(faces[material.surfaces:material.surfaces+material.surface_count],material.surfaces):
                if all(probes[i] is not None for i in range(clusters) if memberships[at]>>i&1):continue
                v=[positions[i] for i in face];center=[sum(p[a] for p in v)/3 for a in range(3)]
                ab=[v[1][a]-v[0][a] for a in range(3)];ac=[v[2][a]-v[0][a] for a in range(3)]
                normal=[ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0]]
                length=math.sqrt(sum(x*x for x in normal))
                if length<1e-12:continue
                for offset in (.01,-.01,.05,-.05,.2,-.2,.5,-.5,1.,-1.,2.,-2.):
                    p=[center[a]+normal[a]*offset/length for a in range(3)];cluster=point_cluster(p)
                    if cluster>=0 and probes[cluster] is None:probes[cluster]=p
    assert all(p is not None for p in probes),'No verified interior probe for source cluster'
    result=dict(schema=2,map_name=name,map_id=map_ids()[name],map_sha256=hashlib.sha256(bank).hexdigest(),
                source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                exporter_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
                annotated_exporter_sha256=hashlib.sha256(annotated.encode()).hexdigest(),
                clusters=clusters,rows=rows,chunk_masks=masks,chunk_source_ids=sources,
                cluster_probes=probes,
                fail_open_chunks=unknown,nodes=nodes,planes=planes,leaf_clusters=leaf_clusters,
                nonopaque_fail_open_chunks=nonopaque,
                pixel_fail_open_chunks=guarded,
                bsp_depth=depth,static_bytes=len(nodes)*12+len(planes)*16+len(leaves)*2+len(masks)*8+clusters*8,
                normal_limit=max(math.sqrt(sum(v*v for v in p[:3])) for p in planes)*1.0001,
                source_reference='source/structures/structure_visibility.c:structure_visibility_find_camera; source/structures/structure_bsp_definitions.c:structure_bsp_get_cluster_pvs')
    (out/'visibility.json').write_text(json.dumps(result,separators=(',',':'))+'\n')
    print(json.dumps({k:result[k] for k in ('clusters','fail_open_chunks','bsp_depth','static_bytes','map_sha256')}))
    return result


def emit_c(data, destination):
    assert data['schema'] in (1,2) and 0<data['clusters']<=64
    name=data.get('map_name',next(name for name,id in map_ids().items() if id==data['map_id']))
    bank=ROOT/'halo64-assets/generated/maps'/(name+'.map64')
    payload=bank.read_bytes()
    assert hashlib.sha256(payload).hexdigest()==data['map_sha256'],'PVS/accepted map identity mismatch'
    chunk_offset,chunk_count,chunk_stride=struct.unpack_from('>3I',payload,16+12)
    flag_offset,flag_count,flag_stride=struct.unpack_from('>3I',payload,16+12*6)
    flags=payload[flag_offset:flag_offset+flag_count*flag_stride]
    masks=list(data['chunk_masks']);assert len(masks)==chunk_count
    all_mask=(1<<data['clusters'])-1
    if name=='sidewinder':
        assert data['map_sha256']==SIDEWINDER_PIXEL_GUARDS['map_sha256'],'Sidewinder pixel guards need revalidation'
        for chunk in SIDEWINDER_PIXEL_GUARDS['chunks']:masks[chunk]=all_mask
    # Enforce the rendering fallback for legacy sidecars too, not just fresh
    # exports. An old source-PVS file cannot re-enable nonopaque rejection.
    for chunk in range(chunk_count):
        material=struct.unpack_from('>H',payload,chunk_offset+chunk*chunk_stride+6)[0]
        if flags[material]:masks[chunk]=all_mask
    def array(name,kind,rows,convert=str):
        return 'static const '+kind+' '+name+'[]={'+','.join(convert(x) for x in rows)+'};\n'
    text='#include "render_pvs.h"\n'
    text+=array('nodes','bg_pvs_node',data['nodes'],lambda r:'{'+','.join(map(str,r))+'}')
    text+=array('planes','bg_pvs_plane',data['planes'],lambda r:'{{'+','.join(float(x).hex()+'f' for x in r)+'}}')
    text+=array('leaves','int16_t',data['leaf_clusters'])
    text+=array('rows','uint64_t',data['rows'],lambda x:'UINT64_C('+str(x)+')')
    text+=array('chunks','uint64_t',masks,lambda x:'UINT64_C('+str(x)+')')
    limit=data.get('normal_limit',max(math.sqrt(sum(v*v for v in p[:3])) for p in data['planes'])*1.0001)
    text+='const bg_pvs_data bg_world_pvs={nodes,planes,leaves,rows,chunks,'+','.join(map(str,[len(data['nodes']),len(data['planes']),len(data['leaf_clusters']),data['clusters'],len(data['chunk_masks'])]))+','+float(limit).hex()+'f,'+str(data['map_id'])+'};\n'
    destination.write_text(text)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'build/n64-chiron-visibility/data')
    parser.add_argument('--map',choices=('putput','sidewinder','ratrace'),default='putput')
    parser.add_argument('--pixel-guards',type=Path,help='Hash-bound conservative batch exceptions from native pixel counterexamples')
    args=parser.parse_args();export(args.output_dir,args.map,args.pixel_guards)
