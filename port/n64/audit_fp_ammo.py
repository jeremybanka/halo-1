#!/usr/bin/env python3
"""Offline 160x120 FP-ammo preview; perspective CPU proxy, not target pixels."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from pack_fp_ammo import prepare_ar, prepare_needler
from pack_firstperson import prepare_model
from pack_assets import position


def render_tri(canvas, points, colors, center, uv=None, texture=None, counter=False):
    p=np.asarray(points,float)
    # Match existing FP bank CULL_FRONT; source numeric planes are CULL_BACK.
    facing=float(np.cross(p[1]-p[0],p[2]-p[0])@(-p[0]))
    if (facing<=0 if counter else facing>=0) or np.min(p[:,0])<=1.4/32:
        return
    focal=60/math.tan(1.08/2)
    q=np.stack((center[0]+p[:,2]/p[:,0]*focal,center[1]-p[:,1]/p[:,0]*focal),axis=1)
    lo=np.maximum(np.floor(q.min(0)).astype(int),0);hi=np.minimum(np.ceil(q.max(0)).astype(int),[159,119])
    if np.any(hi<lo):return
    xx,yy=np.meshgrid(np.arange(lo[0],hi[0]+1)+.5,np.arange(lo[1],hi[1]+1)+.5)
    den=(q[1,1]-q[2,1])*(q[0,0]-q[2,0])+(q[2,0]-q[1,0])*(q[0,1]-q[2,1])
    if abs(den)<1e-12:return
    a=((q[1,1]-q[2,1])*(xx-q[2,0])+(q[2,0]-q[1,0])*(yy-q[2,1]))/den
    b=((q[2,1]-q[0,1])*(xx-q[2,0])+(q[0,0]-q[2,0])*(yy-q[2,1]))/den
    weights=np.stack((a,b,1-a-b),axis=-1);mask=np.min(weights,axis=-1)>=-1e-7
    if not np.any(mask):return
    if uv is None:rgb=weights@np.asarray(colors,float)
    else:
        persp=weights/p[:,0];persp/=persp.sum(-1)[...,None]
        st=persp@np.asarray(uv,float)
        # Bilinear proxy; actual RDP's three-point filter/coverage may differ.
        x=st[...,0];y=st[...,1];x0=np.floor(x).astype(int);y0=np.floor(y).astype(int)
        dx=x-x0;dy=y-y0;x0=np.clip(x0,0,texture.shape[1]-2);y0=np.clip(y0,0,texture.shape[0]-2)
        rgb=(texture[y0,x0]*(1-dx)[...,None]*(1-dy)[...,None]+texture[y0,x0+1]*dx[...,None]*(1-dy)[...,None]+
             texture[y0+1,x0]*(1-dx)[...,None]*dy[...,None]+texture[y0+1,x0+1]*dx[...,None]*dy[...,None])
    region=canvas[lo[1]:hi[1]+1,lo[0]:hi[0]+1];region[mask]=np.clip(rgb[mask],0,255).astype(np.uint8)


def run(assets,output):
    assets=Path(assets);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    reduced=json.loads((assets/'firstperson-reduced.json').read_text());raw=json.loads((assets/'firstperson-raw.json').read_text())
    meta=json.loads((assets/'firstperson-ammo.json').read_text());ar=prepare_ar(reduced,meta);needler=prepare_needler(raw,reduced,meta)
    meshes={n:prepare_model(reduced['weapons'][n],n) for n in ('ar','needler')}
    teams=((225,45,38),(39,92,215),(215,179,44),(57,183,69))
    bounds={}
    def draw(name,p,ammo,clip=0,frame=0):
        mesh,clips,_=meshes[name];clipname=('idle','fire','reload','melee')[clip]
        points=np.array([[round(v*256)/256 for v in position(point,(0,0,0))] for point in clips[clipname]['frames'][frame]])
        if name=='needler':
            for i,v in enumerate(needler['vertices']):
                track=needler['indices'][ammo*len(needler['vertices'])+i]
                start=((frame+needler['clip_offsets'][clip])*needler['tracks']+track)*3
                points[v]=[(needler['values'][start+a]+needler['origin'][a])/256 for a in range(3)]
        colors=[]
        for _,rgb,mask in mesh['vertices']:
            colors.append([(c*(65025-mask*(255-teams[p][a]))+32512)//65025 for a,c in enumerate(rgb)])
        colors=np.array(colors)
        image=np.full((120,160,3),(73,83,90),dtype=np.uint8)
        center=(91 if p%2==0 else 69,68 if p//2==0 else 52)
        for first,_,index_first,index_count in mesh['batches']:
            for i in range(index_first,index_first+index_count,3):
                ids=[first+j for j in mesh['indices'][i:i+3]]
                render_tri(image,points[ids],colors[ids],center)
        if name=='ar':
            points=np.array(ar['poses'][clip][frame])/4096
            uv=np.array(ar['uv'],float)/32
            uv[:4,0]+=ammo//10*10;uv[4:,0]+=ammo%10*10
            for ids in ((0,1,2),(2,1,3),(4,5,6),(6,5,7)):
                ids=list(ids);render_tri(image,points[ids],None,center,uv[ids],np.array(ar['atlas'],float),True)
            focal=60/math.tan(1.08/2)
            xy=np.stack((center[0]+points[:,2]/points[:,0]*focal,center[1]-points[:,1]/points[:,0]*focal),axis=1)
            bounds[f'{p}/{clip}/{frame}']={'min':xy.min(0).tolist(),'max':xy.max(0).tolist()}
        return Image.fromarray(image)
    for name,counts in [('ar',(60,37,10,0)),('needler',(20,13,7,0))]:
        sheet=Image.new('RGB',(320,240))
        for p,ammo in enumerate(counts):sheet.paste(draw(name,p,ammo),(p%2*160,p//2*120))
        sheet.save(output/(name+'-native.png'));sheet.resize((960,720),Image.Resampling.NEAREST).save(output/(name+'-enlarged.png'))
        montage=Image.new('RGB',(4*320,3*280),(24,29,34));text=ImageDraw.Draw(montage)
        for row,clip in enumerate((0,1,2)):
            w=reduced['weapons'][name];frames=len(w['clips'][('idle','fire','reload')[row]]['frames'])
            for col in range(4):
                frame=round(col*(frames-1)/3);im=draw(name,0,counts[col],clip,frame)
                montage.paste(im.resize((320,240),Image.Resampling.NEAREST),(col*320,row*280+28))
                text.text((col*320+8,row*280+8),f'{name} {("idle","fire","reload")[row]} frame {frame} / ammo {counts[col]}',fill='white')
        montage.save(output/(name+'-animation.png'))
    report={'scope':'CPU perspective proxy, current quantized FP geometry/vertex colors, source digit texture, CULL_FRONT base/CULL_BACK numeric planes, depth disabled, 1.08FOV and exact per-player safe-center projection. No RDP coverage/target readback claim.',
            'ar_bounds':bounds,'visible_needler_crystals':needler['visible_crystals'],
            'counts':{'ar':[60,37,10,0],'needler':[20,13,7,0]},
            'inputs':{str((assets/n).resolve()):hashlib.sha256((assets/n).read_bytes()).hexdigest() for n in ('firstperson-raw.json','firstperson-reduced.json','firstperson-ammo.json')}}
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(output.resolve())


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--assets',type=Path,default=Path('build/n64/assets'))
    p.add_argument('--output',type=Path,default=Path('build/n64/fp-ammo-proof/cpu-preview'))
    a=p.parse_args();run(a.assets,a.output)
