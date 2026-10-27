"""Check native mixed-case glyphs, atlas overlap and source silhouette bounds."""
import argparse
import json
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw
from pack_prompt_icons import bake
from test_render_matrix import function

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
    retired={y*64+x for y in range(116,124) for x in range(60)}
    assert all(i in retired or not b or a==b for i,(b,a) in enumerate(zip(before,after))), 'Existing HUD ink was overwritten'
    assert all(after[i]==0 for i in retired), 'Retired digit outlines are still in the atlas'
    cells=set()
    for g in range(37,67):
        x=40+(g-37)%5*4 if g<52 else 60
        y=52+(g-37)//5*6 if g<52 else (g-52)*6
        indices={yy*64+xx for yy in range(y,y+6) for xx in range(x,x+4)}
        assert not cells.intersection(indices)
        assert all(before[i]==0 for i in indices)
        assert any(after[i] for i in indices)
        cells.update(indices)
    assert all(i in cells or i in retired for i,(b,a) in enumerate(zip(before,after)) if a!=b)
    assert set(after)<={0,15}
    image=Image.new('RGB',(320,96),'#091923');draw=ImageDraw.Draw(image)
    samples=['Hold  Pick up', '2:05  Assault Rifle', '+1 Frag Grenade', '+3 Plasma Grenades',
             'Double Kill!', 'Rejoin in 3', 'Drive Warthog', 'Ride Scorpion']
    for row,text in enumerate(samples):
        for column,ch in enumerate(text):
            g=ord(ch)-48 if '0'<=ch<='9' else ord(ch)-65+10 if 'A'<=ch<='Z' else ord(ch)-97+37 if 'a'<=ch<='z' else {'+':63,'!':64,'.':65,':':66}.get(ch,-1)
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
    # Thin guards, grip connectors and barrels must belong to the weapon,
    # rather than appearing as detached coverage samples.
    for weapon in (1,6,7):
        icon=Image.open(output/f'icons/weapon-{weapon}.png')
        ink={(x,y) for y in range(icon.height) for x in range(icon.width)
             if icon.getpixel((x,y))}
        seen={next(iter(ink))};todo=list(seen)
        while todo:
            x,y=todo.pop()
            for dx in (-1,0,1):
                for dy in (-1,0,1):
                    p=x+dx,y+dy
                    if p in ink and p not in seen:seen.add(p);todo.append(p)
        assert seen==ink, f'Weapon {weapon} contains floating pixels'
    # Flood from the pistol's open trigger-guard interior. It must be enclosed
    # by ink, not leak through either end of the guard to the background.
    pistol=Image.open(output/'icons/weapon-1.png');seen={(7,5)};todo=list(seen)
    while todo:
        x,y=todo.pop()
        assert 0<x<pistol.width-1 and 0<y<pistol.height-1, 'Pistol guard is open'
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            p=x+dx,y+dy
            if p not in seen and not pistol.getpixel(p):seen.add(p);todo.append(p)
    assert len(seen)>=3, 'Pistol guard interior was filled in'
    hud=(ROOT/'port/n64/hud.c').read_text()
    # Exercise production hud_text rather than a duplicate renderer. Every
    # digit, uppercase/lowercase letter and punctuation must use the same
    # 4x6 source cell and a (1,1) shadow, including fading message text.
    c=output/'text-shadow.c'
    c.write_text('''#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "hud_pixels.h"
typedef struct { unsigned char r,g,b,a; } color_t;
static const color_t hud_shadow={3,13,22,235};
enum { TILE0 };
typedef struct { int x,y,w,h,u,v; color_t color; } quad;
static quad quads[256];static unsigned count;static color_t tint;
static void set_combiner(int n){assert(n==1);}
static void rdpq_set_prim_color(color_t c){tint=c;}
static void rdpq_texture_rectangle(int tile,int x,int y,int r,int b,int u,int v){
 assert(tile==TILE0);quads[count++]=(quad){x,y,r-x,b-y,u,v,tint};}
static void hud_text(const char *text,int x,int y,color_t color){
'''+function(hud,'hud_text')+'''}
int main(void){
 const char *s="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz+!.";
 for(unsigned pass=0;pass<2;pass++){
  color_t color={100,220,255,pass?64:255};count=0;hud_text(s,17,23,color);
  unsigned n=strlen(s);assert(count==2*n);
  for(unsigned i=0;i<n;i++){
   quad shadow=quads[i],ink=quads[n+i];
   assert(shadow.x==ink.x+1&&shadow.y==ink.y+1);
   assert(shadow.w==4&&shadow.h==6&&ink.w==4&&ink.h==6);
   assert(shadow.u==ink.u&&shadow.v==ink.v);
   assert(shadow.color.a==235u*color.a/255&&ink.color.a==color.a);
  }
 }
 puts("PASS: all digits and text use matching 4x6 glyphs and (1,1) fading shadows");
}
''')
    binary=output/'text-shadow'
    subprocess.run(['clang','-std=c17','-Wall','-Wextra','-Werror','-Wno-unused-function',
                    '-fsanitize=address,undefined','-I'+str(ROOT/'port/n64'),
                    str(c),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
    assert '"RELOADING"' not in hud and '"OVERHEATED"' not in hud and '"HEAT"' not in hud
    assert 'HUD_XBOX_EXIT' not in hud and 'HUD_EXIT' not in hud
    print('PASS: 4096-byte HUD preserves glyphs/meters/radar/reticles, retires digit outlines; 4x6 mixed-case grid; 2048-byte binary weapon masks; connected pistol guard, sniper barrel and rocket grip; invented status labels removed')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'build/n64-prompt-audit/pixels')
    run(parser.parse_args().output.resolve())
