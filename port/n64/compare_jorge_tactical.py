"""Matched static and animated comparisons of the tactical Jorge reduction."""
import json,sys,os,subprocess
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'halo64-assets/assets/jorge';OUT=BASE/'tactical-5000';RENDERS=OUT/'renders'
FONT='/System/Library/Fonts/Supplemental/Arial.ttf'

def sheets():
    inventory=json.loads((OUT/'export-inventory.json').read_text());count=inventory['jorge']['vertices'];font=ImageFont.truetype(FONT,20)
    def sheet(filename,files,columns=2):
        w=450;h=610;canvas=Image.new('RGB',(w*columns,h*((len(files)+columns-1)//columns)),(29,34,38));draw=ImageDraw.Draw(canvas)
        for i,(path,label) in enumerate(files):
            im=Image.open(path).convert('RGBA');im.thumbnail((w,565));x=i%columns*w;y=i//columns*h;canvas.paste(im,(x,y),im);draw.text((x+10,y+575),label,font=font,fill='white')
        canvas.save(OUT/filename)
    for style in ('textured','clay'):
        files=[]
        for view in ('three_quarter','front','back','left','right'):
            for prefix,label in [('source-','Source: 20,757 vertices'),('',f'Reduced: {count:,} vertices')]:files.append((RENDERS/f'{prefix}{style}-idle-000-{view}.png',label+' / '+view.replace('_',' ')))
        sheet(f'comparison-{style}.jpg',files)
    files=[]
    for name,fraction in [('run',25),('run',50),('reload',40),('reload',80)]:
        for prefix,label in [('source-','Source'),('','Reduced')]:files.append((RENDERS/f'{prefix}textured-{name}-{fraction:03d}-three_quarter.png',f'{label} / {name} {fraction}%'))
    sheet('comparison-poses.jpg',files)
    files=[(RENDERS/f'{prefix}textured-idle-000-three_quarter.png',label) for prefix,label in [('source-','Source: 20,757 vertices'),('',f'Reduced: {count:,} vertices')]];sheet('comparison-hero.jpg',files)
    metrics={}
    for path in RENDERS.glob('mask-source-*.png'):
        target=RENDERS/path.name.replace('mask-source-','mask-reduced-');a=np.array(Image.open(path))[:,:,3]>127;b=np.array(Image.open(target))[:,:,3]>127
        metrics[path.stem.removeprefix('mask-source-')]={'intersection_over_union':float((a&b).sum()/(a|b).sum()),'source_pixels':int(a.sum()),'reduced_pixels':int(b.sum()),'lost_pixels':int((a&~b).sum()),'added_pixels':int((b&~a).sum())}
    (OUT/'silhouette-validation.json').write_text(json.dumps({'resolution':[480,600],'scope':'Body only, including backpack and decals; weapon excluded','views':metrics},indent=2)+'\n')
    print('SILHOUETTES',json.dumps({k:round(v['intersection_over_union']*100,2) for k,v in metrics.items()}))

def movie():
    count=json.loads((OUT/'export-inventory.json').read_text())['jorge']['vertices'];font=ImageFont.truetype(FONT,20);small=ImageFont.truetype(FONT,17);frames=OUT/'frames/comparison';frames.mkdir(exist_ok=True)
    index=0
    for name,repeat in [('idle',1),('run',3),('fire',4),('reload',1)]:
        sources=sorted((BASE/'animation-proof/frames'/name).glob('*.png'));targets=sorted((OUT/'frames'/name).glob('*.png'));assert len(sources)==len(targets)>0
        for _ in range(repeat):
            for source,target in zip(sources,targets):
                a=Image.open(source).convert('RGB');b=Image.open(target).convert('RGB');canvas=Image.new('RGB',(840,600),(27,32,36));draw=ImageDraw.Draw(canvas)
                canvas.paste(a,(0,45));canvas.paste(b,(420,45));draw.text((12,12),'Source / 20,757 body vertices',font=font,fill='white');draw.text((432,12),f'Reduced / {count:,} body vertices',font=font,fill='white');draw.text((12,577),name.upper()+' — shared CE motion, original timing',font=small,fill='white');canvas.save(frames/f'{index:04d}.png');index+=1
    ffmpeg=os.environ.get('JORGE_FFMPEG','ffmpeg');subprocess.run([ffmpeg,'-y','-loglevel','error','-framerate','30','-i',str(frames/'%04d.png'),'-c:v','libx264','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(OUT/'jorge-5000-comparison.mp4')],check=True)
    print('MOVIE',index,'frames',index/30,'seconds')

if __name__=='__main__':
    if '--sheets' in sys.argv:sheets()
    if '--movie' in sys.argv:movie()
