"""Compare production C tinting with review portraits for both packed LODs."""
from pathlib import Path
import subprocess, tempfile
import numpy as np
from review_armor_palettes import A, ROOT, masks, palette

def run():
    cases=[]; expected=[]
    for lod in ('near','far'):
        colors=np.load(A/f'assets/jorge/playable-lods/{lod}/packed-preview.npz')['colors']
        mask=masks(lod)
        kinds=mask&15;dark=(mask&16)!=0
        assert len(mask)==len(colors) and set(kinds)=={0,1,2,3,4,5,6} and dark.any()
        visor=np.all(colors==[255,224,18],axis=1)
        assert visor.any() and not mask[visor].any()
        assert not mask[(colors.max(axis=1)<=65)&(mask!=2)].any()
        variants=[]
        for p in range(4):
            result=palette(colors,mask,p)
            assert np.array_equal(result[mask==0],colors[mask==0])
            if p==3:assert np.array_equal(result[(mask!=2)&~dark],colors[(mask!=2)&~dark])
            else:assert np.any(result[mask==1]!=colors[mask==1])
            assert np.array_equal(result[dark],palette(colors,kinds,p)[dark]*4//5)
            gray=result[mask==2]
            assert np.array_equal(gray[:,0],gray[:,1]) and np.array_equal(gray[:,1],gray[:,2])
            assert np.array_equal(gray,palette(colors,mask,3)[mask==2])
            variants.append(result.tobytes())
            for c,m,r in zip(colors,mask,result):
                packed=(int(c[0])<<24)|(int(c[1])<<16)|(int(c[2])<<8)|173
                cases.append(f'{packed} {p} {m}\n')
                expected.append((int(r[0])<<24)|(int(r[1])<<16)|(int(r[2])<<8)|173)
        assert len(set(variants))==4
    with tempfile.TemporaryDirectory(prefix='armor-palette-') as temp:
        temp=Path(temp)
        (temp/'test.c').write_text('''#include <stdio.h>
#include "armor_palette.h"
int main(void){unsigned color,profile,mask;
while(scanf("%u %u %u",&color,&profile,&mask)==3)
printf("%u\\n",bg_jorge_palette_color(color,profile,mask));}
''')
        subprocess.run(['clang','-std=c17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
                        '-I'+str(ROOT/'port/n64'),str(temp/'test.c'),'-o',str(temp/'test')],check=True)
        output=subprocess.check_output([str(temp/'test')],input=''.join(cases),text=True)
        assert list(map(int,output.split()))==expected
    print(f'PASS: {len(cases)} production vertex/palette pairs agree with C; gray bags, protected visor/fabric/alpha, component accents and 20% darker regions')

if __name__=='__main__':run()
