"""Native matched scope comparisons. Source-derived photos stay local/private."""
import hashlib,html,json,re,shutil
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).parent;OUT=ROOT/'build/scope-fix'
WEB=Path('/Users/jem/dojo/halo-1/build/n64-scope-fix');PRIVATE=ROOT/'halo64-assets/assets/scope-fix'
for p in (WEB,PRIVATE):p.mkdir(parents=True,exist_ok=True)
labels=['Reported ground view · Magnum 2×','Crouched ground · Magnum 2×','Steep ground · sniper 10×','Close wall · Magnum 2×','Distant precision · 1× / 2× / 2× / 10×','Distant precision · small camera turn','Two players · mixed scopes','Three players · wide P3','Four players · mixed scopes','Crouched steep ground · Magnum 2×']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
logs={case:(OUT/f'{case}-native.log').read_text(errors='replace') for case in ('before','after')}
for case in logs:assert 'PASS 10 scope photos' in (OUT/f'{case}-capture.log').read_text()
assert re.findall(r'POLISH_POSE[^\n]+',logs['before'])==re.findall(r'POLISH_POSE[^\n]+',logs['after'])
assert 'PASS: 47 configurations / 188 target translation units' in (OUT/'config.log').read_text()
frames=[];cards=''
for n,label in enumerate(labels):
 images={case:Image.open(OUT/case/f'photo-{n}.png').convert('RGB') for case in logs}
 a,b=(np.asarray(images[case]).astype(int) for case in ('before','after'))
 diff=Image.fromarray(np.clip(abs(b-a)*4,0,255).astype('uint8'))
 for case,im in {**images,'diff':diff}.items():
  name=f'{case}-{n}.png';im.save(WEB/name);shutil.copy2(WEB/name,PRIVATE/name)
 frames.append({'page':n,'label':label,'before_png_sha256':sha(WEB/f'before-{n}.png'),'after_png_sha256':sha(WEB/f'after-{n}.png'),'changed_pixels':int(np.any(a!=b,axis=2).sum())})
 cards+=f'<section><h2>{html.escape(label)}</h2><div class="pair"><figure><img src="before-{n}.png"><figcaption>Before</figcaption></figure><figure><img src="after-{n}.png"><figcaption>After</figcaption></figure></div><details><summary>Pixel difference ×4</summary><img src="diff-{n}.png"></details></section>'
y,x=np.mgrid[:240,:320];far=[]
for n in (4,5):
 a=np.asarray(Image.open(WEB/f'before-{n}.png'));b=np.asarray(Image.open(WEB/f'after-{n}.png'));diff=np.any(a!=b,axis=2)
 for v,(cx,cy) in enumerate(((91,69),(229,69),(91,171),(229,171))):
  roi=(x-cx)**2+(y-cy)**2<28**2
  if v>1:
   # Remove both old/new bitmap rectangles, with a two-pixel filter margin.
   for scale in (1,.5):
    for (ox,oy),(w,h) in zip(((-101,18),(115,18),(-33,0),(33,0),(0,42)),((16,64),(16,64),(64,2),(64,2),(2,32))):
     left=cx+ox*.25-w*scale*.5;top=cy+oy*.25-h*scale*.5
     roi&=~((x>=left-2)&(x<=left+w*scale+2)&(y>=top-2)&(y<=top+h*scale+2))
  changed=int((diff&roi).sum());assert changed==0,(n,v,changed)
  far.append({'page':n,'player':v+1,'world_pixels_checked':int(roi.sum()),'changed':changed})
# The reported missing-ground band shows bluish sky; it is all ground now.
holes=[]
for case in ('before','after'):
 a=np.asarray(Image.open(WEB/f'{case}-0.png')).astype(int)
 holes.append(int(((a[:,:,2]>a[:,:,0]+10)&(x>=80)&(x<240)&(y>=160)&(y<230)).sum()))
assert holes[0]>1000 and holes[1]<30,holes # cyan HUD text is not terrain
# A flat ground photo makes the native sniper ink and reticle independently measurable.
a=np.asarray(Image.open(WEB/'after-2.png'));base=a[100,150];ink=np.all(a<base*.8,axis=2)
cyan=(a[:,:,1]>130)&(a[:,:,2]>130)&(abs(x-160)<8)&(abs(y-120)<8)
cx,cy=float(x[cyan].mean()),float(y[cyan].mean())
left=np.flatnonzero(ink[119,112:156])+112;right=np.flatnonzero(ink[119,164:209])+164
stem=np.flatnonzero(ink[130,155:165])+155
center_error=abs((int(left.max())+int(right.min()))*.5-cx)
assert center_error<=1 and abs(stem.mean()-cx)<=1 and abs(119-cy)<=1
colors=np.unique(a[90:160,100:221].reshape(-1,3),axis=0)
assert len(colors)==3,colors # terrain, one translucent ink color, cyan reticle; no blurred fringe
marks={'reticle_center':[cx,cy],'horizontal_gap_center_error_px':center_error,'vertical_stem_center_error_px':float(abs(stem.mean()-cx)),'aim_line_center_error_px':abs(119-cy),'decal_region_colors':colors.tolist()}
# Extract the selected depth for each captured camera, rather than inferring it from colors.
near=[];recent=[]
for line in logs['after'].splitlines():
 if line.startswith('SCOPE_DEPTH '):recent.append(dict((k,int(v)) for k,v in re.findall(r'(p|near|query_us|candidates)=(\d+)',line)))
 if line.startswith('FF_PHOTO_BEGIN'):
  page=int(re.search(r'tick=(\d+)',line).group(1));count=4 if page in (4,5,8) else 2 if page==6 else 3 if page==7 else 1
  rows=recent[-count:];expected=[4,32,32,32] if page in (4,5) else [4]*count
  assert [r['near'] for r in rows]==expected,(page,rows)
  near.append({'page':page,'cameras':rows})
play=json.loads(next((OUT/'play').glob('*.build.json')).read_text());rom=Path(play['rom']['path']);assert sha(rom)==play['rom']['sha256']
shutil.copy2(rom,WEB/'halo64-scope-fix.z64')
report={'date':'2026-10-30','frozen_photos_not_fps':True,'matched_camera_poses':22,'frames':frames,'far_world_pixel_checks':far,'ground_band_blue_pixels_before_after':holes,'sniper_markings':marks,'native_near_plane_selection':near,'runtime_configurations':47,'rom':{'bytes':rom.stat().st_size,'sha256':sha(rom)},'notes':['Sniper uses its original rectangular shape; no added outlines.','Pistol remains circular in every layout.','Native cached/cold-query timings do not represent combat FPS.']}
(HERE/'results.json').write_text(json.dumps(report,indent=2)+'\n');shutil.copy2(HERE/'results.json',PRIVATE/'results.json')
for case in ('before','after','play'):
 for p in (OUT/case).glob('*.build.json'):shutil.copy2(p,PRIVATE/(case+'-build.json'))
 shutil.copy2(OUT/f'{case}-build.log',PRIVATE/f'{case}-build.log')
for name in ('before-native.log','after-native.log','before-capture.log','after-capture.log','config.log'):shutil.copy2(OUT/name,PRIVATE/name)
for case in logs:(PRIVATE/f'{case}-poses.txt').write_text('\n'.join(re.findall(r'POLISH_POSE[^\n]+',logs[case]))+'\n')
shutil.copytree(OUT/'before-source',PRIVATE/'before-source',dirs_exist_ok=True)
files=['hud.c','scene.c','view_camera.h','scope_mask.h','scope_depth.h','scene_scope_depth.inc','scope_qa.h','m64_polish_qa.h','build.py','test_scope_mask.c','test_scope_depth.c','test_view_camera.c','test_hud_layout.c','test_runtime_configs.py','SCOPE_RENDERING.md']
manifest={name:sha(ROOT/'port/n64'/name) for name in files};(HERE/'source-sha256.json').write_text(json.dumps(manifest,indent=2)+'\n')
(PRIVATE/'after-source').mkdir(exist_ok=True)
for name in files:shutil.copy2(ROOT/'port/n64'/name,PRIVATE/'after-source'/name)
for p in HERE.iterdir():
 if p.is_file():shutil.copy2(p,PRIVATE/p.name)
(WEB/'comparison.html').write_text('''<!doctype html><html><meta charset="utf-8"><title>Halo 64 · scope corrections</title><style>
body{background:#0b121b;color:#dce8f5;font:16px system-ui;max-width:1200px;margin:40px auto;padding:0 24px}h1,h2,a{color:#86ccff}p{line-height:1.5;max-width:950px}.pair{display:flex;gap:24px;flex-wrap:wrap}figure{margin:0}img{width:480px;max-width:100%;image-rendering:pixelated}figcaption{color:#a6b7c8;margin:8px 0}section{margin-top:32px;border-top:1px solid #294059;padding-top:14px}details{margin-top:16px}summary{cursor:pointer;margin-bottom:12px}button{background:#21435f;color:white;padding:8px 14px;border:0;cursor:pointer}.smooth img{image-rendering:auto}</style>
<h1>Halo 64 · terrain and scope corrections</h1><p>Nearby terrain and walls remain visible while scoped. The Magnum is circular; the sniper keeps its wide rounded rectangle. No added outlines. Sniper markings are sharp and aligned with the aiming reticle.</p>
<p><a href="halo64-scope-fix.z64">Playable ROM</a> · <button onclick="document.body.classList.toggle('smooth')">Toggle display smoothing</button></p>
<p>Native 320×240 Ares captures, 22 matched camera poses. These frozen photos are visual checks, not frame-rate benchmarks. Every section includes a pixel difference filter. The checked distant world pixels remain identical after excluding the intentionally changed HUD markings.</p>'''+cards+f'<section><h2>Verification</h2><p>Host camera, HUD alignment, conservative depth and mask checks passed. 47 runtime configurations compiled. Close views use the 4-unit near plane; clear distant views retain 32.</p><p>ROM: {rom.stat().st_size:,} bytes<br>SHA-256: <code>{sha(rom)}</code></p></section></html>')
shutil.copy2(WEB/'comparison.html',PRIVATE/'comparison.html')
print(json.dumps({'far_checks':far,'ground_band':holes,'markings':marks,'rom':report['rom']},indent=2));print(WEB/'comparison.html')
