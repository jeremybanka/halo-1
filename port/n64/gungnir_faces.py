"""Bind the supplied face art to existing animated helmet triangles.

The source PNGs remain unchanged. IA8 stores the original dark ink and alpha;
the 64x64 decal occupies exactly 4096 bytes of TMEM. No body vertices, skin,
positions, animation tracks, colors or topology are added or changed.
"""
import argparse,hashlib,json,shutil,struct
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from audit_models import Mesh,matching_bounds,camera_basis
from demake_raster import Raster
from pack_gungnir import palette

EYE_UV=(.66,.46)
FACE_SIZE=(.080,.090)

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def textures_from_pngs(pngs):
    result=[]
    for i in range(4):
        p=np.array(Image.open(Path(pngs)/f'Artboard {i+1}.png').convert('RGBA'))
        intensity=np.rint(p[:,:,:3].mean(2)/17)*17;alpha=np.rint(p[:,:,3]/17)*17
        result.append(np.stack((intensity,intensity,intensity,alpha),axis=2))
    return result

def face_uv(source,engine_positions):
    lens=np.array([t['p'] for t in source['lods'][0]['triangles'] if t['component']=='helmet-lens']).mean((0,1))
    p=np.asarray(engine_positions)
    return np.stack(((-p[...,2]-lens[1])/FACE_SIZE[0]+EYE_UV[0],
                     (lens[2]-p[...,1])/FACE_SIZE[1]+EYE_UV[1]),axis=-1)

def sample(texture,uv):
    xy=uv*64-.5;lo=np.floor(xy).astype(int);fraction=xy-lo;hi=np.clip(lo+1,0,63);lo=np.clip(lo,0,63)
    x,y=fraction[:,0,None],fraction[:,1,None]
    return ((texture[lo[:,1],lo[:,0]]*(1-x)+texture[lo[:,1],hi[:,0]]*x)*(1-y)+
            (texture[hi[:,1],lo[:,0]]*(1-x)+texture[hi[:,1],hi[:,0]]*x)*y)

def render(bank,metadata,textures,lod,profile,direction,output,head=False,size=(240,280)):
    data=np.load(bank/f'gungnir-{lod}-preview.npz');points=data['frames_0'][0]/512;tris=data['triangles'];colors=palette(data['colors'],data['mask'],profile)[tris];mesh=Mesh(points[tris],rgb=colors);face=metadata['lods'][lod]
    bounds=matching_bounds([mesh],direction)
    if head:
        # Artist closeups isolate the helmet; the body's raised firing hands
        # can otherwise cover the face from its own forward direction.
        head_mask=np.isin(data['sources'][tris]//3,np.array(face['source_helmet_triangles'])).all(1)
        mesh=Mesh(points[tris[head_mask]],rgb=colors[head_mask]);bounds=matching_bounds([mesh],direction)
    width,height=size;im,_,depth=Raster(output).render(mesh,bounds,direction,width=width,height=height)
    rgb=np.array(im,dtype=float);center,span=bounds;look,right,up=camera_basis(direction);scale=min(width/span[0],height/span[1])*.80
    uv=np.array(face['uv'])
    for ti in face['triangle_ids']:
        ids=tris[ti];ps=points[ids];relative=ps-center;screen=np.stack((relative@right*scale+width/2,-relative@up*scale+height/2),axis=1);z=relative@look
        if np.cross(ps[1]-ps[0],ps[2]-ps[0])@look<=0:continue
        low=np.maximum(0,np.floor(screen.min(0)).astype(int));high=np.minimum((width-1,height-1),np.ceil(screen.max(0)).astype(int))
        if np.any(low>high):continue
        xx,yy=np.meshgrid(np.arange(low[0],high[0]+1)+.5,np.arange(low[1],high[1]+1)+.5);a,b,c=screen;den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(den)<1e-9:continue
        u=((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/den;v=((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/den;w=1-u-v;zz=u*z[0]+v*z[1]+w*z[2]
        keep=(u>=0)&(v>=0)&(w>=0)&(np.abs(depth[low[1]:high[1]+1,low[0]:high[0]+1]-zz)<1e-6)
        bary=np.stack((u[keep],v[keep],w[keep]),axis=1);tex=sample(textures[profile],bary@uv[ids]);alpha=tex[:,3,None]/255
        target=rgb[low[1]:high[1]+1,low[0]:high[0]+1];target[keep]=target[keep]*(1-alpha)+tex[:,:3]*alpha
    return Image.fromarray(np.uint8(np.clip(np.rint(rgb),0,255)))

def run(candidate,bank,pngs,output):
    output.mkdir(parents=True,exist_ok=True);source=json.loads(candidate.read_text());report=json.loads((bank/'gungnir-report.json').read_text());raw=(bank/'gungnir.bin').read_bytes()
    assert report['source_sha256']==sha(candidate) and report['bank_sha256']==sha(bank/'gungnir.bin')
    lines=['/* User-supplied 64x64 GUNGNIR face art; original PNGs retained. */','#include "gungnir_faces.h"'];textures=[];source_files=[];encoded=[];lods=[];descriptors=[]
    for profile in range(4):
        name=f'Artboard {profile+1}.png';path=pngs/name;im=Image.open(path).convert('RGBA');assert im.size==(64,64)
        pixels=np.array(im);ink=pixels[:,:,3]>0
        assert ink.any() and not ((pixels[:,:,0]>150)&(pixels[:,:,1]>50)&(pixels[:,:,1]<210)&(pixels[:,:,2]<70)&ink).any(),'Unexpected orange optic in the supplied art'
        intensity=np.rint(pixels[:,:,:3].mean(2)/17).astype(np.uint8);alpha=np.rint(pixels[:,:,3]/17).astype(np.uint8);data=(intensity<<4)|alpha
        decoded=np.stack((intensity*17,intensity*17,intensity*17,alpha*17),axis=2);assert np.array_equal(decoded[:,:,3],pixels[:,:,3])
        assert np.abs(decoded[:,:,:3][ink].astype(int)-pixels[:,:,:3][ink].astype(int)).max()<=8
        encoded.append(data);textures.append(decoded.astype(float));source_files.append(dict(profile=profile,file=name,sha256=sha(path),ink_pixels=int(ink.sum())));shutil.copy2(path,output/name)
    lines.append('const uint8_t bg_gungnir_face_textures[4][64*64] __attribute__((aligned(8)))={')
    lines.extend('{'+','.join(map(str,t.ravel()))+'},' for t in encoded);lines.append('};')
    for lod,r in enumerate(report['lods']):
        d=np.load(bank/f'gungnir-{lod}-preview.npz');triangles=d['triangles'];ps=d['positions'][triangles];n=np.cross(ps[:,1]-ps[:,0],ps[:,2]-ps[:,0]);components=[source['lods'][lod]['triangles'][int(i)//3]['component'] for i in d['sources']]
        selected=np.array([all(components[i]=='helmet-shell' for i in t) for t in triangles])&(n[:,0]>.12*np.linalg.norm(n,axis=1))
        uv=face_uv(source,d['positions']);uv_fixed=np.rint((uv*64-.5)*32).astype(int);assert np.abs(uv_fixed).max()<32768
        vertices=np.unique(triangles[selected]);lines.append(f'static const bg_gungnir_face_uv face_uv_{lod}[]={{'+','.join('{'+f'{i},{uv_fixed[i,0]},{uv_fixed[i,1]}'+'}' for i in vertices)+'};')
        batches=[];indices=[];triangle_offset=0
        for bi in range(r['batches']):
            first,count,off,num=struct.unpack_from('>4H',raw,r['offset']+r['batches_offset']+bi*8);chosen=[]
            for j in range(num//3):
                if selected[triangle_offset+j]:chosen.extend(struct.unpack_from('>3h',raw,r['offset']+r['indices_offset']+(off+j*3)*2))
            triangle_offset+=num//3
            if not chosen:continue
            begin=min(chosen)&~1;count=max(chosen)-begin+1
            while len(indices)%4:indices.append(0)
            batches.append((first+begin,count,len(indices),len(chosen)));indices.extend(i-begin for i in chosen)
        while len(indices)%4:indices.append(0)
        assert triangle_offset==len(triangles) and sum(b[3] for b in batches)==int(selected.sum())*3
        lines.append(f'static int16_t face_indices_{lod}[] __attribute__((aligned(8)))={{'+','.join(map(str,indices))+'};')
        lines.append(f'static const bg_mesh_batch face_batches_{lod}[]={{'+','.join('{'+','.join(map(str,b))+'}' for b in batches)+'};')
        loads=sum((b[1]+1)&~1 for b in batches);descriptors.append('{'+f'face_uv_{lod},face_batches_{lod},face_indices_{lod},{len(vertices)},{len(batches)},{int(selected.sum())},{loads}'+'}')
        lods.append(dict(lod=lod,vertices=vertices.tolist(),uv=((uv_fixed/32+.5)/64).tolist(),triangle_ids=np.flatnonzero(selected).tolist(),source_helmet_triangles=[i for i,t in enumerate(source['lods'][lod]['triangles']) if t['component'].startswith('helmet-')],overlay_triangles=int(selected.sum()),extra_vertex_loads=loads,batches=batches,body_vertices_unchanged=r['vertices'],body_triangles_unchanged=r['triangles']))
    lines.append('const bg_gungnir_face_mesh bg_gungnir_faces[2]={'+','.join(descriptors)+'};');(output/'gungnir_faces_data.c').write_text('\n'.join(lines)+'\n')
    result=dict(schema=1,source_candidate_sha256=sha(candidate),body_bank_sha256=sha(bank/'gungnir.bin'),profiles=source_files,eye_anchor_uv=EYE_UV,face_extent_halo_units=FACE_SIZE,format='IA8',width=64,height=64,tmem_bytes=4096,total_texture_bytes=16384,mode='Coplanar depth-tested decal using the existing animated helmet vertices',lods=lods)
    (output/'faces.json').write_text(json.dumps(result,indent=2)+'\n')
    for lod in range(2):
        sheet=Image.new('RGB',(960,306),'#202428');draw=ImageDraw.Draw(sheet)
        d=np.load(bank/f'gungnir-{lod}-preview.npz');ids=np.array(lods[lod]['vertices']);basis=np.c_[d['positions'][ids],np.ones(len(ids))];matrix=np.linalg.lstsq(basis,d['frames_0'][0,ids]/512,rcond=None)[0];direction=matrix[0]/np.linalg.norm(matrix[0])
        for profile,label in enumerate(('Red / Artboard 1','Blue / Artboard 2','Gold / Artboard 3','Green / Artboard 4')):
            im=render(bank,result,textures,lod,profile,direction,output,True);sheet.paste(im,(profile*240,26));draw.text((profile*240+8,8),label,fill='white')
        sheet.save(output/f'faces-lod-{lod}.png')
    print('FACES',[(d['overlay_triangles'],d['extra_vertex_loads']) for d in lods],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','bank','pngs','output'):p.add_argument(name,type=Path)
    a=p.parse_args();run(a.candidate,a.bank,a.pngs,a.output)
