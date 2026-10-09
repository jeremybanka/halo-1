#!/usr/bin/env python3
"""Overlay M6D source and proxy silhouettes in one shared coordinate frame.

Supply saved pre-edit reduced JSON banks. No independent scaling, registration
or perspective manipulation: all three columns use the same orthographic
camera, center and bounds. First-person comparisons use the original idle
pose and omit the hands; world comparisons use the source world bind pose.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
import audit_models as audit

ROOT=Path(__file__).resolve().parents[2]
ANGLES=[('side',(0,0,-1)),('top',(0,1,0)),
        ('front',(1,0,0)),('three-quarter',(1,.4,-1))]

def proxy(model,fp=False):
    triangles=model['triangles'][model.get('hand_triangle_count',0) if fp else 0:]
    points=audit.engine([t['p'] for t in triangles])
    return audit.Mesh(points,np.ones(points.shape)*190)

def sheet(source,before,after,path):
    canvas=Image.new('RGB',(1200,1330),'#102330');draw=ImageDraw.Draw(canvas)
    draw.text((12,12),'CYAN: source only   ORANGE: proxy only   GRAY: overlap — identical scale and alignment',fill='white',font=audit.font(19))
    metrics={}
    for row,(label,angle) in enumerate(ANGLES):
        bounds=audit.matching_bounds([source,before,after],angle)
        renders=[audit.render(m,bounds,angle,width=400,height=290,cull='none') for m in (source,before,after)]
        top=50+row*320
        canvas.paste(renders[0][0],(0,top+30))
        draw.text((8,top+6),'Xbox source — '+label,fill='white',font=audit.font(17))
        metrics[label]={}
        for column,name in [(1,'before'),(2,'after')]:
            original=renders[0][1];reduced=renders[column][1]
            rgb=np.zeros((290,400,3),dtype=np.uint8)+[16,35,48]
            rgb[original&reduced]=[185,203,214]
            rgb[original&~reduced]=[40,211,246]
            rgb[reduced&~original]=[255,136,58]
            canvas.paste(Image.fromarray(rgb.astype('uint8')),(column*400,top+30))
            iou=float((original&reduced).sum()/(original|reduced).sum())
            metrics[label][name]=iou
            draw.text((column*400+8,top+6),f'{label}: {name} IoU {iou:.3f}',fill='white',font=audit.font(17))
    canvas.save(path)
    return metrics

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before-world',type=Path,required=True)
    parser.add_argument('--before-firstperson',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    assets=ROOT/'build/n64/assets';load=audit.load
    raw=load(assets/'extended-raw.json')['models']['pistol']
    before=load(args.before_world)['models']['pistol'];after=load(assets/'extended-reduced.json')['models']['pistol']
    metrics={'world':sheet(audit.source_mesh(raw),proxy(before),proxy(after),args.output/'world-overlays.png')}
    raw=load(assets/'firstperson-raw.json')['weapons']['pistol']
    vertices=audit.posed_vertices(raw['gun'],raw['clips']['idle']['frames'][0],raw['nodes'])
    source=audit.source_mesh(raw['gun'],vertices,family='fp')
    before=load(args.before_firstperson)['weapons']['pistol'];after=load(assets/'firstperson-reduced.json')['weapons']['pistol']
    metrics['firstperson_idle']=sheet(source,proxy(before,True),proxy(after,True),args.output/'firstperson-overlays.png')
    (args.output/'silhouette-metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
    print(json.dumps(metrics,indent=2))

if __name__=='__main__':main()
