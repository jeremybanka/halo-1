"""Source-to-solid reduction comparisons, with the same actual N64 AR."""
import json, os, subprocess, sys, hashlib
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import compare_jorge_ce_materials as util

ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'halo64-assets/assets/jorge';OUT=BASE/'solid-2000'
BEFORE=BASE/'half-budget/reference'
FONT='/System/Library/Fonts/Supplemental/Arial.ttf'

def counts():return json.loads((OUT/'export-inventory.json').read_text())

def sheets():
    util.OUT=OUT;d=counts();after=f"After / {d['body_vertices']:,} vertices"
    def pair(clip='idle',fraction=0,view='three_quarter'):
        path=f'ce-{clip}-{fraction:03d}-{view}.png';detail=clip.title()+' / '+view.replace('_',' ')+' / port AR'
        return [(BEFORE/'renders'/path,'Source / 3,867 vertices',detail),(OUT/'renders'/path,after,detail)]
    util.sheet('comparison-hero.jpg',pair());util.sheet('comparison-five-views.jpg',sum((pair(view=v) for v in ('front','back','left','right','three_quarter')),[]))
    util.sheet('comparison-poses.jpg',sum((pair(c,f) for c,f in [('run',25),('run',50),('reload',40),('reload',80)]),[]))
    util.sheet('jorge-solid-overview.jpg',[(OUT/'renders'/f'ce-idle-000-{v}.png',after,v.replace('_',' ')) for v in ('front','three_quarter','back')],3)
    # The reused reference frames were rendered from this exact checkpoint.
    source=BASE/'detail-pass/jorge-detail-pass.blend';expected=json.loads((BASE/'half-budget/reduction-report.json').read_text())['source_sha256']
    assert hashlib.sha256(source.read_bytes()).hexdigest()==expected
    (OUT/'comparison-provenance.json').write_text(json.dumps({'source_blend_sha256':expected,'reference_frames':str(BEFORE.relative_to(ROOT)),'same_camera_scale':True,'same_port_ar':True},indent=2)+'\n')

def movie():
    folder=OUT/'frames/comparison';folder.mkdir(exist_ok=True);font=ImageFont.truetype(FONT,20);small=ImageFont.truetype(FONT,17);index=0;d=counts()
    for clip,repeat in [('idle',1),('run',3),('fire',4),('reload',1)]:
        a=sorted((BEFORE/'frames'/clip).glob('*.png'));b=sorted((OUT/'frames'/clip).glob('*.png'));assert len(a)==len(b)>0
        for _ in range(repeat):
            for left,right in zip(a,b):
                canvas=Image.new('RGB',(840,600),(27,32,36));draw=ImageDraw.Draw(canvas)
                canvas.paste(Image.open(left).convert('RGB'),(0,45));canvas.paste(Image.open(right).convert('RGB'),(420,45))
                draw.text((12,12),'Source / 3,867 body vertices',font=font,fill='white');draw.text((432,12),f"Solid / {d['body_vertices']:,} body vertices",font=font,fill='white')
                draw.text((12,577),clip.upper()+' / preserved rims and joint coverage / N64 port AR',font=small,fill='white');canvas.save(folder/f'{index:04d}.png');index+=1
    subprocess.run([os.environ.get('JORGE_FFMPEG','ffmpeg'),'-y','-loglevel','error','-framerate','30','-i',str(folder/'%04d.png'),'-c:v','libx264','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(OUT/'jorge-solid-comparison.mp4')],check=True)
    print('COMPARISON MOVIE',index,'frames',flush=True)

if __name__=='__main__':
    if '--sheets' in sys.argv:sheets()
    if '--movie' in sys.argv:movie()
