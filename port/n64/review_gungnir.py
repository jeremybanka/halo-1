"""Matched source/quantized candidate views, coverage and source-face repair ledger."""
import argparse,hashlib,json
from collections import Counter
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from audit_models import Mesh,engine,matching_bounds,ANGLES,camera_basis
from demake_raster import Raster
from extract_gungnir import bone_globals
from pack_gungnir import corner_colors,palette,prepare_broad_colors
from review_odst import new_holes
from gungnir_assets import texture_path

def gap_boundaries(new,reference,ids,triangles,source_ids=None):
    remaining=set(map(tuple,np.argwhere(new)));result=[];h,w=ids.shape
    while remaining:
        seed=remaining.pop();todo=[seed];group=[seed];border=Counter()
        while todo:
            y,x=todo.pop()
            for dy,dx in ((0,1),(0,-1),(1,0),(-1,0)):
                p=y+dy,x+dx
                if p in remaining:remaining.remove(p);todo.append(p);group.append(p)
                elif 0<=p[0]<h and 0<=p[1]<w and ids[p]>=0:border[triangles[int(ids[p])]['component']]+=1
        count=sum(bool(reference[p]) for p in group)
        if count:result.append(dict(void_pixels=len(group),lost_source_pixels=count,boundary_components=dict(border),source_faces=sorted({int(source_ids[p]) for p in group if reference[p]}) if source_ids is not None else []))
    return result


def run(source,motion,candidate,output,full=False,packed=None,with_ar=False):
    output=Path(output);output.mkdir(parents=True,exist_ok=True);m=json.loads(Path(source).read_text());data=json.loads((Path(candidate)/'solid.json').read_text());meta=json.loads((Path(motion)/'motion-report.json').read_text());poses=np.load(Path(motion)/'native-poses.npz');raster=Raster(output)
    points=np.c_[m['vertices'],np.ones(len(m['vertices']))];weights=np.zeros((len(points),len(m['nodes'])))
    for i,values in enumerate(m['weights']):
        for b,w in values:weights[i,b]=w
    inverse=np.linalg.inv(np.array(bone_globals(m['nodes'])));faces=np.array(m['faces']);seen=[];repairs=[set(),set()];views=[];rows=[];worst=[-1,-1];hints=[{},{}]
    textures={i:Image.open(texture_path(p,source)).convert('RGB') for i,p in enumerate(data['textures']) if p};prepare_broad_colors(data,textures);colors=[]
    for lod in data['lods']:
        colors.append(np.array([palette(rgb,mask,0) for t in lod['triangles'] for rgb,mask in [corner_colors(t,data['materials'],textures)]]))
    authored=[np.load(Path(candidate)/f'poses-{lod}.npz') for lod in range(2)]
    if with_ar:
        ar_path=Path(__file__).resolve().parents[2]/'halo64-assets/generated/model-preview.json';ar=json.loads(ar_path.read_text())['ar'];assert ar['triangle_count']==140
        ar_points=np.array(ar['positions']);ar_colors=np.array(ar['colors']).reshape(-1,3,3)
    runtime=[np.load(Path(packed)/f'gungnir-{lod}-preview.npz') for lod in range(2)] if packed else None
    samples=[(i,f) for i in range(39) for f in (0,.45,.9)] if full else [(i,f) for i,c in enumerate(meta['clips']) for f in (0,.45,.9) if c['name'] in ('idle','run','reload','passenger')]
    for ci,fraction in samples:
        clip=meta['clips'][ci];frames=poses['matrices_'+str(ci)];fi=round(fraction*(len(frames)-1));skin=frames[fi]@inverse;vertices=np.zeros((len(points),3))
        for b in np.flatnonzero(weights.sum(0)):vertices+=(points@skin[b].T)[:,:3]*weights[:,b,None]
        src=Mesh(np.rint(engine(vertices)[faces]*512)/512,rgb=np.full((len(faces),3,3),205.))
        models=[Mesh(np.rint(authored[l]['frames_'+str(ci)][fi]*512).reshape(-1,3,3)/512,rgb=colors[l]) for l in range(2)]
        if runtime:
            models=[]
            for d in runtime:
                bank=d['frames_'+str(ci)];clock=fi/max(1,len(frames)-1)*(len(bank)-1);a=int(clock);b=min(a+1,len(bank)-1);t=clock-a;runtime_points=(bank[a]*(1-t)+bank[b]*t)/512
                models.append(Mesh(runtime_points[d['triangles']],rgb=palette(d['colors'],d['mask'],0)[d['triangles']]))
        diagnostic_triangles=[l['triangles'] for l in data['lods']]
        if with_ar:
            hand=authored[0]['grips_'+str(ci)][fi];x,y,z,w=hand[3:];rotation=np.array(((1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)),(2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)),(2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y))))
            weapon=(ar_points@rotation.T+hand[:3]).reshape(-1,3,3)
            src=Mesh(np.concatenate((src.p,weapon)),rgb=np.concatenate((src.rgb,ar_colors)))
            models=[Mesh(np.concatenate((mesh.p,weapon)),rgb=np.concatenate((mesh.rgb,ar_colors))) for mesh in models]
            diagnostic_triangles=[[*ts,*[dict(component='production-ar') for _ in range(140)]] for ts in diagnostic_triangles]
        for vi,(angle,direction) in enumerate(ANGLES):
            bounds=matching_bounds([src,*models],direction)
            for size in (64,96):
                _,source_ids,_=raster.render(src,bounds,direction,width=size,height=size);reference=source_ids>=0
                for lod,mesh in enumerate(models):
                    _,ids,_=raster.render(mesh,bounds,direction,width=size,height=size);mask=ids>=0;new,components,growth=new_holes(reference,mask);missing=new&reference
                    repairs[lod].update(int(i) for i in np.unique(source_ids[missing]) if 0<=i<len(faces))
                    look,right,up=camera_basis(direction);center,span=bounds;scale=min(size/span[0],size/span[1])*.80
                    for py,px in np.argwhere(missing):
                        face=int(source_ids[py,px])
                        if face>=len(faces):continue
                        triangle=src.p[face];relative=triangle-center;screen=np.column_stack((relative@right*scale+size/2,-relative@up*scale+size/2,np.ones(3)))
                        try:bary=np.linalg.solve(screen.T,np.array((px+.5,py+.5,1)))
                        except np.linalg.LinAlgError:continue
                        point=bary@np.array([m['vertices'][i] for i in m['faces'][face]]);key=tuple(np.rint(point/.002).astype(int))
                        hints[lod][key]=dict(face=face,point=point.tolist(),clip=clip['name'],frame=fi,angle=angle,size=size)

                    if int(missing.sum())>worst[lod]:
                        worst[lod]=int(missing.sum());im,_,_=raster.render(mesh,bounds,direction,width=size,height=size);array=np.array(im);array[missing]=[255,20,20];Image.fromarray(array).resize((576,576),Image.Resampling.NEAREST).save(output/f'holes-{lod}.png')
                    diagnostic=gap_boundaries(new,reference,ids,diagnostic_triangles[lod],source_ids) if not runtime else []
                    views.append(dict(clip=clip['name'],frame=fi,fraction=fraction,angle=angle,size=size,lod=lod,new_enclosed_components=components,new_enclosed_pixels=int(missing.sum()),gap_boundaries=diagnostic,existing_gap_growth_pixels=growth,silhouette_iou=float((reference&mask).sum()/max(1,(reference|mask).sum()))))
            if fraction==.45 and clip['name'] in ('idle','run','reload','passenger'):
                sheet=Image.new('RGB',(480,180),'#202428');draw=ImageDraw.Draw(sheet)
                for i,(mesh,label) in enumerate(zip([src,*models],('Source clay','Near packed RGB','Far packed RGB'))):
                    im,_,_=raster.render(mesh,bounds,direction,width=160,height=160);sheet.paste(im,(i*160,20));draw.text((i*160+3,3),label,fill='white')
                sheet.save(output/(clip['name']+'-'+str(vi)+'.png'))
                if clip['name']=='idle' and vi<4:rows.append(sheet)
        print('COVERAGE',clip['name'],fraction,'worst',max(v['new_enclosed_pixels'] for v in views[-32:]),flush=True)
    overview=Image.new('RGB',(480,180*len(rows)))
    for i,row in enumerate(rows):overview.paste(row,(0,i*180))
    overview.save(output/'overview.png')
    report=dict(source_sha256=hashlib.sha256(Path(source).read_bytes()).hexdigest(),candidate_sha256=hashlib.sha256((Path(candidate)/'solid.json').read_bytes()).hexdigest(),packed_report_sha256=hashlib.sha256((Path(packed)/'gungnir-report.json').read_bytes()).hexdigest() if packed else None,production_ar_sha256=hashlib.sha256(ar_path.read_bytes()).hexdigest() if with_ar else None,samples=len(views),maximum_new_enclosed_pixels=max(v['new_enclosed_pixels'] for v in views),maximum_existing_gap_growth=max(v['existing_gap_growth_pixels'] for v in views),minimum_silhouette_iou=[min(v['silhouette_iou'] for v in views if v['lod']==l) for l in range(2)],repair_source_faces=[sorted(s) for s in repairs],repair_samples=[list(h.values()) for h in hints],views=views)
    (output/'coverage.json').write_text(json.dumps(report,indent=2)+'\n');print('REVIEW',report['samples'],report['maximum_new_enclosed_pixels'],[len(s) for s in repairs],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('motion');p.add_argument('candidate');p.add_argument('output');p.add_argument('--full',action='store_true');p.add_argument('--packed');p.add_argument('--with-ar',action='store_true');a=p.parse_args();run(a.source,a.motion,a.candidate,a.output,a.full,a.packed,a.with_ar)
