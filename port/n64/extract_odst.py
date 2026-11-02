#!/usr/bin/env python3
"""Extract the helmeted standard ODST and rebind it to the existing CE rig.

Requires locally supplied retail Xbox 360 c100.map and its shared caches,
plus the existing CE extended-raw.json. Writes only derived private assets.
"""
import argparse
import hashlib
import json
import struct
from collections import defaultdict
from pathlib import Path

import numpy as np

from halo3_cache import OdstCache


def decode_uv(u,v,bounds):
    """Gen-3 D3D texture coordinates already use the image's top-left origin."""
    return [bounds[0]+u/65535*(bounds[1]-bounds[0]),
            bounds[2]+v/65535*(bounds[3]-bounds[2])]


def shader_metadata(cache,shader):
    """Retain named source shader constants, including glass reflection tints."""
    properties=cache.block(shader['offset']+40,132)
    if not properties:return {}
    prop=properties[0];template=cache.tag_ref(prop)
    if template is None:return {}
    names=[cache.sid(cache.u32(p)) for p in cache.block(template['offset']+72,4)]
    values=[list(cache.unpack('4f',p)) for p in cache.block(prop+28,16)]
    if len(names)!=len(values):raise ValueError('Shader argument and constant counts differ')
    return {'shader_template':template['path'],'shader_constants':dict(zip(names,values))}


def globals_for(nodes, conjugate=True):
    result = []
    for node in nodes:
        x, y, z, w = node['q']
        if conjugate:
            x, y, z = -x, -y, -z
        norm = (x*x + y*y + z*z + w*w)**.5
        x, y, z, w = (v/norm for v in (x,y,z,w))
        matrix = np.eye(4)
        matrix[:3,:3] = [[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                         [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                         [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]]
        matrix[:3,3] = node['p']
        parent = node['parent']
        result.append(result[parent] @ matrix if parent >= 0 else matrix)
    return result


def bitmap(cache, tag, output):
    from arbytmap import Arbytmap, bitmap_io, FORMAT_DXT1, FORMAT_DXT3, FORMAT_DXT5, FORMAT_DXT5AY, TYPE_2D
    from reclaimer.h3.util import get_virtual_dimension
    output.mkdir(parents=True, exist_ok=True)
    target = output / (tag['path'].replace('\\','/').split('/')[-1] + '.png')
    bitmaps = cache.block(tag['offset'] + 96, 48)
    if len(bitmaps) != 1:
        raise ValueError('Expected a single 2D bitmap')
    b = bitmaps[0]
    width, height, depth, flags, typ, fmt = cache.unpack('HHBBhh', b+4)
    if typ != 0 or depth != 1:
        raise ValueError('Only 2D ODST diffuse/mask bitmaps are supported')
    formats = {14: FORMAT_DXT1, 15: FORMAT_DXT3, 16: FORMAT_DXT5, 39: FORMAT_DXT5AY}
    if fmt not in formats:
        raise ValueError(f'Unsupported ODST bitmap format: {fmt}')
    refs = cache.block(tag['offset'] + 140, 8)
    if len(refs) != 1 or cache.block(tag['offset'] + 152, 8):
        raise ValueError('Unexpected interleaved bitmap resource')
    _, data = cache.resource(cache.u32(refs[0]))
    size = width * height // 2 if fmt == 14 else width * height
    if len(data) < size:
        raise ValueError('Truncated highest-mip bitmap')
    texture = []
    bitmap_io.bitmap_bytes_to_array(data, 0, texture, formats[fmt], 1, 1, 1, size)
    arby = Arbytmap()
    arby.load_new_texture(texture_block=texture, texture_info=dict(
        width=width, height=height, depth=1, mipmap_count=0,
        swizzled=False, big_endian=True, packed=True, tiled=bool(flags & 8),
        tile_method='DXGI', packed_width_calc=get_virtual_dimension,
        packed_height_calc=get_virtual_dimension, texture_type=TYPE_2D,
        sub_bitmap_count=1, format=formats[fmt], filepath=str(target)),
        tile_mode=False, swizzle_mode=False)
    arby.save_to_file(keep_alpha=True)
    if not target.exists():
        raise ValueError('Bitmap decode failed')
    return str(target.resolve())


def extract(cache_path, ce_path, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    ce = json.loads(Path(ce_path).read_text())
    ce_model = ce['models']['spartan']
    cache = OdstCache(cache_path)
    try:
        tag = next(t for t in cache.by_class['mode']
                   if t['path'].replace('\\','/').endswith('characters/odst/odst'))
        m = tag['offset']
        nodes = [{'name': cache.sid(cache.u32(n)),
                  'parent': cache.unpack('h', n+4)[0],
                  'p': list(cache.unpack('3f', n+12)),
                  'q': list(cache.unpack('4f', n+24))}
                 for n in cache.block(m+48,96)]
        source_globals = globals_for(nodes, conjugate=False)
        # Check the quaternion convention against the authored inverse bind.
        for n, matrix in zip(cache.block(m+48,96), source_globals):
            stored = np.eye(4)
            stored[:3,:] = np.array(cache.unpack('12f',n+44)).reshape(4,3).T
            if not np.allclose(np.linalg.inv(matrix), stored, atol=2e-5):
                raise ValueError('ODST inverse-bind convention mismatch')
        targets = {n['name'].removeprefix('bip01 ').replace(' ','_'): i
                   for i,n in enumerate(ce_model['nodes'])}
        aliases = {'l_upperarm':'l_upperarm','r_upperarm':'r_upperarm'}
        mapping = []
        for i,node in enumerate(nodes):
            anchor = i
            while aliases.get(nodes[anchor]['name'],nodes[anchor]['name']) not in targets:
                anchor = nodes[anchor]['parent']
                if anchor < 0:
                    raise ValueError('ODST node cannot be mapped: '+node['name'])
            target = targets[aliases.get(nodes[anchor]['name'],nodes[anchor]['name'])]
            mapping.append((anchor,target))
        ce_globals = globals_for(ce_model['nodes'])
        correction = [ce_globals[t] @ np.linalg.inv(source_globals[a]) for a,t in mapping]
        info, resource = cache.resource(cache.u32(m+224))
        start = info['fixup_start']
        vertex_count = cache.u32(start + info['fixup_size'] - 24)
        index_count = cache.u32(start + info['fixup_size'] - 12)
        vertex_info = [(cache.u32(start+i*28),cache.u32(start+i*28+8)) for i in range(vertex_count)]
        index_info = [cache.unpack('II',start+vertex_count*40+i*24) for i in range(index_count)]
        bounds = cache.unpack('10f', cache.block(m+116,44)[0]+4)
        selection = {'body':'standard','chest':'standard','gear':'standard',
                     'hands':'standard','helmet':'standard','knife':'on',
                     'l_shoulder':'standard','r_shoulder':'standard'}
        sections = cache.block(m+104,76)
        node_maps = cache.block(m+176,12)
        chosen = []
        for region in cache.block(m+12,16):
            name = cache.sid(cache.u32(region))
            if name not in selection:
                continue
            permutation = next(p for p in cache.block(region+4,24)
                               if cache.sid(cache.u32(p)) == selection[name])
            first,count = cache.unpack('hh',permutation+4)
            chosen.extend((name,i) for i in range(first,first+count))
        if {r for r,_ in chosen} != selection.keys():
            raise ValueError('Missing standard ODST regions')
        model = {'name':'standard helmeted ODST', 'path':tag['path'],
                 'source_cache':Path(cache_path).name, 'source_lod':'retail highest-detail standard permutation',
                 'vertices':[], 'uv':[], 'weights':[], 'skin_weights':[], 'faces':[], 'materials':[], 'regions':[],
                 'nodes':ce_model['nodes'], 'markers':ce_model['markers'], 'uv_origin':'top-left',
                 'uv_source_convention':'Halo 3 native top-left'}
        original = {**model, 'vertices':[], 'weights':[], 'skin_weights':[], 'nodes':nodes}
        for region, section_index in chosen:
            s = sections[section_index]
            vb, ib = cache.unpack('h',s+24)[0],cache.unpack('h',s+40)[0]
            rigid,fmt = cache.unpack('BB',s+45)
            if fmt not in (1,2):
                raise ValueError('Unsupported ODST vertex format')
            count,length = vertex_info[vb]
            stride = length//count
            if stride != (24 if fmt==1 else 32):
                raise ValueError('Unexpected ODST vertex stride')
            offset = info['fixups'][vb]
            index_format,index_length = index_info[ib]
            index_offset = info['fixups'][vertex_count*2+ib]
            indices = struct.unpack_from('>'+str(index_length//2)+'H',resource,index_offset)
            local_map = [cache.data[p] for p in cache.block(node_maps[section_index],1)] if node_maps else None
            base = len(model['vertices'])
            for i in range(count):
                at = offset+i*stride
                packed = struct.unpack_from('>6H',resource,at)
                position = np.array([bounds[a*2]+packed[a]/65535*(bounds[a*2+1]-bounds[a*2]) for a in range(3)]+[1.])
                uv = decode_uv(packed[4],packed[5],bounds[6:10])
                if fmt==1:
                    influences = [(rigid,1.)]
                else:
                    bones = resource[at+24:at+28]
                    weights = resource[at+28:at+32]
                    total = sum(weights)
                    if not total:
                        raise ValueError('Unweighted ODST vertex')
                    influences = [(local_map[b] if local_map else b,w/total) for b,w in zip(bones,weights) if w]
                if any(b>=len(nodes) for b,w in influences):
                    raise ValueError('Invalid ODST bone index')
                placed = sum((correction[b]@position)*w for b,w in influences)
                combined = defaultdict(float)
                for b,w in influences:
                    combined[mapping[b][1]] += w
                strongest = sorted(combined.items(),key=lambda p:p[1],reverse=True)[:2]
                kept = sum(w for b,w in strongest)
                model['vertices'].append(placed[:3].tolist())
                model['uv'].append(uv)
                model['weights'].append([strongest[0][0],strongest[1][0] if len(strongest)>1 else -1,
                                         strongest[1][1]/kept if len(strongest)>1 else 0.])
                model['skin_weights'].append(sorted(combined.items()))
                original['vertices'].append(position[:3].tolist())
                original['weights'].append(influences)
                original['skin_weights'].append(influences)
            for part in cache.block(s,16):
                material = cache.unpack('h',part)[0]
                first,length = cache.unpack('HH',part+4)
                strip = indices[first:first+length]
                if index_format != 5:
                    raise ValueError('Expected ODST triangle strip')
                for i in range(len(strip)-2):
                    a,b,c = strip[i:i+3]
                    if i&1:
                        a,b = b,a
                    if len({a,b,c})<3:
                        continue
                    if max(a,b,c)>=count:
                        raise ValueError('ODST triangle references invalid vertex')
                    model['faces'].append([base+a,base+b,base+c])
                    model['materials'].append(material)
                    model['regions'].append(region)
        shaders = [cache.tag_ref(s) for s in cache.block(m+72,36)]
        textures, masks, metadata, overrides = [],[],[],[]
        used = set(model['materials'])
        for i,shader in enumerate(shaders):
            diffuse = mask = None
            if i in used:
                prop = cache.block(shader['offset']+40,132)[0]
                refs = [cache.tag_ref(p) for p in cache.block(prop+16,24)]
                diffuse = bitmap(cache,refs[0],output/'textures')
                cc = next((t for t in refs if t and t['path'].endswith('_cc')),None)
                if cc:
                    mask = bitmap(cache,cc,output/'textures')
            textures.append(diffuse);masks.append(mask)
            metadata.append({'path':shader['path'],'class':shader['class'],
                             **(shader_metadata(cache,shader) if i in used else {})})
            overrides.append(None)
        model.update(textures=textures,textures_fullres=textures,team_masks=masks,
                     team_mask_channels=[0 if p else None for p in masks],
                     material_metadata=metadata,material_overrides=overrides)
        original.update({k:v for k,v in model.items() if k not in ('vertices','weights','skin_weights','nodes')})
        # The native reference must not inherit CE marker indices into its
        # different 55-node skeleton. Gameplay sockets belong to the CE adapter.
        original.pop('markers',None)
        retarget = {'source_build':cache.build,'source_tag':tag['path'],
                    'uv_source_convention':'Halo 3 native top-left',
                    'source_node_count':len(nodes),'target_node_count':len(ce_model['nodes']),
                    'source_influences_preserved':True,
                    'regions':selection,
                    'bone_map':[{'source':nodes[i]['name'],'anchor':nodes[a]['name'],
                                 'target':ce_model['nodes'][t]['name']} for i,(a,t) in enumerate(mapping)]}
        raw = {'models':{'spartan':model},'animations':ce['animations'],
               'audio':{},'hud':{},'sources':{**ce['sources'],
                   'odst_c100':hashlib.file_digest(Path(cache_path).open('rb'),'sha256').hexdigest()},
               'retarget':retarget}
        (output/'odst-ce-raw.json').write_text(json.dumps(raw))
        (output/'odst-original.json').write_text(json.dumps(original))
        (output/'retarget-report.json').write_text(json.dumps(retarget,indent=2)+'\n')
        print(json.dumps({'triangles':len(model['faces']),'vertices':len(model['vertices']),**retarget},indent=2))
    finally:
        cache.close()


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache',type=Path,required=True)
    parser.add_argument('--ce',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    extract(args.cache,args.ce,args.output)
