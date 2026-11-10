"""Measure garment occlusion of the front codpiece in its animated local frame.

Full-body silhouettes cannot detect fabric covering an armor plate. This audit
isolates the rigid plate and its deforming underlayers, then compares depth at
three frontal directions. It reports intersections rather than blessing a mesh
solely because the assembled character has no background holes.
"""
from pathlib import Path
import argparse,hashlib,json,math
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
DEFAULT=ROOT/'halo64-assets/assets/jorge/playable-lods'

def depth(points,triangles,center,scale,direction,size=80):
    direction=np.array(direction,dtype=float);direction/=np.linalg.norm(direction)
    right=np.cross(direction,[0,1,0]);right/=np.linalg.norm(right)
    up=np.cross(right,direction)
    local=(points-center)@np.array([right,up,direction]).T
    local[:,:2]=local[:,:2]/scale*size+size/2
    result=np.full((size,size),-np.inf)
    for tri in local[triangles]:
        lo=np.maximum(0,np.floor(tri[:,:2].min(0)).astype(int));hi=np.minimum(size-1,np.ceil(tri[:,:2].max(0)).astype(int))
        if np.any(lo>hi):continue
        x,y=np.meshgrid(np.arange(lo[0],hi[0]+1)+.5,np.arange(lo[1],hi[1]+1)+.5)
        a,b,c=tri;den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(den)<1e-10:continue
        u=((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/den
        v=((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/den;w=1-u-v
        z=u*a[2]+v*b[2]+w*c[2];valid=(u>=-1e-8)&(v>=-1e-8)&(w>=-1e-8)
        area=result[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
        np.maximum(area,np.where(valid,z,-np.inf),out=area)
    return result

def run(folder,output,full=False,check=False):
    from PIL import Image
    output.mkdir(parents=True,exist_ok=True)
    reports={}
    for lod in ('near','far'):
        source=folder/lod if (folder/lod).is_dir() else folder
        d=np.load(source/'gameplay-poses.npz');m=json.loads((source/'gameplay-poses.json').read_text())
        aliases={'body-09:001':'codpiece','body-10:000':'pelvis','body-10:001':'waist',
                 'body-00:000':'chest','body-09:000':'collar'}
        components=np.array([aliases.get(c,c) for c in m['components'][::3]]);faces=d['triangles']
        plate=faces[components=='codpiece'];cloth=faces[np.isin(components,['pelvis','waist'])]
        ids=np.unique(plate);rest=d['rest'][ids];basis=np.column_stack((rest,np.ones(len(rest))))
        # The rear/inner faces of the closed belt are intentionally behind the
        # wearer. Audit the forward exterior plate, not those buried surfaces.
        tri=d['rest'][plate];normals=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
        plate=plate[(tri[:,:,0].mean(1)>0)&(normals[:,0]>.2*np.linalg.norm(normals,axis=1))]
        assert len(plate)>0
        center=(rest.max(0)+rest.min(0))/2;scale=max(np.ptp(rest[:,1]),np.ptp(rest[:,2]))*1.35
        rows=[];worst=None
        samples=[(i,f) for i in range(39) for f in (0,.45,.9)] if full else [(0,0),(1,.25),(1,.75),(2,.5),(3,.4),(3,.8)]
        for clip,fraction in samples:
            frames=d['frames_'+str(clip)];f=fraction*(len(frames)-1);a=int(f);b=min(a+1,len(frames)-1);t=f-a
            posed=(np.rint(frames[a]*512)*(1-t)+np.rint(frames[b]*512)*t)/512
            transform=np.linalg.lstsq(basis,posed[ids],rcond=None)[0]
            local=(posed-transform[3])@np.linalg.inv(transform[:3])
            for angle in (-35,0,35):
                direction=(math.cos(math.radians(angle)),0,math.sin(math.radians(angle)))
                armor=depth(local,plate,center,scale,direction)
                under=depth(local,cloth,center,scale,direction)
                region=np.isfinite(armor);occluded=region&(under>armor+1/512)
                row=dict(clip=m['clips'][clip]['name'],fraction=fraction,angle=angle,
                         plate_pixels=int(region.sum()),occluded_pixels=int(occluded.sum()),
                         occluded_fraction=float(occluded.sum()/max(1,region.sum())))
                rows.append(row)
                if worst is None or row['occluded_fraction']>worst[0]['occluded_fraction']:
                    rgb=np.full((*region.shape,3),30,dtype=np.uint8);rgb[region]=[60,180,160];rgb[occluded]=[240,80,70]
                    worst=(row,rgb)
        Image.fromarray(np.flipud(worst[1])).resize((400,400),Image.Resampling.NEAREST).save(output/f'{lod}-worst-codpiece.png')
        # The chest and collar are torso-rigid; inspect their front exterior in
        # rest space, separately from legitimate arm/weapon occlusion in poses.
        chest=faces[components=='chest'];tri=d['rest'][chest]
        normals=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
        chest=chest[(tri[:,:,0].mean(1)>0)&(normals[:,0]>.2*np.linalg.norm(normals,axis=1))]
        points=d['rest'][np.unique(chest)];mid=(points.min(0)+points.max(0))/2
        extent=max(np.ptp(points[:,1]),np.ptp(points[:,2]))*1.15;layering=[]
        for angle in (-35,0,35):
            direction=(math.cos(math.radians(angle)),0,math.sin(math.radians(angle)))
            armor=depth(d['rest'],chest,mid,extent,direction);region=np.isfinite(armor)
            for component in ('collar','chest-backing','waist'):
                under=depth(d['rest'],faces[components==component],mid,extent,direction)
                overlap=region&(under>armor+1/512)
                layering.append(dict(angle=angle,underlayer=component,plate_pixels=int(region.sum()),
                                     occluded_pixels=int(overlap.sum()),occluded_fraction=float(overlap.sum()/max(1,region.sum()))))
        idle=max(r['occluded_fraction'] for r in rows if r['clip']=='idle' and r['fraction']==0)
        reports[lod]=dict(samples=len(rows),pose_bank_sha256=hashlib.sha256((source/'gameplay-poses.npz').read_bytes()).hexdigest(),
                          maximum_idle_occlusion=idle,mean_occluded_fraction=float(np.mean([r['occluded_fraction'] for r in rows])),
                          worst=worst[0],chest_front_layering=layering,views=rows)
        if check:
            # Allow a narrow subpixel seam at the cloth boundary. The previous
            # failure hid 26% of the near plate and 57% of the far plate here.
            assert idle<=.02,(lod,'idle codpiece obscured',idle)
            assert not any(r['occluded_pixels'] for r in layering),(lod,'chest support breaks the exterior')
        print(lod,{k:v for k,v in reports[lod].items() if k!='views'},flush=True)
    (output/'codpiece-clearance.json').write_text(json.dumps(reports,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=DEFAULT)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--full',action='store_true');p.add_argument('--check',action='store_true')
    args=p.parse_args();run(args.source,args.output,args.full,args.check)
