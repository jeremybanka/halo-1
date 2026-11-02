"""Stage a complete reviewable native bank and matching production portraits."""
import argparse,json,shutil
from pathlib import Path
import numpy as np
from PIL import Image
from audit_models import Mesh,matching_bounds
from demake_raster import Raster
from pack_gungnir import palette


def run(packed,firstperson,output):
    output.mkdir(parents=True,exist_ok=True)
    for p in packed.iterdir():
        if p.is_file():shutil.copy2(p,output/p.name)
    shutil.copy2(firstperson/'gungnir_firstperson_data.c',output/'gungnir_firstperson_data.c')
    data=np.load(packed/'gungnir-0-preview.npz');direction=(.75,.2,.55);base=data['frames_0'][0]/512;tri=data['triangles'];neutral=Mesh(base[tri],rgb=data['colors'][tri]);bounds=matching_bounds([neutral],direction);raster=Raster(output)
    lines=['/* Matched packed GUNGNIR menu portraits. */','#include "asset_gungnir.h"','const uint16_t bg_gungnir_portraits[4][32*40]={']
    for profile in range(4):
        mesh=Mesh(base[tri],rgb=palette(data['colors'],data['mask'],profile)[tri]);im,ids,_=raster.render(mesh,bounds,direction,width=32,height=40);rgb=np.array(im,dtype=np.uint16);alpha=ids>=0;rgba=np.dstack((rgb.astype(np.uint8),alpha.astype(np.uint8)*255));Image.fromarray(rgba).save(output/f'portrait-{profile}.png');pixels=((rgb[:,:,0]>>3)<<11)|((rgb[:,:,1]>>3)<<6)|((rgb[:,:,2]>>3)<<1)|alpha
        lines.append('{'+','.join(hex(int(v)) for v in pixels.ravel())+'},')
    lines.append('};');(output/'gungnir_portraits.c').write_text('\n'.join(lines)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('packed',type=Path);p.add_argument('firstperson',type=Path);p.add_argument('output',type=Path);a=p.parse_args();run(a.packed,a.firstperson,a.output)
