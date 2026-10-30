#!/usr/bin/env python3
"""Pack owned CE damage arrows, retaining 8-bit coverage (no alpha threshold)."""
import contextlib,io,json,hashlib
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/m64-polish';OUT.mkdir(parents=True,exist_ok=True)
with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
 from reclaimer.meta.wrappers.halo1_map import Halo1Map
 from reclaimer.bitmaps.bitmap_decompilation import extract_bitmaps
 h=Halo1Map();h.load_map(ROOT/'build/n64/assets/bloodgulch-decompressed.map')
 e=h.tag_index.tag_index
 ix=next(i for i,t in enumerate(e) if t.class_1.enum_name=='hud_globals')
 d=h.get_meta(ix).hud_damage_indicators
 bi=d.indicator_bitmap.id&65535;b=h.get_meta(bi);h.meta_to_tag_data(b,'bitm',e[bi])
 extract_bitmaps(b,'damage',out_dir=OUT,bitmap_ext='png',halo_map=h)
im=Image.open(OUT/'damage.png').convert('RGBA');lines=['#include "asset_hud.h"'];spec=[];report={'bitmap':e[bi].path,'color_argb':hex(d.color),'offsets':[d.top_offset,d.left_offset,d.bottom_offset,d.right_offset],'sequences':[]}
for n,seq in enumerate((d.sequence_index,d.multiplayer_sequence_index)):
 s=b.sequences.STEPTREE[seq].sprites.STEPTREE[0]
 bounds=[round(x*v) for x,v in zip((s.left_side,s.top_side,s.right_side,s.bottom_side),(im.width,im.height,im.width,im.height))]
 crop=im.crop(bounds)
 # AY8 source intensity is duplicated into alpha by the decompressor.
 mask=crop.getchannel('A');mask.save(OUT/f'damage-{n}-alpha.png')
 stride=(mask.width+7)&~7;data=bytearray(stride*mask.height)
 for y in range(mask.height):data[y*stride:y*stride+mask.width]=mask.crop((0,y,mask.width,y+1)).tobytes()
 lines.append(f'static const uint8_t damage_{n}[] __attribute__((aligned(8)))={{'+','.join(map(str,data))+'};')
 spec.append(f'{{damage_{n},{mask.width},{mask.height},{stride}}}')
 report['sequences'].append({'sequence':seq,'bounds':bounds,'size':mask.size,'alpha_values':len(set(mask.tobytes()))})
lines.append('const bg_scope_image bg_damage_images[2]={'+','.join(spec)+'};')
lines.append(f'const uint32_t bg_damage_color=0x{((d.color<<8)&0xffffffff)|(d.color>>24):08x};')
lines.append('const uint16_t bg_damage_offsets[4]={'+','.join(map(str,report['offsets']))+'};')
# Weapon-specific screen-flash tags, following the existing damage profile map.
from extract_combat import PROFILES
from extract_extended import tag_values
import math
paths={name:('weapons\\'+weapon+'\\'+leaf if weapon else 'globals\\'+leaf) for name,weapon,leaf in PROFILES}
paths.update(HOG=r'vehicles\warthog\bullet',GHOST=r'vehicles\ghost\ghost bolt',TANK=r'vehicles\scorpion\shell explosion',TANK_MG=r'vehicles\scorpion\bullet',BANSHEE=r'vehicles\banshee\banshee bolt',FUEL_ROD=r'vehicles\banshee\fuel rod explosion',WRAITH=r'vehicles\wraith\explosion',SHADE=r'vehicles\c gun turret\bolt')
with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
 campaign=Halo1Map();campaign.load_map(ROOT/'build/n64/assets/b40-decompressed.map')
rows={}
for name,path in paths.items():
 cache=h if any(e.path==path and e.class_1.enum_name=='damage_effect' for e in h.tag_index.tag_index) else campaign
 ix=next(i for i,e in enumerate(cache.tag_index.tag_index) if e.path==path and e.class_1.enum_name=='damage_effect')
 block=cache.get_meta(ix,disable_tag_cleaning=True).screen_flash
 flash=tag_values(block);flash['zero_scale']=0.0;flash['path']=path
 rows[name]=flash
rows['LEGACY']=rows['AR'];report['screen_flashes']=rows
lines+=['#include "damage_flash.h"','const bg_damage_flash_definition bg_damage_flashes[BG_D_COUNT]={']
for name,d in rows.items():
 if name in ('WRAITH','SHADE'):lines.append('#ifdef BG_ENEMY_VEHICLES')
 types=['none','lighten','darken','max','min','invert','tint'];fades=['linear','early','very_early','late','very_late','cosine']
 rgba=[round(d['tint_lower_bound'][a]*255) for a in 'rgba']
 def cf(v):return format(v,'.9g')+('f' if '.' in format(v,'.9g') or 'e' in format(v,'.9g') else '.0f')
 lines.append('[BG_D_'+name+']={'+','.join([cf(d['duration']),cf(d['maximum_intensity']),cf(d['zero_scale']),str(types.index(d['type'])),str(['low','medium','high'].index(d['priority'])),str(fades.index(d['fade_function'])),'{'+','.join(map(str,rgba))+'}'])+'},')
 if name in ('WRAITH','SHADE'):lines.append('#endif')
lines+=['};','const uint8_t bg_damage_fades[6][1024]={']
for kind in range(6):
 values=[]
 for i in range(1024):
  x=i/1023;v=[x,x**.5,x**.25,x*x,x**4,(math.sin(x*math.pi-math.pi/2)+1)/2][kind]
  values.append(str(max(0,min(255,int(v*255)))))
 lines.append('{'+','.join(values)+'},')
lines.append('};')
f=ROOT/'halo64-assets/generated/hud_damage_data.c';f.write_text('\n'.join(lines)+'\n');report['bank_sha256']=hashlib.sha256(f.read_bytes()).hexdigest()
(OUT/'damage-source.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
