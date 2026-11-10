"""Matched body-only production RGB/cost comparison; weapons stay separate."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from audit_models import Mesh,ANGLES,matching_bounds,engine
from demake_raster import Raster
from pack_gungnir import palette as gpalette
from pack_odst import palette as opalette
from review_armor_palettes import palette as jpalette,masks as jmasks

ROOT=Path(__file__).resolve().parents[2];A=ROOT/'halo64-assets'

def run(bank,output):
    output.mkdir(parents=True,exist_ok=True);raster=Raster(output);raw=json.loads((A/'assets/extended-reduced.json').read_text());preview=json.loads((A/'generated/model-preview.json').read_text());extended=json.loads((A/'generated/extended-report.json').read_text());meshes=[[],[]];rows=[]
    gr=json.loads((bank/'gungnir-report.json').read_text());orr=json.loads((A/'generated/odst/odst-report.json').read_text())
    for lod,key in enumerate(('spartan','spartan_lod')):
        frame=raw['animations_lod' if lod else 'animations']['idle']['frames'][0];scale=extended['model_position_scales'][key];points=np.rint(engine(np.array(frame).reshape(-1,3,3)[extended['triangle_order'][key]])*scale)/scale;model=preview[key];colors=opalette(model['colors'],np.rint(np.array(model['team_mask'])*255),0).reshape(-1,3,3)
        meshes[lod].append(Mesh(points,rgb=colors));j=np.load(A/f'assets/jorge/playable-lods/{"far" if lod else "near"}/packed-preview.npz');meshes[lod].append(Mesh(j['frames_0'][0,j['triangles']]/512,rgb=jpalette(j['colors'],jmasks('far' if lod else 'near'),0)[j['triangles']]))
        for name,path,pal in [('ODST',A/'generated/odst'/f'odst-{lod}-preview.npz',opalette),('GUNGNIR',bank/f'gungnir-{lod}-preview.npz',gpalette)]:
            d=np.load(path);meshes[lod].append(Mesh(d['frames_0'][0,d['triangles']]/512,rgb=pal(d['colors'],d['mask'],0)[d['triangles']]))
        rows.append([dict(armor='Spartan',vertices=(250 if lod else 562),triangles=(135 if lod else 328)),dict(armor='Jorge',vertices=(390 if lod else 670),triangles=(556 if lod else 949)),dict(armor='ODST',vertices=orr['lods'][lod]['vertices'],triangles=orr['lods'][lod]['triangles']),dict(armor='GUNGNIR',vertices=gr['lods'][lod]['vertices'],triangles=gr['lods'][lod]['triangles'])])
    sheet=Image.new('RGB',(640,8*180),'#202428');draw=ImageDraw.Draw(sheet)
    for lod in range(2):
        for row,(angle,direction) in enumerate(ANGLES[:4]):
            bounds=matching_bounds(meshes[lod],direction);y=(lod*4+row)*180
            for col,(mesh,cost) in enumerate(zip(meshes[lod],rows[lod])):
                im,_,_=raster.render(mesh,bounds,direction,width=160,height=160);sheet.paste(im,(col*160,y+20));draw.text((col*160+3,y+3),f'{cost["armor"]} {"far" if lod else "near"} / {cost["vertices"]}v',fill='white')
    sheet.save(output/'armor-comparison.png');(output/'comparison.json').write_text(json.dumps(dict(body_only=True,production_ar_triangles_separate=140,source_pose='same CE idle clock; independent native rigs and production palettes',gungnir_bank_sha256=gr['bank_sha256'],costs=rows),indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('bank',type=Path);p.add_argument('output',type=Path);a=p.parse_args();run(a.bank,a.output)
