"""Pack independent near/far trajectories; publish only after review passes."""
from pathlib import Path
import argparse,hashlib,json,math,struct
import numpy as np
from pack_mesh import indexed_mesh

ROOT=Path(__file__).resolve().parents[2]
ASSETS=ROOT/'halo64-assets';SOURCE=ASSETS/'assets/jorge/playable-lods';SCALE=512

def pack_lod(lod,bank):
    folder=SOURCE/lod;d=np.load(folder/'gameplay-poses.npz');meta=json.loads((folder/'gameplay-poses.json').read_text())
    corners=d['triangles'].flatten();rest=np.rint(d['rest']*SCALE).astype(int)
    colors=np.rint(d['colors']*.85).astype(int)
    for i,c in enumerate(meta['components']):
        if c=='visor':colors[i]=[255,224,18]
    frames=[np.rint(d['frames_'+str(i)]*SCALE).astype(np.int16) for i in range(len(meta['clips']))]
    keys=[hashlib.sha256(b''.join(f[:,v].tobytes() for f in frames)).digest() for v in range(len(rest))]
    # Start a fresh cache at physical component boundaries instead of
    # splitting a small articulated part across two 40-triangle batches.
    # Triangle/component order and all animated positions remain exact.
    breaks=[0]+[i for i in range(3,len(corners),3) if meta['components'][i]!=meta['components'][i-3]]+[len(corners)]
    segments=[(a,b-a) for a,b in zip(breaks,breaks[1:])]
    order=[]
    for a,count in segments:
        if meta['components'][a] in meta.get('rigid_components',{}):
            # A single-bone component has an affine pose: its coplanar face
            # precedence is invariant. Reuse the audited static ordering;
            # retain exact per-vertex motion keys in the final packing pass.
            trial=indexed_mesh(rest[corners[a:a+count]].tolist(),colors[a:a+count].tolist(),
                               [0]*count,color_tolerance=48,reorder_static=True)
            order.extend(a+i*3+c for i in trial['triangle_order'] for c in range(3))
        else:order.extend(range(a,a+count))
    corners=corners[order];colors=colors[order]
    mesh=indexed_mesh(rest[corners].tolist(),colors.tolist(),[0]*len(corners),[keys[v] for v in corners],
                      color_tolerance=48,segments=segments)
    sources=corners[mesh['sources']];start=len(bank);assert start%16==0
    cloth={'pelvis','waist','neck','torso-backing','knee-l','knee-r',
           'armpit-l','armpit-r','ankle-l','ankle-r','elbow-l','elbow-r'}
    components=np.array(meta['components'])[order]
    secondary={'chest','thigh-l','thigh-r','boot-l','boot-r','glove-l','glove-r'}
    accent={'helmet','shoulder-l','shoulder-r','forearm-l','forearm-r','codpiece'}
    def palette_class(component,color):
        # Stable IDs from armor_palette.h: keep, base, gray bag, secondary, accent.
        if component in {'pack','pack-backing'}:return 2
        if component=='visor' or component in cloth or max(color)<=65:return 0
        return 3 if component in secondary else 4 if component in accent else 1
    palette_mask=[palette_class(components[i],v[1]) for i,v in zip(mesh['sources'],mesh['vertices'])]
    for i in range(0,len(mesh['vertices']),2):
        a,b=mesh['vertices'][i:i+2]
        def rgba(rgb):return (rgb[0]<<24)|(rgb[1]<<16)|(rgb[2]<<8)|255
        bank.extend(struct.pack('>3hH3hHII4h',*a[0],0,*b[0],0,rgba(a[1]),rgba(b[1]),0,0,0,0))
    indices_offset=len(bank)-start;bank.extend(struct.pack('>'+str(len(mesh['indices']))+'h',*mesh['indices']))
    batches_offset=len(bank)-start
    for batch in mesh['batches']:bank.extend(struct.pack('>4H',*batch))
    bank.extend(bytes((-len(bank))%16));mesh_bytes=len(bank)-start
    stride=(len(sources)*6+28+15)&~15;clips=[]
    for i,c in enumerate(meta['clips']):
        pos=frames[i][:,sources];grips=d['grips_'+str(i)];offset=len(bank)
        for points,hand in zip(pos,grips):
            sample=points.astype('>i2').tobytes()+hand.astype('>f4').tobytes()
            bank.extend(sample);bank.extend(bytes(stride-len(sample)))
        clips.append({**c,'offset':offset,'stride':stride,
                      'bounds':[(pos.min(axis=(0,1))/SCALE).tolist(),(pos.max(axis=(0,1))/SCALE).tolist()],
                      'grip_bounds':[grips[:,:3].min(0).tolist(),grips[:,:3].max(0).tolist()]})
    report=dict(lod=lod,vertices=len(sources),native_vertices=len(rest),triangles=len(corners)//3,
                bank_offset=start,mesh_bytes=mesh_bytes,indices_offset=indices_offset,batches_offset=batches_offset,
                batches=len(mesh['batches']),frame_cache_bytes=stride*2,rom_bytes=len(bank)-start,
                position_scale=SCALE,max_position_error_m=math.sqrt(3)*3.048/(2*SCALE),color_tolerance=48,
                radius=float(np.linalg.norm(d['rest'],axis=1).max()),clips=clips,
                source_blend_sha256=hashlib.sha256((folder/('jorge-'+lod+'.blend')).read_bytes()).hexdigest(),
                source_directory=str(folder.relative_to(ROOT)),source_name='jorge-'+lod)
    triangles=np.array([[first+j for j in mesh['indices'][offset+k:offset+k+3]]
                        for first,count,offset,n in mesh['batches'] for k in range(0,n,3)])
    np.savez_compressed(folder/'packed-preview.npz',positions=np.array([v[0] for v in mesh['vertices']])/SCALE,
                        colors=np.array([v[1] for v in mesh['vertices']]),triangles=triangles,sources=sources,
                        batches=np.array(mesh['batches']),indices=np.array(mesh['indices']),
                        **{'frames_'+str(i):f[:,sources] for i,f in enumerate(frames)},
                        **{'grips_'+str(i):d['grips_'+str(i)] for i in range(len(clips))})
    (folder/'runtime-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(lod,{k:report[k] for k in ('vertices','native_vertices','triangles','batches','mesh_bytes','frame_cache_bytes','rom_bytes')})
    return report,palette_mask

def run(publish=False):
    bank=bytearray();packed=[pack_lod(lod,bank) for lod in ('near','far')]
    reports=[p[0] for p in packed]
    floats=lambda a:'{'+','.join(f'{float(x):.7f}f' for x in a)+'}'
    bounds=lambda b:'{'+','.join(floats(a) for a in b)+'}'
    lines=['/* Generated Jorge near/far LODs from the owned Reach/CE source. */','#include "asset_jorge.h"']
    for r,suffix in zip(reports,('','_lod')):
        mask=packed[bool(suffix)][1]
        lines.append('const uint8_t bg_jorge'+suffix+'_palette_mask[]={'+','.join(map(str,mask))+'};')
        lines.append(f'const bg_jorge_mesh_info bg_jorge{suffix}_mesh={{'+
                     ','.join(str(r[k]) for k in ('bank_offset','mesh_bytes','indices_offset','batches_offset','vertices','batches','triangles'))+
                     f',{r["radius"]:.7f}f}};')
        lines.append(f'const bg_jorge_clip bg_jorge{suffix}_clips[BG_J_CLIP_COUNT]={{')
        for i,c in enumerate(r['clips']):
            # The common culling path must enclose either selected LOD.
            box=[np.minimum(*[x['clips'][i]['bounds'][0] for x in reports]).tolist(),
                 np.maximum(*[x['clips'][i]['bounds'][1] for x in reports]).tolist()]
            lines.append('{'+f'{c["offset"]},{c["stride"]},{c["frames"]},{c["duration"]:.7f}f,'+bounds(box)+','+bounds(c['grip_bounds'])+'},')
        lines.append('};')
    report=dict(format=2,lods=reports,rom_bytes=len(bank),mesh_bytes=sum(r['mesh_bytes'] for r in reports),
                frame_cache_bytes=max(r['frame_cache_bytes'] for r in reports))
    compiled=SOURCE/'compiled';compiled.mkdir(exist_ok=True)
    (compiled/'jorge.bin').write_bytes(bank)
    (compiled/'jorge_data.c').write_text('\n'.join(lines)+'\n')
    (compiled/'jorge-report.json').write_text(json.dumps(report,indent=2)+'\n')
    if publish:
        import shutil
        # Prevent an older export/coverage report from blessing a new bank.
        for r in reports:
            folder=SOURCE/r['lod']
            checked=json.loads((folder/'bank-validation.json').read_text())
            exported=json.loads((folder/'export-validation.json').read_text())
            audited=json.loads((folder/'coverage-full.json').read_text())
            assert checked['bank_sha256']==hashlib.sha256(bank).hexdigest(), 'Run test_jorge_bank.py --candidate first'
            assert exported['blend_sha256']==r['source_blend_sha256'], 'Export validation is stale'
            assert audited['pose_bank_sha256']==hashlib.sha256((folder/'gameplay-poses.npz').read_bytes()).hexdigest(), 'Coverage audit is stale'
            assert audited['samples']==2340 and exported['clips']==39
        for name,dest in [('jorge.bin','frontend-files'),('jorge_data.c','generated'),('jorge-report.json','generated')]:
            shutil.copy2(compiled/name,ASSETS/dest/name)
    print('PACKED',len(bank),'bytes; production published:',publish)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--publish',action='store_true')
    run(parser.parse_args().publish)
