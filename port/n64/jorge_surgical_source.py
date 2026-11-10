"""Recover original normals/maps and assemble a derived full Jorge inspection source.

Reads the preserved extraction and owned Reach caches. Never overwrites originals.
"""
from pathlib import Path
import json,struct,hashlib
import numpy as np
from reach_cache import ReachCache
from extract_jorge import bitmap

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'halo64-assets/assets/jorge'
OUT=BASE/'full-cleanup'

def enhance(cache,filename):
    raw=json.loads((BASE/filename).read_text())
    tag=next(t for t in cache.by_class['mode'] if t['path']==raw['tag']);m=tag['offset']
    info,data=cache.resource(cache.u32(m+248));start=info['fixup_start']
    nv=cache.u32(start+info['fixup_size']-24)
    buffers=[(cache.u32(start+i*28),cache.u32(start+i*28+8)) for i in range(nv)]
    sections=cache.block(m+104,92);normals=[]
    for r in cache.block(m+12,16):
        p=cache.block(r+4,24)[0];first,n=cache.unpack('hh',p+4)
        for si in range(first,first+n):
            vb=cache.unpack('h',sections[si]+24)[0];count,length=buffers[vb];stride=length//count
            for i in range(count):
                bits=struct.unpack_from('>I',data,info['fixups'][vb]+i*stride+8)[0];normal=[]
                for shift,size in [(0,10),(10,11),(21,11)]:
                    v=(bits>>shift)&((1<<size)-1)
                    if v&(1<<(size-1)):v-=1<<size
                    normal.append(max(-1,v/((1<<(size-1))-1)))
                normals.append(normal)
    assert len(normals)==len(raw['vertices']);raw['normals']=normals
    for meta,p in zip(raw['material_metadata'],cache.block(m+72,44)):
        sh=cache.tag_ref(p);prop=cache.block(sh['offset']+56,172)[0]
        refs=[cache.tag_ref(v) for v in cache.block(prop+16,24)]
        normal=next((t for t in refs if t and (t['path'].endswith('_normal') or t['path'].endswith('_zbump'))),None)
        if normal:meta['normal_map']=bitmap(cache,normal,OUT/'textures')
    return raw

def main():
    OUT.mkdir(exist_ok=True)
    cache=ReachCache(ROOT/'build/jorge-inspection/cache/maps/m05.map')
    body=enhance(cache,'jorge-original.json');pack=enhance(cache,'backpack-original.json');cache.close()
    attachment=json.loads((BASE/'backpack-attachment.json').read_text());xf=np.array(attachment['matrix'])
    body['source_hashes']={name:hashlib.sha256((BASE/name).read_bytes()).hexdigest() for name in ['jorge-original.json','backpack-original.json','backpack-attachment.json']}
    body['source_vertex_origin']=[['body',i] for i in range(len(body['vertices']))]
    body['source_face_origin']=[['body',i] for i in range(len(body['faces']))]
    base=len(body['vertices']);matbase=len(body['material_metadata'])
    body['vertices'] += [(xf@np.array([*v,1]))[:3].tolist() for v in pack['vertices']]
    body['normals'] += [(xf[:3,:3]@np.array(v)).tolist() for v in pack['normals']]
    body['uv'] += pack['uv'];body['weights'] += [[[attachment['parent_node'],1.]]] * len(pack['vertices'])
    body['faces'] += [[v+base for v in f] for f in pack['faces']]
    body['materials'] += [m+matbase for m in pack['materials']];body['regions'] += ['backpack']*len(pack['faces'])
    body['material_metadata'] += pack['material_metadata'];body['backpack_attachment']=attachment
    body['source_vertex_origin'] += [['backpack',i] for i in range(len(pack['vertices']))]
    body['source_face_origin'] += [['backpack',i] for i in range(len(pack['faces']))]
    (OUT/'source-complete.json').write_text(json.dumps(body,separators=(',',':')))
    print('Full derived source:',len(body['faces']),'triangles;',len(body['vertices']),'vertices;',len(body['nodes']),'bones')

if __name__=='__main__':main()
