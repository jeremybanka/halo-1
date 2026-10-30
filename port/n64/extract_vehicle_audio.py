"""Bounded original Wraith/Shade weapon PCM, streamed by the native mixer."""
import audioop,contextlib,hashlib,json,wave
from pack_enemy_vehicles import ROOT,OUT,BANK

def extract():
 from reclaimer.meta.wrappers.halo1_map import Halo1Map
 from reclaimer.sounds.sound_decompilation import extract_h1_sounds
 from extract_extended import tag_values
 report={}
 with (OUT/'audio.log').open('w') as log,contextlib.redirect_stdout(log):
  h=Halo1Map();h.load_map(ROOT/'build/n64/assets/b40-decompressed.map');es=h.tag_index.tag_index
  def tag(path,kind):
   i=next(i for i,e in enumerate(es) if e.path==path and e.class_1.enum_name==kind);return h.get_meta(i),i
  for name,path in [('wraith',r'vehicles\wraith\effects\wraith fire'),('shade',r'vehicles\c gun turret\effects\c gun turret fire'),('wraith-engine',r'sound\sfx\vehicles\wraith_eng1'),('shade-engine',r'sound\sfx\vehicles\c_turret1')]:
   if name.endswith('-engine'):soundpath=path
   else:
    effect,_=tag(path,'effect');fx=tag_values(effect)
    soundpath=next(p['type'] for e in fx['events'] for p in e['parts'] if p['effect_class']=='sound')
   sound,i=tag(soundpath,'sound');h.meta_to_tag_data(sound,'snd!',es[i]);extract_h1_sounds(sound,name,out_dir=OUT/'sounds',decode_adpcm=True)
   wav=sorted((OUT/'sounds'/name).rglob('*.wav'))[0]
   with wave.open(str(wav),'rb') as w:pcm=w.readframes(w.getnframes());channels=w.getnchannels();width=w.getsampwidth();rate=w.getframerate()
   if channels==2:pcm=audioop.tomono(pcm,width,.5,.5)
   pcm=audioop.lin2lin(audioop.ratecv(pcm,width,1,rate,11025,None)[0],width,1)
   (BANK/('enemy-'+name+'.s8')).write_bytes(pcm+pcm[:1024] if name.endswith('-engine') else pcm);report[name]={'effect':path,'tag':soundpath,'permutation':str(wav.relative_to(OUT)),'samples':len(pcm),'rate':11025,'sha256':hashlib.sha256(pcm).hexdigest()}
 (BANK/'audio-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':extract()
