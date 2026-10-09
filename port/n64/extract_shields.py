#!/usr/bin/env python3
"""Extract owned Xbox shield warnings and depletion sprites; no assets in Git."""
import audioop, contextlib, hashlib, json, wave
from pathlib import Path
from PIL import Image
from extract_extended import tag_values
ROOT=Path(__file__).resolve().parents[2]
A=ROOT/'build/n64/assets'; OUT=ROOT/'build/n64/generated'; WORK=A/'shields'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 WORK.mkdir(exist_ok=True); report={'tags':{},'audio':[]}; images=[]; sounds=[]
 with (WORK/'extract.log').open('w') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
  from reclaimer.meta.wrappers.halo1_map import Halo1Map
  from reclaimer.sounds.sound_decompilation import extract_h1_sounds
  from reclaimer.bitmaps.bitmap_decompilation import extract_bitmaps
  h=Halo1Map();h.load_map(A/'bloodgulch-decompressed.map');es=h.tag_index.tag_index
  def tag(path,kind):
   i=next(i for i,e in enumerate(es) if e.path==path and e.class_1.enum_name==kind)
   m=h.get_meta(i);report['tags'][path+' ['+kind+']']=tag_values(m);return i,m
  for name in ('shield_low','shield_depleted'):
   i,m=tag('sound\\sfx\\ui\\'+name,'sound');h.meta_to_tag_data(m,'snd!',es[i])
   extract_h1_sounds(m,name,out_dir=WORK,decode_adpcm=True)
   with wave.open(str(sorted((WORK/name).rglob('*.wav'))[0])) as w:
    rate=w.getframerate();width=w.getsampwidth();ch=w.getnchannels();pcm=w.readframes(w.getnframes())
   if ch==2:pcm=audioop.tomono(pcm,width,.5,.5)
   pcm=audioop.ratecv(pcm,width,1,rate,5512,None)[0];pcm=audioop.lin2lin(pcm,width,1)
   sounds.append(pcm);(WORK/(name+'.s8')).write_bytes(pcm)
   report['audio'].append({'name':name,'bytes':len(pcm),'rate':5512,'seconds':len(pcm)/5512,'tag':i})
  for name in ('shield_charge','shield_low','shield_depleted'):tag('sound\\sfx\\ui\\'+name,'sound_looping')
  for path,kind in [(r'characters\cyborg_mp\cyborg_mp','biped'),(r'characters\cyborg\cyborg','model_collision_geometry'),(r'characters\cyborg\shaders\shield hit','shader_transparent_plasma'),(r'characters\cyborg\cyborg shield depletion','effect'),(r'ui\hud\cyborg','unit_hud_interface')]:tag(path,kind)
  for name in ('shield jackal depletion','shield jackal sparks'):
   _,p=tag('effects\\particles\\energy\\'+name,'particle');i=p.bitmap.id&65535;m=h.get_meta(i)
   seq=m.sequences.STEPTREE[0];sp=seq.sprites.STEPTREE[0];bi=sp.bitmap_index
   crop=[sp.left_side,sp.top_side,sp.right_side,sp.bottom_side]
   h.meta_to_tag_data(m,'bitm',es[i]);prefix='bitmap-'+str(i);extract_bitmaps(m,prefix,out_dir=WORK,bitmap_ext='png',halo_map=h)
   im=Image.open(sorted(WORK.glob(prefix+'*.png'))[bi]).convert('RGBA')
   im=im.crop(tuple(round(v*(im.width if k%2==0 else im.height)) for k,v in enumerate(crop))).resize((16,16),Image.Resampling.BOX)
   im.putdata([(round(r*255/peak),round(g*255/peak),round(b*255/peak),round(a*peak/255)) if (peak:=max(r,g,b)) else (0,0,0,0) for r,g,b,a in im.getdata()]);images.append(im);im.save(WORK/(name+'.png'))
 lines=['/* Generated from owned Xbox cache. */','#include "shield_assets.h"']
 for i,s in enumerate(sounds):lines.append(f'static const int8_t pcm_{i}[]={{'+','.join(str(v if v<128 else v-256) for v in s)+'};')
 lines.append('const bg_audio_asset bg_shield_audio[2]={'+','.join('{pcm_%d,%d,5512,true}'%(i,len(s)) for i,s in enumerate(sounds))+'};')
 lines.append('const uint32_t bg_shield_textures[2][256] __attribute__((aligned(8)))={')
 for im in images:lines.append('{'+','.join(f'0x{r:02x}{g:02x}{b:02x}{a:02x}' for r,g,b,a in im.getdata())+'},')
 lines.append('};');path=OUT/'shield_data.c';path.write_text('\n'.join(lines)+'\n')
 report['inputs']={str(p.relative_to(ROOT)):sha(p) for p in [A/'bloodgulch-decompressed.map',Path(__file__).resolve(),ROOT/'source/objects/damage.c',ROOT/'source/interface/hud_unit.c',ROOT/'source/interface/hud_sounds.c']}
 report['generated_sha256']=sha(path);(OUT/'shield-report.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report['audio']));print('Shield bank:',sum(map(len,sounds))+2048,'bytes')
if __name__=='__main__':main()
