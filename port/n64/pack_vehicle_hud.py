"""Source Shade reticle in two spare quadrants of the existing 4 KiB HUD atlas."""
import contextlib,json
from pathlib import Path
from PIL import Image,ImageOps
from pack_enemy_vehicles import ROOT,OUT,BANK

def pack():
 from reclaimer.meta.wrappers.halo1_map import Halo1Map
 from extract_extended import tag_values
 with (OUT/'hud-inspect.log').open('w') as log,contextlib.redirect_stdout(log):
  h=Halo1Map();h.load_map(ROOT/'build/n64/assets/b40-decompressed.map');es=h.tag_index.tag_index
  metadata={}
  for i,e in enumerate(es):
   if e.class_1.enum_name=='weapon_hud_interface' and e.path in (r'vehicles\wraith\wraith mortar',r'vehicles\c gun turret\c gun turret'):
    metadata[e.path]=tag_values(h.get_meta(i,disable_tag_cleaning=True))
  (OUT/'hud-interfaces.json').write_text(json.dumps(metadata))
 sequences={name:next(c for c in row['crosshairs'] if c['crosshair_type']=='aim')['crosshair_overlays'][0]['sequence_index'] for name,row in metadata.items()}
 assert sequences=={r'vehicles\wraith\wraith mortar':9,r'vehicles\c gun turret\c gun turret':12}
 raw=json.loads((ROOT/'build/n64/assets/extended-raw.json').read_text())['hud']['reticles']
 sprite=raw['sequences'][12]['sprites'][0];path=Path(next(p for p in raw['files'] if p.endswith(f"__{sprite['bitmap']}.png")))
 image=Image.open(path).convert('RGBA');l,t,r,b=sprite['bounds'];image=image.crop((round(l*image.width),round(t*image.height),round(r*image.width),round(b*image.height)))
 image.save(OUT/'shade-reticle-source.png')
 mask=image.getchannel('A').point(lambda a:255 if a>=128 else 0).resize((24,24),Image.Resampling.BOX)
 mask=Image.blend(mask,ImageOps.mirror(mask),.5).point(lambda a:255 if a>=72 else 0)
 mask.save(OUT/'shade-reticle-native.png')
 rows=[[sum(1<<(11-x) for x in range(12) if mask.getpixel((x,y+12*half))) for y in range(12)] for half in range(2)]
 target=BANK/'enemy_vehicle_data.c';text=target.read_text().split('/* Enemy vehicle HUD */')[0]
 text+='/* Enemy vehicle HUD */\nconst uint16_t bg_enemy_shade_reticle[2][12]={'+','.join('{'+','.join(str(v) for v in row)+'}' for row in rows)+'};\n';target.write_text(text)
 (BANK/'hud-report.json').write_text(json.dumps({'source_sequences':sequences,'shade_atlas_quadrants':[15,16],'wraith_reuses_rocket_sequence':9,'atlas_bytes_unchanged':4096,'shade_rows':rows},indent=2)+'\n')
 print('Source vehicle reticles: Wraith sequence 9, Shade sequence 12')

if __name__=='__main__':pack()
