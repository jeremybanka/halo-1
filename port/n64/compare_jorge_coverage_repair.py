"""Matched previews of the local coverage repairs, using the port AR."""
import json,os,sys,subprocess,hashlib
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import compare_jorge_ce_materials as util

ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'halo64-assets/assets/jorge'
OUT=BASE/'coverage-repair';BEFORE=BASE/'solid-2000'

def sheets():
    util.OUT=OUT;d=json.loads((OUT/'export-inventory.json').read_text());after=f"Repaired / {d['body_vertices']:,} vertices"
    def pair(clip='idle',fraction=0,view='three_quarter'):
        name=f'ce-{clip}-{fraction:03d}-{view}.png';detail=f'{clip.title()} / {view.replace("_"," ")} / port AR'
        return [(BEFORE/'renders'/name,'Before / 2,169 vertices',detail),(OUT/'renders'/name,after,detail)]
    util.sheet('comparison-hero.jpg',pair())
    util.sheet('comparison-five-views.jpg',sum((pair(view=v) for v in ('front','back','left','right','three_quarter')),[]))
    util.sheet('comparison-poses.jpg',sum((pair(c,f) for c,f in [('run',25),('run',50),('reload',40),('reload',80)]),[]))
    util.sheet('comparison-repairs.jpg',[(OUT/'renders'/f'close-{side}-{name}.png','Before' if side=='before' else 'Repaired',name.replace('-',' '))
               for name in ('collar-front','collar-oblique','rump-rest','rump-running','rump-running-back') for side in ('before','after')])
    util.sheet('jorge-repaired-overview.jpg',[(OUT/'renders'/f'ce-idle-000-{v}.png',after,v.replace('_',' ')) for v in ('front','three_quarter','back')],3)
    source=BEFORE/'jorge-solid-2000.blend';digest=hashlib.sha256(source.read_bytes()).hexdigest()
    assert digest==json.loads((OUT/'repair-report.json').read_text())['source_sha256']
    (OUT/'comparison-provenance.json').write_text(json.dumps({'source_blend_sha256':digest,'reference_frames':str(BEFORE.relative_to(ROOT)),'same_camera_scale':True,'same_port_ar':True},indent=2)+'\n')

def movie():
    folder=OUT/'frames/comparison';folder.mkdir(exist_ok=True);font=ImageFont.truetype(util.FONT,20);small=ImageFont.truetype(util.FONT,17);index=0
    for clip,repeat in [('idle',1),('run',3),('fire',4),('reload',1)]:
        a=sorted((BEFORE/'frames'/clip).glob('*.png'));b=sorted((OUT/'frames'/clip).glob('*.png'));assert len(a)==len(b)>0
        for _ in range(repeat):
            for left,right in zip(a,b):
                canvas=Image.new('RGB',(840,600),(27,32,36));draw=ImageDraw.Draw(canvas)
                canvas.paste(Image.open(left).convert('RGB'),(0,45));canvas.paste(Image.open(right).convert('RGB'),(420,45))
                draw.text((12,12),'Before / accepted solid model',font=font,fill='white');draw.text((432,12),'After / fitted coverage repairs',font=font,fill='white')
                draw.text((12,577),clip.upper()+' / unchanged CE motion / actual N64 port AR',font=small,fill='white');canvas.save(folder/f'{index:04d}.png');index+=1
    subprocess.run([os.environ.get('JORGE_FFMPEG','ffmpeg'),'-y','-loglevel','error','-framerate','30','-i',str(folder/'%04d.png'),'-c:v','libx264','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(OUT/'jorge-repaired-comparison.mp4')],check=True)
    print('COMPARISON MOVIE',index,'frames',flush=True)

if __name__=='__main__':
    if '--sheets' in sys.argv:sheets()
    if '--movie' in sys.argv:movie()
