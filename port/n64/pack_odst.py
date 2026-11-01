"""Pack the fresh ODST candidate into a bounded, optional ROM-streamed bank."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import numpy as np
from PIL import Image
from pack_assets import position, normal
from pack_mesh import indexed_mesh

SCALE = 512
COLORS = np.array(((225,45,38),(39,92,215),(215,179,44),(57,183,69)))


def palette(rgb, mask, profile):
    rgb = np.array(rgb, dtype=int)
    mask = np.array(mask, dtype=int)[:,None]
    return (rgb * (65025 - mask * (255-COLORS[profile])) + 32512) // 65025


def corner_colors(tri, materials, textures):
    role = materials[tri['material']]['path'].split('\\')[-1]
    if role == 'odst_crown_stripe':
        return [[235,235,235]]*3, [255]*3
    if role == 'odst_visor':
        # Intentional cyan adaptation, protected from all profile/team tints.
        return [[24,230,255]]*3, [0]*3
    image = textures.get(tri['material'])
    light = .68 + .32 * max(0, np.dot(normal([position(p,(0,0,0)) for p in tri['p']]), (.25,.83,.49)))
    colors = []
    for i, uv in enumerate(tri['uv']):
        uv = np.array(uv)*.94 + np.mean(tri['uv'],axis=0)*.06
        if image is None:
            rgb = np.array((100,105,108))
        else:
            x,y = (int(uv[0]%1*image.width), int(uv[1]%1*image.height))
            rgb = np.array(image.getpixel((x,y)))
        colors.append(np.rint(rgb*light).astype(int).tolist())
    return colors, [0]*3


def pack(source, output):
    source, output = Path(source), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    data = json.loads(source.read_text())
    textures = {i:Image.open(p).convert('RGB') for i,p in enumerate(data['textures']) if p}
    bank = bytearray(); reports = []; meshes = []; previews = []
    lines = ['/* Generated from the owned Halo 3: ODST source; private assets. */', '#include "asset_odst.h"']
    for lod, model in enumerate(data['lods']):
        native = np.load(source.parent/f'poses-{lod}.npz')
        # Retain the complete authoring proof. The runtime linearly interpolates
        # seven near / four far samples per action, with original durations.
        poses, grips = [], []
        for i,c in enumerate(model['animations']):
            count = min(7 if lod==0 else 4,c['frames'])
            samples = np.rint(np.linspace(0,c['frames']-1,count)).astype(int)
            poses.append(np.rint(native['frames_'+str(i)][samples]*SCALE).astype(np.int16))
            grips.append(native['grips_'+str(i)][samples])
        count = len(poses[0][0]); signatures = []
        for v in range(count):
            signatures.append(hashlib.sha256(b''.join(f[:,v].tobytes() for f in poses)).digest())
        track_lookup = {}; track_sources = []; corner_tracks = []
        for v,key in enumerate(signatures):
            if key not in track_lookup:
                track_lookup[key] = len(track_sources); track_sources.append(v)
            corner_tracks.append(track_lookup[key])
        points = [[round(x*SCALE) for x in position(p,(0,0,0))] for t in model['triangles'] for p in t['p']]
        colors,mask = [],[]
        for t in model['triangles']:
            rgb,amount = corner_colors(t,data['materials'],textures)
            colors.extend(rgb); mask.extend(amount)
        mesh = indexed_mesh(points, colors, mask, signatures, color_tolerance=24)
        n = len(mesh['vertices']); tracks = len(track_sources)
        first = len(bank)
        def rgba(c): return (c[0]<<24)|(c[1]<<16)|(c[2]<<8)|255
        for a,b in zip(mesh['vertices'][::2],mesh['vertices'][1::2]):
            bank.extend(struct.pack('>3hH3hHII4h',*a[0],0,*b[0],0,rgba(a[1]),rgba(b[1]),0,0,0,0))
        indices = len(bank)-first
        bank.extend(np.array(mesh['indices'],dtype='>i2').tobytes())
        batches = len(bank)-first
        for batch in mesh['batches']: bank.extend(struct.pack('>4H',*batch))
        bank.extend(bytes((-len(bank))%16)); size = len(bank)-first
        high = (tracks+7)//8
        grip_offset = (8+tracks*3+high*3+3)&~3
        stride = (grip_offset+28+15)&~15
        clips = []
        for i,c in enumerate(model['animations']):
            offset = len(bank); all_positions = poses[i][:,track_sources]
            for p,hand in zip(all_positions,grips[i]):
                origin = p.min(0); delta = p.astype(int)-origin
                assert delta.max() < 512, 'ODST coordinate span exceeds exact 9-bit encoding'
                frame = bytearray(struct.pack('>3hH',*origin,0))
                frame.extend((delta.T&255).astype(np.uint8).tobytes())
                frame.extend(np.packbits((delta.T>>8).astype(np.uint8),axis=1,bitorder='little').tobytes())
                frame.extend(bytes(grip_offset-len(frame)))
                frame.extend(hand.astype('>f4').tobytes())
                frame.extend(bytes(stride-len(frame))); bank.extend(frame)
            clips.append(dict(name=c['name'],offset=offset,stride=stride,frames=len(all_positions),duration=c['duration'],
                bounds=[(all_positions.min((0,1))/SCALE).tolist(),(all_positions.max((0,1))/SCALE).tolist()],
                grip_bounds=[grips[i][:,:3].min(0).tolist(),grips[i][:,:3].max(0).tolist()]))
        meshes.append(dict(offset=first,bytes=size,indices_offset=indices,batches_offset=batches,vertices=n,
            batches=len(mesh['batches']),triangles=len(model['triangles']),radius=float(np.linalg.norm(np.array(points)/SCALE,axis=1).max())))
        reports.append(dict(**meshes[-1],tracks=tracks,frame_cache_bytes=stride*2,clips=clips))
        sources = mesh['sources']; mapping = [corner_tracks[v] for v in sources]
        lines.append(f'static const uint16_t odst_tracks_{lod}[]={{'+','.join(map(str,mapping))+'};')
        lines.append(f'static const uint8_t odst_mask_{lod}[]={{'+','.join(str(v[2]) for v in mesh['vertices'])+'};')
        triangles = np.array([[f+j for j in mesh['indices'][off+k:off+k+3]] for f,n,off,nindices in mesh['batches'] for k in range(0,nindices,3)])
        packed = dict(positions=np.array([v[0] for v in mesh['vertices']])/SCALE, colors=np.array([v[1] for v in mesh['vertices']]),
            mask=np.array([v[2] for v in mesh['vertices']]),triangles=triangles, sources=np.array(sources),tracks=np.array(mapping),
            **{'frames_'+str(i):f[:,sources] for i,f in enumerate(poses)}, **{'grips_'+str(i):g for i,g in enumerate(grips)})
        np.savez_compressed(output/f'odst-{lod}-preview.npz',**packed); previews.append(packed)
    floats = lambda xs:'{'+','.join(f'{float(x):.7f}f' for x in xs)+'}'
    box = lambda b:'{'+','.join(floats(a) for a in b)+'}'
    lines.append('const bg_jorge_mesh_info bg_odst_meshes[2]={')
    for m in meshes:
        lines.append('{'+','.join(str(m[k]) for k in ('offset','bytes','indices_offset','batches_offset','vertices','batches','triangles'))+f',{m["radius"]:.7f}f'+'},')
    lines.append('};')
    lines.append('const bg_jorge_clip bg_odst_clips[BG_J_CLIP_COUNT]={')
    for i,c in enumerate(reports[0]['clips']):
        bounds = [np.minimum(*[r['clips'][i]['bounds'][0] for r in reports]),np.maximum(*[r['clips'][i]['bounds'][1] for r in reports])]
        lines.append('{'+f'{c["offset"]},{c["stride"]},{c["frames"]},{c["duration"]:.7f}f,'+box(bounds)+','+box([np.minimum(*[r['clips'][i]['grip_bounds'][0] for r in reports]),np.maximum(*[r['clips'][i]['grip_bounds'][1] for r in reports])])+'},')
    lines.append('};')
    lines.append('const bg_jorge_clip bg_odst_lod_clips[BG_J_CLIP_COUNT]={')
    for i,c in enumerate(reports[1]['clips']):
        bounds = [np.minimum(*[r['clips'][i]['bounds'][0] for r in reports]),np.maximum(*[r['clips'][i]['bounds'][1] for r in reports])]
        lines.append('{'+f'{c["offset"]},{c["stride"]},{c["frames"]},{c["duration"]:.7f}f,'+box(bounds)+','+box([np.minimum(*[r['clips'][i]['grip_bounds'][0] for r in reports]),np.maximum(*[r['clips'][i]['grip_bounds'][1] for r in reports])])+'},')
    lines.extend(['};','const uint16_t *const bg_odst_tracks[2]={odst_tracks_0,odst_tracks_1};',
        'const uint8_t *const bg_odst_team_masks[2]={odst_mask_0,odst_mask_1};',
        'const unsigned bg_odst_track_counts[2]={'+','.join(str(r['tracks']) for r in reports)+'};'])
    (output/'odst_data.c').write_text('\n'.join(lines)+'\n')
    (output/'odst.bin').write_bytes(bank)
    report = dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),bank_sha256=hashlib.sha256(bank).hexdigest(),
        rom_bytes=len(bank),position_scale=SCALE,lods=reports,frame_encoding='per-frame origin + three 9-bit planes; exact quantized track sharing')
    (output/'odst-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='lods'}))
    print([(r['vertices'],r['triangles'],r['tracks'],r['bytes']) for r in reports])


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path); parser.add_argument('output',type=Path)
    args=parser.parse_args(); pack(args.source,args.output)
