"""Pack the fresh GUNGNIR candidate into a bounded, optional ROM-streamed bank."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import numpy as np
from PIL import Image
from pack_assets import position, normal
from pack_mesh import indexed_mesh
from gungnir_colors import special_colors,team_amount
from gungnir_assets import texture_path

SCALE = 512
COLORS = np.array(((225,45,38),(39,92,215),(215,179,44),(57,183,69)))


def palette(rgb, mask, profile):
    rgb = np.array(rgb, dtype=int)
    mask = np.array(mask, dtype=int)[:,None]
    return (rgb * (65025 - mask * (255-COLORS[profile])) + 32512) // 65025


def corner_colors(tri, materials, textures):
    special=special_colors(tri,materials)
    if special is not None:return special
    image = textures.get(tri['material'])
    light=1.
    colors = []
    for i, uv in enumerate(tri['uv']):
        uv = np.array(uv)*.94 + np.mean(tri['uv'],axis=0)*.06
        if image is None:
            rgb = np.array((100,105,108))
        else:
            x,y = (int(uv[0]%1*image.width), int(uv[1]%1*image.height))
            rgb = np.array(image.getpixel((x,y)))
        # Broad source diffuse values survive; high-frequency baked scratches
        # do not spend separate packed vertices at N64 display scale.
        role=tri.get('color_family',tri['component'])
        if 'broad_rgb' in tri:rgb=np.array(tri.get('broad_vertex_rgb',[tri['broad_rgb']]*3)[i])
        if role.startswith('garment-') or role.endswith('-glove'):rgb=np.minimum(rgb,np.array((65,68,70)))
        elif 'broad_rgb' not in tri:rgb=rgb*.70
        # Shared bind coordinates get identical broad gradient values.
        x,y,z=tri['p'][i];n=np.array(tri.get('broad_normals',[[1,0,0]]*3)[i],dtype=float);n/=max(np.linalg.norm(n),1e-12)
        if role=='helmet-shell':n[1]=abs(n[1])
        light=.68+.32*max(0,float(np.dot(n,[.25,-.49,.83])))
        colors.append((np.clip(np.rint(rgb*light/12)*12,0,255).astype(int)).tolist())
    return colors, [team_amount(tri)]*3


def prepare_broad_colors(data,textures):
    # Preserve broad source material identity. Median UV samples are scoped to
    # each retained component; scratches and bevel lighting do not cause seams.
    for lod in data['lods']:
        groups={}
        for tri in lod['triangles']:
            groups.setdefault(tri['component'],[]).append(tri)
        for component,tris in groups.items():
            pixels=[]
            for tri in tris:
                image=textures.get(tri['material'])
                if image:
                    for uv in tri['uv']:pixels.append(image.getpixel((int(uv[0]%1*image.width),int(uv[1]%1*image.height))))
            if pixels:
                rgb=np.median(pixels,axis=0)
                family=tris[0].get('color_family',component)
                armor=family=='helmet-shell' or family.startswith('torso') or family=='belt' or family.startswith(('shoulder-','waist-plate-','knee-')) or family.endswith(('-thigh','-calf','-forearm','-upperarm','-boot')) or family=='wrist-buckler'
                if armor:rgb=np.clip(rgb-rgb.mean()+np.array([176,181,177]),125,205)
                elif family.startswith('chest-'):rgb=np.clip(rgb*.9+35,55,165)
                normals={}
                for tri in tris:
                    if tri.get('return_reverse'):continue
                    p=np.array(tri['p']);n=np.cross(p[1]-p[0],p[2]-p[0])
                    for point in tri['p']:
                        key=tuple(round(x,6) for x in point);normals[key]=normals.get(key,np.zeros(3))+n
                if family=='helmet-shell':
                    points=np.array([p for t in tris for p in t['p']]);low=points.min(0);high=points.max(0);center=(low+high)/2;radii=(high-low)/2
                    # A smooth convex normal field avoids triangulation-valence
                    # pinches around the optic on the deliberately coarse shell.
                    normals={tuple(round(x,6) for x in p):(p-center)/(radii*radii) for p in points}
                for tri in tris:
                    tri['broad_rgb']=rgb.tolist();tri['broad_normals']=[normals[tuple(round(x,6) for x in point)].tolist() for point in tri['p']]
                if family=='helmet-shell':
                    # The source diffuse includes an optic-shaped dark stain.
                    # Preserve the convex surface and its smooth geometric
                    # lighting, with one clean silver material under the ink.
                    for tri in tris:tri['broad_vertex_rgb']=[rgb.tolist()]*3


def pack(source, output):
    source, output = Path(source), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    data = json.loads(source.read_text())
    textures = {i:Image.open(texture_path(p,source)).convert('RGB') for i,p in enumerate(data['textures']) if p}
    prepare_broad_colors(data,textures)
    bank = bytearray(); reports = []; meshes = []; previews = []
    lines = ['/* Generated from the owned Halo: Reach GUNGNIR source; private assets. */', '#include "asset_gungnir.h"']
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
        authored=[np.rint(native['frames_'+str(i)]*SCALE).astype(np.int16) for i in range(len(model['animations']))]
        for v in range(count):
            signatures.append(hashlib.sha256(b''.join(f[:,v].tobytes() for f in authored)).digest())
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
        render_signatures=signatures
        if data.get('opaque_motion_reorder'):
            # These vertex-colored surfaces are opaque. Use the complete
            # runtime trajectory as an immutable identity in the static cache
            # optimizer: coincident bind points with different motion cannot
            # merge. Its coplanar predecessor constraints retain source order
            # for overlapping bind surfaces. No pose or clock is changed.
            mesh=indexed_mesh(points,colors,mask,material_keys=render_signatures,
                color_tolerance=data.get('color_tolerance',24),reorder_static=True)
            emitted=[first+j for first,_,off,nindices in mesh['batches'] for j in mesh['indices'][off:off+nindices]]
            for k,v in enumerate(emitted):
                assert signatures[mesh['sources'][v]]==signatures[mesh['triangle_order'][k//3]*3+k%3]
            # Check against every independent authoring pose, beyond the
            # sparse runtime endpoints used to identify reusable trajectories.
            original_corners=np.array(mesh['triangle_order'])[:,None]*3+np.arange(3)
            packed_sources=np.array(mesh['sources'])[emitted]
            for i in range(len(model['animations'])):
                full=np.rint(native['frames_'+str(i)]*SCALE).astype(np.int16)
                assert np.array_equal(full[:,packed_sources],full[:,original_corners.ravel()])
        else:
            mesh = indexed_mesh(points, colors, mask, render_signatures, color_tolerance=data.get("color_tolerance",24))
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
                assert delta.max() < 512, 'GUNGNIR coordinate span exceeds exact 9-bit encoding'
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
        lines.append(f'static const uint16_t gungnir_tracks_{lod}[]={{'+','.join(map(str,mapping))+'};')
        lines.append(f'static const uint8_t gungnir_mask_{lod}[]={{'+','.join(str(v[2]) for v in mesh['vertices'])+'};')
        triangles = np.array([[f+j for j in mesh['indices'][off+k:off+k+3]] for f,n,off,nindices in mesh['batches'] for k in range(0,nindices,3)])
        packed = dict(positions=np.array([v[0] for v in mesh['vertices']])/SCALE, colors=np.array([v[1] for v in mesh['vertices']]),
            mask=np.array([v[2] for v in mesh['vertices']]),triangles=triangles, sources=np.array(sources),tracks=np.array(mapping),
            **{'frames_'+str(i):f[:,sources] for i,f in enumerate(poses)}, **{'grips_'+str(i):g for i,g in enumerate(grips)})
        np.savez_compressed(output/f'gungnir-{lod}-preview.npz',**packed); previews.append(packed)
    floats = lambda xs:'{'+','.join(f'{float(x):.7f}f' for x in xs)+'}'
    box = lambda b:'{'+','.join(floats(a) for a in b)+'}'
    lines.append('const bg_jorge_mesh_info bg_gungnir_meshes[2]={')
    for m in meshes:
        lines.append('{'+','.join(str(m[k]) for k in ('offset','bytes','indices_offset','batches_offset','vertices','batches','triangles'))+f',{m["radius"]:.7f}f'+'},')
    lines.append('};')
    lines.append('const bg_jorge_clip bg_gungnir_clips[BG_J_CLIP_COUNT]={')
    for i,c in enumerate(reports[0]['clips']):
        bounds = [np.minimum(*[r['clips'][i]['bounds'][0] for r in reports]),np.maximum(*[r['clips'][i]['bounds'][1] for r in reports])]
        lines.append('{'+f'{c["offset"]},{c["stride"]},{c["frames"]},{c["duration"]:.7f}f,'+box(bounds)+','+box([np.minimum(*[r['clips'][i]['grip_bounds'][0] for r in reports]),np.maximum(*[r['clips'][i]['grip_bounds'][1] for r in reports])])+'},')
    lines.append('};')
    lines.append('const bg_jorge_clip bg_gungnir_lod_clips[BG_J_CLIP_COUNT]={')
    for i,c in enumerate(reports[1]['clips']):
        bounds = [np.minimum(*[r['clips'][i]['bounds'][0] for r in reports]),np.maximum(*[r['clips'][i]['bounds'][1] for r in reports])]
        lines.append('{'+f'{c["offset"]},{c["stride"]},{c["frames"]},{c["duration"]:.7f}f,'+box(bounds)+','+box([np.minimum(*[r['clips'][i]['grip_bounds'][0] for r in reports]),np.maximum(*[r['clips'][i]['grip_bounds'][1] for r in reports])])+'},')
    lines.extend(['};','const uint16_t *const bg_gungnir_tracks[2]={gungnir_tracks_0,gungnir_tracks_1};',
        'const uint8_t *const bg_gungnir_team_masks[2]={gungnir_mask_0,gungnir_mask_1};',
        'const unsigned bg_gungnir_track_counts[2]={'+','.join(str(r['tracks']) for r in reports)+'};'])
    (output/'gungnir_data.c').write_text('\n'.join(lines)+'\n')
    (output/'gungnir.bin').write_bytes(bank)
    report = dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),bank_sha256=hashlib.sha256(bank).hexdigest(),
        rom_bytes=len(bank),position_scale=SCALE,lods=reports,frame_encoding='per-frame origin + three 9-bit planes; exact quantized track sharing')
    (output/'gungnir-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='lods'}))
    print([(r['vertices'],r['triangles'],r['tracks'],r['bytes']) for r in reports])


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path); parser.add_argument('output',type=Path)
    args=parser.parse_args(); pack(args.source,args.output)
