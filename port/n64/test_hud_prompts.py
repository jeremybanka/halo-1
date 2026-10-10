"""Check native mixed-case glyphs, atlas overlap and source silhouette bounds."""
import argparse
import json
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw
from pack_prompt_icons import bake

ROOT = Path(__file__).resolve().parents[2]


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    old = subprocess.check_output(['git', 'show', '656e18b5:port/n64/hud_pixels.h'], cwd=ROOT)
    (output/'old_pixels.h').write_bytes(old)
    banks = []
    for name, header in [('old', 'old_pixels.h'), ('new', 'hud_pixels.h')]:
        c = output/(name+'.c')
        c.write_text('#include <stdint.h>\n#include <stdio.h>\n#include "'+header+'"\n'
                     'int main(void){hud_pixels_init();fwrite(hud_pixels,1,sizeof(hud_pixels),stdout);}\n')
        binary = output/name
        subprocess.run(['clang','-std=c17','-Wall','-Wextra','-Werror','-Wno-unused-function',
                        '-fsanitize=address,undefined','-I'+str(ROOT/'port/n64'),
                        '-I'+str(output),str(c),'-o',str(binary)],check=True)
        packed = subprocess.check_output([str(binary)])
        assert len(packed)==4096
        banks.append([a for b in packed for a in (b>>4,b&15)])
    before, after = banks
    assert all(not b or a==b for b,a in zip(before,after)), 'Existing HUD ink was overwritten'
    cells=set()
    for g in range(37,66):
        x=40+(g-37)%5*4 if g<52 else 60
        y=52+(g-37)//5*6 if g<52 else (g-52)*6
        indices={yy*64+xx for yy in range(y,y+6) for xx in range(x,x+4)}
        assert not cells.intersection(indices)
        assert all(before[i]==0 for i in indices)
        assert any(after[i] for i in indices)
        cells.update(indices)
    assert all(i in cells for i,(b,a) in enumerate(zip(before,after)) if a!=b)
    assert set(after)<={0,15}
    image=Image.new('RGB',(320,96),'#091923');draw=ImageDraw.Draw(image)
    samples=['Hold  Pick up', '+50 Assault Rifle', '+1 Frag Grenade', '+3 Plasma Grenades',
             'Double Kill!', 'Rejoin in 3', 'Drive Warthog', 'Ride Scorpion']
    for row,text in enumerate(samples):
        for column,ch in enumerate(text):
            g=ord(ch)-48 if '0'<=ch<='9' else ord(ch)-65+10 if 'A'<=ch<='Z' else ord(ch)-97+37 if 'a'<=ch<='z' else {'+':63,'!':64,'.':65}.get(ch,-1)
            if g<0:continue
            x=(g%10)*6 if g<37 else 40+(g-37)%5*4 if g<52 else 60
            y=(g//10)*8 if g<37 else 52+(g-37)//5*6 if g<52 else (g-52)*6
            for yy in range(6):
                for xx in range(4):
                    if after[(y+yy)*64+x+xx]:image.putpixel((8+column*5+xx,4+row*11+yy),(100,220,255))
    image.resize((960,288),Image.Resampling.NEAREST).save(output/'font.png')
    bake(output/'icons')
    report=json.loads((output/'icons/icons-report.json').read_text())
    for i,record in enumerate(report['icons']):
        icon=Image.open(output/f'icons/weapon-{i}.png')
        assert icon.width<=31 and icon.height<=12
        assert set(icon.getdata())=={0,255}
        assert icon.getbbox() is not None
    # The long sniper barrel must connect to its receiver after reduction.
    icon=Image.open(output/'icons/weapon-6.png');ink=set()
    for y in range(icon.height):
        for x in range(icon.width):
            if icon.getpixel((x,y)):ink.add((x,y))
    seen={next(iter(ink))};todo=list(seen)
    while todo:
        x,y=todo.pop()
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                p=x+dx,y+dy
                if p in ink and p not in seen:seen.add(p);todo.append(p)
    assert seen==ink, 'Sniper barrel broke into disconnected pixels'
    hud=(ROOT/'port/n64/hud.c').read_text()
    assert '"RELOADING"' not in hud and '"OVERHEATED"' not in hud and '"HEAT"' not in hud
    assert 'HUD_XBOX_EXIT' not in hud and 'HUD_EXIT' not in hud
    print('PASS: 4096-byte HUD unchanged outside 29 new glyph cells; old digits, meters, radar and reticles intact; 4x6 mixed-case grid; 2048-byte binary weapon masks; connected sniper barrel; invented status labels removed')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'build/n64-prompt-audit/pixels')
    run(parser.parse_args().output.resolve())
