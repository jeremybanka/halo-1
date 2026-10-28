#!/usr/bin/env python3
"""Decode diagnostic native RDP RGBA5551 readback, without rescaling/filtering."""
import argparse,re,struct
from pathlib import Path
from PIL import Image

def decode(log,output):
    text=log.read_text(errors='replace');header=re.search(r'FF_PHOTO_BEGIN tick=(\d+) width=(\d+) height=(\d+) format=RGBA5551',text)
    if not header or 'FF_PHOTO_END' not in text:raise ValueError('Incomplete native photo')
    tick,width,height=map(int,header.groups());pixels=[None]*(width*height)
    for first,hexdata in re.findall(r'^FF_PIX (\d+) ([0-9a-f]+)$',text,re.M):
        values=struct.unpack('>'+str(len(hexdata)//4)+'H',bytes.fromhex(hexdata));first=int(first)
        assert first+len(values)<=len(pixels)
        for i,v in enumerate(values):
            assert pixels[first+i] is None,'Duplicate pixel chunk'
            pixels[first+i]=tuple(((v>>shift)&31)*255//31 for shift in (11,6,1))
    assert all(p is not None for p in pixels),'Missing native pixel chunk'
    image=Image.new('RGB',(width,height));image.putdata(pixels);image.save(output)
    print(output,tick,width,height)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('log',type=Path);p.add_argument('output',type=Path);a=p.parse_args();decode(a.log,a.output)
