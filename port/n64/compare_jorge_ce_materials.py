"""Matched review sheets and full-speed motion for the CE texture pass."""
import json,os,subprocess,sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'halo64-assets/assets/jorge';OUT=BASE/'ce-materials';BEFORE=BASE/'tactical-5000'
FONT='/System/Library/Fonts/Supplemental/Arial.ttf'

def sheet(filename,files,columns=2):
    w,h=450,620;canvas=Image.new('RGB',(w*columns,h*((len(files)+columns-1)//columns)),(29,34,38));draw=ImageDraw.Draw(canvas);font=ImageFont.truetype(FONT,20);small=ImageFont.truetype(FONT,17)
    for i,(path,label,detail) in enumerate(files):
        im=Image.open(path).convert('RGBA');im.thumbnail((w,562));x=i%columns*w;y=i//columns*h;canvas.paste(im,(x,y),im);draw.text((x+14,y+571),label,font=font,fill='white');draw.text((x+14,y+598),detail,font=small,fill=(177,190,194))
    canvas.save(OUT/filename,quality=94)

def sheets():
    def pair(clip='idle',fraction=0,view='three_quarter'):
        suffix=f'{clip}-{fraction:03d}-{view}.png';detail=f'{clip.title()} / {view.replace("_"," ")}'
        return [(BEFORE/'renders'/('textured-'+suffix),'Before / Reach materials',detail),(OUT/'renders'/('ce-'+suffix),'After / CE texture atlas',detail)]
    sheet('comparison-hero.jpg',pair());sheet('comparison-five-views.jpg',sum((pair(view=v) for v in ('front','back','left','right','three_quarter')),[]));sheet('comparison-poses.jpg',sum((pair(c,f) for c,f in [('run',25),('run',50),('reload',40),('reload',80)]),[]))
    sheet('jorge-ce-overview.jpg',[(OUT/'renders'/f'ce-idle-000-{v}.png','Jorge / CE texture pass',v.replace('_',' ')) for v in ('front','three_quarter','back')],3)
    report=json.loads((OUT/'material-report.json').read_text());canvas=Image.new('RGB',(1120,730),(29,34,38));draw=ImageDraw.Draw(canvas);font=ImageFont.truetype(FONT,22);small=ImageFont.truetype(FONT,16)
    draw.text((24,18),'Actual CE Spartan diffuse',font=font,fill='white');draw.text((24,48),'512 x 512 source / unchanged',font=small,fill=(177,190,194))
    canvas.paste(Image.open(ROOT/'build/n64/assets/model-textures-reference/spartan_2_diffuse.png').convert('RGB'),(24,82));draw.text((584,18),'Jorge: one baked atlas',font=font,fill='white');draw.text((584,48),'256 x 256 / 16 shared regions',font=small,fill=(177,190,194))
    canvas.paste(Image.open(OUT/'textures/jorge-ce-atlas-256.png').convert('RGB').resize((512,512),Image.Resampling.NEAREST),(584,82))
    for i,p in enumerate(report['patches']):
        x=24+(i%4)*274;y=618+(i//4)*24;draw.text((x,y),f'{i+1:02d}  {p["name"].replace("_"," ")}',font=small,fill='white')
    canvas.save(OUT/'texture-provenance.jpg',quality=96)

def movie():
    frames=OUT/'frames/comparison';frames.mkdir(exist_ok=True);font=ImageFont.truetype(FONT,20);small=ImageFont.truetype(FONT,17);index=0
    for name,repeat in [('idle',1),('run',3),('fire',4),('reload',1)]:
        sources=sorted((BEFORE/'frames'/name).glob('*.png'));targets=sorted((OUT/'frames'/name).glob('*.png'));assert len(sources)==len(targets)>0
        for _ in range(repeat):
            for source,target in zip(sources,targets):
                canvas=Image.new('RGB',(840,600),(27,32,36));draw=ImageDraw.Draw(canvas);canvas.paste(Image.open(source).convert('RGB'),(0,45));canvas.paste(Image.open(target).convert('RGB'),(420,45));draw.text((12,12),'Before / Reach textures',font=font,fill='white');draw.text((432,12),'After / CE texture atlas',font=font,fill='white');draw.text((12,577),name.upper()+'  /  same rig, shared CE motion, original timing',font=small,fill='white');canvas.save(frames/f'{index:04d}.png');index+=1
    ffmpeg=os.environ.get('JORGE_FFMPEG','ffmpeg');subprocess.run([ffmpeg,'-y','-loglevel','error','-framerate','30','-i',str(frames/'%04d.png'),'-c:v','libx264','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(OUT/'jorge-ce-materials-comparison.mp4')],check=True);print('CE MOVIE',index,'frames',index/30,'seconds')

if __name__=='__main__':
    if '--sheets' in sys.argv:sheets()
    if '--movie' in sys.argv:movie()
