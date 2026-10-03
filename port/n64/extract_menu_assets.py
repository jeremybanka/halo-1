#!/usr/bin/env python3
"""Subset original owned Xbox menu fonts and pausebox into a small N64 bank."""
import argparse
import contextlib
import hashlib
import json
from pathlib import Path

from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
FONT_NAMES=(r'ui\large_ui',r'ui\small_ui')
PANEL_NAMES=tuple(r'ui\shell\bitmaps\pausebox2_'+s for s in ('left','center','right'))
FIRST,COUNT,WIDTH,HEIGHT=32,64,128,64


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def font_bank(meta):
    """Preserve bitmap metrics; quantize only 8-bit coverage to four bits."""
    chars={c.character:c for c in meta.characters.STEPTREE}
    source=bytes(meta.pixels.STEPTREE)
    pages=[Image.new('L',(WIDTH,HEIGHT))];x=y=row=0;glyphs=[]
    for code in range(FIRST,FIRST+COUNT):
        c=chars[code];w,h=max(0,int(c.bitmap_width)),max(0,int(c.bitmap_height))
        if not w or not h:w=h=0
        if x+w+2>WIDTH:x=0;y+=row;row=0
        if y+h+2>HEIGHT:pages.append(Image.new('L',(WIDTH,HEIGHT)));x=y=row=0
        assert w+2<=WIDTH and h+2<=HEIGHT
        sx,sy=x+1,y+1
        if w and h:
            start=c.pixels_offset;raw=source[start:start+w*h];assert len(raw)==w*h
            pages[-1].paste(Image.frombytes('L',(w,h),raw),(sx,sy))
        glyphs.append([len(pages)-1,sx,sy,w,h,c.character_width,c.bitmap_origin_x,c.bitmap_origin_y])
        x+=w+2;row=max(row,h+2)
    packed=bytearray()
    for im in pages:
        pixels=im.tobytes()
        for i in range(0,len(pixels),2):
            packed.append(((pixels[i]+8)//17<<4)|((pixels[i+1]+8)//17))
    return pages,bytes(packed),glyphs


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--map',type=Path,default=ROOT/'build/assets/halo-retail/maps/bloodgulch.map')
    p.add_argument('--assets',type=Path,default=ROOT/'build/n64/assets/menu')
    p.add_argument('--generated',type=Path,default=ROOT/'build/n64/generated')
    a=p.parse_args();a.assets.mkdir(parents=True,exist_ok=True);a.generated.mkdir(parents=True,exist_ok=True)
    from extract_extended import open_cache
    from reclaimer.bitmaps.bitmap_decompilation import extract_bitmaps
    with (a.assets/'extraction.log').open('w') as log,contextlib.redirect_stdout(log):
        halo=open_cache(a.map,a.assets)
    entries=halo.tag_index.tag_index;by_path={t.path:i for i,t in enumerate(entries)}
    report={'source_map':str(a.map.resolve()),'source_map_sha256':sha(a.map),'fonts':{},'panel':{},'inputs':{str(Path(__file__).relative_to(ROOT)):sha(Path(__file__)),
        'port/n64/asset_menu.h':sha(ROOT/'port/n64/asset_menu.h'),'port/n64/extract_extended.py':sha(ROOT/'port/n64/extract_extended.py')}}
    lines=['/* Locally extracted original Xbox fonts/pausebox. Do not redistribute. */','#include "asset_menu.h"']
    font_records=[];total=0
    for index,name in enumerate(FONT_NAMES):
        tag=by_path[name];meta=halo.get_meta(tag);pages,data,glyphs=font_bank(meta)
        ident='menu_font_'+str(index);lines.append('static const uint8_t '+ident+'[] __attribute__((aligned(16)))={')
        lines += [','.join(str(v)for v in data[i:i+32])+',' for i in range(0,len(data),32)];lines.append('};')
        lines.append('static const bg_menu_glyph '+ident+'_glyphs[BG_MENU_GLYPH_COUNT]={')
        lines += ['{'+','.join(map(str,g))+'},'for g in glyphs];lines.append('};')
        font_records.append('{'+f'{ident},{ident}_glyphs,{len(pages)},{meta.ascending_height},{meta.decending_height},{meta.leading_height}'+'}')
        for i,im in enumerate(pages):im.save(a.assets/(f'font-{index}-{i}.png'))
        report['fonts'][name]={'tag':tag,'pages':len(pages),'atlas_bytes':len(data),'glyph_bytes':len(glyphs)*8,
            'metrics':[meta.ascending_height,meta.decending_height,meta.leading_height], 'glyphs':glyphs,
            'original_pixel_bytes':len(meta.pixels.STEPTREE),'source_alpha_sha256':hashlib.sha256(bytes(meta.pixels.STEPTREE)).hexdigest()}
        total+=len(data)+len(glyphs)*8
    lines.append('const bg_menu_font bg_menu_fonts[BG_MENU_FONT_COUNT]={'+','.join(font_records)+'};')
    strips=[]
    for col,name in enumerate(PANEL_NAMES):
        tag=by_path[name];meta=halo.get_meta(tag);halo.meta_to_tag_data(meta,'bitm',entries[tag])
        extract_bitmaps(meta,'panel-'+str(col),out_dir=a.assets,bitmap_ext='png',halo_map=halo)
        im=Image.open(a.assets/(f'panel-{col}.png')).convert('RGBA');assert im.size[1]>=159
        strips.append(im.crop((0,0,im.width,159)))
        report['panel'][name]={'tag':tag,'source_dimensions':list(im.size),'widget_visible_height':159}
    records=[]
    for row in range(3):
        for col,im in enumerate(strips):
            lo,hi=((0,16),(16,143),(143,159))[row];size=(2 if col==1 else 8,2 if row==1 else 8)
            patch=im.crop((0,lo,im.width,hi)).resize(size,Image.Resampling.BOX)
            values=[r<<24|g<<16|b<<8|alpha for r,g,b,alpha in patch.getdata()]
            ident=f'menu_panel_{row*3+col}'
            lines.append('static const uint32_t '+ident+'[] __attribute__((aligned(16)))={'+','.join(f'0x{x:08x}'for x in values)+'};')
            records.append('{'+f'{ident},{size[0]},{size[1]}'+'}');total+=len(values)*4
            patch.save(a.assets/(f'panel-patch-{row*3+col}.png'))
    lines.append('const bg_menu_patch bg_menu_panel[9]={'+','.join(records)+'};')
    widget=halo.get_meta(by_path[r'ui\shell\multiplayer_game\pause_game\resume_game_button'])
    report['source_style']={'menu_text_rgba':list(widget.text_box.text_color),'font':widget.text_box.text_font.filepath,
        'source_widget_bounds':list(widget.bounds),'focused_white_source':'source/interface/ui_widget.c get_ui_rgb_white/global_ui_white_* = 0.8',
        'dimmer_source':r'ui\shell\bitmaps\semi_transparent_grey: RGBA(0,0,0,170)'}
    report['asset_bytes_excluding_descriptor_tables']=total
    report['adaptations']=['ASCII32–95 subset; uppercase menu copy. Native glyph bearings and advances retained.',
        'Glyph alpha quantized from8bits to4bits with nearest rounding, no spatial font resampling.',
        'Pausebox source159px widget region cropped from256px bitmap; nine slices box-filtered to8/2/8px spans. Fullscreen layout expands the source panel for readable mappings.']
    target=a.generated/'menu_data.c';target.write_text('\n'.join(lines)+'\n');report['generated_sha256']=sha(target)
    (a.generated/'menu-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'asset_bytes':total,'font_pages':[v['pages']for v in report['fonts'].values()],'generated':str(target),'sha256':report['generated_sha256']},indent=2))


if __name__=='__main__':main()
