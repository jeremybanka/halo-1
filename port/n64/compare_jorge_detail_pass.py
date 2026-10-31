"""Matched before/after review for color corrections and component culling."""
import json,os,subprocess,sys
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from compare_jorge_ce_materials import sheet as original_sheet
import compare_jorge_ce_materials as ce_compare

ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'halo64-assets/assets/jorge';OUT=BASE/'detail-pass';BEFORE=BASE/'ce-materials'
FONT='/System/Library/Fonts/Supplemental/Arial.ttf'

def sheets():
    ce_compare.OUT=OUT
    def pair(name='idle',fraction=0,view='three_quarter'):
        filename=f'ce-{name}-{fraction:03d}-{view}.png';detail=f'{name.title()} / {view.replace("_"," ")}'
        return [(BEFORE/'renders'/filename,'Before / CE texture pass',detail),(OUT/'renders'/filename,'After / colors + detail cull',detail)]
    original_sheet('comparison-hero.jpg',pair());original_sheet('comparison-five-views.jpg',sum((pair(view=v) for v in ('front','back','left','right','three_quarter')),[]));original_sheet('comparison-poses.jpg',sum((pair(c,f) for c,f in [('run',25),('run',50),('reload',40),('reload',80)]),[]))
    original_sheet('jorge-detail-overview.jpg',[(OUT/'renders'/f'ce-idle-000-{v}.png','Jorge / revised colors + details',v.replace('_',' ')) for v in ('front','three_quarter','back')],3)
    metrics={}
    for path in (OUT/'renders').glob('mask-before-*.png'):
        target=path.with_name(path.name.replace('mask-before','mask-after'));a=np.array(Image.open(path))[:,:,3]>127;b=np.array(Image.open(target))[:,:,3]>127
        metrics[path.stem.removeprefix('mask-before-')]={'intersection_over_union':float((a&b).sum()/(a|b).sum()),'lost_pixels':int((a&~b).sum()),'added_pixels':int((b&~a).sum())}
    if metrics:
        (OUT/'silhouette-validation.json').write_text(json.dumps({'resolution':[480,600],'scope':'Body only; explicit fitting removal; no retained surface movement','views':metrics},indent=2)+'\n');print('SILHOUETTE IoU', {k:round(v['intersection_over_union']*100,3) for k,v in metrics.items()})

def movie():
    frames=OUT/'frames/comparison';frames.mkdir(exist_ok=True);font=ImageFont.truetype(FONT,20);small=ImageFont.truetype(FONT,17);index=0
    for name,repeat in [('idle',1),('run',3),('fire',4),('reload',1)]:
        a=sorted((BEFORE/'frames'/name).glob('*.png'));b=sorted((OUT/'frames'/name).glob('*.png'));assert len(a)==len(b)>0
        for _ in range(repeat):
            for left,right in zip(a,b):
                canvas=Image.new('RGB',(840,600),(27,32,36));draw=ImageDraw.Draw(canvas);canvas.paste(Image.open(left).convert('RGB'),(0,45));canvas.paste(Image.open(right).convert('RGB'),(420,45));draw.text((12,12),'Before / CE texture pass',font=font,fill='white');draw.text((432,12),'After / colors + detail cull',font=font,fill='white');draw.text((12,577),name.upper()+' / unchanged armor surfaces, rig and clip timing',font=small,fill='white');canvas.save(frames/f'{index:04d}.png');index+=1
    subprocess.run([os.environ.get('JORGE_FFMPEG','ffmpeg'),'-y','-loglevel','error','-framerate','30','-i',str(frames/'%04d.png'),'-c:v','libx264','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(OUT/'jorge-detail-comparison.mp4')],check=True);print('MOVIE',index,'frames')

if __name__=='__main__':
    if '--sheets' in sys.argv:sheets()
    if '--movie' in sys.argv:movie()
