"""Compose the final matched packed-color comparison sheets."""
from pathlib import Path
import json
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'halo64-assets/assets/jorge/playable-lods'

def run():
    folder=BASE/'review';report=json.loads((BASE/'compiled/jorge-report.json').read_text())
    counts={r['lod']:r['vertices'] for r in report['lods']}
    names=('personal','near','far','spartan','spartan_lod')
    labels=('Previous Jorge: 2264 vertices',f'Jorge near: {counts["near"]} vertices',
            f'Jorge far: {counts["far"]} vertices','CE near: 562 vertices','CE far: 250 vertices')
    for view in ('front','back','left','right','three_quarter'):
        out=Image.new('RGB',(1250,285),(38,42,45));draw=ImageDraw.Draw(out)
        for i,(name,label) in enumerate(zip(names,labels)):
            im=Image.open(folder/f'packed-{name}-idle-0-{view}-400.png').resize((250,250),Image.Resampling.LANCZOS)
            out.paste(im,(250*i,30),im);draw.text((250*i+10,10),label,fill='white')
        out.save(folder/f'final-{view}.png')
    for view in ('front','left','three_quarter'):
        out=Image.new('RGB',(720,270),(38,42,45));draw=ImageDraw.Draw(out)
        for i,name in enumerate(names[:3]):
            im=Image.open(folder/f'head-{name}-{view}.png');out.paste(im,(i*240,30),im);draw.text((i*240+10,10),name,fill='white')
        out.save(folder/f'helmet-compare-{view}.png')
    out=Image.new('RGB',(1000,245),(38,42,45));draw=ImageDraw.Draw(out)
    for i,name in enumerate(names):
        im=Image.open(folder/f'packed-{name}-idle-0-three_quarter-48.png').resize((192,192),Image.Resampling.NEAREST)
        out.paste(im,(i*200,30),im);draw.text((i*200+5,7),name,fill='white')
    out.save(folder/'game-size-comparison.png')

if __name__=='__main__':run()
