"""Validate the exact runtime icon bank, pixel symmetries and prompt footprint."""
from pathlib import Path
import subprocess
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
out = ROOT/'build/n64/button-audit'
out.mkdir(parents=True, exist_ok=True)
c = out/'icon-test.c'
c.write_text('''#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include <stdio.h>
#include "hud_pixels.h"
#include "hud_buttons.h"
int main(void){hud_buttons_init();fwrite(hud_button_pixels,1,sizeof(hud_button_pixels),stdout);}
''')
exe=out/'icon-test'
subprocess.run(['clang','-std=c17','-Wall','-Wextra','-Werror','-Wno-unused-function',
                '-fsanitize=address,undefined','-I'+str(ROOT/'port/n64'),str(c),'-o',str(exe)],check=True)
bank=subprocess.check_output([str(exe)])
assert len(bank)==1536
n=np.frombuffer(bank,dtype=np.uint8)
pixels=np.stack([n>>4,n&15],axis=1).reshape(48,64)
icons=[pixels[i//4*16:i//4*16+16,i%4*16:i%4*16+16] for i in range(11)]
widths=[10,10,14,14,14,13,13,13,13,14,13]
heights=[10]*5+[13]*4+[10,13]
for p,w,h in zip(icons,widths,heights):
    assert not np.any(p[h:,:]) and not np.any(p[:,w:])
    assert set(np.unique(p))<={0,1,5,15}
    assert np.any(p==15) and np.any(p==1)
assert np.array_equal(icons[2][:10,:14]&1,np.fliplr(icons[3][:10,:14]&1))
assert np.array_equal(icons[4][:10,:14]&1,np.fliplr(icons[4][:10,:14]&1))
up,down,left,right=[p[:13,:13] for p in icons[5:9]]
assert np.array_equal(up,np.flipud(down))
assert np.array_equal(left,np.fliplr(right))
assert np.array_equal(up.T,left)
for selected,p in enumerate([up,down,left,right]):
    for d,(x,y) in enumerate([(4,0),(4,8),(0,4),(8,4)]):
        node=p[y:y+5,x:x+5]
        assert np.any(node==15)==(selected==d)
        if d!=selected:assert np.any(node==5)
# The longest interaction label plus either live-use icon fits a 160px view.
for label in ['PICK UP','FLIP WARTHOG','FLIP GHOST','FLIP BANSHEE','DRIVE SCORPION','GUNNER','PASSENGER','EXIT SCORPION']:
    for w in [10,13]:
        assert (24 if label=='PICK UP' else 0)+w+3+len(label)*5-1<=140
print('PASS: 1536-byte runtime atlas, native pixel bounds, mirrored L/R, symmetric Z, four exact C-direction rotations, split-screen prompt footprints')
