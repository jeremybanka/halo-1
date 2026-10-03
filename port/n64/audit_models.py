#!/usr/bin/env python3
"""Deterministic source/packed-model visual audit (NumPy + Pillow, no Blender).

All generated imagery contains locally extracted game assets and belongs in
ignored build/. The source view renders original diffuse maps with neutral
fixed lighting; it is deliberately not an emulation of the Xbox shader.
"""
from __future__ import annotations
import argparse, hashlib, html, json, math, os, re, time
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[2]
GUNS=('ar','pistol','plasma_pistol','plasma_rifle','needler','shotgun','sniper','rocket')
VEHICLES=('warthog','ghost','scorpion','banshee')
TEAMS={'red':(225,45,38),'blue':(39,92,215),'gold':(215,179,44),'green':(57,183,69)}
ANGLES=(('front',(1,.02,0)),('right',(0,.02,1)),('rear',(-1,.02,0)),('left',(0,.02,-1)),
        ('front 3/4',(1,.40,1)),('rear 3/4',(-1,.40,-1)),('top',(.001,1,.001)),('low 3/4',(1,.16,-1)))
BG=np.array((150,158,168),dtype=np.uint8)

@dataclass
class Mesh:
    p:np.ndarray
    rgb:np.ndarray|None=None
    uv:np.ndarray|None=None
    materials:np.ndarray|None=None
    textures:list|None=None
    masks:list|None=None
    team_mask:np.ndarray|None=None
    team:tuple|None=None
    source:bool=False
    family:str='world'
    provenance:str=''
    material_colors:list|None=None


def load(path):return json.loads(Path(path).read_text())
def engine(p):
    a=np.asarray(p,dtype=np.float64)
    return np.stack((a[...,0],a[...,2],-a[...,1]),axis=-1)
def quaternion(q):
    x,y,z,w=q;x,y,z=-x,-y,-z
    return np.array(((1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w),0),
                     (2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w),0),
                     (2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y),0),(0,0,0,1)),dtype=float)
def globals_for(states,nodes):
    result=[None]*len(states)
    def visit(i):
        if result[i] is not None:return result[i]
        m=quaternion(states[i]['q']);m[:3,3]=states[i]['p'];parent=nodes[i]['parent']
        result[i]=visit(parent)@m if parent>=0 and parent!=i else m
        return result[i]
    for i in range(len(states)):visit(i)
    return np.array(result)
def posed_vertices(model,states,skeleton):
    bind=globals_for(model['nodes'],model['nodes']);pose=globals_for(states,skeleton)
    names={n['name']:i for i,n in enumerate(skeleton)}
    skin=np.array([pose[names[n['name']]]@np.linalg.inv(bind[i]) for i,n in enumerate(model['nodes'])])
    p=np.c_[np.asarray(model['vertices']),np.ones(len(model['vertices']))];out=np.zeros((len(p),3))
    for i,(n0,n1,w) in enumerate(model['weights']):
        out[i]=(skin[n0]@p[i])[:3]*(1-w)
        if n1>=0 and w>0:out[i]+=(skin[n1]@p[i])[:3]*w
    return out

def texture_paths(model,key='textures_fullres'):
    paths=model.get(key,model.get('textures',[]))
    if isinstance(paths,dict):paths=[paths.get(str(i),paths.get(i)) for i in range(len(model['textures']))]
    return paths

def source_mesh(model,vertices=None,family='world'):
    faces=np.asarray(model['faces'],dtype=int)
    p=np.asarray(model['vertices'] if vertices is None else vertices)[faces]
    textures=list(texture_paths(model));masks=model.get('team_masks',model.get('multipurpose_fullres',model.get('material_multipurpose',[])))
    if family=='fp' and model.get('material_change_source'):
        masks=[p if model['material_change_source'][i]==3 else None for i,p in enumerate(masks)]
    colors=list(model.get('material_colors',[None]*len(textures)))
    for i,c in enumerate(model.get('material_overrides',[])):
        if c is not None:
            colors[i]=c
            # Native meter/glass proxies replace the bitmap on these materials.
            # The packer applies this same explicit override.
            if i<len(textures):textures[i]=None
    uv=np.asarray(model['uv'],dtype=float)[faces].copy()
    if family=='world' and model.get('uv_origin')!='top-left':uv[...,1]=1-uv[...,1]
    return Mesh(engine(p),uv=uv,materials=np.asarray(model['materials']),
                textures=textures,masks=masks,source=True,family=family,
                provenance=f"{model.get('source_lod','legacy extracted LOD')} / {len(faces):,} triangles",material_colors=colors)

def concat_mesh(a,b):
    return Mesh(np.concatenate((a.p,b.p)),uv=np.concatenate((a.uv,b.uv)),
                materials=np.r_[a.materials,b.materials+len(a.textures)],textures=a.textures+b.textures,
                masks=(a.masks or [None]*len(a.textures))+(b.masks or [None]*len(b.textures)),
                source=True,family='fp',provenance=a.provenance+' + '+b.provenance,material_colors=(a.material_colors or [None]*len(a.textures))+(b.material_colors or [None]*len(b.textures)))

def packed_c(path,prefix,scale,model_scales=None):
    text=Path(path).read_text();out={}
    arrays=re.findall(r'static T3DVertPacked '+prefix+r'_(\w+)\[\].*?=\{(.*?)\n\};',text,re.S)
    pair=re.compile(r'\{\{(-?\d+),(-?\d+),(-?\d+)\},\d+,\{(-?\d+),(-?\d+),(-?\d+)\},\d+,0x([0-9a-fA-F]+),0x([0-9a-fA-F]+),')
    for name,body in arrays:
        p=[];rgb=[];local_scale=(model_scales or {}).get(name,scale)
        for v in pair.findall(body):
            p.extend(([int(x)/local_scale for x in v[:3]],[int(x)/local_scale for x in v[3:6]]))
            for value in v[6:]:
                color=int(value,16);rgb.append(((color>>24)&255,(color>>16)&255,(color>>8)&255))
        count=len(p)//3*3
        if count:out[name]=Mesh(np.asarray(p[:count]).reshape(-1,3,3),np.asarray(rgb[:count],dtype=float).reshape(-1,3,3),family='fp' if prefix=='fp' else 'world',provenance='Exact packed positions and vertex RGB')
    if not out:raise ValueError('No packed vertices found: '+str(path))
    return out

def preview(path,fallback):
    if not Path(path).exists():return fallback
    data=load(path);models=data.get('models',data.get('weapons',data))
    for name,m in models.items():
        if not isinstance(m,dict) or 'positions' not in m:continue
        p=np.asarray(m['positions'],dtype=float).reshape(-1,3,3)
        colors=np.asarray(m.get('colors',m.get('rgb',[])),dtype=float)
        if colors.size==0:continue
        colors=colors.reshape(len(p),3,-1)[...,:3]
        tm=np.asarray(m['team_mask'],dtype=float).reshape(len(p),3) if 'team_mask' in m else None
        if tm is not None and tm.max()>1:tm/=255
        fallback[name]=Mesh(p,colors,team_mask=tm,family='fp' if 'firstperson' in str(path) else 'world',provenance='Exact packer preview positions and vertex RGB')
    return fallback

def animate_spartan(mesh,data,lod=False,scale=32):
    a=data.get('animations_lod' if lod else 'animations',{}).get('idle')
    if a and np.asarray(a['frames'][0]).size==mesh.p.size:
        return replace(mesh,p=np.round(engine(a['frames'][0])*scale).reshape(-1,3,3)/scale)
    return mesh

def tinted(mesh,team,before=False):
    if mesh.source:return replace(mesh,team=team)
    rgb=mesh.rgb.copy()
    if mesh.team_mask is not None:mask=mesh.team_mask
    else:mask=((np.abs(rgb[...,0]-rgb[...,1])<20)&(np.abs(rgb[...,0]-rgb[...,2])<20)).astype(float)
    rgb*=1-mask[...,None]+mask[...,None]*np.array(team)[None,None,:]/255
    rgb=np.floor(rgb) if before else np.round(rgb)
    return replace(mesh,rgb=rgb)

@lru_cache(maxsize=128)
def image_array(path):
    if not path or not Path(path).exists():return None
    return np.asarray(Image.open(path).convert('RGBA'),dtype=float)

def sample_texture(texture,uv,fallback=(130,133,135)):
    if texture is None:return np.broadcast_to(np.asarray(fallback,dtype=float),uv.shape[:-1]+(3,)).copy()
    h,w=texture.shape[:2];x=np.floor((uv[...,0]%1)*w).astype(int)%w;y=np.floor((uv[...,1]%1)*h).astype(int)%h
    return texture[y,x,:3]

def camera_basis(direction):
    look=np.asarray(direction,dtype=float);look/=np.linalg.norm(look)
    up=np.array((0.,1.,0.)) if abs(look[1])<.98 else np.array((0.,0.,-1.))
    right=np.cross(up,look);right/=np.linalg.norm(right);up=np.cross(look,right)
    return look,right,up

def matching_bounds(meshes,direction):
    _,right,up=camera_basis(direction)
    points=np.concatenate([m.p.reshape(-1,3) for m in meshes])
    xy=np.stack((points@right,points@up),axis=-1);low=xy.min(axis=0);high=xy.max(axis=0);mid=(low+high)/2
    return right*mid[0]+up*mid[1],np.maximum(high-low,1e-5)

def render(mesh,bounds,direction,width=224,height=184,pixel_span=None):
    center,span=bounds;look,right,up=camera_basis(direction)
    relative=mesh.p-center;scale=pixel_span/max(span) if pixel_span is not None else min(width/span[0],height/span[1])*.80
    screen=np.stack((relative@right*scale+width/2,-relative@up*scale+height/2),axis=-1);depth=relative@look
    rgb=np.broadcast_to(BG,(height,width,3)).copy();zbuf=np.full((height,width),-np.inf);mask=np.zeros((height,width),bool)
    lightdir=np.array((.25,.83,.49))
    for ti,(t,d) in enumerate(zip(screen,depth)):
        x0=max(0,int(np.floor(t[:,0].min())));x1=min(width-1,int(np.ceil(t[:,0].max())))
        y0=max(0,int(np.floor(t[:,1].min())));y1=min(height-1,int(np.ceil(t[:,1].max())))
        if x1<x0 or y1<y0:continue
        det=(t[1,1]-t[2,1])*(t[0,0]-t[2,0])+(t[2,0]-t[1,0])*(t[0,1]-t[2,1])
        if abs(det)<1e-8:continue
        xx,yy=np.meshgrid(np.arange(x0,x1+1)+.5,np.arange(y0,y1+1)+.5)
        b0=((t[1,1]-t[2,1])*(xx-t[2,0])+(t[2,0]-t[1,0])*(yy-t[2,1]))/det
        b1=((t[2,1]-t[0,1])*(xx-t[2,0])+(t[0,0]-t[2,0])*(yy-t[2,1]))/det;b2=1-b0-b1
        zz=b0*d[0]+b1*d[1]+b2*d[2];old=zbuf[y0:y1+1,x0:x1+1]
        keep=(b0>=-1e-7)&(b1>=-1e-7)&(b2>=-1e-7)&(zz>old)
        if not np.any(keep):continue
        weights=np.stack((b0[keep],b1[keep],b2[keep]),axis=-1)
        if mesh.source:
            uv=weights@mesh.uv[ti];mat=int(mesh.materials[ti]);tex=image_array(mesh.textures[mat]) if mat<len(mesh.textures) else None
            fallback=mesh.material_colors[mat] if mesh.material_colors and mat<len(mesh.material_colors) else None
            fallback=(130,133,135) if fallback is None else fallback
            colors=sample_texture(tex,uv,fallback)
            if mesh.team is not None and mat<len(mesh.masks or []):
                multip=image_array(mesh.masks[mat]);amount=sample_texture(multip,uv,(0,0,0))[:,2]/255 if multip is not None else np.zeros(len(uv))
                colors*=1-amount[:,None]+amount[:,None]*np.asarray(mesh.team)/255
            n=np.cross(mesh.p[ti,1]-mesh.p[ti,0],mesh.p[ti,2]-mesh.p[ti,0]);n/=max(1e-12,np.linalg.norm(n))
            base=.78 if mesh.family=='fp' else .68;colors*=base+(1-base)*max(0,n@lightdir)
        else:colors=weights@mesh.rgb[ti]
        old[keep]=zz[keep];rgb[y0:y1+1,x0:x1+1][keep]=np.clip(np.round(colors),0,255).astype(np.uint8);mask[y0:y1+1,x0:x1+1][keep]=True
    return Image.fromarray(rgb),mask

def compare(source,image,mask,other_mask):
    a=np.asarray(source,dtype=float);b=np.asarray(image,dtype=float);overlap=mask&other_mask;union=mask|other_mask
    iou=float(overlap.sum()/max(1,union.sum()));mae=float(np.abs(a[overlap]-b[overlap]).mean()/255) if overlap.any() else None
    errors=[]
    for y in range(0,a.shape[0],8):
        for x in range(0,a.shape[1],8):
            m=overlap[y:y+8,x:x+8]
            if m.sum()>=8:errors.append(float(np.abs(a[y:y+8,x:x+8][m].mean(axis=0)-b[y:y+8,x:x+8][m].mean(axis=0)).mean()/255))
    return {'silhouette_iou':iou,'overlap_rgb_mae':mae,'color_block_mae':float(np.mean(errors)) if errors else None,'reference_pixels':int(mask.sum()),'packed_pixels':int(other_mask.sum()),'overlap_pixels':int(overlap.sum())}


def font(size=15):
    for p in ('/System/Library/Fonts/Supplemental/Arial.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if Path(p).exists():return ImageFont.truetype(p,size)
    return ImageFont.load_default()
def label(im,text,xy=(8,5),size=14,fill=(21,31,43)):
    ImageDraw.Draw(im).text(xy,text,font=font(size),fill=fill)
def build_catalog(ref_world,ref_fp,before_world,before_fp,after_world,after_fp,before_data,after_data,before_fpd,after_fpd,after_scale=32,model_scales=None):
    catalog=[]
    def add(name,title,group,source,old,new):
        if old is None or new is None:raise ValueError('Missing packed model '+name)
        catalog.append((name,title,group,source,old,new))
    for name in GUNS+('frag','plasma_grenade','healthpack','overshield','camouflage'):
        add('world_'+name,'World '+name.replace('_',' '),'World weapons and pickups',source_mesh(ref_world['models'][name]),before_world.get(name),after_world.get(name))
    for name in VEHICLES:
        ref=source_mesh(ref_world['models'][name])
        for lod in ('','_lod'):add(name+lod,name.title()+(' far LOD' if lod else ' near LOD'),'Vehicles',ref,before_world.get(name+lod),after_world.get(name+lod))
    sp=ref_world['models']['spartan'];pose=ref_world['animations']['idle']['frames'][0]
    source=source_mesh(sp,posed_vertices(sp,pose,sp['nodes']))
    for lod in ('','_lod'):
        old=animate_spartan(before_world['spartan'+lod],before_data,bool(lod));new=animate_spartan(after_world['spartan'+lod],after_data,bool(lod),(model_scales or {}).get('spartan'+lod,after_scale))
        for color,team in TEAMS.items():add('spartan'+lod+'_'+color,'Spartan '+color+(' far LOD' if lod else ''),'Spartan',tinted(source,team),tinted(old,team,True),tinted(new,team))
    hands=ref_fp['hands'];source_hands=None
    for name in GUNS:
        weapon=ref_fp['weapons'][name];states=weapon['clips']['idle']['frames'][0];nodes=weapon['nodes']
        h=source_mesh(hands,posed_vertices(hands,states,nodes),'fp');gun=weapon['gun'];g=source_mesh(gun,posed_vertices(gun,states,nodes),'fp')
        new_fp=after_fp.get(name)
        if new_fp is not None and new_fp.team_mask is not None:new_fp=tinted(new_fp,TEAMS['red'])
        add('fp_'+name,'First person '+name.replace('_',' ')+' with hands','First-person weapons',tinted(concat_mesh(h,g),TEAMS['red']),before_fp.get(name),new_fp)
        before_hands=before_fpd['weapons'][name].get('hand_triangle_count',100)
        after_hands=after_fpd['weapons'][name].get('hand_triangle_count',after_fpd.get('hand_triangle_count',100))
        old_gun=before_fp[name]
        add('fp_gun_'+name,'First person '+name.replace('_',' ')+' gun only','First-person gun geometry',tinted(g,TEAMS['red']),
            replace(old_gun,p=old_gun.p[before_hands:],rgb=old_gun.rgb[before_hands:]),
            replace(new_fp,p=new_fp.p[after_hands:],rgb=new_fp.rgb[after_hands:]))
        if name=='ar':source_hands=tinted(h,TEAMS['red'])
    old_count=before_fpd['weapons']['ar'].get('hand_triangle_count',100)
    new_count=after_fpd['weapons']['ar'].get('hand_triangle_count',after_fpd.get('hand_triangle_count',100))
    old=before_fp['ar'];new=after_fp['ar']
    if new.team_mask is not None:new=tinted(new,TEAMS['red'])
    add('hands','First-person hands (AR idle pose)','Hands',source_hands,replace(old,p=old.p[:old_count],rgb=old.rgb[:old_count]),replace(new,p=new.p[:new_count],rgb=new.rgb[:new_count]))
    return catalog


def audit(args):
    output=args.output;output.mkdir(parents=True,exist_ok=True);(output/'images').mkdir(exist_ok=True)
    before=output/'before';reference=output/'reference';assets=args.assets;generated=args.generated
    rw=reference/'extended-raw.json';rf=reference/'firstperson-raw.json'
    if not rw.exists() or not rf.exists():
        if not args.allow_legacy_reference:raise FileNotFoundError('Highest-source reference JSON missing; coordinate extraction or use explicitly labeled --allow-legacy-reference')
        rw=before/'extended-raw.json';rf=before/'firstperson-raw.json'
    refw,reff=load(rw),load(rf)
    bw=packed_c(before/'models_data.c','model',32);bf=packed_c(before/'firstperson_data.c','fp',256)
    report=load(generated/'extended-report.json') if (generated/'extended-report.json').exists() else {}
    aw=preview(generated/'model-preview.json',packed_c(generated/'models_data.c','model',report.get('position_scale',32),report.get('model_position_scales')));af=preview(generated/'firstperson-preview.json',packed_c(generated/'firstperson_data.c','fp',256))
    bd,ad=load(before/'extended-reduced.json'),load(assets/'extended-reduced.json')
    bfd,afd=load(before/'firstperson-reduced.json'),load(assets/'firstperson-reduced.json')
    catalog=build_catalog(refw,reff,bw,bf,aw,af,bd,ad,bfd,afd,report.get('position_scale',32),report.get('model_position_scales'))
    if args.only:catalog=[item for item in catalog if any(s in item[0] for s in args.only.split(','))]
    inputs=[rw,rf,before/'models_data.c',before/'firstperson_data.c',generated/'models_data.c',generated/'firstperson_data.c',before/'extended-reduced.json',before/'firstperson-reduced.json',assets/'extended-reduced.json',assets/'firstperson-reduced.json']
    inputs.extend(p for p in (generated/'model-preview.json',generated/'firstperson-preview.json',generated/'extended-report.json') if p.exists())
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    texture_inputs=set()
    for _,_,_,mesh,_,_ in catalog:
        texture_inputs.update(p for p in (mesh.textures or [])+(mesh.masks or []) if p and Path(p).exists())
    texture_hashes={str(Path(p).relative_to(ROOT)):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in sorted(texture_inputs)}
    legacy=rw.parent==before;source_label='Lower LOD (provisional)' if legacy else 'Original highest LOD';results=[];overviews={};started=time.monotonic()
    for index,(name,title,group,source,old,new) in enumerate(catalog):
        meshes=(source,old,new)
        width,height=args.size,round(args.size*.82);sheet=Image.new('RGB',(90+3*width,40+len(ANGLES)*(height+28)),tuple(BG));label(sheet,title,(8,8),16)
        metrics=[];hero=None
        for row,(angle,direction) in enumerate(ANGLES):
            bounds=matching_bounds(meshes,direction)
            src,sm=render(source,bounds,direction,width,height);oldim,om=render(old,bounds,direction,width,height);newim,nm=render(new,bounds,direction,width,height)
            metrics.append({'angle':angle,'before':compare(src,oldim,sm,om),'after':compare(src,newim,sm,nm)})
            y=40+row*(height+28);label(sheet,angle,(4,y+8),12)
            for column,(im,title2) in enumerate(((src,source_label),(oldim,'Before packed RGB'),(newim,'Revised packed RGB'))):
                sheet.paste(im,(90+column*width,y+22));label(sheet,title2,(90+column*width+6,y+2),12)
            if row==4:hero=(src,oldim,newim)
        sheet.save(output/'images'/(name+'.png'))
        # Actual 160x120 viewport-size rasterization, displayed with nearest
        # neighbor scaling so no invented detail smooths the demake.
        small=Image.new('RGB',(3*320,34+240),tuple(BG))
        for column,(mesh,title2) in enumerate(((source,source_label),(old,'Before'),(new,'Revised'))):
            im,_=render(mesh,matching_bounds(meshes,ANGLES[4][1]),ANGLES[4][1],160,120);small.paste(im.resize((320,240),Image.Resampling.NEAREST),(column*320,34));label(small,title2,(column*320+8,8))
        small.save(output/'images'/(name+'-160x120.png'))
        distance=Image.new('RGB',(960,2*274),tuple(BG));distance_metrics=[]
        for row,pixel_span in enumerate((48,24)):
            frames=[render(mesh,matching_bounds(meshes,ANGLES[4][1]),ANGLES[4][1],160,120,pixel_span) for mesh in meshes]
            src,sm=frames[0]
            distance_metrics.append({'maximum_projected_extent_pixels':pixel_span,'before':compare(src,frames[1][0],sm,frames[1][1]),'after':compare(src,frames[2][0],sm,frames[2][1])})
            for column,((im,_),title2) in enumerate(zip(frames,(source_label,'Before','Revised'))):
                distance.paste(im.resize((320,240),Image.Resampling.NEAREST),(column*320,row*274+34));label(distance,f'{title2} / {pixel_span}px extent',(column*320+8,row*274+8))
        distance.save(output/'images'/(name+'-distance.png'))
        avg={stage:{key:float(np.mean([m[stage][key] for m in metrics if m[stage][key] is not None])) for key in ('silhouette_iou','overlap_rgb_mae','color_block_mae')} for stage in ('before','after')}
        result={'id':name,'title':title,'group':group,'triangles':{'source':len(source.p),'before':len(old.p),'after':len(new.p)},'average':avg,'angles':metrics,'distance_readability':distance_metrics,'source_provenance':source.provenance}
        results.append(result);overviews.setdefault(group,[]).append((name,title,hero))
        print(f'{index+1}/{len(catalog)} {name}: IoU {avg["before"]["silhouette_iou"]:.3f}->{avg["after"]["silhouette_iou"]:.3f}; color {avg["before"]["color_block_mae"]:.3f}->{avg["after"]["color_block_mae"]:.3f}',flush=True)
    for group,rows in overviews.items():
        width,height=args.size,round(args.size*.82);im=Image.new('RGB',(90+width*3,(height+30)*len(rows)+28),tuple(BG))
        for col,title in enumerate((source_label,'Before exact packed','Revised exact packed')):label(im,title,(90+col*width+8,4),12)
        for row,(name,title,hero) in enumerate(rows):
            y=28+row*(height+30);label(im,title,(8,y+4),12)
            for col,frame in enumerate(hero):im.paste(frame,(90+col*width,y+26))
        im.save(output/'images'/('overview-'+group.lower().replace(' ','-')+'.png'))
    for rel,digest in {**hashes,**texture_hashes}.items():
        if hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()!=digest:
            raise RuntimeError(f'Audit input changed during rendering: {rel}. Regenerate from stable packed assets.')
    manifest={'reference_is_legacy_low_lod':legacy,'renderer':'orthographic CPU barycentric z-buffer; no backface culling; exact packed vertex RGB; fixed neutral source lighting',
              'angles':[a for a,_ in ANGLES],'viewport_preview':[160,120],'distance_preview_extent_pixels':[48,24],'color_metric':'Mean absolute RGB deviation on overlapping silhouettes; 8x8 block means. Lower is better; not a perceptual recognition score.',
              'texture_inputs':texture_hashes,'inputs':hashes,'revised_is_frozen_baseline':hashlib.sha256((before/'models_data.c').read_bytes()).digest()==hashlib.sha256((generated/'models_data.c').read_bytes()).digest() and hashlib.sha256((before/'firstperson_data.c').read_bytes()).digest()==hashlib.sha256((generated/'firstperson_data.c').read_bytes()).digest(),'results':results,'elapsed_seconds':time.monotonic()-started}
    (output/'metrics.json').write_text(json.dumps(manifest,indent=2)+'\n');write_html(output,manifest)
    print('Report:',output/'index.html',flush=True)


CUES={
    'ar':'Carry handle, barrel width, receiver and magazine profile.',
    'pistol':'Barrel/slide width, grip, and the trigger-guard opening.',
    'plasma_pistol':'Open horseshoe silhouette, paired plasma prongs, and cyan tips.',
    'plasma_rifle':'Twin forward prongs, curved grip, and purple/cyan color blocks.',
    'needler':'The row of crystal needles, curved housing, and luminous color contrast.',
    'shotgun':'Long barrel, separate pump, pistol grip, and shoulder stock.',
    'sniper':'Long thin barrel, scope, magazine and shoulder-stock separation.',
    'rocket':'Two launcher tubes, carry assembly and rear shoulder stock.',
    'frag':'Round body and the small upper fuse/lever silhouette.',
    'plasma_grenade':'Round plasma-grenade silhouette and luminous blue coloration.',
    'warthog':'Four wheels, open cabin, windscreen, passenger seat and rear turret.',
    'ghost':'Twin wing lobes, open driver saddle and swept front profile.',
    'scorpion':'Separated track housings, raised turret and long cannon.',
    'banshee':'Closed canopy, curved wing tips, rear fins and purple body.',
    'spartan':'Helmet/visor separation, shoulder and forearm mass, undersuit and leg gaps.',
    'hands':'Forearm volume, wrist transitions, fingers and grip contact.',
    'healthpack':'Rectangular pack silhouette and medical markings.',
    'overshield':'Pickup silhouette; the runtime orange tint is an intentional identification cue.',
    'camouflage':'Pickup silhouette; the runtime blue tint is an intentional identification cue.'}
REVIEW_NOTES={
    'spartan':'Armor and undersuit colors are separated using the original mask. The joined armor shell restores continuous chest, shoulder and limb volume; both LODs remain visibly faceted. Armor color becomes dark at 24-pixel size, especially blue.',
    'hands':'The revised forearms retain substantially more volume and continuous wrist connections. Fingers and forearm curves are still coarse; compare the gun-and-hands views as well as the isolated hands.',
    'needler':'The revised pink crystal row survives the small previews. The shell is angular and its source reflections are approximated with diffuse/flat colors.',
    'warthog':'The revised far model restores a coherent cabin and wheel arrangement. Tire circles, windshield and turret are simplified; the 24-pixel view is the useful distant-reading check.',
    'ghost':'The revised hull retains both swept lobes and the open saddle. Fine mechanical details and reflective surface response are absent.',
    'scorpion':'Track housings, turret and barrel remain separate. Far-LOD color error is higher than before in this diffuse-only comparison; tread detail is not reproduced.',
    'banshee':'The closed canopy and curved wing outline are retained in both distances. Metallic reflections and fine surface detail are outside the vertex-color approximation.',
    'world_frag':'The body and upper lever are recognizable again, with a deliberately faceted lower shell. Small lettering and surface grooves are absent.',
    'world_plasma_grenade':'The higher body budget restores a round silhouette across the eight views. Fine panel markings and luminous shader effects remain approximated by broad vertex colors.',
    'healthpack':'The rectangular silhouette is improved, but the small red medical cross is lost in the vertex-color approximation.',
    'overshield':'The orange runtime identification color is intentional and increases error against this dark diffuse-only source proxy; no Xbox active-shield shader is reproduced.',
    'camouflage':'The blue runtime identification color is intentional and increases error against this dark diffuse-only source proxy; no Xbox camouflage shader is reproduced.'}
def findings(r):
    b,a=r['average']['before'],r['average']['after'];delta=a['silhouette_iou']-b['silhouette_iou'];cd=b['color_block_mae']-a['color_block_mae']
    shape=f"Mean silhouette IoU {'increased' if delta>=0 else 'decreased'} by {abs(delta):.3f}."
    colors=f"Overlap color-block error {'decreased' if cd>=0 else 'increased'} by {abs(cd):.3f}."
    worst=min(r['angles'],key=lambda x:x['after']['silhouette_iou'])
    cue=next((v for k,v in CUES.items() if k in r['id']),'Inspect the silhouette and large material color regions.')
    note=next((v for k,v in REVIEW_NOTES.items() if k in r['id']), 'The main weapon outline is retained more closely; fine markings, small controls and curved surfaces remain reduced to vertex colors and planar faces.')
    return note+' '+shape+' '+colors+f" Lowest revised silhouette agreement: {worst['angle']} ({worst['after']['silhouette_iou']:.3f}). Inspection cues: "+cue

def runtime_validation_html(output):
    """Optional emulator evidence; relative media paths resolve from the report."""
    path=output/'runtime-validation.json'
    if not path.is_file():return ''
    data=load(path)
    if not isinstance(data,dict):raise ValueError('runtime-validation.json must contain an object')
    fields=(('emulator','Emulator'),('ram_mib','RAM (MiB)'),('rdp_errors','RDP errors'),
            ('rdp_warnings','RDP warnings'),('observed_profile_fps','Observed profile FPS'),
            ('heap_free_kib','Free heap (KiB)'))
    parts=['<section class="runtime"><h2>Runtime validation</h2><table>']
    for key,label_text in fields:
        if data.get(key) is not None:
            parts.append(f'<tr><th>{label_text}</th><td>{html.escape(str(data[key]))}</td></tr>')
    parts.append('</table>')
    if data.get('note'):parts.append('<p>'+html.escape(str(data['note']))+'</p>')
    for key in ('screenshot','recording'):
        value=data.get(key)
        if not isinstance(value,str) or not value:continue
        media=Path(value)
        if not media.is_absolute():media=output/media
        if not media.is_file():continue
        href=html.escape(quote(os.path.relpath(media.resolve(),output.resolve()),safe='/'),quote=True)
        if key=='screenshot':
            parts.append(f'<p><a href="{href}"><img loading="lazy" src="{href}" alt="Emulator runtime validation screenshot"></a></p>')
        else:
            parts.append(f'<video controls preload="metadata" style="max-width:100%" src="{href}"></video><p><a href="{href}">Open emulator gameplay recording</a></p>')
    parts.append('</section>')
    return '\n'.join(parts)


def write_html(output,manifest):
    parts=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Blood Gulch model audit</title>',
           '<style>body{background:#111923;color:#dce6f2;font:15px system-ui;margin:32px auto;max-width:1200px;padding:0 20px}a{color:#84c9ff}p{line-height:1.6}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}td,th{padding:9px;border-bottom:1px solid #314153;text-align:left}img{max-width:100%;height:auto;background:#161d27}summary{cursor:pointer;padding:14px;font-size:17px}details{border:1px solid #314153;margin:16px 0;border-radius:8px;padding:8px}.warning{background:#47341e;padding:14px}.up{color:#93dfb2}.down{color:#ffb09d}nav a{display:inline-block;margin:8px}code{color:#addbff}</style>',
           '<h1>Blood Gulch model comparison</h1><p>Original highest-detail source geometry and diffuse maps, the frozen pre-revision N64 build, and the current packed N64 build. Within each angle, all three models share scale, pose, camera, and background; framing fits the combined projected bounds to 80% of the panel. Packed colors include their original baked lighting; the source uses the same neutral light direction. These are offline model diagnostics, not screenshots of the Xbox renderer or ares.</p>',
           '<p>Source surfaces use the full diffuse textures when available; native flat color proxies represent complex meter and glass materials. Xbox environment mapping, specular, emissive, and transparency effects are not reconstructed. Original Xbox multipurpose blue masks tint Spartan armor; first-person change-color C uses player-one red for a matching source/revised comparison. The before column keeps its actual old untinted first-person colors. Geometry is rendered from both sides so winding does not hide silhouette defects. The 160×120 strips rasterize at a four-player viewport size and enlarge using nearest neighbor; the fit-to-model camera helps inspect detail and does not imply every model is that large during gameplay. Additional 48-pixel and 24-pixel maximum-extent strips show detail loss when models occupy smaller parts of that viewport; these are screen-size probes, not calibrated in-game distances.</p>']
    if manifest.get('revised_is_frozen_baseline'):parts.append('<p class="warning">IN PROGRESS: the revised pack has not been generated. The right column still duplicates the frozen build and is not a completed revision.</p>')
    if manifest['reference_is_legacy_low_lod']:parts.append('<p class="warning">PROVISIONAL: highest-source extraction has not arrived. Source column is explicitly the old low-LOD extraction, not the original highest-detail model.</p>')
    parts.append('<p>Silhouette intersection-over-union (IoU): higher is better. Color block error (including the approximation of baked lighting): mean RGB error on overlapping 8×8 blocks, normalized 0–1; lower is better. Color error excludes angles without silhouette overlap; those missing surfaces are measured by IoU. Neither metric measures player recognition or original shader fidelity. Thin parts and absent pixels require inspection of the silhouettes and the small previews.</p>')
    comparisons=manifest['results']
    mean_before=float(np.mean([r['average']['before']['silhouette_iou'] for r in comparisons]));mean_after=float(np.mean([r['average']['after']['silhouette_iou'] for r in comparisons]))
    color_before=float(np.mean([r['average']['before']['color_block_mae'] for r in comparisons]));color_after=float(np.mean([r['average']['after']['color_block_mae'] for r in comparisons]))
    improved=sum(r['average']['after']['silhouette_iou']>r['average']['before']['silhouette_iou'] for r in comparisons)
    parts.append(f'<p><strong>{improved} of {len(comparisons)} catalog entries improve their eight-view average silhouette IoU.</strong> The equally weighted catalog mean is {mean_before:.3f} before and {mean_after:.3f} revised; mean color-block error is {color_before:.3f} before and {color_after:.3f} revised. This catalog includes separate color/LOD/first-person variants of shared geometry, so this is a diagnostic comparison, not a count of independent assets or a recognition rating.</p>')
    parts.append(runtime_validation_html(output));parts.append('<nav>')
    groups=list(dict.fromkeys(r['group'] for r in manifest['results']))
    for group in groups:parts.append(f"<a href=\"#{group.lower().replace(' ','-')}\">{html.escape(group)}</a>")
    parts.append('</nav><p><a href="metrics.json">Full metrics and input SHA-256 provenance</a></p>')
    for group in groups:
        parts.append(f"<h2 id=\"{group.lower().replace(' ','-')}\">{html.escape(group)}</h2>")
        parts.append('<table><tr><th>Model</th><th>Triangles source / before / revised</th><th>IoU before → revised</th><th>Color error before → revised</th></tr>')
        rows=[r for r in manifest['results'] if r['group']==group]
        for r in rows:
            b,a=r['average']['before'],r['average']['after'];t=r['triangles'];color='up' if a['silhouette_iou']>=b['silhouette_iou'] else 'down'
            parts.append(f'<tr><td><a href="#{r["id"]}">{html.escape(r["title"])}</a></td><td>{t["source"]:,} / {t["before"]:,} / {t["after"]:,}</td><td class="{color}">{b["silhouette_iou"]:.3f} → {a["silhouette_iou"]:.3f}</td><td>{b["color_block_mae"]:.3f} → {a["color_block_mae"]:.3f}</td></tr>')
        parts.append('</table>')
        overview='overview-'+group.lower().replace(' ','-')+'.png';parts.append(f'<a href="images/{overview}"><img loading="lazy" src="images/{overview}" alt="{html.escape(group)} source before revised overview"></a>')
        for r in rows:
            name=r['id'];parts.append(f'<details id="{name}"><summary>{html.escape(r["title"])} — eight matching angles and 160×120 readability</summary><p>Source: {html.escape(r["source_provenance"])}</p><p>{html.escape(findings(r))}</p><a href="images/{name}.png"><img loading="lazy" src="images/{name}.png" alt="Eight angles of {html.escape(r["title"])}"></a><img loading="lazy" src="images/{name}-160x120.png" alt="160 by 120 viewport-size comparison"><img loading="lazy" src="images/{name}-distance.png" alt="48 and 24 pixel extent comparison in a 160 by 120 viewport"></details>')
    parts.append('</html>');(output/'index.html').write_text('\n'.join(parts))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT/'build/n64/model-audit')
    parser.add_argument('--assets',type=Path,default=ROOT/'build/n64/assets');parser.add_argument('--generated',type=Path,default=ROOT/'build/n64/generated')
    parser.add_argument('--size',type=int,default=224);parser.add_argument('--only',help='Comma-separated substrings of catalog IDs');parser.add_argument('--allow-legacy-reference',action='store_true')
    parser.add_argument('--html-only',action='store_true',help='Refresh index.html from existing metrics and optional runtime-validation.json; do not rerender images')
    args=parser.parse_args()
    if args.html_only:
        write_html(args.output,load(args.output/'metrics.json'));print('Report:',args.output/'index.html')
    else:audit(args)
