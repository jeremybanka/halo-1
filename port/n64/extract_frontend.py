#!/usr/bin/env python3
"""Owned Xbox front-end tags -> original layout metadata and streamed ROM bank.
Textures, full ASCII fonts and all original backdrop triangles retain provenance.
No asset blobs are committed. Runtime only loads the current front-end page.
"""
from pathlib import Path
import audioop,contextlib,hashlib,io,json,math,struct,sys,wave
from PIL import Image
from extract_extended import open_cache
from reclaimer.bitmaps.bitmap_decompilation import extract_bitmaps
from reclaimer.model.model_decompilation import extract_model
from reclaimer.sounds.sound_decompilation import extract_h1_sounds
import extract_menu_assets as fonts
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'build/n64';A=OUT/'assets/frontend';G=OUT/'generated';D=OUT/'frontend-files'
for p in [A,G,D]:p.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def cstr(s):return json.dumps(s,ensure_ascii=True)
def short(s):return s.replace('ui\\shell\\main_menu\\','')
with (A/'extraction.log').open('w') as log,contextlib.redirect_stdout(log):
 h=open_cache(ROOT/'build/assets/halo-retail/maps/ui.map',A)
e=h.tag_index.tag_index;paths={t.path:i for i,t in enumerate(e)}
blob=bytearray();images=[];image_groups={};nodes=[];records={};meshes=[]
def add(data):
 while len(blob)%16:blob.append(0)
 off=len(blob);blob.extend(data);return off

def bitmap(tag):
 tag&=65535
 if tag in image_groups:return image_groups[tag]
 m=h.get_meta(tag);h.meta_to_tag_data(m,'bitm',e[tag]);name='bitmap-'+str(tag)
 with contextlib.redirect_stdout(io.StringIO()):extract_bitmaps(m,name,out_dir=A,bitmap_ext='png',halo_map=h)
 files=sorted(A.glob(name+'*.png'))
 # Bitmap indices are numeric, not lexicographic (__10 must follow __9).
 files.sort(key=lambda p:int(p.stem.split('__')[-1])if '__' in p.stem else 0)
 result=[]
 for frame,p in enumerate(files):
  im=Image.open(p).convert('RGBA');im=im.resize((max(1,im.width//2),max(1,im.height//2)),Image.Resampling.LANCZOS)
  offset=add(im.tobytes());result.append(len(images));images.append(dict(offset=offset,w=im.width,h=im.height,tag=tag,frame=frame))
 image_groups[tag]=result;return result
# Keep source front-end definitions, even where the current capability table
# does not allow entering them. No strings gain "disabled"/"coming soon" labels.
for tag,t in enumerate(e):
 if t.class_1.enum_name!='ui_widget_definition':continue
 m=h.get_meta(tag);b=list(m.bounds);ref=m.background_bitmap.id&65535
 # Front-end relevant nodes: screen chrome, main/multiplayer/join/carousels/pregame.
 path=t.path
 keep=any(s in path for s in ('main_menu\\main_menu','main_menu\\halo_logo','multiplayer_type_select','main_menu\\gametype_select','main_menu\\button_key','main_menu\\a_butn','main_menu\\b_butn','main_menu\\=','main_menu\\blueline','postgame','settings_select','player_profiles_select','main_menu\\x_butn'))
 if not keep:continue
 if ref!=65535:bitmap(ref)
 text='';tr=m.text_box.text_label_unicode_strings_list.id&65535
 if tr!=65535:
  strings=h.get_meta(tr).strings.STEPTREE;ix=m.text_box.string_list_index
  if 0<=ix<len(strings):text=str(strings[ix].data).replace('\r\n','\n')
 color=m.text_box.text_color;rgba=[max(0,min(255,round(v*255)))for v in [color.r,color.g,color.b,color.a]]
 node=dict(tag=tag,path=path,bounds=b,bitmap=ref if ref!=65535 else -1,text=text,font=0 if 'large' in m.text_box.text_font.filepath else 1,align=m.text_box.justification.data,text_x=m.text_box.horizontal_offset,text_y=m.text_box.vertical_offset,rgba=rgba)
 nodes.append(node)
 records[path]={**node,'children':[dict(path=c.widget_tag.filepath,x=c.horizontal_offset,y=c.vertical_offset)for c in m.child_widgets.STEPTREE]}
# Fonts keep the original lowercase glyphs too (the original descriptions are mixed case).
fonts.COUNT=95;fo=[];fp=[];fg=[];fa=[]
for name in fonts.FONT_NAMES:
 m=h.get_meta(paths[name]);pages,data,glyphs=fonts.font_bank(m);fo.append(add(data));fp.append(len(pages));fg.append(glyphs);fa.append(m.ascending_height)
 assert len(pages)<=4
# Original sky and ring, with their exact source geometry; textures limited to
# a TMEM-sized tile per material. World conversion is Halo XYZ -> X,Z,-Y.
for tag in [2,16]:
 m=h.get_meta(tag);h.meta_to_tag_data(m,'mode',e[tag]);model=max((x for x in extract_model(m,write_jms=False)if x.tris),key=lambda x:len(x.tris))
 for material,s in enumerate(m.shaders.STEPTREE):
  shader=h.get_meta(s.shader.id);refs=[]
  def refs_in(o):
   if hasattr(o,'filepath'):
    if o.filepath in paths and e[paths[o.filepath]].class_1.enum_name=='bitmap':refs.append(paths[o.filepath])
   elif hasattr(o,'desc') and o.desc.get('NAME_MAP'):
    for k in o.desc['NAME_MAP']:
     if k not in ('pointer','id','path_pointer','path_length') and hasattr(o,k):refs_in(getattr(o,k))
   elif isinstance(o,(list,tuple)):
    for v in o:refs_in(v)
  refs_in(shader)
  # Explicit original diffuse layers: sky space/planets/galaxy and ring base/shadow.
  source_tags={3:6,7:8,9:10,11:12,17:18,21:22,25:26}
  tex_tag=source_tags.get(s.shader.id&65535,refs[0]if refs else 6)
  bitmap(tex_tag);src=next(p for p in A.glob('bitmap-'+str(tex_tag)+'*.png'))
  im=Image.open(src).convert('RGBA').resize((32,32),Image.Resampling.BOX)
  image_id=len(images);images.append(dict(offset=add(im.tobytes()),w=32,h=32,tag=tex_tag,frame=65535))
  verts=[]
  for tri in model.tris:
   if tri.shader!=material:continue
   for vi in [tri.v0,tri.v1,tri.v2]:
    v=model.verts[vi];x,y,z=v.pos_x/100,v.pos_y/100,v.pos_z/100
    if tag==2:x/=100;y/=100;z/=100
    else:
     # scenario scenery placement: yaw -24 degrees, roll -10 degrees.
     a=-math.pi/18; y,z=y*math.cos(a)-z*math.sin(a),y*math.sin(a)+z*math.cos(a)
     a=-math.pi*24/180;x,y=x*math.cos(a)-y*math.sin(a),x*math.sin(a)+y*math.cos(a)
     x+=12.3;y-=1.8;z+=15.5
    pos=[round(x*32),round(z*32),round(-y*32)];assert all(-32768<=n<=32767 for n in pos)
    uv=[round(v.tex_u*32*32),round((1-v.tex_v)*32*32)]
    # RDP texture coordinates are signed16; wrapping by whole tile periods retains sampling.
    uv=[((n+32768)%65536)-32768 for n in uv];verts.append((pos,uv))
  if len(verts)%2:verts.append(verts[-1])
  data=bytearray()
  for j in range(0,len(verts),2):
   a,b=verts[j:j+2];data+=struct.pack('>3hH3hHII4h',*a[0],0,*b[0],0,0xffffffff,0xffffffff,*a[1],*b[1])
  meshes.append(dict(offset=add(data),count=len(verts),image=image_id,alpha=int(material==2 and tag==16),source=e[tag].path,triangles=sum(t.shader==material for t in model.tris)))
# Original menu effects and the title track, stored in ROM and read on demand.
audio={}
for name,tag in [('back',892),('forward',893),('cursor',977),('reject',978),('music-in',980),('music-loop',981)]:
 m=h.get_meta(tag);h.meta_to_tag_data(m,'snd!',e[tag])
 with contextlib.redirect_stdout(io.StringIO()):extract_h1_sounds(m,name,out_dir=A,decode_adpcm=True)
 files=sorted((A/name).rglob('*.wav'));pcm=bytearray()
 for file in files:
  with wave.open(str(file))as w:
   raw=w.readframes(w.getnframes());rate=w.getframerate();width=w.getsampwidth();channels=w.getnchannels()
  if channels==2:raw=audioop.tomono(raw,width,.5,.5)
  raw=audioop.ratecv(raw,width,1,rate,11025,None)[0];pcm.extend(audioop.lin2lin(raw,width,1))
  if not name.startswith('music'):break
 assert pcm,name
 (D/(name+'.s8')).write_bytes(pcm);audio[name]=dict(tag=e[tag].path,bytes=len(pcm),rate=11025)
# Countdown tone is the original multiplayer countdown asset, not a synthesized beep.
with contextlib.redirect_stdout(io.StringIO()):blood=open_cache(ROOT/'build/assets/halo-retail/maps/bloodgulch.map',A)
be= blood.tag_index.tag_index
candidates=[i for i,t in enumerate(be)if t.class_1.enum_name=='sound' and ('countdown' in t.path or 'countdown' in t.path.replace('_',''))]
assert candidates,'Missing original countdown sound'
tag=next((i for i in candidates if 'for_respawn' not in be[i].path and 'end' not in be[i].path),candidates[0])
m=blood.get_meta(tag);blood.meta_to_tag_data(m,'snd!',be[tag])
with contextlib.redirect_stdout(io.StringIO()):extract_h1_sounds(m,'countdown',out_dir=A,decode_adpcm=True)
file=sorted((A/'countdown').rglob('*.wav'))[0]
with wave.open(str(file))as w:
 raw=w.readframes(w.getnframes());rate=w.getframerate();width=w.getsampwidth();channels=w.getnchannels()
if channels==2:raw=audioop.tomono(raw,width,.5,.5)
pcm=audioop.lin2lin(audioop.ratecv(raw,width,1,rate,11025,None)[0],width,1)
(D/'countdown.s8').write_bytes(pcm);audio['countdown']=dict(tag=be[tag].path,bytes=len(pcm),rate=11025)
intro=(D/'music-in.s8').read_bytes();loop=(D/'music-loop.s8').read_bytes();(D/'music.s8').write_bytes(intro+loop)
# Postgame chrome is supplied by the gameplay HUD rather than ui.map.
post=next(i for i,t in enumerate(be)if t.path==r'ui\shell\bitmaps\postgame_carnage_report')
m=blood.get_meta(post);blood.meta_to_tag_data(m,'bitm',be[post])
with contextlib.redirect_stdout(io.StringIO()):extract_bitmaps(m,'postgame',out_dir=A,bitmap_ext='png',halo_map=blood)
im=Image.open(A/'postgame.png').convert('RGBA');im=im.resize((im.width//2,im.height//2),Image.Resampling.LANCZOS)
images.append(dict(offset=add(im.tobytes()),w=im.width,h=im.height,tag=11420,frame=0))
(D/'shell.bin').write_bytes(blob)
scenario=h.get_meta(0)
cameras=[dict(name=c.name,position=list(c.position),orientation=list(c.orientation),fov=c.field_of_view)for c in scenario.cutscene_camera_points.STEPTREE]
strings=lambda path:[str(s.data).replace('\r\n','\n')for s in h.get_meta(paths[path]).strings.STEPTREE]
descriptions=strings(r'ui\shell\main_menu\multiplayer_type_select\mp_map_select\map_data')[:13]
names=strings(r'ui\default_multiplayer_game_setting_names')[:26]
type_desc=strings(r'ui\shell\strings\game_variant_descriptions')[10:36]
lines=['/* Extracted locally from the supplied Xbox disc. */','#include "asset_frontend.h"']
lines+=['const float bg_shell_cameras[15][7]={']+['{'+','.join(repr(float(v))+'f'for v in c['position']+c['orientation']+[c['fov']])+'},'for c in cameras]+['};']
lines+=['const bg_shell_image bg_shell_images[]={']+['{'+','.join(str(i[k])for k in ['offset','w','h','tag','frame'])+'},'for i in images]+['};',f'const unsigned bg_shell_image_count={len(images)};']
lines+=['const bg_shell_node bg_shell_nodes[]={']
for n in nodes:
 t,l,b,r=n['bounds'];color=sum(n['rgba'][i]<<(24-8*i)for i in range(4))
 lines.append('{'+','.join(map(str,[n['tag'],l,t,r-l,b-t,n['bitmap'],n['font'],n['align'],n['text_x'],n['text_y']]))+f',0x{color:08x},'+cstr(n['text'])+'},')
lines+=['};',f'const unsigned bg_shell_node_count={len(nodes)};','const bg_shell_mesh bg_shell_meshes[]={']
lines+=['{'+','.join(str(m[k])for k in ['offset','count','image','alpha'])+'},'for m in meshes]+['};',f'const unsigned bg_shell_mesh_count={len(meshes)};']
lines+=['const uint32_t bg_shell_font_offsets[2]={'+','.join(map(str,fo))+'};','const uint8_t bg_shell_font_pages[2]={'+','.join(map(str,fp))+'};','const uint8_t bg_shell_font_ascending[2]={'+','.join(map(str,fa))+'};','const bg_menu_glyph bg_shell_glyphs[2][95]={']
for gs in fg:lines+=['{']+['{'+','.join(map(str,g))+'},'for g in gs]+['},']
lines+=['};','const char *const bg_shell_map_descriptions[13]={'+','.join(cstr(s)for s in descriptions)+'};','const char *const bg_shell_type_names[26]={'+','.join(cstr(s)for s in names)+'};','const char *const bg_shell_type_descriptions[26]={'+','.join(cstr(s)for s in type_desc)+'};',f'const uint32_t bg_shell_music_loop={len(intro)};']
(G/'frontend_data.c').write_text('\n'.join(lines)+'\n')
report=dict(files={str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'build/assets/halo-retail/maps/ui.map',ROOT/'build/assets/halo-retail/maps/bloodgulch.map',Path(__file__).resolve(),ROOT/'port/n64/asset_frontend.h',G/'frontend_data.c',*sorted(D.glob('*'))] if p.is_file()},source_map_sha256=sha(ROOT/'build/assets/halo-retail/maps/ui.map'),blob_bytes=len(blob),cameras=cameras,images=images,meshes=meshes,audio=audio,widgets=records,fonts=dict(pages=fp,ascending=fa),type_names=names,generated_sha256=sha(G/'frontend_data.c'),blob_sha256=sha(D/'shell.bin'),extractor_sha256=sha(Path(__file__)),header_sha256=sha(ROOT/'port/n64/asset_frontend.h'))
(G/'frontend-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k]for k in ['blob_bytes','fonts','type_names','audio']},indent=2))
