"""Matched color comparison and updated selection portrait for personal Jorge."""
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from review_jorge_playable import tile
ROOT=Path(__file__).resolve().parents[2];A=ROOT/'halo64-assets';BASE=A/'assets/jorge';OUT=BASE/'playable-personal';F=OUT/'runtime-renders'
def run():
    im=Image.new('RGB',(1440,650),(25,29,34));draw=ImageDraw.Draw(im)
    for i,(base,name,label) in enumerate([(F,'spartan','Standard CE Spartan'),(BASE/'playable-refined/runtime-renders','jorge','Previous metallic backpack'),(F,'jorge','Matte pack / warm shoulder / Jorge arms')]):
        tile(im,base/f'{name}-idle-three_quarter.png',(480*i,40,480,600));draw.text((480*i+20,16),label,fill='white')
    im.save(OUT/'standard-comparison.png')
    im=Image.new('RGB',(1600,660),(25,29,34));draw=ImageDraw.Draw(im)
    for i,view in enumerate(('front','back')):
        for row,base in enumerate((BASE/'playable-refined/runtime-renders',F)):
            tile(im,base/f'jorge-idle-{view}.png',(i*800+row*400,30,400,600));draw.text((i*800+row*400+20,12),view+' / '+('previous' if row==0 else 'revised'),fill='white')
    im.save(OUT/'material-comparison.png')
    image=Image.open(F/'jorge-idle-three_quarter.png').convert('RGBA');image=image.crop(image.getbbox());image.thumbnail((30,39));portrait=Image.new('RGBA',(32,40));portrait.alpha_composite(image,((32-image.width)//2,40-image.height));portrait.save(OUT/'jorge-portrait.png')
    v=np.array(portrait,dtype=np.uint16).reshape(-1,4);q=((v[:,0]>>3)<<11)|((v[:,1]>>3)<<6)|((v[:,2]>>3)<<1)|(v[:,3]>64)
    (A/'generated/jorge_portrait.c').write_text('#include "asset_jorge.h"\nconst uint16_t bg_jorge_portrait[32*40] __attribute__((aligned(16)))={'+','.join(hex(int(x)) for x in q)+'};\n')
if __name__=='__main__':run()
