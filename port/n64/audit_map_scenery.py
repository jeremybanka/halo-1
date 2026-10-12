"""Matched textured silhouettes for source/new-map scenery; not retail pixels."""
import argparse,json,math
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from audit_models import engine,camera_basis,matching_bounds,Mesh
ROOT=Path(__file__).resolve().parents[2]
ANGLES=[('front',(1,.12,0)),('quarter',(1,.3,1)),('right',(0,.12,1)),('rear quarter',(-1,.3,1)),('rear',(-1,.12,0)),('left rear',(-1,.3,-1)),('left',(0,.12,-1)),('front left',(1,.3,-1))]
def render(model,textures,bounds,direction,extent=96,return_depth=False):
    faces=np.array(model['faces'],dtype=int).reshape(-1,3);p=engine(np.array(model['vertices'])[faces]);uv=np.array(model['uv'])[faces].copy();uv[...,1]=1-uv[...,1]
    look,right,up=camera_basis(direction);center,span=bounds;relative=p-center;scale=extent/max(span)
    screen=np.stack([relative@right*scale+64,-relative@up*scale+64],axis=-1);depth=relative@look
    rgb=np.zeros((128,128,3),np.uint8)+np.array([16,35,48],np.uint8);mask=np.zeros((128,128),bool);zbuf=np.full((128,128),-np.inf)
    for ti,(tri,z) in enumerate(zip(screen,depth)):
        x0=max(0,math.floor(tri[:,0].min()));x1=min(127,math.ceil(tri[:,0].max()));y0=max(0,math.floor(tri[:,1].min()));y1=min(127,math.ceil(tri[:,1].max()))
        if x1<x0 or y1<y0:continue
        determinant=(tri[1,1]-tri[2,1])*(tri[0,0]-tri[2,0])+(tri[2,0]-tri[1,0])*(tri[0,1]-tri[2,1])
        if abs(determinant)<1e-8:continue
        xx,yy=np.meshgrid(np.arange(x0,x1+1)+.5,np.arange(y0,y1+1)+.5)
        a=((tri[1,1]-tri[2,1])*(xx-tri[2,0])+(tri[2,0]-tri[1,0])*(yy-tri[2,1]))/determinant
        b=((tri[2,1]-tri[0,1])*(xx-tri[2,0])+(tri[0,0]-tri[2,0])*(yy-tri[2,1]))/determinant;w=np.stack([a,b,1-a-b],axis=-1)
        texture=textures[model['materials'][ti]];st=w@uv[ti];h,width=texture.shape[:2]
        colors=texture[np.floor(st[...,1]*h).astype(int)%h,np.floor(st[...,0]*width).astype(int)%width]
        zz=w@z;old=zbuf[y0:y1+1,x0:x1+1];keep=(w.min(-1)>=-1e-7)&(zz>old)&(colors[...,3]>=128)
        old[keep]=zz[keep];rgb[y0:y1+1,x0:x1+1][keep]=colors[...,:3][keep];mask[y0:y1+1,x0:x1+1][keep]=True
    return (Image.fromarray(rgb),mask,zbuf) if return_depth else (Image.fromarray(rgb),mask)

def run(source,candidate,output):
    source=json.loads(source.read_text());candidate=json.loads(candidate.read_text());output.mkdir(parents=True,exist_ok=True)
    report=json.loads((ROOT/'halo64-assets/generated/maps/maps-report.json').read_text());metrics={}
    for path,original in source.items():
        reduced=candidate[path];map_name='chillout' if 'teleporter_base' in path else 'beavercreek';materials=report['maps'][map_name]['materials']
        textures=[np.array(Image.open(ROOT/f'halo64-assets/generated/maps/{map_name}-textures/packed-{materials.index(shader)}.png').convert('RGBA')) for shader in original['shaders']]
        short=path.split('\\')[-1];sheet=Image.new('RGB',(768,8*286+42),'#102330');draw=ImageDraw.Draw(sheet)
        draw.text((8,8),short+': full source / candidate / cyan missing, orange added',fill='white');scores={}
        meshes=[Mesh(engine(np.array(m['vertices'])[np.array(m['faces'])])) for m in [original,reduced]]
        for row,(label,angle) in enumerate(ANGLES):
            bounds=matching_bounds(meshes,angle);a,ma=render(original,textures,bounds,angle);b,mb=render(reduced,textures,bounds,angle)
            overlap=np.zeros((128,128,3),np.uint8)+np.array([16,35,48],np.uint8);overlap[ma&mb]=[185,203,214];overlap[ma&~mb]=[40,211,246];overlap[mb&~ma]=[255,136,58]
            union=(ma|mb).sum();iou=float((ma&mb).sum()/union) if union else 1;area=float(mb.sum()/max(1,ma.sum()))
            scores[label]={'iou96':iou,'coverage_ratio':area}
            _,a32=render(original,textures,bounds,angle,32);_,b32=render(reduced,textures,bounds,angle,32);scores[label]['iou32']=float((a32&b32).sum()/max(1,(a32|b32).sum()))
            top=42+row*286
            for column,image in enumerate([a,b,Image.fromarray(overlap)]):sheet.paste(image.resize((256,256),Image.Resampling.NEAREST),(column*256,top+24))
            draw.text((8,top+5),label,fill='white');draw.text((520,top+5),f'IoU {iou:.3f} / 32px {scores[label]["iou32"]:.3f}',fill='white')
        sheet.save(output/(short.replace(' ','-')+'.png'));metrics[path]={'source_triangles':len(original['faces']),'candidate_triangles':len(reduced['faces']),'angles':scores}
    (output/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n');print(json.dumps({p:{'triangles':(m['source_triangles'],m['candidate_triangles']),'worst_iou96':min(a['iou96'] for a in m['angles'].values()),'worst_iou32':min(a['iou32'] for a in m['angles'].values())} for p,m in metrics.items()},indent=2))
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',type=Path,required=True);parser.add_argument('--candidate',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();run(args.source,args.candidate,args.output)
