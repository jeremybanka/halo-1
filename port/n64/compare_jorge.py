from PIL import Image,ImageDraw,ImageFont
from pathlib import Path
import numpy as np,json
p=Path(__file__).resolve().parents[2]/'halo64-assets/assets/jorge/renders';vs=['front','back','left','right','three_quarter']
try:font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',19)
except OSError:font=ImageFont.load_default()
im=Image.new('RGB',(1600,880),(28,34,39));d=ImageDraw.Draw(im);metrics={}
for i,v in enumerate(vs):
 d.text((i*320+15,18),v.replace('_',' ').upper(),font=font,fill=(225,230,220))
 masks=[]
 for j,prefix in enumerate(['before','after']):
  a=Image.open(p/(prefix+'-'+v+'.png')).convert('RGBA');masks.append(np.array(a)[:,:,3]>127)
  a.thumbnail((310,388));im.paste(a,(i*320+5,53+j*412),a)
 metrics[v]={'silhouette_iou':float((masks[0]&masks[1]).sum()/(masks[0]|masks[1]).sum()),'source_pixels':int(masks[0].sum()),'final_pixels':int(masks[1].sum())}
d.text((15,442),'RETAIL REFERENCE  /  33,208 TRIANGLES',font=font,fill='white')
d.text((15,855),'SEMANTIC REBUILD  /  600 TRIANGLES',font=font,fill='white')
im.save(p/'comparison.jpg',quality=94)
(p.parent/'silhouette-comparison.json').write_text(json.dumps(metrics,indent=2));print(metrics)
# A larger three-quarter pair for a useful final preview.
im=Image.new('RGB',(1280,860),(28,34,39));d=ImageDraw.Draw(im)
for i,prefix in enumerate(['before','after']):
 a=Image.open(p/(prefix+'-three_quarter.png'));im.paste(a,(i*640,50),a)
 d.text((i*640+32,20),['RETAIL / 33,208 TRIANGLES','REBUILD / 600 TRIANGLES'][i],font=font,fill='white')
im.save(p/'hero-comparison.jpg',quality=95)
