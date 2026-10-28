#!/usr/bin/env python3
"""Decode exact native frames and build paired motion previews (private output)."""
import argparse,hashlib,json,re,struct
from pathlib import Path
from PIL import Image,ImageDraw
p=argparse.ArgumentParser();p.add_argument('capture',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
frames={};report={}
for version in ['before','after']:
 log=a.capture/(version+'-native.log');text=log.read_text();blocks=re.findall(r'FF_PHOTO_BEGIN.*?FF_PHOTO_END',text,re.S);assert len(blocks)==51
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
 report[version]={'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),'frames':51,'native_size':[320,240]}
for name,start,end in [('standing',0,21),('crouched',21,51)]:
 sequence=[]
 for index in range(start,end):
  image=Image.new('RGB',(640,260),(18,23,29));draw=ImageDraw.Draw(image)
  draw.text((8,4),'BEFORE',fill='white');draw.text((328,4),'AFTER',fill='white')
  image.paste(frames['before'][index],(0,20));image.paste(frames['after'][index],(320,20));sequence.append(image)
 sequence[0].save(a.output/(name+'.gif'),save_all=True,append_images=sequence[1:],duration=[30,30,40]*((len(sequence)+2)//3),loop=0,optimize=False)
 # Static contact sheet retains exact native RGB for inspection of foot poses.
 selected=[start,start+(end-start)//3,start+2*(end-start)//3]
 sheet=Image.new('RGB',(640,240*3))
 for row,index in enumerate(selected):
  for column,version in enumerate(['before','after']):sheet.paste(frames[version][index],(column*320,row*240))
 sheet.save(a.output/(name+'-poses.png'))
 report[name]={'source_frames':[start,end-1],'seconds':(end-start)/30}
(a.output/'frames.json').write_text(json.dumps(report,indent=2)+'\n')
(a.output/'comparison.html').write_text('''<!doctype html><meta charset="utf-8"><title>Spartan firing locomotion</title>
<style>body{margin:36px auto;max-width:900px;background:#12171d;color:#e7edf3;font:17px system-ui;line-height:1.5}img{width:100%;image-rendering:pixelated}a{color:#63d4f5}h1{font-size:30px}</style>
<h1>Walking while firing</h1><p>Before / after: native N64 RDP frames from the same four-angle fixture. The character stays at a fixed world position so the stride and recoil are easy to compare.</p>
<h2>Standing movement</h2><img src="standing.gif"><h2>Crouched movement</h2><img src="crouched.gif">
<p>The original recoil is composed with the locomotion skeleton before skinning. Movement and firing have independent clocks; animated hit surfaces follow the same pose. Source geometry and first-person firing behavior are retained.</p>
<p>These staged captures are visual checks, not gameplay or performance measurements. PNG frames preserve the native pixels; GIFs are palette previews.</p>''')
print(json.dumps(report,indent=2))
