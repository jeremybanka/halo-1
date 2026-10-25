"""Offline perspective checks at the exact 24 SDK photo cameras.

Float clipping/rasterization, nearest textures, perspective-correct attributes
and alpha cutouts. This does not emulate RSP/RDP rounding, fog, HUD or dynamics.
"""
import csv
import json
import numpy as np
from PIL import Image,ImageDraw
from sidewinder_structures import PREVIOUS,OUT
from remap_sidewinder_visibility import sections
import struct


def load_bank(path):
    ss=sections(path.read_bytes());triangles=[];materials=[];owners=[]
    for b,c in enumerate(struct.iter_unpack('>IHH6hHH',ss[1])):
        first,count,material,*rest=c;at,n=rest[-2:];ix=struct.unpack_from('>'+str(n)+'H',ss[2],at*2);vertices=[]
        for i in range(count):
            o=(first+i)//2*32;h=(first+i)%2
            vertices.append([*struct.unpack_from('>3h',ss[0],o+h*8),*ss[0][o+16+h*4:o+19+h*4],*struct.unpack_from('>2h',ss[0],o+24+h*4)])
        for t in range(0,n,3):triangles.append([vertices[i] for i in ix[t:t+3]]);materials.append(material);owners.append(b)
    textures=[]
    palette=np.frombuffer(ss[7],dtype='>u2')
    for mi,width in enumerate(ss[4]):
        raw=ss[3][mi*2048:(mi+1)*2048]
        if ss[5][mi]:
            indices=np.frombuffer(raw,dtype=np.uint8);indices=np.stack((indices>>4,indices&15),axis=-1).reshape(-1);pixels=palette[indices[:width*width]]
        else:pixels=np.frombuffer(raw,dtype='>u2')[:width*width]
        rgba=np.stack((((pixels>>11)&31)*255//31,((pixels>>6)&31)*255//31,((pixels>>1)&31)*255//31,(pixels&1)*255),axis=-1).astype(np.uint8)
        textures.append(rgba.reshape(width,width,4))
    a=np.array(triangles,dtype=float);a[:,:,:3]/=8
    for i,m in enumerate(materials):a[i,:,6:]/=ss[4][m]*32
    return a,np.array(materials),np.array(owners),textures,list(ss[6])


def render(bank,matrix,masks=None,visible=None,width=640,height=240,return_mask=False):
    vertices,materials,owners,textures,flags=bank;w,h=width,height
    image=np.full((h,w,3),(18,24,34),dtype=np.uint8);depth=np.full((h,w),np.inf)
    clip=np.concatenate((vertices[:,:,:3],np.ones((*vertices.shape[:2],1))),axis=2)@matrix
    planes=np.stack((clip[:,:,3]+clip[:,:,0],clip[:,:,3]-clip[:,:,0],clip[:,:,3]+clip[:,:,1],clip[:,:,3]-clip[:,:,1],clip[:,:,3]+clip[:,:,2],clip[:,:,3]-clip[:,:,2]),axis=2)
    eligible=~np.any(np.all(planes<0,axis=1),axis=1)
    if masks is not None:eligible&=np.array([bool(int(masks[b])&visible) for b in owners])
    for ti in np.flatnonzero(eligible):
        polygon=[np.concatenate((c,v[3:])) for c,v in zip(clip[ti],vertices[ti])]
        for axis,sign in ((0,1),(0,-1),(1,1),(1,-1),(2,1),(2,-1)):
            clipped=[]
            for i,a in enumerate(polygon):
                b=polygon[(i+1)%len(polygon)];da=a[3]+sign*a[axis];db=b[3]+sign*b[axis]
                if da>=0:clipped.append(a)
                if (da>=0)!=(db>=0):clipped.append(a+(b-a)*(da/(da-db)))
            polygon=clipped
            if len(polygon)<3:break
        for i in range(1,len(polygon)-1):
            tri=np.array([polygon[0],polygon[i],polygon[i+1]]);inv=1/tri[:,3];ndc=tri[:,:3]*inv[:,None]
            screen=np.stack(((ndc[:,0]+1)*w/2,(1-ndc[:,1])*h/2),axis=-1);t=screen
            x0=max(0,int(np.floor(t[:,0].min())));x1=min(w-1,int(np.ceil(t[:,0].max())));y0=max(0,int(np.floor(t[:,1].min())));y1=min(h-1,int(np.ceil(t[:,1].max())))
            if x1<x0 or y1<y0:continue
            det=(t[1,1]-t[2,1])*(t[0,0]-t[2,0])+(t[2,0]-t[1,0])*(t[0,1]-t[2,1])
            if abs(det)<1e-8:continue
            xx,yy=np.meshgrid(np.arange(x0,x1+1)+.5,np.arange(y0,y1+1)+.5)
            b0=((t[1,1]-t[2,1])*(xx-t[2,0])+(t[2,0]-t[1,0])*(yy-t[2,1]))/det
            b1=((t[2,1]-t[0,1])*(xx-t[2,0])+(t[0,0]-t[2,0])*(yy-t[2,1]))/det;b2=1-b0-b1
            z=b0*ndc[0,2]+b1*ndc[1,2]+b2*ndc[2,2];old=depth[y0:y1+1,x0:x1+1]
            keep=(b0>=-1e-7)&(b1>=-1e-7)&(b2>=-1e-7)&(z<old)
            if not keep.any():continue
            weights=np.stack((b0[keep],b1[keep],b2[keep]),axis=-1)*inv;weights/=weights.sum(axis=1)[:,None]
            uv=weights@tri[:,7:9];rgb=weights@tri[:,4:7];texture=textures[materials[ti]];size=len(texture)
            texel=texture[np.floor((uv[:,1]%1)*size).astype(int)%size,np.floor((uv[:,0]%1)*size).astype(int)%size]
            yy0,xx0=np.where(keep);mode=flags[materials[ti]]
            opaque=texel[:,3]>=128 if mode&3 else np.ones(len(texel),dtype=bool);yy0=yy0[opaque];xx0=xx0[opaque]
            image[y0+yy0,x0+xx0]=np.clip(np.round(texel[opaque,:3].astype(float)*rgb[opaque]/255),0,255).astype(np.uint8)
            if not mode&1:old[yy0,xx0]=z[keep][opaque]
    return (image,np.isfinite(depth)) if return_mask else image


def main():
    before=load_bank(PREVIOUS/'candidate-maps/sidewinder.map64');after=load_bank(OUT/'candidate-maps/sidewinder.map64')
    old_masks=json.loads((PREVIOUS/'data/visibility.json').read_text())['chunk_masks'];new_masks=json.loads((OUT/'packing-report.json').read_text())['chunk_masks']
    cameras={int(r['tick']):r for r in csv.DictReader((OUT/'photos/cameras.csv').open()) if r['candidate']=='1'}
    matrices=list(csv.reader((OUT/'photos/matrix-trace.csv').open()));assert len(matrices)==24
    poses=json.loads((OUT/'photos/poses.json').read_text());directory=OUT/'player-photos';directory.mkdir(exist_ok=True);results=[];sheet=[]
    for row in matrices:
        photo=int(row[0]);matrix=np.array([float(v) for v in row[1:]]).reshape(4,4);visible=int(cameras[photo]['pvs_mask'])
        a=render(before,matrix,old_masks,visible);b=render(after,matrix,new_masks,visible);control=render(after,matrix)
        difference=np.abs(a.astype(np.int16)-b.astype(np.int16));pvs_difference=np.abs(b.astype(np.int16)-control.astype(np.int16))
        for name,im in [('before',a),('after',b),('difference',np.clip(difference*6,0,255).astype(np.uint8)),('visibility-control',control)]:Image.fromarray(im).save(directory/f'{photo:02}-{name}.png')
        result=dict(photo=photo,label=poses[photo]['label'],matrix_columns=matrix.tolist(),pose=poses[photo],rgb_changed_pixels=int(np.count_nonzero(difference.max(axis=2))),rgb_mean_absolute_error=float(difference.mean()),pvs_control_changed_pixels=int(np.count_nonzero(pvs_difference.max(axis=2))))
        results.append(result);contact=Image.new('RGB',(1280,265),(18,24,34));contact.paste(Image.fromarray(a),(0,25));contact.paste(Image.fromarray(b),(640,25));draw=ImageDraw.Draw(contact);draw.text((8,5),f'{photo:02} {result["label"]} — before',fill='white');draw.text((648,5),'reduced',fill='white');sheet.append(contact)
        print(photo,result['rgb_changed_pixels'],'geometry pixels,',result['pvs_control_changed_pixels'],'PVS-control pixels',flush=True)
    contact=Image.new('RGB',(1280,len(sheet)*265),(18,24,34))
    for i,im in enumerate(sheet):contact.paste(im,(0,i*265))
    contact.save(OUT/'player-photo-contact.png');(OUT/'player-photos.json').write_text(json.dumps({'scope':__doc__,'photos':results},indent=2)+'\n')

def interiors():
    """Additional authored interior viewpoints; not added to performance means."""
    import math
    before=load_bank(PREVIOUS/'candidate-maps/sidewinder.map64');after=load_bank(OUT/'candidate-maps/sidewinder.map64')
    directory=OUT/'interiors';directory.mkdir(exist_ok=True);results=[]
    # Source-authored standing spawn positions, with a 0.62-unit eye height.
    stations=[('West lower room',(-31.26398277,-3.84095788,38.97298813)),('East lower room',(31.03555298,-3.84095788,42.95240021)),('West roof',(-31.71850014,.55905598,33.12189865)),('East roof',(30.24319649,.55930310,36.75874710))]
    for si,(label,position) in enumerate(stations):
        for ai,yaw in enumerate((0.,math.pi/2,math.pi,math.pi*1.5)):
            eye=np.array(position);eye[1]+=.62;eye*=32;forward=np.array([math.cos(yaw),0,-math.sin(yaw)]);right=np.cross(forward,[0,1,0]);right/=np.linalg.norm(right);up=np.cross(right,forward)
            view=np.eye(4);view[:3,:3]=np.stack((right,up,-forward));view[:3,3]=-view[:3,:3]@eye
            near,far=.05*32,300*32;f=1/math.tan(1.08/2);projection=np.zeros((4,4));projection[0,0]=f/(4/3);projection[1,1]=f;projection[2,2]=-(far+near)/(far-near);projection[2,3]=-2*far*near/(far-near);projection[3,2]=-1
            matrix=(projection@view).T;a=render(before,matrix);b=render(after,matrix);difference=np.abs(a.astype(np.int16)-b.astype(np.int16));index=si*4+ai
            for name,im in [('before',a),('after',b),('difference',np.clip(difference*6,0,255).astype(np.uint8))]:Image.fromarray(im).save(directory/f'{index:02}-{name}.png')
            results.append(dict(index=index,label=label,position=list(position),eye_height=.62,crouched=False,yaw=yaw,pitch=0,fov=1.08,projection_aspect=4/3,matrix_columns=matrix.tolist(),rgb_changed_pixels=int(np.count_nonzero(difference.max(axis=2))),rgb_mean_absolute_error=float(difference.mean())))
            print('interior',index,results[-1]['rgb_changed_pixels'],flush=True)
    (OUT/'interiors.json').write_text(json.dumps({'scope':'Offline authored spawn-position interior views in four horizontal directions. Same camera before/after. Separate from the 24 production photo fixtures; no PVS, dynamic objects or native-renderer claims.','views':results},indent=2)+'\n')


if __name__=='__main__':main()
