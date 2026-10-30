"""Publish native photos, geometric pixel checks and local/private provenance."""
import json,hashlib,shutil,re,html
from pathlib import Path
import numpy as np
from PIL import Image,ImageChops,ImageEnhance
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent;OUT=ROOT/'build/m64-polish';WEB=Path('/Users/jem/dojo/halo-1/build/n64-m64-polish');PRIVATE=ROOT/'halo64-assets/assets/m64-polish'
assert 'PASS 20 native photos' in (OUT/'capture.log').read_text(), 'Wait for the current capture to finish'
WEB.mkdir(parents=True,exist_ok=True);PRIVATE.mkdir(parents=True,exist_ok=True)
labels=['1 player — clear','1 player — damage','2 players — clear','2 players — damage','3 players — clear','3 players — damage','4 players — clear','4 players — damage','Duke controls','Bond controls','P3 wide scoreboard','Flashlight off','Flashlight on','Zoomed damage','4P flash baseline','P3 red flash — peak','P3 red flash — half duration','P3 red flash — expired','P2 plasma flash','3P wide view — flash and arrow']
frames=[];pixels=[]
for n,label in enumerate(labels):
 p=OUT/f'photo-{n}.png';shutil.copy2(p,WEB/p.name);shutil.copy2(p,PRIVATE/p.name)
 frames.append({'page':n,'label':label,'png_sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
for count in range(1,5):
 a=np.asarray(Image.open(OUT/f'photo-{(count-1)*2}.png')).astype(int);b=np.asarray(Image.open(OUT/f'photo-{(count-1)*2+1}.png')).astype(int)
 changed=np.any(a!=b,axis=2);outside=0
 for p in range(count):
  w=320 if count<=2 or count==3 and p==2 else 160;h=240 if count==1 else 120
  x=(p%2)*160 if count>=3 and not(count==3 and p==2) else 0;y=0 if count==1 else (p//2 if count>=3 else p)*120
  outside+=int(changed[y+20:y+h-20,x+20:x+w-20].sum())
  # Center tips extend farther inward than the arms on both horizontal edges.
  def ys(cx):return np.flatnonzero(changed[y:y+h,x+cx])
  mid=ys(w//2);arm=ys(w//2+25)
  topmid=mid[mid<20];toparm=arm[arm<20];botmid=mid[mid>=h-20];botarm=arm[arm>=h-20]
  assert len(topmid) and len(toparm) and max(topmid)>max(toparm),(count,p,'top orientation')
  assert len(botmid) and len(botarm) and min(botmid)<min(botarm),(count,p,'bottom orientation')
 assert outside==0,(count,outside)
 pixels.append({'players':count,'changed_pixels':int(changed.sum()),'changes_outside_edge_bands':outside,'top_bottom_tips_inward':True})
 diff=Image.fromarray(np.clip(abs(b-a)*4,0,255).astype('uint8'));diff.save(WEB/f'diff-{count}.png');shutil.copy2(WEB/f'diff-{count}.png',PRIVATE/f'diff-{count}.png')
# A brief whole-view flash belongs only to its damaged player.
base=np.asarray(Image.open(OUT/'photo-14.png')).astype(int)
peak=np.asarray(Image.open(OUT/'photo-15.png')).astype(int)
expired=np.asarray(Image.open(OUT/'photo-17.png')).astype(int)
changed=np.any(base!=peak,axis=2)
assert not changed[:120,:].any() and not changed[120:,160:].any()
assert changed[140:220,20:140].sum()>1000
assert np.array_equal(base,expired),'Flash must fully expire'
flash_check={'only_p3_changed':True,'peak_changed_pixels':int(changed.sum()),'expired_identical':True}
m=json.loads(next((OUT/'play').glob('*.build.json')).read_text());rom=Path(m['rom']['path']);sha=hashlib.sha256(rom.read_bytes()).hexdigest();assert sha==m['rom']['sha256'];shutil.copy2(rom,WEB/'halo64-m64-polish.z64')
photo_build=json.loads(next((OUT/'photos').glob('*.build.json')).read_text())
report={'date':'2026-10-30','hardware_feedback':{'device':'ModRetro M64','overclock':'Insane','modes':['Firefight','Slayer Pro'],'qualitative':'Almost always smooth; a few frame drops at wave arrivals; skill-based fights and good long-distance hit registration.','measured_fps':None},'photos':frames,'pixel_checks':pixels,'screen_flash_checks':flash_check,'rom':{'bytes':rom.stat().st_size,'sha256':sha},'photo_rom_sha256':photo_build['rom']['sha256'],'frozen_photos_not_performance':True,'gameplay_scores_hint':False,'runtime_configurations':46}
(HERE/'results.json').write_text(json.dumps(report,indent=2)+'\n');(PRIVATE/'results.json').write_text(json.dumps(report,indent=2)+'\n')
for name in ('damage-source.json','native.log','capture.log','play-build.log','photos-build.log','config.log'):
 shutil.copy2(OUT/name,PRIVATE/name)
for folder in ('photos','play'):
 for p in (OUT/folder).glob('*.build.json'):shutil.copy2(p,PRIVATE/(folder+'-build.json'))
source_files=['controls.c','controls.h','game.h','game.c','damage_indicator.h','damage_flash.h','scene_flashlight.inc','flashlight_surface.h','scene.c','hud.c','hud_layout.h','view_layout.h','menu_draw.c','menu.c','frontend.c','main.c','build.py','asset_hud.h','extract_damage_hud.py','m64_polish_qa.h']
manifest={str(Path('port/n64')/name):hashlib.sha256((ROOT/'port/n64'/name).read_bytes()).hexdigest() for name in source_files}
(HERE/'source-sha256.json').write_text(json.dumps(manifest,indent=2)+'\n')
shutil.copy2(ROOT/'port/n64/M64_PLAYTEST.md',PRIVATE/'M64_PLAYTEST.md')
shutil.copy2(ROOT/'halo64-assets/generated/hud_damage_data.c',PRIVATE/'hud_damage_data.c')
pose='\n'.join(line for line in (OUT/'native.log').read_text(errors='replace').splitlines() if line.startswith('POLISH_POSE'))
(PRIVATE/'poses.txt').write_text(pose+'\n')
cards=''
for count in range(1,5):
 base=(count-1)*2
 cards+=f'<section><h2>{count} player'+('s' if count>1 else '')+f'</h2><div class="pair"><figure><img src="photo-{base}.png"><figcaption>Clear</figcaption></figure><figure><img src="photo-{base+1}.png"><figcaption>Damage · all four directions</figcaption></figure><figure><img src="diff-{count}.png"><figcaption>Pixel difference ×4 · confined to view edges</figcaption></figure></div></section>'
for n in range(8,20):cards+=f'<section><h2>{labels[n]}</h2><img src="photo-{n}.png"></section>'
(WEB/'comparison.html').write_text('''<!doctype html><html><meta charset="utf-8"><title>Halo 64 · M64 playtest follow-up</title><style>
body{background:#0a111b;color:#d8e8f7;font:16px system-ui;max-width:1200px;margin:40px auto;padding:0 24px}h1,h2{color:#74c6ff}p{line-height:1.55;max-width:920px}a{color:#84d4ff}section{border-top:1px solid #2b455b;margin-top:36px;padding-top:14px}.pair{display:flex;gap:20px;flex-wrap:wrap}figure{margin:0}img{width:480px;max-width:100%;image-rendering:pixelated}figure img{width:320px}figcaption{margin:8px 0;color:#9eb5ca;font-size:14px}button{padding:8px 14px;background:#23445f;color:white;border:0;cursor:pointer}body.smooth img{image-rendering:auto}</style>
<h1>Halo 64 · M64 playtest follow-up</h1><p>P3 now has the wide bottom view. Duke is the default; Bond preserves the previous N64 layout. Source damage artwork is translucent, points inward and sits behind the HUD. The gameplay scores hint has been removed.</p>
<p><a href="halo64-m64-polish.z64">Download playable ROM</a> · <button onclick="document.body.classList.toggle('smooth')">Toggle pixel scaling</button></p>
<p>These are native 320×240 Ares readbacks of frozen poses, not FPS measurements. The M64 playtest used the Insane overclock and was reported as almost always smooth, with occasional wave-arrival drops.</p>'''+cards+f'<section><h2>Build</h2><p>ROM: {rom.stat().st_size:,} bytes<br>SHA-256: <code>{sha}</code></p><p>The flashlight is a bounded surface-light approximation; it does not reproduce CE’s full dynamic lighting or battery system, and uneven terrain still needs visual polish.</p></section></html>')
print('PASS',json.dumps(pixels));print(WEB/'comparison.html')
