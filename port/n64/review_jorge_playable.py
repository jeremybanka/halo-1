"""Assemble rendered comparisons and the ROM menu portrait."""
from pathlib import Path
import json,struct
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[2];A=ROOT/'halo64-assets';OUT=A/'assets/jorge/playable-half';F=OUT/'runtime-renders'
def tile(canvas,path,box):
    image=Image.open(path).convert('RGBA');image.thumbnail((box[2],box[3]));canvas.paste(image,(box[0],box[1]),image)
def run():
    image=Image.new('RGB',(1440,650),(25,29,34));draw=ImageDraw.Draw(image)
    for i,(name,view,label) in enumerate([('spartan','three_quarter','Standard CE Spartan'),('jorge','three_quarter','Jorge - game colors'),('jorge','back','Jorge - rear')]):
        tile(image,F/f'{name}-idle-{view}.png',(480*i,40,480,600));draw.text((480*i+20,16),label,fill='white')
    image.save(OUT/'standard-comparison.png')
    image=Image.new('RGB',(1600,480),(25,29,34));draw=ImageDraw.Draw(image)
    for i,view in enumerate(('front','back','left','right','three_quarter')):
        for row,base in enumerate((OUT.parent/'coverage-repair',OUT)):
            tile(image,base/'renders'/f'ce-idle-000-{view}.png',(i*320+row*160,30,160,220))
            draw.text((i*320+row*160+5,8),'Before' if row==0 else 'Half budget',fill='white')
        tile(image,F/f'jorge-idle-{view}.png',(i*320+40,270,160,200));draw.text((i*320+12,250),view+' / N64 colors',fill='white')
    image.save(OUT/'before-after.png')
    clips=json.loads((OUT/'gameplay-poses.json').read_text())['clips'];image=Image.new('RGB',(1280,1125),(25,29,34));draw=ImageDraw.Draw(image)
    for i,c in enumerate(clips):
        tile(image,F/f'motion-{i:02d}.png',(i%8*160,i//8*225,160,200));draw.text((i%8*160+2,i//8*225+201),str(i)+' '+c['name'][:24],fill='white')
    image.save(OUT/'motion-contact-sheet.png')
    a=Image.open(F/'jorge-idle-three_quarter.png').convert('RGBA');a=a.crop(a.getbbox());a.thumbnail((30,39));portrait=Image.new('RGBA',(32,40));portrait.alpha_composite(a,((32-a.width)//2,40-a.height));portrait.save(OUT/'jorge-portrait.png')
    v=np.array(portrait,dtype=np.uint16).reshape(-1,4);q=((v[:,0]>>3)<<11)|((v[:,1]>>3)<<6)|((v[:,2]>>3)<<1)|(v[:,3]>64)
    (A/'generated/jorge_portrait.c').write_text('#include "asset_jorge.h"\nconst uint16_t bg_jorge_portrait[32*40] __attribute__((aligned(16)))={'+','.join(hex(int(x)) for x in q)+'};\n')
    raw=(OUT/'jorge-playable-half.glb').read_bytes();n=struct.unpack_from('<I',raw,12)[0];gltf=json.loads(raw[20:20+n]);rows=[]
    for node in gltf['nodes']:
        if 'mesh' not in node:continue
        ps=gltf['meshes'][node['mesh']]['primitives'];rows.append({'component':node['extras']['source_component'],'vertices':sum(gltf['accessors'][p['attributes']['POSITION']]['count'] for p in ps),'triangles':sum(gltf['accessors'][p['indices']]['count']//3 for p in ps)})
    report={'vertices':sum(r['vertices'] for r in rows),'triangles':sum(r['triangles'] for r in rows),'bones':len(gltf['skins'][0]['joints']),'clips':len(gltf['animations']),'components':rows};assert report['bones']==85 and report['clips']==39
    (OUT/'export-inventory.json').write_text(json.dumps(report,indent=2)+'\n');print({k:v for k,v in report.items() if k!='components'})
if __name__=='__main__':run()
