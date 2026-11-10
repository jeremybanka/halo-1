"""Make matched refinement evidence and refresh Jorge's ROM portrait."""
from pathlib import Path
import json
import numpy as np
from PIL import Image,ImageDraw
from review_jorge_playable import tile
ROOT=Path(__file__).resolve().parents[2];A=ROOT/'halo64-assets';OUT=A/'assets/jorge/playable-refined';F=OUT/'runtime-renders'
def run():
    image=Image.new('RGB',(1440,650),(25,29,34));draw=ImageDraw.Draw(image)
    for i,(base,name,label) in enumerate([(F,'spartan','Standard CE Spartan'),(OUT.parent/'playable-half/runtime-renders','jorge','Previous Jorge'),(F,'jorge','Refined Jorge / game colors')]):
        tile(image,base/f'{name}-idle-three_quarter.png',(480*i,40,480,600));draw.text((480*i+20,16),label,fill='white')
    image.save(OUT/'standard-comparison.png')
    image=Image.new('RGB',(1600,530),(25,29,34));draw=ImageDraw.Draw(image)
    for i,view in enumerate(('front','back','left','right','three_quarter')):
        for row,base in enumerate((OUT.parent/'playable-half/runtime-renders',F)):
            tile(image,base/f'jorge-idle-{view}.png',(i*320+row*160,40,160,450))
            draw.text((i*320+row*160+5,16),'Before' if row==0 else 'Refined',fill='white')
        draw.text((i*320+10,500),view,fill='white')
    image.save(OUT/'before-after.png')
    clips=json.loads((OUT/'gameplay-poses.json').read_text())['clips'];image=Image.new('RGB',(1280,1125),(25,29,34));draw=ImageDraw.Draw(image)
    for i,c in enumerate(clips):
        tile(image,F/f'motion-{i:02d}.png',(i%8*160,i//8*225,160,200));draw.text((i%8*160+2,i//8*225+201),str(i)+' '+c['name'][:24],fill='white')
    image.save(OUT/'motion-contact-sheet.png')
    a=Image.open(F/'jorge-idle-three_quarter.png').convert('RGBA');a=a.crop(a.getbbox());a.thumbnail((30,39));portrait=Image.new('RGBA',(32,40));portrait.alpha_composite(a,((32-a.width)//2,40-a.height));portrait.save(OUT/'jorge-portrait.png')
    v=np.array(portrait,dtype=np.uint16).reshape(-1,4);q=((v[:,0]>>3)<<11)|((v[:,1]>>3)<<6)|((v[:,2]>>3)<<1)|(v[:,3]>64)
    (A/'generated/jorge_portrait.c').write_text('#include "asset_jorge.h"\nconst uint16_t bg_jorge_portrait[32*40] __attribute__((aligned(16)))={'+','.join(hex(int(x)) for x in q)+'};\n')
if __name__=='__main__':run()
