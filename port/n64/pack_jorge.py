"""Pack Jorge into an optional streamed bank using native Tiny3D batches."""
import json,struct,hashlib,math,argparse
from pathlib import Path
import numpy as np
from PIL import Image
from pack_mesh import indexed_mesh
ROOT=Path(__file__).resolve().parents[2];A=ROOT/'halo64-assets';OUT=A/'assets/jorge/playable-half';SCALE=512
def run(name='jorge-playable-half'):
    d=np.load(OUT/'gameplay-poses.npz');meta=json.loads((OUT/'gameplay-poses.json').read_text());corners=d['triangles'].flatten();rest=np.rint(d['rest']*SCALE).astype(int)
    image=np.array(Image.open(OUT/'textures/jorge-ce-atlas-256.png').convert('RGB'))
    colors=[]
    for u,v in d['uv']:
        x=min(255,max(0,u*256-.5));y=min(255,max(0,(1-v)*256-.5));ix,iy=int(x),int(y);fx,fy=x-ix,y-iy
        a=image[iy,ix]*(1-fx)+image[iy,min(255,ix+1)]*fx;b=image[min(255,iy+1),ix]*(1-fx)+image[min(255,iy+1),min(255,ix+1)]*fx
        colors.append(np.rint(a*(1-fy)+b*fy).astype(int).tolist())
    if 'colors' in d:colors=d['colors'].astype(int).tolist()
    # Match the standard Spartan's fixed CE vertex-light bake.
    tri=d['rest'][d['triangles']];normals=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-12)
    light=.68+.32*np.maximum(0,normals@np.array([.25,.83,.49]))
    for i in range(len(colors)):
        if meta['components'][i]=='body-06:000':colors[i]=[255,224,18]
        # Refined COLOR_0 already contains a continuous plate-normal response.
        # A second per-face light bake breaks both the gradient and shared verts.
        else:colors[i]=np.rint(np.array(colors[i])*(.85 if 'colors' in d else light[i//3])).astype(int).tolist()
    # Merge only identical complete quantized trajectories, never merely bind positions.
    frames=[np.rint(d['frames_'+str(i)]*SCALE).astype(np.int16) for i in range(len(meta['clips']))]
    keys=[hashlib.sha256(b''.join(f[:,vi].tobytes() for f in frames)).digest() for vi in range(len(rest))]
    mesh=indexed_mesh(rest[corners].tolist(),colors,[0]*len(corners),[keys[i] for i in corners],color_tolerance=24)
    sources=corners[mesh['sources']];bank=bytearray()
    for i in range(0,len(mesh['vertices']),2):
        a,b=mesh['vertices'][i:i+2];rgba=lambda rgb:(rgb[0]<<24)|(rgb[1]<<16)|(rgb[2]<<8)|255
        bank.extend(struct.pack('>3hH3hHII4h',*a[0],0,*b[0],0,rgba(a[1]),rgba(b[1]),0,0,0,0))
    indices_offset=len(bank);bank.extend(struct.pack('>'+str(len(mesh['indices']))+'h',*mesh['indices']));batch_offset=len(bank)
    for batch in mesh['batches']:bank.extend(struct.pack('>4H',*batch))
    bank.extend(bytes((-len(bank))%16));mesh_bytes=len(bank);clips=[];stride=(len(sources)*6+28+15)&~15
    for i,c in enumerate(meta['clips']):
        pos=frames[i][:,sources];grips=d['grips_'+str(i)];offset=len(bank)
        for frame,hand in zip(pos,grips):
            p=frame.astype('>i2').tobytes()+hand.astype('>f4').tobytes();bank.extend(p);bank.extend(bytes(stride-len(p)))
        clips.append({**c,'offset':offset,'stride':stride,'bounds':[(pos.min(axis=(0,1))/SCALE).tolist(),(pos.max(axis=(0,1))/SCALE).tolist()],'grip_bounds':[grips[:,:3].min(axis=0).tolist(),grips[:,:3].max(axis=0).tolist()]})
    (A/'frontend-files/jorge.bin').write_bytes(bank)
    floats=lambda a:'{'+','.join(f'{float(x):.7f}f' for x in a)+'}'
    bounds=lambda b:'{'+','.join(floats(a) for a in b)+'}'
    radius=float(np.linalg.norm(d['rest'],axis=1).max())
    lines=['/* Generated from locally supplied Reach/CE data. */','#include "asset_jorge.h"',f'const bg_jorge_mesh_info bg_jorge_mesh={{{mesh_bytes},{indices_offset},{batch_offset},{len(sources)},{len(mesh["batches"])},{len(corners)//3},{radius:.7f}f}};',f'const bg_jorge_clip bg_jorge_clips[BG_J_CLIP_COUNT]={{']
    for c in clips:lines.append('{'+f'{c["offset"]},{c["stride"]},{c["frames"]},{c["duration"]:.7f}f,'+bounds(c['bounds'])+','+bounds(c['grip_bounds'])+'},')
    lines.append('};');(A/'generated/jorge_data.c').write_text('\n'.join(lines)+'\n')
    np.savez_compressed(OUT/'packed-preview.npz',positions=np.array([v[0] for v in mesh['vertices']])/SCALE,colors=np.array([v[1] for v in mesh['vertices']]),triangles=np.array([[first+j for j in mesh['indices'][offset+k:offset+k+3]] for first,count,offset,n in mesh['batches'] for k in range(0,n,3)]),sources=sources,**{'frames_'+str(i):f[:,sources] for i,f in enumerate(frames)},**{'grips_'+str(i):d['grips_'+str(i)] for i in range(len(clips))})
    report={'vertices':len(sources),'triangles':len(corners)//3,'native_vertices':len(rest),'mesh_bytes':mesh_bytes,'frame_cache_bytes':stride*2,'rom_bytes':len(bank),'position_scale':SCALE,'max_position_error_m':math.sqrt(3)*3.048/(2*SCALE),'color_tolerance':24,'clips':clips,'source_blend_sha256':hashlib.sha256((OUT/(name+'.blend')).read_bytes()).hexdigest(),'source_directory':str(OUT.relative_to(ROOT)),'source_name':name}
    (A/'generated/jorge-report.json').write_text(json.dumps(report,indent=2)+'\n');(OUT/'runtime-report.json').write_text(json.dumps(report,indent=2)+'\n');print({k:v for k,v in report.items() if k!='clips'})
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--asset-dir',type=Path,default=OUT);parser.add_argument('--name',default='jorge-playable-half');args=parser.parse_args();OUT=args.asset_dir.resolve();run(args.name)
