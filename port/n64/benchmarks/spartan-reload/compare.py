#!/usr/bin/env python3
"""Decode exact native frames and build paired motion previews (private output)."""
import argparse,hashlib,json,re,struct
import numpy as np
from pathlib import Path
from PIL import Image,ImageDraw
p=argparse.ArgumentParser();p.add_argument('capture',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
frames={};report={}
for version in ['before','after']:
 log=a.capture/(version+'-native.log');text=log.read_text();blocks=re.findall(r'FF_PHOTO_BEGIN.*?FF_PHOTO_END',text,re.S);assert len(blocks)==72
 folder=a.output/version;folder.mkdir(exist_ok=True);frames[version]=[]
 for index,block in enumerate(blocks):
  assert int(re.search(r'tick=(\d+)',block)[1])==index
  pixels=[None]*(320*240)
  for start,data in re.findall(r'^FF_PIX (\d+) ([0-9a-f]+)$',block,re.M):
   start=int(start);values=struct.unpack('>'+str(len(data)//4)+'H',bytes.fromhex(data))
   for n,value in enumerate(values):
    assert pixels[start+n] is None
    pixels[start+n]=tuple(((value>>s)&31)*255//31 for s in [11,6,1])
  assert all(x is not None for x in pixels)
  image=Image.new('RGB',(320,240));image.putdata(pixels);image.save(folder/f'{index:02}.png');frames[version].append(image)
 report[version]={'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),'frames':72,'native_size':[320,240]}
for name,start,end in [('standing',0,36),('crouched',36,72)]:
 sequence=[]
 for index in range(start,end):
  image=Image.new('RGB',(640,260),(18,23,29));draw=ImageDraw.Draw(image)
  draw.text((8,4),'BEFORE',fill='white');draw.text((328,4),'AFTER',fill='white')
  image.paste(frames['before'][index],(0,20));image.paste(frames['after'][index],(320,20));sequence.append(image)
 sequence[0].save(a.output/(name+'.gif'),save_all=True,append_images=sequence[1:],duration=100,loop=0,optimize=False)
 # Static contact sheet retains exact native RGB for inspection of foot poses.
 selected=[start,start+(end-start)//3,start+2*(end-start)//3]
 sheet=Image.new('RGB',(640,240*3))
 for row,index in enumerate(selected):
  for column,version in enumerate(['before','after']):sheet.paste(frames[version][index],(column*320,row*240))
 sheet.save(a.output/(name+'-poses.png'))
 report[name]={'source_frames':[start,end-1],'seconds':(end-start)/10}
states=[re.findall(r'^RELOAD_PHOTO .*$',(a.capture/(v+'-native.log')).read_text(),re.M)[:72] for v in ['before','after']]
assert len(states[0])==72 and states[0]==states[1]
(a.output/'diff').mkdir(exist_ok=True)
checks={'checks':'Changed during reload; exactly identical after completion in both stances','frames':[]}
for i,(before,after) in enumerate(zip(frames['before'],frames['after'])):
 delta=np.abs(np.array(before).astype(int)-np.array(after).astype(int))
 changed=int(np.any(delta,axis=2).sum())
 assert (changed==0) if i%36>=29 else (changed>0), (i,changed)
 checks['frames'].append({'frame':i,'changed_pixels':changed})
 Image.fromarray(np.minimum(delta*4,255).astype('uint8')).save(a.output/'diff'/f'{i:02}.png')
(a.output/'pixel-checks.json').write_text(json.dumps(checks,indent=2)+'\n')
report['fixture_states']=states[0]
(a.output/'frames.json').write_text(json.dumps(report,indent=2)+'\n')
(a.output/'comparison.html').write_text('''<!doctype html><meta charset="utf-8"><title>Spartan reload locomotion</title>
<style>body{margin:36px auto;max-width:900px;background:#12171d;color:#e7edf3;font:17px system-ui;line-height:1.5}img{width:100%;image-rendering:pixelated}a{color:#63d4f5}h1{font-size:30px}</style>
<h1>Walking while reloading</h1><p>Before / after: native N64 RDP frames from the same four-angle fixture. The character stays at a fixed world position so the stride and reload are easy to compare.</p>
<p>Both native four-camera captures run with RDP validation. The character uses the existing 12 third-person reload samples, interpolated over the actual weapon reload timer.</p><h2>Standing movement</h2><img src="standing.gif"><h2>Crouched movement</h2><img src="crouched.gif">
<p>CE’s source reload replaces only its masked upper-body channels. The pelvis and legs retain the independently advancing base gait, including crouched movement. Animated hit surfaces and the weapon attachment use the same composition. First-person poses, weapon timing and ammo rules are unchanged.</p>
<p>These staged captures are visual checks, not gameplay or performance measurements. One frame is sampled every three simulation ticks (10 Hz preview). PNG frames preserve native pixels; GIFs are palette previews. The 3.6-second sequence includes completion and continued walking.</p><p><label>Exact frame <input id=frame type=range min=0 max=71 value=0></label> <button id=mode>Show difference ×4</button></p><img id=still src=after/00.png><script>let diff=false;const f=document.getElementById('frame'),b=document.getElementById('mode'),im=document.getElementById('still');function show(){im.src=(diff?'diff/':'after/')+String(f.value).padStart(2,'0')+'.png'}f.oninput=show;b.onclick=()=>{diff=!diff;b.textContent=diff?'Show candidate':'Show difference ×4';show()}</script>''')
print(json.dumps(report,indent=2))
