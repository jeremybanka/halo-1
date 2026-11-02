"""Matched untouched source / packed ODST views and production menu portraits."""
import argparse,json
from dataclasses import replace
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from audit_models import Mesh,engine,source_mesh,globals_for,render,matching_bounds,ANGLES,camera_basis
from pack_odst import palette

def original_pose(model,states):
    skin=globals_for(states,model['nodes'])@np.linalg.inv(globals_for(model['nodes'],model['nodes']))
    pts=np.c_[np.array(model['vertices']),np.ones(len(model['vertices']))];out=np.zeros((len(pts),3))
    for i,values in enumerate(model['skin_weights']):
        for b,w in values:out[i]+=(skin[b]@pts[i])[:3]*w
    return out

def holes(mask):
    from collections import deque
    h,w=mask.shape;outside=np.zeros_like(mask);todo=deque()
    for y in range(h):
        for x in (0,w-1):
            if not mask[y,x]:outside[y,x]=True;todo.append((y,x))
    for x in range(w):
        for y in (0,h-1):
            if not mask[y,x] and not outside[y,x]:outside[y,x]=True;todo.append((y,x))
    while todo:
        y,x=todo.popleft()
        for dy,dx in ((0,1),(0,-1),(1,0),(-1,0)):
            j,i=y+dy,x+dx
            if 0<=j<h and 0<=i<w and not mask[j,i] and not outside[j,i]:outside[j,i]=True;todo.append((j,i))
    return ~mask&~outside

def new_holes(reference,candidate):
    old=holes(reference);current=holes(candidate);remaining=set(map(tuple,np.argwhere(current)))
    new=np.zeros_like(current);grown=0;components=0
    nearby=old.copy()
    for dy,dx in ((0,1),(0,-1),(1,0),(-1,0)):
        nearby|=np.roll(old,(dy,dx),(0,1))
    while remaining:
        start=remaining.pop();todo=[start];group=[start]
        while todo:
            y,x=todo.pop()
            for dy,dx in ((0,1),(0,-1),(1,0),(-1,0)):
                other=(y+dy,x+dx)
                if other in remaining:remaining.remove(other);todo.append(other);group.append(other)
        if any(nearby[y,x] for y,x in group):grown+=sum(reference[y,x] for y,x in group)
        else:
            components+=1
            for y,x in group:new[y,x]=True
    return new,components,int(grown)

def source_face(mesh,bounds,direction,size,y,x):
    center,span=bounds;look,right,up=camera_basis(direction);relative=mesh.p-center
    scale=min(size/span[0],size/span[1])*.80
    screen=np.stack((relative@right*scale+size/2,-relative@up*scale+size/2),axis=-1);depth=relative@look
    a,b,c=screen[:,0],screen[:,1],screen[:,2]
    det=(b[:,1]-c[:,1])*(a[:,0]-c[:,0])+(c[:,0]-b[:,0])*(a[:,1]-c[:,1]);safe=np.where(abs(det)>1e-10,det,1)
    w0=((b[:,1]-c[:,1])*(x+.5-c[:,0])+(c[:,0]-b[:,0])*(y+.5-c[:,1]))/safe
    w1=((c[:,1]-a[:,1])*(x+.5-c[:,0])+(a[:,0]-c[:,0])*(y+.5-c[:,1]))/safe;w2=1-w0-w1
    facing=np.cross(mesh.p[:,1]-mesh.p[:,0],mesh.p[:,2]-mesh.p[:,0])@look
    valid=(abs(det)>1e-10)&(facing>0)&(w0>=-1e-7)&(w1>=-1e-7)&(w2>=-1e-7)
    if not valid.any():return None
    z=w0*depth[:,0]+w1*depth[:,1]+w2*depth[:,2]
    return int(np.argmax(np.where(valid,z,-np.inf)))

def run(folder,packed,output,candidate="covered"):
    output.mkdir(parents=True,exist_ok=True)
    raw=json.loads((folder/'source/odst-ce-raw.json').read_text());model=raw['models']['spartan']
    data=json.loads((folder/candidate/'solid.json').read_text());pv=[np.load(packed/f'odst-{lod}-preview.npz') for lod in range(2)]
    rows=[];metrics=[];coverage=[];repairs=[set(),set()]
    for name,fraction in [('idle',0),('run',.4),('melee',.4),('passenger',.5)]:
        ci=next(i for i,c in enumerate(data['lods'][0]['animations']) if c['name']==name)
        original=raw['animations'][name]
        authored=np.load(folder/candidate/'poses-0.npz')['frames_'+str(ci)]
        sample=round(fraction*(len(authored)-1))
        original_index=round(sample*(len(original['frames'])-1)/max(1,len(authored)-1))
        src=source_mesh(model,original_pose(model,original['frames'][original_index]))
        native=[]
        for lod,p in enumerate(pv):
            frames=np.load(folder/candidate/f'poses-{lod}.npz')['frames_'+str(ci)]
            # Match the exact source skeleton sample, using production mesh
            # sharing, colors and quantization. Clock sparsity is audited by
            # the independent bank/decoder check.
            points=np.rint(frames[sample,p['sources']]*512)[p['triangles']]/512
            native.append(Mesh(points,rgb=palette(p['colors'],p['mask'],0)[p['triangles']]))
        for angle,direction in ANGLES:
            bounds=matching_bounds([src,*native],direction);ims=[];masks=[]
            for mesh in [src,*native]:
                im,mask=render(mesh,bounds,direction,width=160,height=160);ims.append(im);masks.append(mask)
            metrics.append(dict(pose=name,angle=angle,near_iou=float((masks[0]&masks[1]).sum()/max(1,(masks[0]|masks[1]).sum())),far_iou=float((masks[0]&masks[2]).sum()/max(1,(masks[0]|masks[2]).sum()))))
            for size in (64,96):
                coverage_source=replace(src,p=np.rint(src.p.astype(np.float32)*512)/512)
                small=[render(mesh,bounds,direction,width=size,height=size)[1] for mesh in [coverage_source,*native]]
                for lod in (0,1):
                    new,components,growth=new_holes(small[0],small[lod+1])
                    missing=new&small[0]
                    coverage.append(dict(pose=name,angle=angle,size=size,lod=lod,new_enclosed_components=components,new_enclosed_pixels=int(missing.sum()),existing_gap_growth_pixels=growth))
                    for y,x in np.argwhere(missing):
                        fi=source_face(coverage_source,bounds,direction,size,y,x)
                        if fi is not None:repairs[lod].add(fi)

            sheet=Image.new('RGB',(480,180),'#202428');draw=ImageDraw.Draw(sheet)
            for i,(im,label) in enumerate(zip(ims,['Source','Fresh near','Fresh far'])):
                sheet.paste(im,(i*160,20));draw.text((i*160+4,4),f'{name} / {angle} / {label}',fill='white')
            sheet.save(output/f'{name}-{angle.replace(" ","-").replace("/","-")}.png')
            if name=='idle' and angle in ('front','rear','front 3/4','right'):rows.append(sheet)
    overview=Image.new('RGB',(480,180*len(rows)))
    for i,im in enumerate(rows):overview.paste(im,(0,i*180))
    overview.save(output/'overview.png')
    (output/'continuity-repair-faces.json').write_text(json.dumps([sorted(s) for s in repairs],indent=2)+'\n')
    (output/'coverage.json').write_text(json.dumps(coverage,indent=2)+'\n')
    print('Coverage probes',len(coverage),'worst new enclosed pixels',max(c['new_enclosed_pixels'] for c in coverage))
    (output/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
    lines=['/* Generated from the fresh packed ODST asset. */','#include "asset_odst.h"','const uint16_t bg_odst_portraits[4][32*40]={']
    p=pv[0];direction=(1,.25,1);base=p['frames_0'][0,p['triangles']]/512
    for profile in range(4):
        mesh=Mesh(base,rgb=palette(p['colors'],p['mask'],profile)[p['triangles']])
        im,mask=render(mesh,matching_bounds([mesh],direction),direction,width=32,height=40)
        im.save(output/f'portrait-{profile}.png');rgb=np.array(im,dtype=np.uint16)
        vals=((rgb[:,:,0]>>3)<<11)|((rgb[:,:,1]>>3)<<6)|((rgb[:,:,2]>>3)<<1)|mask.astype(np.uint16)
        vals[~mask]=0;lines.append('{'+','.join(hex(int(x)) for x in vals.ravel())+'},')
    lines.append('};');(packed/'odst_portraits.c').write_text('\n'.join(lines)+'\n')
    print('Fresh source/packed comparisons:',len(metrics),'minimum IoU',min(r['near_iou'] for r in metrics),min(r['far_iou'] for r in metrics))


def compare_ce(folder,packed,output):
    """Same CE idle sample, Halo scale, camera, lighting and production RGB."""
    output.mkdir(parents=True,exist_ok=True)
    assets=folder.parent.parent
    raw=json.loads((assets/'assets/extended-reduced.json').read_text())
    previews=json.loads((assets/'generated/model-preview.json').read_text())
    report=json.loads((assets/'generated/extended-report.json').read_text())
    meshes=[]
    for lod,key in enumerate(('spartan','spartan_lod')):
        motion=raw['animations_lod' if lod else 'animations']['idle']['frames'][0]
        order=report['triangle_order'][key];scale=report['model_position_scales'][key]
        points=np.rint(engine(np.array(motion).reshape(-1,3,3)[order])*scale)/scale
        model=previews[key]
        colors=palette(model['colors'],np.rint(np.array(model['team_mask'])*255),0).reshape(-1,3,3)
        meshes.append(Mesh(points,rgb=colors))
    for lod in range(2):
        p=np.load(packed/f'odst-{lod}-preview.npz')
        meshes.append(Mesh(p['frames_0'][0,p['triangles']]/512,rgb=palette(p['colors'],p['mask'],0)[p['triangles']]))
    costs=json.loads((packed/'odst-report.json').read_text())['lods']
    labels=('CE near / 562 verts','CE far / 250 verts',f"ODST near / {costs[0]['vertices']} verts",f"ODST far / {costs[1]['vertices']} verts")
    sheet=Image.new('RGB',(640,180*4),'#202428');draw=ImageDraw.Draw(sheet)
    for row,(angle,direction) in enumerate(ANGLES[:4]):
        bounds=matching_bounds(meshes,direction)
        for col,(mesh,label) in enumerate(zip(meshes,labels)):
            im,_=render(mesh,bounds,direction,width=160,height=160)
            sheet.paste(im,(col*160,row*180+20));draw.text((col*160+3,row*180+4),angle+' / '+label,fill='white')
    sheet.save(output/'standard-game-comparison.png')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('folder',type=Path);p.add_argument('packed',type=Path);p.add_argument('output',type=Path);p.add_argument('--candidate',default='covered');p.add_argument('--ce-only',action='store_true');a=p.parse_args();compare_ce(a.folder,a.packed,a.output)
    if not a.ce_only:run(a.folder,a.packed,a.output,a.candidate)
