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
    diffuse_atlas:str|None=None


def load(path):return json.loads(Path(path).read_text())
def provenance_path(path):
    """Store local inputs relative to the repo and external inputs absolutely."""
    resolved=Path(path).resolve()
    try:return str(resolved.relative_to(ROOT))
    except ValueError:return str(resolved)
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
        if m.get('texture'):
            fallback[name]=replace(fallback[name],uv=np.asarray(m['uvs'],dtype=float).reshape(-1,3,2)/[2048,1024],diffuse_atlas=m['texture'])
    return fallback

def packed_models(directory,firstperson=False,report=None):
    """Previews preserve triangle order even when C uses indexed batches."""
    path=directory/('firstperson-preview.json' if firstperson else 'model-preview.json')
    if path.exists():return preview(path,{})
    report=report or {}
    packed=directory/('firstperson_data.c' if firstperson else 'models_data.c')
    if 'static const bg_mesh_batch' in packed.read_text():
        raise ValueError(f'Indexed models require the expanded triangle preview: {path}')
    return packed_c(packed,
        'fp' if firstperson else 'model',256 if firstperson else report.get('position_scale',32),
        None if firstperson else report.get('model_position_scales'))

def packing_statistics(before_world,after_world,before_fp,after_fp):
    """Stored-vertex savings are distinct from triangle geometry reductions."""
    world_vertices=after_world.get('vertices',{})
    retained={n:v for n,v in world_vertices.items() if not n.endswith('_pickup_lod')}
    return {'world_vertices_before':before_world.get('model_bytes',0)//16,
            'world_vertices_after_existing_banks':sum(retained.values()),
            'world_vertices_after_new_far_banks':sum(v for n,v in world_vertices.items() if n.endswith('_pickup_lod')),
            'fp_vertices_before':sum((v+1)//2*2 for v in before_fp.get('vertices',{}).values()),
            'fp_vertices_after':sum(after_fp.get('vertices',{}).values()),
            'fp_bank_bytes_before':before_fp.get('total_bytes'),
            'fp_bank_bytes_after':after_fp.get('total_bytes'),
            'maximum_color_weld_channel_delta':max(after_world.get('color_weld_max_channel_delta',0),after_fp.get('color_weld_tolerance',0)),
            'model_color_tolerances':{'world':after_world.get('color_weld_tolerances',{}),'first-person':after_fp.get('color_weld_tolerances',{})}}

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
    rgb=np.floor(rgb) if before and mesh.team_mask is None else np.round(rgb)
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

def render(mesh,bounds,direction,width=224,height=184,pixel_span=None,cull="back"):
    center,span=bounds;look,right,up=camera_basis(direction)
    relative=mesh.p-center;scale=pixel_span/max(span) if pixel_span is not None else min(width/span[0],height/span[1])*.80
    screen=np.stack((relative@right*scale+width/2,-relative@up*scale+height/2),axis=-1);depth=relative@look
    rgb=np.broadcast_to(BG,(height,width,3)).copy();zbuf=np.full((height,width),-np.inf);mask=np.zeros((height,width),bool)
    lightdir=np.array((.25,.83,.49))
    for ti,(t,d) in enumerate(zip(screen,depth)):
        normal=np.cross(mesh.p[ti,1]-mesh.p[ti,0],mesh.p[ti,2]-mesh.p[ti,0])
        facing=normal@look
        if (cull=="back" and facing<=0) or (cull=="front" and facing>=0):continue
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
        else:
            colors=weights@mesh.rgb[ti]
            if mesh.diffuse_atlas:
                tex=sample_texture(image_array(mesh.diffuse_atlas),weights@mesh.uv[ti]).astype(np.uint8)>>3
                colors*=((tex<<3)|(tex>>2))/255
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
def build_catalog(ref_world,ref_fp,before_world,before_fp,after_world,after_fp,before_data,after_data,before_fpd,after_fpd,after_scale=32,model_scales=None,before_scale=32,before_model_scales=None):
    catalog=[]
    def add(name,title,group,source,old,new):
        if old is None or new is None:raise ValueError('Missing packed model '+name)
        catalog.append((name,title,group,source,old,new))
    for name in GUNS+('frag','plasma_grenade','healthpack','overshield','camouflage'):
        add('world_'+name,'World '+name.replace('_',' '),'World weapons and pickups',source_mesh(ref_world['models'][name]),before_world.get(name),after_world.get(name))
        if name+'_pickup_lod' in after_world:
            add('pickup_lod_'+name,'Distant '+name.replace('_',' '),'Distant pickups',source_mesh(ref_world['models'][name]),before_world.get(name),after_world[name+'_pickup_lod'])
    for name in VEHICLES:
        ref=source_mesh(ref_world['models'][name])
        for lod in ('','_lod'):add(name+lod,name.title()+(' far LOD' if lod else ' near LOD'),'Vehicles',ref,before_world.get(name+lod),after_world.get(name+lod))
    sp=ref_world['models']['spartan'];pose=ref_world['animations']['idle']['frames'][0]
    source=source_mesh(sp,posed_vertices(sp,pose,sp['nodes']))
    for lod in ('','_lod'):
        old=animate_spartan(before_world['spartan'+lod],before_data,bool(lod),(before_model_scales or {}).get('spartan'+lod,before_scale));new=animate_spartan(after_world['spartan'+lod],after_data,bool(lod),(model_scales or {}).get('spartan'+lod,after_scale))
        for color,team in TEAMS.items():add('spartan'+lod+'_'+color,'Spartan '+color+(' far LOD' if lod else ''),'Spartan',tinted(source,team),tinted(old,team,True),tinted(new,team))
    hands=ref_fp['hands'];source_hands=None
    for name in GUNS:
        weapon=ref_fp['weapons'][name];states=weapon['clips']['idle']['frames'][0];nodes=weapon['nodes']
        h=source_mesh(hands,posed_vertices(hands,states,nodes),'fp');gun=weapon['gun'];g=source_mesh(gun,posed_vertices(gun,states,nodes),'fp')
        new_fp=after_fp.get(name);old_fp=before_fp.get(name)
        if old_fp is not None and old_fp.team_mask is not None:old_fp=tinted(old_fp,TEAMS['red'])
        if new_fp is not None and new_fp.team_mask is not None:new_fp=tinted(new_fp,TEAMS['red'])
        add('fp_'+name,'First person '+name.replace('_',' ')+' with hands','First-person weapons',tinted(concat_mesh(h,g),TEAMS['red']),old_fp,new_fp)
        before_hands=before_fpd['weapons'][name].get('hand_triangle_count',100)
        after_hands=after_fpd['weapons'][name].get('hand_triangle_count',after_fpd.get('hand_triangle_count',100))
        old_gun=old_fp
        add('fp_gun_'+name,'First person '+name.replace('_',' ')+' gun only','First-person gun geometry',tinted(g,TEAMS['red']),
            replace(old_gun,p=old_gun.p[before_hands:],rgb=old_gun.rgb[before_hands:]),
            replace(new_fp,p=new_fp.p[after_hands:],rgb=new_fp.rgb[after_hands:]))
        if name=='ar':source_hands=tinted(h,TEAMS['red'])
    old_count=before_fpd['weapons']['ar'].get('hand_triangle_count',100)
    new_count=after_fpd['weapons']['ar'].get('hand_triangle_count',after_fpd.get('hand_triangle_count',100))
    old=before_fp['ar'];new=after_fp['ar']
    if old.team_mask is not None:old=tinted(old,TEAMS['red'])
    if new.team_mask is not None:new=tinted(new,TEAMS['red'])
    add('hands','First-person hands (AR idle pose)','Hands',source_hands,replace(old,p=old.p[:old_count],rgb=old.rgb[:old_count]),replace(new,p=new.p[:new_count],rgb=new.rgb[:new_count]))
    return catalog


def audit(args):
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True);(output/'images').mkdir(exist_ok=True)
    before=output/'before';reference=output/'reference';assets=args.assets.resolve();generated=args.generated.resolve()
    rw=reference/'extended-raw.json';rf=reference/'firstperson-raw.json'
    if not rw.exists() or not rf.exists():
        if not args.allow_legacy_reference:raise FileNotFoundError('Highest-source reference JSON missing; coordinate extraction or use explicitly labeled --allow-legacy-reference')
        rw=before/'extended-raw.json';rf=before/'firstperson-raw.json'
    refw,reff=load(rw),load(rf)
    before_report=load(before/'extended-report.json') if (before/'extended-report.json').exists() else {}
    bw=packed_models(before,report=before_report);bf=packed_models(before,True)
    report=load(generated/'extended-report.json') if (generated/'extended-report.json').exists() else {}
    aw=packed_models(generated,report=report);af=packed_models(generated,True)
    bd,ad=load(before/'extended-reduced.json'),load(assets/'extended-reduced.json')
    bfd,afd=load(before/'firstperson-reduced.json'),load(assets/'firstperson-reduced.json')
    catalog=build_catalog(refw,reff,bw,bf,aw,af,bd,ad,bfd,afd,report.get('position_scale',32),report.get('model_position_scales'),before_report.get('position_scale',32),before_report.get('model_position_scales'))
    if args.only:catalog=[item for item in catalog if any(s in item[0] for s in args.only.split(','))]
    inputs=[rw,rf,before/'models_data.c',before/'firstperson_data.c',generated/'models_data.c',generated/'firstperson_data.c',before/'extended-reduced.json',before/'firstperson-reduced.json',assets/'extended-reduced.json',assets/'firstperson-reduced.json']
    inputs.extend(p for p in (generated/'model-preview.json',generated/'firstperson-preview.json',generated/'extended-report.json',generated/'firstperson-report.json',before/'model-preview.json',before/'firstperson-preview.json',before/'extended-report.json',before/'firstperson-report.json') if p.exists())
    hashes={provenance_path(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    texture_inputs=set()
    for _,_,_,mesh,_,_ in catalog:
        texture_inputs.update(p for p in (mesh.textures or [])+(mesh.masks or []) if p and Path(p).exists())
    texture_hashes={provenance_path(p):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in sorted(texture_inputs)}
    baseline_label='Approved quality' if args.performance else 'Before packed RGB';revision_label='Optimized' if args.performance else 'Revised packed RGB'
    legacy=rw.parent==before;source_label='Lower LOD (provisional)' if legacy else 'Original highest LOD';results=[];overviews={};started=time.monotonic()
    for index,(name,title,group,source,old,new) in enumerate(catalog):
        meshes=(source,old,new)
        distant=group=='Distant pickups'
        row_baseline='Approved near model' if distant else baseline_label
        row_revision='New distant LOD' if distant else revision_label
        width,height=args.size,round(args.size*.82);sheet=Image.new('RGB',(90+3*width,40+len(ANGLES)*(height+28)),tuple(BG));label(sheet,title,(8,8),16)
        metrics=[];hero=None
        for row,(angle,direction) in enumerate(ANGLES):
            bounds=matching_bounds(meshes,direction)
            src,sm=render(source,bounds,direction,width,height);oldim,om=render(old,bounds,direction,width,height);newim,nm=render(new,bounds,direction,width,height)
            metrics.append({'angle':angle,'before':compare(src,oldim,sm,om),'after':compare(src,newim,sm,nm)})
            y=40+row*(height+28);label(sheet,angle,(4,y+8),12)
            for column,(im,title2) in enumerate(((src,source_label),(oldim,row_baseline),(newim,row_revision))):
                sheet.paste(im,(90+column*width,y+22));label(sheet,title2,(90+column*width+6,y+2),12)
            if row==4:hero=(src,oldim,newim)
        sheet.save(output/'images'/(name+'.png'))
        # Actual 160x120 viewport-size rasterization, displayed with nearest
        # neighbor scaling so no invented detail smooths the demake.
        small=Image.new('RGB',(3*320,34+240),tuple(BG))
        for column,(mesh,title2) in enumerate(((source,source_label),(old,row_baseline),(new,row_revision))):
            im,_=render(mesh,matching_bounds(meshes,ANGLES[4][1]),ANGLES[4][1],160,120);small.paste(im.resize((320,240),Image.Resampling.NEAREST),(column*320,34));label(small,title2,(column*320+8,8))
        small.save(output/'images'/(name+'-160x120.png'))
        distance=Image.new('RGB',(960,2*274),tuple(BG));distance_metrics=[]
        extents=(12,8) if distant else (48,24)
        for row,pixel_span in enumerate(extents):
            frames=[render(mesh,matching_bounds(meshes,ANGLES[4][1]),ANGLES[4][1],160,120,pixel_span) for mesh in meshes]
            src,sm=frames[0]
            distance_metrics.append({'maximum_projected_extent_pixels':pixel_span,'before':compare(src,frames[1][0],sm,frames[1][1]),'after':compare(src,frames[2][0],sm,frames[2][1])})
            for column,((im,_),title2) in enumerate(zip(frames,(source_label,row_baseline,row_revision))):
                distance.paste(im.resize((320,240),Image.Resampling.NEAREST),(column*320,row*274+34));label(distance,f'{title2} / {pixel_span}px extent',(column*320+8,row*274+8))
        distance.save(output/'images'/(name+'-distance.png'))
        avg={stage:{key:float(np.mean([m[stage][key] for m in metrics if m[stage][key] is not None])) for key in ('silhouette_iou','overlap_rgb_mae','color_block_mae')} for stage in ('before','after')}
        result={'id':name,'title':title,'group':group,'new_distance_lod':distant,'triangles':{'source':len(source.p),'before':len(old.p),'after':len(new.p)},'average':avg,'angles':metrics,'distance_readability':distance_metrics,'source_provenance':source.provenance}
        results.append(result);overviews.setdefault(group,[]).append((name,title,hero))
        print(f'{index+1}/{len(catalog)} {name}: IoU {avg["before"]["silhouette_iou"]:.3f}->{avg["after"]["silhouette_iou"]:.3f}; color {avg["before"]["color_block_mae"]:.3f}->{avg["after"]["color_block_mae"]:.3f}',flush=True)
    for group,rows in overviews.items():
        width,height=args.size,round(args.size*.82);im=Image.new('RGB',(90+width*3,(height+30)*len(rows)+28),tuple(BG))
        titles=(source_label,'Approved near model','New distant LOD') if group=='Distant pickups' else (source_label,baseline_label,revision_label)
        for col,title in enumerate(titles):label(im,title,(90+col*width+8,4),12)
        for row,(name,title,hero) in enumerate(rows):
            y=28+row*(height+30);label(im,title,(8,y+4),12)
            for col,frame in enumerate(hero):im.paste(frame,(90+col*width,y+26))
        im.save(output/'images'/('overview-'+group.lower().replace(' ','-')+'.png'))
    for rel,digest in {**hashes,**texture_hashes}.items():
        if hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()!=digest:
            raise RuntimeError(f'Audit input changed during rendering: {rel}. Regenerate from stable packed assets.')
    manifest={'comparison_mode':'performance' if args.performance else 'quality','baseline_label':baseline_label,'revision_label':revision_label,'reference_is_legacy_low_lod':legacy,'renderer':'orthographic CPU barycentric z-buffer; outward faces with backface culling; exact packed vertex RGB; fixed neutral source lighting',
              'angles':[a for a,_ in ANGLES],'viewport_preview':[160,120],'distance_preview_extent_pixels':[48,24],'new_pickup_lod_extent_pixels':[12,8],'color_metric':'Mean absolute RGB deviation on overlapping silhouettes; 8x8 block means. Lower is better; not a perceptual recognition score.',
              'texture_inputs':texture_hashes,'inputs':hashes,'revised_is_frozen_baseline':hashlib.sha256((before/'models_data.c').read_bytes()).digest()==hashlib.sha256((generated/'models_data.c').read_bytes()).digest() and hashlib.sha256((before/'firstperson_data.c').read_bytes()).digest()==hashlib.sha256((generated/'firstperson_data.c').read_bytes()).digest(),'results':results,'elapsed_seconds':time.monotonic()-started}
    if (before/'firstperson-report.json').exists() and (generated/'firstperson-report.json').exists():
        manifest['packing']=packing_statistics(before_report,report,load(before/'firstperson-report.json'),load(generated/'firstperson-report.json'))
    if getattr(args,'micro_dir',None):attach_micro_audit(args,manifest)
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
def findings(r,performance=False):
    b,a=r['average']['before'],r['average']['after'];delta=a['silhouette_iou']-b['silhouette_iou'];cd=b['color_block_mae']-a['color_block_mae']
    shape=f"Mean silhouette IoU {'increased' if delta>=0 else 'decreased'} by {abs(delta):.3f}."
    colors=f"Overlap color-block error {'decreased' if cd>=0 else 'increased'} by {abs(cd):.3f}."
    worst=min(r['angles'],key=lambda x:x['after']['silhouette_iou'])
    cue=next((v for k,v in CUES.items() if k in r['id']),'Inspect the silhouette and large material color regions.')
    if r.get('new_distance_lod'):
        old_count=r['triangles']['before'];new_count=r['triangles']['after']
        return (f'New distant pickup bank: {new_count} triangles versus {old_count} in the approved near model. '
                'There was no approved distant mesh; the middle column deliberately uses that near model for comparison. '
                'The 0.03 near-model loss budget does not apply to this new screen-size-specific LOD. '
                'Inspect the 12-pixel and 8-pixel native extent strips for identity; the large eight-view sheet exposes reduction artifacts. '
                +colors+' Inspection cues: '+cue)
    if performance:
        old_count=r['triangles']['before'];new_count=r['triangles']['after'];saving=1-new_count/max(1,old_count)
        return f'Packed triangles {old_count} → {new_count} ({saving:+.1%} saving). Source silhouette IoU changed by {delta:+.3f} against the approved quality build; '+('within' if delta>=-.03 else 'outside')+' the 0.03 loss budget. '+colors+f' Lowest optimized source agreement: {worst["angle"]} ({worst["after"]["silhouette_iou"]:.3f}). Inspection cues: '+cue
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


def runtime_benchmarks_html(output):
    """Show saved measurements without interpreting CPU queueing as GPU throughput.

    Source JSON remains the provenance record. Optional gpu_completed phase
    dictionaries use the same timing fields as the top-level acquisition data.
    Optional vi_presented phases measure fresh poses at VI selection and judge
    retrace gaps, rather than applying the legacy 33.33-ms/FPS threshold.
    """
    def natural_key(path):
        name=path.name.removeprefix('runtime-').removesuffix('-results.json')
        return [(1,int(s)) if s.isdigit() else (0,s) for s in re.split(r'(\d+)',name)]
    def number(value,digits=1):
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):return '—'
        return f'{value:,.{digits}f}'
    def href(path):
        return html.escape(quote(os.path.relpath(path.resolve(),output.resolve()),safe='/'),quote=True)
    def evidence(path,data,completed=False,vi=False):
        links=[f'<a href="{href(path)}">JSON</a>']
        value=data.get('vi_evidence' if vi else 'completion_evidence' if completed else 'evidence')
        if isinstance(value,str) and value:
            media=Path(value)
            if not media.is_absolute():media=output/media
            if media.is_file():links.append(f'<a href="{href(media)}">Screenshot</a>')
        for field,label in (('source_provenance','Build proof'),('micro_quality_proof','Asset proof'),('micro_packed_proof','Packing proof')):
            value=data.get(field)
            if not isinstance(value,str) or not value:continue
            proof=Path(value)
            if not proof.is_absolute():proof=output/proof
            if proof.is_file():links.append(f'<a href="{href(proof)}">{label}</a>')
        return ' · '.join(links)
    runs=[]
    for path in sorted(output.glob('runtime-*-results.json'),key=natural_key):
        data=load(path)
        if not isinstance(data,dict):raise ValueError(f'{path.name} must contain an object')
        name=path.name.removeprefix('runtime-').removesuffix('-results.json')
        anchor='benchmark-'+re.sub(r'[^a-zA-Z0-9_-]','-',name)
        diagnostic=bool(data.get('diagnostic_only')) or 'gpu-diagnostic' in str(data.get('rom',''))
        runs.append((path,data,name,anchor,diagnostic))
    if not runs:return ''

    def table(rows,completed=False):
        parts=['<div class="table-scroll"><table class="benchmarks"><thead><tr><th>Saved run / evidence</th><th>Phase</th><th>Frames</th><th>FPS</th><th>Mean ms</th><th>p95 ms</th><th>Max ms</th><th>Submitted vertices<br>run avg / peak</th></tr></thead>']
        for path,data,name,anchor,_ in rows:
            timings=data.get('gpu_completed',{}) if completed else data
            if not isinstance(timings,dict):continue
            phases=[(key,label) for key,label in (('all','All'),('combat','Combat'),('vehicles','Vehicles'))
                    if isinstance(timings.get(key),dict)]
            if not phases:continue
            parts.append('<tbody>')
            for i,(key,label) in enumerate(phases):
                stats=timings[key];parts.append('<tr>')
                if i==0:
                    parts.append(f'<th rowspan="{len(phases)}"><a href="#{anchor}">{html.escape(name)}</a><br><small>{evidence(path,data,completed)}</small></th>')
                parts.append(f'<th>{label}</th><td>{number(stats.get("frames"),0)}</td>')
                for field in ('fps','mean_ms','p95_ms','max_ms'):
                    value=stats.get(field)
                    slow=isinstance(value,(int,float)) and not isinstance(value,bool) and (value<30 if field=='fps' else value>1000/30)
                    parts.append(f'<td class="{"down" if slow else ""}">{number(value)}</td>')
                if i==0:
                    vertices=data.get('submitted_vertices',{})
                    if not isinstance(vertices,dict):vertices={}
                    parts.append(f'<td rowspan="{len(phases)}">{number(vertices.get("average"),0)} / {number(vertices.get("peak"),0)}</td>')
                parts.append('</tr>')
            parts.append('</tbody>')
        parts.append('</table></div>');return '\n'.join(parts)

    def vi_table(rows):
        fields=(('fps','FPS',1),('p95_ms','p95 ms',1),('max_ms','Max ms',1),
                ('max_gap_vi','Max retraces',0),('gap_1_vi','1 retrace',0),
                ('gap_2_vi','2 retraces',0),('gap_over_2_vi','>2 retraces',0))
        parts=['<div class="table-scroll"><table class="benchmarks"><thead><tr><th>Saved run / VI evidence</th><th>Phase</th><th>Fresh poses</th>'+''.join(f'<th>{label}</th>' for _,label,_ in fields)+'</tr></thead>']
        for path,data,name,anchor,_ in rows:
            timings=data['vi_presented']
            phases=[(key,label) for key,label in (('all','All'),('combat','Combat'),('vehicles','Vehicles')) if isinstance(timings.get(key),dict)]
            parts.append('<tbody>')
            for i,(key,label) in enumerate(phases):
                stats=timings[key];parts.append('<tr>')
                if i==0:parts.append(f'<th rowspan="{len(phases)}"><a href="#{anchor}">{html.escape(name)}</a><br><small>{evidence(path,data,vi=True)}</small></th>')
                poses=stats.get('frames') if stats.get('frames') is not None else stats.get('poses')
                parts.append(f'<th>{label}</th><td>{number(poses,0)}</td>')
                for field,_,digits in fields:
                    value=stats.get(field)
                    missed=isinstance(value,(int,float)) and not isinstance(value,bool) and ((field=='max_gap_vi' and value>2) or (field=='gap_over_2_vi' and value>0))
                    parts.append(f'<td class="{"down" if missed else ""}">{number(value,digits)}</td>')
                parts.append('</tr>')
            parts.append('</tbody>')
        parts.append('</table></div>')
        telemetry=(('buffer_flips','Buffer flips',0,False),('same_pose_flips','Flips repeating the same pose',0,True),
                   ('missed_deadlines','Missed presentation deadlines',0,True),('skipped_poses','Skipped simulation poses',0,True),
                   ('dropped_ticks','Catch-up ticks dropped',0,True),
                   ('sample_to_vi_mean_ms','Input sample to VI: mean ms',1,False),('sample_to_vi_max_ms','Input sample to VI: max ms',1,False),
                   ('ready_to_vi_mean_ms','Render completion to VI: mean ms',1,False),('ready_to_vi_max_ms','Render completion to VI: max ms',1,False),
                   ('display_buffers','Display surfaces',0,False),
                   ('held_queue_peak','Held completed surfaces: whole-run peak',0,False),
                   ('sdk_ready_peak','SDK-ready surfaces: whole-run peak',0,False),
                   ('submitted_not_presented_peak','Submitted but not presented: whole-run peak',0,False),
                   ('heap_free_kib','Live free heap before teardown: KiB',0,False))
        for path,data,name,anchor,_ in rows:
            stats=data['vi_presented'].get('all',{})
            if not isinstance(stats,dict):continue
            known=[(field,label,digits,warn) for field,label,digits,warn in telemetry if number(stats.get(field))!='—']
            if not known:continue
            parts.append(f'<details><summary>{html.escape(name)} — VI presentation telemetry</summary><p>{evidence(path,data,vi=True)}</p><table>')
            for field,label,digits,warn in known:
                value=stats[field];parts.append(f'<tr><th>{label}</th><td class="{"down" if warn and value>0 else ""}">{number(value,digits)}</td></tr>')
            parts.append('</table></details>')
        return '\n'.join(parts)

    regular=[r for r in runs if not r[4]];diagnostics=[r for r in runs if r[4]]
    acquisitions=[r for r in regular if any(isinstance(r[1].get(k),dict) for k in ('all','combat','vehicles'))]
    parts=['<section class="runtime"><h2>Saved runtime benchmarks</h2>',
           '<p>These runs measure the complete four-player workload in ares. Each JSON preserves its own ROM hash, configuration and measurement provenance; runs may differ in more than one setting. Entries are ordered by run name, not inferred chronology. An average above 30 FPS alone does not establish steady presentation.</p>',
           '<p>CPU and RDP tables retain the legacy 30 FPS / 33.33 ms threshold and highlight values beyond it. Their over-33.33-ms counters are wall-clock metrics, not missed-retrace counts. For paced NTSC runs, a nominal 30 FPS means one fresh pose every two retraces, with wall-clock duration set by the VI mode; a displayed 29.9 FPS or a small excess over 33.33 ms is not by itself a failure. Use the separately measured VI gaps below to assess presentation.</p>']
    if acquisitions:
        parts.extend(['<h3>CPU frame acquisition intervals</h3>',
                      '<p>Acquisition timing includes CPU work and waits for available frame resources. Deeper command queues can change it independently of completed graphics throughput. These figures do not establish RDP completion or display cadence. Vertex counts are averages and peaks over the whole run, not phase-specific counts; a dash means the value was not recorded.</p>',
                      table(acquisitions)])
    completed=[r for r in regular if isinstance(r[1].get('gpu_completed'),dict) and any(isinstance(r[1]['gpu_completed'].get(k),dict) for k in ('all','combat','vehicles'))]
    if completed:
        parts.extend(['<h3>RDP completion callback cadence</h3>',
                      '<p>This separately measured cadence records completed graphics work. Legacy unpaced builds call display_show in that callback; paced builds retain completed buffers until a scheduled retrace. Completion is distinct from CPU acquisition and from VI presentation.</p>',
                      table(completed,completed=True)])
    missing=[html.escape(r[2]) for r in acquisitions if r not in completed]
    if missing:parts.append('<p class="warning">No completion-cadence measurements are recorded for: '+', '.join(missing)+'. Their acquisition FPS must not be presented as completed-frame FPS.</p>')
    presented=[r for r in regular if isinstance(r[1].get('vi_presented'),dict) and any(isinstance(r[1]['vi_presented'].get(k),dict) for k in ('all','combat','vehicles'))]
    if presented:
        vi_only=[html.escape(r[2]) for r in presented if r not in acquisitions and r not in completed]
        if vi_only:parts.append('<p>VI-only runs intentionally omit CPU acquisition, RDP cadence and geometry counters: '+', '.join(vi_only)+'. Only their recorded presentation measurements appear below.</p>')
        parts.extend(['<h3>Fresh simulation poses presented at VI</h3>',
                      '<p>These samples read the VI origin after the display callback selects its surface. They measure fresh simulation poses, separately from RDP completions and buffer flips; a flip containing the same pose is counted as a duplicate, not a fresh frame. This is VI surface-selection timing, not a photon-emission measurement. The NTSC target is two retraces per fresh pose. Gaps beyond two retraces, missed deadlines, and repeated poses are highlighted; truncated FPS and millisecond values do not determine those flags. Missing fields are shown as a dash or omitted from telemetry, never inferred as zero.</p>',
                      vi_table(presented)])
    if diagnostics:
        parts.append('<details><summary>GPU fence diagnostics — separate, noncomparable measurements</summary><p>These diagnostic runs explicitly serialize GPU work. Their FPS is excluded from the production acquisition and completion tables above.</p>')
        parts.append(table(diagnostics));parts.append('</details>')
    parts.append('<details><summary>ROM provenance and measurement notes</summary>')
    fields=(('rom','ROM path'),('sha256','ROM SHA-256'),('baseline_commit','Baseline commit'),
            ('emulator','Emulator'),('measurement','Measurement'),('model_bank','Model bank'),
            ('models','Models'),('only_change_from_pass4','Change from pass 4'),
            ('phase_caveat','Timing caveat'),('warning','Warning'))
    for path,data,name,anchor,diagnostic in runs:
        parts.append(f'<section id="{anchor}"><h4>{html.escape(name)}'+(' — diagnostic' if diagnostic else '')+f'</h4><p>{evidence(path,data)}</p><table>')
        for key,label in fields:
            if data.get(key) is not None:parts.append(f'<tr><th>{label}</th><td>{html.escape(str(data[key]))}</td></tr>')
        parts.append('</table>')
        tail=data.get('gpu_completed',{}).get('tail',[]) if isinstance(data.get('gpu_completed'),dict) else []
        if isinstance(tail,list) and tail:
            parts.append('<h5>Slowest completed frames — scene metadata</h5><p>Category counts describe geometry submitted in the completing frame, not GPU time spent in each category. Displayed simulation times are rounded or truncated; any candidate snapshot ticks in the JSON are not uniquely recovered timestamps.</p>')
            links=[]
            for value in [data.get('completion_tail_metadata'),*data.get('completion_tail_evidence',[])]:
                if not isinstance(value,str):continue
                media=Path(value)
                if not media.is_absolute():media=output/media
                if media.is_file():links.append(f'<a href="{href(media)}">{html.escape(media.name)}</a>')
            if links:parts.append('<p>'+' · '.join(links)+'</p>')
            parts.append('<div class="table-scroll"><table><tr><th>Rank</th><th>Interval ms</th><th>Scene s</th><th>Vertices</th><th>Triangles</th><th>World / vehicles / bodies / pickups / effects / FP</th><th>Mounted / zoom / dead masks</th></tr>')
            for entry in tail:
                if not isinstance(entry,dict):continue
                categories=entry.get('categories',{})
                if not isinstance(categories,dict):categories={}
                counts=' / '.join(number(categories.get(k),0) for k in ('world','vehicles','bodies_held','pickups','effects','firstperson'))
                masks=' / '.join(number(entry.get(k),0) for k in ('mounted_mask','zoom_mask','dead_mask'))
                cells=[number(entry.get('rank'),0),number(entry.get('interval_ms')),number(entry.get('sim_time_s')),number(entry.get('vertices'),0),number(entry.get('triangles'),0),counts,masks]
                parts.append('<tr>'+''.join('<td>'+cell+'</td>' for cell in cells)+'</tr>')
            parts.append('</table></div>')
        parts.append('</section>')
    parts.append('</details></section>');return '\n'.join(parts)


def attach_micro_audit(args,manifest):
    """Optional supplement; keep the frozen base comparisons and aggregate."""
    from audit_micro_lods import audit_micro
    output=args.output.resolve()
    audit_micro(args.micro_dir,args.generated,output/'reference/extended-raw.json',
                output/'micro',getattr(args,'micro_proof',None))
    path=output/'micro/metrics.json'
    manifest['micro_supplement']={'path':'micro/metrics.json',
                                  'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def write_html(output,manifest):
    performance=manifest.get('comparison_mode')=='performance'
    parts=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Blood Gulch model audit</title>',
           '<style>body{background:#111923;color:#dce6f2;font:15px system-ui;margin:32px auto;max-width:1200px;padding:0 20px}a{color:#84c9ff}p{line-height:1.6}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}td,th{padding:9px;border-bottom:1px solid #314153;text-align:left}img{max-width:100%;height:auto;background:#161d27}summary{cursor:pointer;padding:14px;font-size:17px}details{border:1px solid #314153;margin:16px 0;border-radius:8px;padding:8px}.warning{background:#47341e;padding:14px}.up{color:#93dfb2}.down{color:#ffb09d}nav a{display:inline-block;margin:8px}code{color:#addbff}</style>',
           '<h1>Blood Gulch model comparison</h1><p>Original highest-detail source geometry and diffuse maps, the frozen pre-revision N64 build, and the current packed N64 build. Within each angle, all three models share scale, pose, camera, and background; framing fits the combined projected bounds to 80% of the panel. Packed colors include their original baked lighting; the source uses the same neutral light direction. These are offline model diagnostics, not screenshots of the Xbox renderer or ares.</p>',
           '<p>Source surfaces use the full diffuse textures when available; native flat color proxies represent complex meter and glass materials. Xbox environment mapping, specular, emissive, and transparency effects are not reconstructed. Original Xbox multipurpose blue masks tint Spartan armor; first-person change-color C uses player-one red for a matching source/revised comparison. The before column retains its packed material colors and uses player-one red if that build exported an armor mask; older unmasked first-person builds remain untinted. Geometry uses outward-facing triangles and backface culling, matching the corrected native model path. The earlier two-sided audit could conceal reversed culling and open surfaces. The 160×120 strips rasterize at a four-player viewport size and enlarge using nearest neighbor; the fit-to-model camera helps inspect detail and does not imply every model is that large during gameplay. Additional 48-pixel and 24-pixel maximum-extent strips show detail loss when models occupy smaller parts of that viewport; these are screen-size probes, not calibrated in-game distances.</p>']
    if performance:
        parts[2]=parts[2].replace('the frozen pre-revision N64 build, and the current packed N64 build', 'the approved quality N64 build, and the optimized N64 build')
    if manifest.get('revised_is_frozen_baseline'):parts.append('<p class="warning">IN PROGRESS: the revised pack has not been generated. The right column still duplicates the frozen build and is not a completed revision.</p>')
    if manifest['reference_is_legacy_low_lod']:parts.append('<p class="warning">PROVISIONAL: highest-source extraction has not arrived. Source column is explicitly the old low-LOD extraction, not the original highest-detail model.</p>')
    parts.append('<p>Silhouette intersection-over-union (IoU): higher is better. Color block error (including the approximation of baked lighting): mean RGB error on overlapping 8×8 blocks, normalized 0–1; lower is better. Color error excludes angles without silhouette overlap; those missing surfaces are measured by IoU. Neither metric measures player recognition or original shader fidelity. Thin parts and absent pixels require inspection of the silhouettes and the small previews.</p>')
    distant=[r for r in manifest['results'] if r.get('new_distance_lod')]
    comparisons=[r for r in manifest['results'] if not r.get('new_distance_lod')]
    mean=lambda stage,key:float(np.mean([r['average'][stage][key] for r in comparisons])) if comparisons else 0
    mean_before=mean('before','silhouette_iou');mean_after=mean('after','silhouette_iou')
    color_before=mean('before','color_block_mae');color_after=mean('after','color_block_mae')
    improved=sum(r['average']['after']['silhouette_iou']>r['average']['before']['silhouette_iou'] for r in comparisons)
    parts.append(f'<p><strong>{improved} of {len(comparisons)} catalog entries improve their eight-view average silhouette IoU.</strong> The equally weighted catalog mean is {mean_before:.3f} before and {mean_after:.3f} revised; mean color-block error is {color_before:.3f} before and {color_after:.3f} revised. This catalog includes separate color/LOD/first-person variants of shared geometry, so this is a diagnostic comparison, not a count of independent assets or a recognition rating.</p>')
    if performance:
        within=sum(r['average']['after']['silhouette_iou']-r['average']['before']['silhouette_iou']>=-.03 for r in comparisons)
        banks=[r for r in comparisons if r['group'] not in ('First-person gun geometry','Hands') and (r['group']!='Spartan' or r['id'].endswith('_red'))]
        old_triangles=sum(r['triangles']['before'] for r in banks);new_triangles=sum(r['triangles']['after'] for r in banks)
        parts[-1]=f'<p><strong>{within} of {len(comparisons)} comparisons stay within a 0.03 loss of source silhouette IoU against the approved quality baseline.</strong> Mean IoU: {mean_before:.3f} approved → {mean_after:.3f} optimized. Mean color-block error: {color_before:.3f} → {color_after:.3f}. Listed packed model banks use {old_triangles:,} → {new_triangles:,} triangles ({1-new_triangles/max(1,old_triangles):.1%} fewer); this counts each world array once and each complete first-person weapon array once, including its hands. Metrics average the displayed variants and are not a recognition rating or frame-rate measurement.</p>'
    if not comparisons:parts[-1]='<p>This focused report contains new distant LODs only; it does not recompute the approved-model aggregate.</p>'
    if distant:
        far_triangles=sum(r['triangles']['after'] for r in distant)
        near_triangles=sum(r['triangles']['before'] for r in distant)
        parts.append(f'<p><strong>{len(distant)} additional distant pickup models use {far_triangles:,} triangles in total.</strong> These are new banks with no pre-existing far baseline. Their comparison column uses the approved near models ({near_triangles:,} triangles), and their native size strips use 12-pixel and 8-pixel maximum extents. These entries are excluded from the {len(comparisons)}-entry aggregate and the near-model 0.03 loss budget above.</p>')
    packing=manifest.get('packing')
    if performance and packing:
        old_vertices=packing['world_vertices_before']+packing['fp_vertices_before']
        new_vertices=packing['world_vertices_after_existing_banks']+packing['fp_vertices_after']
        parts.append(f'<p><strong>Stored vertices in the existing world and first-person banks: {old_vertices:,} → {new_vertices:,} ({1-new_vertices/max(1,old_vertices):.1%} fewer).</strong> New distant pickup banks add {packing["world_vertices_after_new_far_banks"]:,} stored vertices. Indexed vertices share identical quantized positions, original materials, exact masks and complete animation trajectories; welding changes each retained RGB channel by at most {packing["maximum_color_weld_channel_delta"]} byte values relative to an immutable source corner. Terrain uses its separate 8/255 color bound with exact texture/UV identities. Index buffers add storage, so vertex reduction alone is not the total memory saving. These vertex counts differ from triangle-corner counts because each shared vertex can serve several triangles.</p>')
        exceptions=[f'{bank} {name.replace("_"," ")}: {limit}/255'
                    for bank,models in packing.get('model_color_tolerances',{}).items()
                    for name,limit in models.items() if limit<packing['maximum_color_weld_channel_delta']]
        if exceptions:parts.append('<p>Reviewed color-bound exceptions: '+html.escape('; '.join(exceptions))+'. The lower bounds preserve the Ghost wing markings and the first-person rocket housing color. The complete applied map is recorded in the metrics.</p>')
    parts.append('<style>.table-scroll{overflow-x:auto}.benchmarks td,.benchmarks th{white-space:nowrap}.benchmarks tbody+tbody tr:first-child{border-top:2px solid #61758b}.runtime td{overflow-wrap:anywhere}</style>')
    parts.append(runtime_validation_html(output));parts.append(runtime_benchmarks_html(output));parts.append('<nav>')
    groups=list(dict.fromkeys(r['group'] for r in manifest['results']))
    for group in groups:parts.append(f"<a href=\"#{group.lower().replace(' ','-')}\">{html.escape(group)}</a>")
    parts.append('</nav><p><a href="metrics.json">Full metrics and input SHA-256 provenance</a></p>')
    for group in groups:
        parts.append(f"<h2 id=\"{group.lower().replace(' ','-')}\">{html.escape(group)}</h2>")
        parts.append('<table><tr><th>Model</th><th>Triangles source / before / revised</th><th>IoU before → revised</th><th>Color error before → revised</th></tr>')
        if group=='Distant pickups':
            parts[-1]=parts[-1].replace('source / before / revised','source / approved near / new far').replace('before → revised','approved near → new far')
        rows=[r for r in manifest['results'] if r['group']==group]
        for r in rows:
            b,a=r['average']['before'],r['average']['after'];t=r['triangles'];color='up' if a['silhouette_iou']>=b['silhouette_iou'] else 'down'
            parts.append(f'<tr><td><a href="#{r["id"]}">{html.escape(r["title"])}</a></td><td>{t["source"]:,} / {t["before"]:,} / {t["after"]:,}</td><td class="{color}">{b["silhouette_iou"]:.3f} → {a["silhouette_iou"]:.3f}</td><td>{b["color_block_mae"]:.3f} → {a["color_block_mae"]:.3f}</td></tr>')
        parts.append('</table>')
        overview='overview-'+group.lower().replace(' ','-')+'.png';parts.append(f'<a href="images/{overview}"><img loading="lazy" src="images/{overview}" alt="{html.escape(group)} source before revised overview"></a>')
        for r in rows:
            name=r['id'];extent_label='12 and 8' if r.get('new_distance_lod') else '48 and 24'
            parts.append(f'<details id="{name}"><summary>{html.escape(r["title"])} — eight matching angles and 160×120 readability</summary><p>Source: {html.escape(r["source_provenance"])}</p><p>{html.escape(findings(r,performance))}</p><a href="images/{name}.png"><img loading="lazy" src="images/{name}.png" alt="Eight angles of {html.escape(r["title"])}"></a><img loading="lazy" src="images/{name}-160x120.png" alt="160 by 120 viewport-size comparison"><img loading="lazy" src="images/{name}-distance.png" alt="{extent_label} pixel extent comparison in a 160 by 120 viewport"></details>')
    if manifest.get('micro_supplement'):
        from audit_micro_lods import micro_html
        path=output/manifest['micro_supplement']['path']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=manifest['micro_supplement']['sha256']:
            raise RuntimeError('Micro audit metadata changed; regenerate the supplement before refreshing HTML')
        parts.append(micro_html(load(path)))
    parts.append('</html>');document='\n'.join(parts)
    if performance:
        document=document.replace('Triangles source / before / revised','Triangles source / approved / optimized').replace('IoU before → revised','IoU approved → optimized').replace('Color error before → revised','Color error approved → optimized')
    (output/'index.html').write_text(document)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT/'build/n64/model-audit')
    parser.add_argument('--assets',type=Path,default=ROOT/'build/n64/assets');parser.add_argument('--generated',type=Path,default=ROOT/'build/n64/generated')
    parser.add_argument('--size',type=int,default=224);parser.add_argument('--only',help='Comma-separated substrings of catalog IDs');parser.add_argument('--allow-legacy-reference',action='store_true')
    parser.add_argument('--performance',action='store_true',help='Compare approved quality baseline against optimized meshes, reporting savings and silhouette loss')
    parser.add_argument('--html-only',action='store_true',help='Refresh index.html from existing metrics and optional runtime validation/benchmark JSON; do not rerender images')
    parser.add_argument('--micro-dir',type=Path,help='Optional separate micro C/preview/report bank to audit at4/6/8px; leaves the existing59-entry aggregate unchanged')
    parser.add_argument('--micro-proof',type=Path,help='Optional independent micro C proof to link alongside the supplement')
    parser.add_argument('--micro-only',action='store_true',help='Generate only the micro supplement, retaining existing base metrics/images')
    args=parser.parse_args()
    if args.micro_only:
        if not args.micro_dir or args.html_only:parser.error('--micro-only requires --micro-dir and cannot combine with --html-only')
        manifest=load(args.output/'metrics.json');attach_micro_audit(args,manifest)
        (args.output/'metrics.json').write_text(json.dumps(manifest,indent=2)+'\n')
        write_html(args.output,manifest);print('Report:',args.output/'index.html')
    elif args.html_only:
        manifest=load(args.output/'metrics.json')
        if args.performance:manifest['comparison_mode']='performance'
        write_html(args.output,manifest);print('Report:',args.output/'index.html')
    else:audit(args)
