"""CPU geometry audit: matched orthographic color, silhouette and winding views.

This supplements native RDP captures. It is not a substitute for hardware
occlusion, lighting, alpha or performance checks.
"""
import argparse,collections,gzip,json,math
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from model_colors import load_images,bake_triangle,bake_team_mask
from pack_assets import position

def read(path):return json.loads(gzip.decompress(path.read_bytes()))
def colors(model,raw,name):
    images=load_images(model['textures']);metadata=model['material_metadata'];masks=load_images([m.get('multipurpose_fullres') for m in metadata]);channels=[2 if m.get('color_change_source')=='A' else None for m in metadata]
    changes=raw['actors'][name]['variant']['change_colors'] if name!='spirit' else []
    if not changes and name!='spirit':
        rows=raw['actors'][name]['biped']['obje_attrs']['change_colors'];changes=rows[0]['permutations'] if rows else []
    tint=np.array([(a+b)*.5 for a,b in zip(changes[0]['color_lower_bound'].values(),changes[0]['color_upper_bound'].values())]) if changes else np.ones(3)
    rgb=[]
    for tri in model['triangles']:
        base=np.array(tri.get('colors') or bake_triangle(tri,images,model));mask=np.array(tri.get('tints') or bake_team_mask(tri,masks,channels))[:,None]/255
        rgb.append(np.rint(base*(1-mask+mask*tint)))
    return np.array(rgb)

def raster(points,rgb,eye,center,extent,size=192,cull=True):
    z=np.array(eye,dtype=float);z/=np.linalg.norm(z);x=np.cross([0,1,0],z);x/=np.linalg.norm(x);y=np.cross(z,x)
    p=(points-center)@np.array([x,y,z]).T;p[:,:,:2]*=size/extent;p[:,:,0]+=size/2;p[:,:,1]=size/2-p[:,:,1]
    image=np.full((size,size,3),24,dtype=np.uint8);depth=np.full((size,size),-np.inf);mask=np.zeros((size,size),bool)
    for t,color in zip(p,rgb):
        a,b,c=t;den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(den)<1e-8 or (cull and den>=0):continue
        lo=np.maximum(np.floor(t[:,:2].min(axis=0)).astype(int),0);hi=np.minimum(np.ceil(t[:,:2].max(axis=0)).astype(int),size-1)
        if np.any(lo>hi):continue
        yy,xx=np.mgrid[lo[1]:hi[1]+1,lo[0]:hi[0]+1];xx=xx+.5;yy=yy+.5
        u=((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/den
        v=((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/den;w=1-u-v
        zz=u*a[2]+v*b[2]+w*c[2];sl=np.s_[lo[1]:hi[1]+1,lo[0]:hi[0]+1];inside=(u>=0)&(v>=0)&(w>=0)&(zz>depth[sl])
        depth[sl][inside]=zz[inside];mask[sl][inside]=True
        shade=u[:,:,None]*color[0]+v[:,:,None]*color[1]+w[:,:,None]*color[2]
        image[sl][inside]=np.clip(shade[inside],0,255)
    return image,mask

def audit(before,after,source,out):
    before=read(before);after=read(after);raw=json.loads(source.read_text());out.mkdir(parents=True,exist_ok=True);report=[]
    views=[(1,.15,0),(-1,.15,0),(0,.15,1),(0,.15,-1),(1,.7,1),(-1,-.4,-1)]
    for name in after:
        for lod in range(2):
            a,b=before[name][lod],after[name][lod];rgb=[colors(m,raw,name) for m in [a,b]]
            # Energy surfaces are not hull silhouette. Native captures audit
            # their current opaque rendering and the candidate alpha pass.
            keep=[np.array([m['material_metadata'][t['material']]['class']=='shader_model' for t in m['triangles']]) for m in [a,b]]
            for clip,phase in ([('idle',0),('run',.5),('melee',.5)] if name=='hunter' else [('exit',0),('exit',.5),('exit',1)]):
                pts=[np.rint(np.array([position(p,(0,0,0)) for p in m['clips'][clip]['frames'][round(phase*(len(m['clips'][clip]['frames'])-1))]])*128).reshape(-1,3,3)/128 for m in [a,b]]
                base=pts[0][keep[0]];center=(base.min(axis=(0,1))+base.max(axis=(0,1)))/2;extent=np.linalg.norm(base.max(axis=(0,1))-base.min(axis=(0,1)))*1.12
                sheet=Image.new('RGB',(192*3,212*6),(24,24,24));draw=ImageDraw.Draw(sheet)
                for view,eye in enumerate(views):
                    results=[raster(p[k],c[k],eye,center,extent) for p,c,k in zip(pts,rgb,keep)]
                    masks=[r[1] for r in results];union=masks[0]|masks[1];inter=masks[0]&masks[1]
                    diff=np.zeros_like(results[0][0]);diff[inter]=[50,65,70];diff[masks[0]&~masks[1]]=[255,75,80];diff[masks[1]&~masks[0]]=[65,210,255]
                    for col,img in enumerate([results[0][0],results[1][0],diff]):sheet.paste(Image.fromarray(img),(col*192,view*212+20))
                    draw.text((6,view*212+3),f'{name} L{lod} {clip} {phase:g} v{view}',fill='white')
                    row={'model':name,'lod':lod,'clip':clip,'phase':phase,'view':view,'silhouette_iou':round(float(inter.sum()/max(1,union.sum())),5),'lost_pixels':int((masks[0]&~masks[1]).sum()),'added_pixels':int((masks[1]&~masks[0]).sum())}
                    for label,p,c,k,r in zip(['before','after'],pts,rgb,keep,results):
                        _,two=raster(p[k],c[k],eye,center,extent,cull=False);row[label+'_backface_only_pixels']=int((two&~r[1]).sum())
                    report.append(row)
                sheet.save(out/f'{name}-{lod}-{clip}-{phase:g}.png')
    (out/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'views':len(report),'minimum_silhouette_iou':min(x['silhouette_iou'] for x in report)},indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('before',type=Path);p.add_argument('after',type=Path);p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();audit(a.before,a.after,a.source,a.output)
