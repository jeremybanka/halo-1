"""Matched 160-pixel shoulder study from independently exported pilot data."""
import json,sys
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from audit_models import Mesh,matching_bounds
from demake_raster import Raster
output=Path(sys.argv[1]);data=json.loads((output/'pilot-render.json').read_text());meshes=[Mesh(np.array(r['positions']),rgb=np.array(r['colors'])) for r in data];raster=Raster(output);sheet=Image.new('RGB',(640,1080),'#202428');draw=ImageDraw.Draw(sheet)
for vi,direction in enumerate(((.8,.2,-1),(0,0,-1),(-.8,.2,-1))):
    bounds=matching_bounds(meshes,direction)
    for shade in range(2):
        for i,(row,mesh) in enumerate(zip(data,meshes)):
            model=mesh if shade else Mesh(mesh.p,rgb=np.full_like(mesh.p,205));im,_,_=raster.render(model,bounds,direction,width=160,height=160);y=(vi*2+shade)*180;sheet.paste(im,(i*160,y+20));draw.text((i*160+3,y+3),row['label']+' / '+str(len(mesh.p)),fill='white')
sheet.save(output/'shoulder-study.png')
