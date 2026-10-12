#!/usr/bin/env python3
"""Bake private, per-map ROM banks without changing the shared weapon bank.

Blood Gulch is serialized from its current emitted C tables, preserving every
float, pixel and index. Wizard retains its original render/collision geometry,
with 32px base textures and source lightmaps baked into vertex colors.
"""
import argparse
import collections
import contextlib
import hashlib
import json
import math
import re
import struct
import subprocess
from pathlib import Path
from PIL import Image
from pack_terrain import indexed_terrain
from extract_extended import tag_values
from blam.tags.export_collision import check, polygons

ROOT = Path(__file__).resolve().parents[2]
NAMES = ('bloodgulch', 'wizard')
STRIDES = (32,24,2,2048,1,1,1,2,12,6,1,4,2,16,20,1,24,16,28,20,3,16,60)
HEADER_BYTES = 16 + len(STRIDES) * 12
KINDS = {'weapons'+chr(92)+n+chr(92)+n: i for i,n in enumerate(
    ('assault rifle','pistol','plasma pistol','plasma rifle','needler','shotgun','sniper rifle','rocket launcher','flamethrower'))}
KINDS.update({r'powerups\health pack':9, r'weapons\frag grenade\frag grenade':10,
              r'weapons\plasma grenade\plasma grenade':11, r'powerups\over shield':12,
              r'powerups\active camouflage':13})

def packed(fmt, rows):
    return b''.join(struct.pack('>'+fmt, *row) for row in rows)

def bank(path, map_id, sections):
    assert len(sections) == len(STRIDES)
    blob = bytearray(HEADER_BYTES); records = []
    for data, stride in zip(sections, STRIDES):
        assert len(data) % stride == 0
        blob.extend(bytes(-len(blob) % 16))
        records.append((len(blob), len(data)//stride, stride)); blob.extend(data)
    struct.pack_into('>4I',blob,0,0x484d3634,1,map_id,len(blob))
    for i,row in enumerate(records):struct.pack_into('>3I',blob,16+i*12,*row)
    path.write_bytes(blob)
    return {'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),'sections':records}

def blood(output):
    """Use the host compiler as the independent oracle for current C values."""
    work=output/'blood-export';(work/'t3d').mkdir(parents=True,exist_ok=True)
    (work/'t3d/t3d.h').write_text('''#include <stdint.h>
typedef struct {int16_t a[3];uint16_t na;int16_t b[3];uint16_t nb;
uint32_t ca,cb;int16_t uva[2],uvb[2];} T3DVertPacked;
''')
    generated=ROOT/'build/n64/generated'
    c=['#include <stdio.h>','#include "pickup_rules.h"']
    c += ['#include "'+str(generated/name)+'"' for name in ('render_data.c','terrain_data.c','pickup_data.c','sky_data.c')]
    c += ['''int main(void){
unsigned counts[]={bg_vertex_count/2,bg_chunk_count,sizeof(bg_chunk_indices)/2,
bg_material_count,bg_collision_count,sizeof(bg_grid_indices)/2,bg_spawn_count,bg_map_item_count};
fwrite(counts,4,8,stdout);
fwrite(bg_vertices,32,counts[0],stdout);fwrite(bg_chunks,24,counts[1],stdout);
fwrite(bg_chunk_indices,2,counts[2],stdout);fwrite(bg_textures,2048,counts[3],stdout);
fwrite(bg_texture_sizes,1,counts[3],stdout);fwrite(bg_texture_ci4,1,counts[3],stdout);
fwrite(bg_texture_overlay,1,counts[3],stdout);fwrite(bg_ground_palette,2,16,stdout);
for(unsigned i=0;i<bg_collision_count;i++)for(unsigned j=0;j<3;j++)fwrite(bg_collision[i].p[j],4,3,stdout);
fwrite(bg_collision_flags,1,bg_collision_count,stdout);fwrite(bg_grid,4,BG_GRID*BG_GRID,stdout);
fwrite(bg_grid_indices,2,counts[5],stdout);fwrite(bg_grid_origin,4,2,stdout);fwrite(bg_grid_size,4,2,stdout);
fwrite(bg_spawns,20,counts[6],stdout);fwrite(bg_slayer_spawns,1,counts[6],stdout);
fwrite(bg_map_items,24,counts[7],stdout);fwrite(bg_start_weapons,4,2,stdout);fwrite(bg_start_grenades,4,2,stdout);
fwrite(bg_sky_rgb,1,99,stdout);
}''']
    (work/'export.c').write_text('\n'.join(c))
    subprocess.run(['clang','-std=c17','-Wall','-Wextra','-Werror','-I'+str(work),'-I'+str(ROOT/'port/n64'),str(work/'export.c'),'-o',str(work/'export')],check=True)
    data=subprocess.check_output([str(work/'export')]);counts=struct.unpack_from('<8I',data);at=32
    def read(fmt,count):
        nonlocal at
        size=struct.calcsize('<'+fmt); rows=list(struct.iter_unpack('<'+fmt,data[at:at+size*count]));at+=size*count
        return packed(fmt,rows)
    sections=[read('3hH3hHII4h',counts[0]),read('IHH6hHH',counts[1]),read('h',counts[2]),
              read('1024H',counts[3]),read('B',counts[3]),read('B',counts[3]),read('B',counts[3]),read('H',16)]
    corners=[];faces=[];lookup={}
    for _ in range(counts[4]):
        face=[]
        for _ in range(3):
            raw=data[at:at+12];at+=12
            if raw not in lookup:lookup[raw]=len(corners);corners.append(struct.unpack('<3f',raw))
            face.append(lookup[raw])
        faces.append(face)
    sections += [packed('3f',corners),packed('3H',faces),read('B',counts[4]),read('2H',576),read('H',counts[5]),
                 read('4f',1),read('4fi',counts[6]),read('B',counts[6]),read('4fH2b2B2x',counts[7]),read('4i',1)]
    # Retain current teleporter headings and expanded vehicle placements.
    game=(ROOT/'port/n64/game.c').read_text();tele=game[game.index('const bg_teleporter bg_teleporters'):game.index('const unsigned bg_teleporter_count')]
    floats=[float(x) for x in re.findall(r'(-?(?:\d+\.\d*|\.\d+))f',tele)];assert len(floats)==14
    sections.append(packed('7f',[floats[:7],floats[7:]]))
    vehicles=[]
    for kind,pos,yaw in re.findall(r'bg_add_vehicle\(BG_V_(\w+),\(float\[\]\)\{([^}]+)\},([^\)]+)\)',(ROOT/'port/n64/scenario.inc').read_text()):
        values=[float(x.strip().rstrip('f')) for x in pos.split(',')]+[float(yaw.strip().rstrip('f'))]
        vehicles.append((*values,('WARTHOG','GHOST','SCORPION','BANSHEE').index(kind)))
    assert len(vehicles)==10
    sections.append(packed('4fI',vehicles));sections.append(read('3B',33));assert at==len(data)
    sections.append(packed('4f',[(68,-118,0,-8)]))
    vr=json.loads((generated/'vehicle-report.json').read_text())
    # Current native layout is also emitted by the C compiler, not inferred
    # from raw tag counts or pointer strides.
    native=(generated/'vehicle_data.c').read_text()
    layout_text=native[native.index('const unsigned bg_vehicle_world_layout'):]
    pairs=[tuple(map(int,m)) for m in re.findall(r'\{(\d+),(\d+)\}',layout_text)]
    assert len(pairs)==7
    world=(ROOT/'build/n64/frontend-files/vehicle-world.bin').read_bytes();assert len(world)==vr['world_bank_bytes']
    (output/'bloodgulch-world.bin').write_bytes(world)
    sections.append(packed('15I',[(len(world),*(v for pair in pairs for v in pair))]))
    info=bank(output/'bloodgulch.map64',9,sections)
    info.update(render_triangles=json.loads((generated/'asset-report.json').read_text())['render_triangles'],collision_triangles=counts[4],materials=counts[3],spawns=counts[6],items=counts[7],vehicles=10,teleporters=2,world_bytes=len(world))
    # One shared, unchanged ammo/power-up bank; map start/items live in ROM.
    text=(generated/'pickup_data.c').read_text()
    common=['#include "pickup_rules.h"']
    for declaration in ('const bg_ammo_rule bg_ammo_rules','const float bg_camo_duration'):
        start=text.index(declaration);common.append(text[start:text.index(';',start)+1])
    (output/'common_data.c').write_text('\n'.join(common)+'\n')
    return info,sections[20]

def world_bank(data, materials):
    bounds=[];indices=[];tree=[]
    for face in polygons(data):
        points=[data['vertices'][v][:3] for v in face]
        bounds.append([math.floor(min(p[a] for p in points)*64) for a in range(3)]+[math.ceil(max(p[a] for p in points)*64) for a in range(3)])
    def build(ids,depth=0):
        assert depth<31
        box=[min(bounds[i][a] for i in ids) for a in range(3)]+[max(bounds[i][a+3] for i in ids) for a in range(3)]
        index=len(tree);tree.append(None)
        if len(ids)<=8:
            first=len(indices);indices.extend(ids);tree[index]=(*box,first,len(ids))
        else:
            axis=max(range(3),key=lambda a:max(bounds[i][a]+bounds[i][a+3] for i in ids)-min(bounds[i][a]+bounds[i][a+3] for i in ids))
            ids.sort(key=lambda i:bounds[i][axis]+bounds[i][axis+3]);mid=len(ids)//2
            assert build(ids[:mid],depth+1)==index+1
            right=build(ids[mid:],depth+1);tree[index]=(*box,right,0)
        return index
    build(list(range(len(bounds))))
    surfaces=[(*s[:-1],materials[s[-1]] if s[-1]>=0 else -1) for s in data['surfaces']]
    blocks=[(data['planes'],'4f'),(surfaces,'2iBBh'),(data['edges'],'6h'),(data['vertices'],'3fi'),
            (tree,'6h2H'),(bounds,'6h'),([(i,) for i in indices],'H')]
    blob=bytearray();layout=[]
    for rows,fmt in blocks:
        assert len(blob)%4==0
        layout.append((len(blob),len(rows)));blob.extend(packed(fmt,rows))
    return blob,packed('15I',[(len(blob),*(v for pair in layout for v in pair))])

def wizard(output, sky):
    from reclaimer.meta.wrappers.halo1_map import Halo1Map
    from reclaimer.bitmaps.bitmap_decompilation import extract_bitmaps
    from reclaimer.util.compression import decompress_normal32
    cache=ROOT/'build/n64-map-survey/wizard-decompressed.map'
    if not cache.exists():
        import zlib
        original=(ROOT/'build/assets/halo-retail/maps/wizard.map').read_bytes()
        expected=struct.unpack_from('<I',original,8)[0]
        raw=original if len(original)==expected else original[:2048]+zlib.decompress(original[2048:])
        cache=output/'wizard-decompressed.map';cache.write_bytes(raw)
    textures=output/'wizard-textures';textures.mkdir(exist_ok=True)
    with (output/'wizard-extract.log').open('w') as log,contextlib.redirect_stdout(log):
        h=Halo1Map();h.load_map(cache);es=h.tag_index.tag_index
        bsp=h.get_meta(next(i for i,e in enumerate(es) if e.class_1.enum_name=='scenario_structure_bsp'))
        sc=tag_values(h.scnr_meta)
        def meta(path,kind):return h.get_meta(next(i for i,e in enumerate(es) if e.path==path and e.class_1.enum_name==kind))
        def bitmap(ref,name):
            m=h.get_meta(ref.id&65535);h.meta_to_tag_data(m,'bitm',es[ref.id&65535]);extract_bitmaps(m,name,out_dir=textures,bitmap_ext='png',halo_map=h)
        bitmap(bsp.lightmap_bitmaps,'lightmap')
        materials={};images=[];overlays=[];groups=collections.defaultdict(list);raw_tris=list(struct.iter_unpack('<3H',bsp.surface.STEPTREE))
        for light in bsp.lightmaps.STEPTREE:
            lm_file=textures/f'lightmap__{light.bitmap_index}.png'
            if light.bitmap_index==0 and not lm_file.exists():lm_file=textures/'lightmap.png'
            lightmap=Image.open(lm_file).convert('RGB') if lm_file.exists() else None
            for m in light.materials.STEPTREE:
                path=m.shader.filepath
                if path not in materials:
                    mi=len(materials);materials[path]=mi
                    shader=h.get_meta(m.shader.id&65535)
                    overlay=hasattr(shader,'sotr_attrs');overlays.append(overlay)
                    ref=shader.sotr_attrs.maps.STEPTREE[0].bitmap if overlay else shader.senv_attrs.diffuse.base_map
                    if ref.id!=0xffffffff:
                        bitmap(ref,f'material-{mi}')
                        file=textures/f'material-{mi}.png'
                        if not file.exists():file=textures/f'material-{mi}__0.png'
                        image=Image.open(file).convert('RGB').resize((32,32),Image.Resampling.BOX)
                    else:
                        color=shader.shdr_attrs.radiosity_light_color
                        image=Image.new('RGB',(32,32),tuple(round(v*255) for v in color))
                    if overlay:
                        tint=tuple(shader.shdr_attrs.radiosity_light_color)
                        image.putdata([tuple(round(c*t) for c,t in zip(pixel,tint)) for pixel in image.get_flattened_data()])
                    image.save(textures/f'packed-{mi}.png');images.append(image)
                mi=materials[path];raw=bytes(m.compressed_vertices.STEPTREE);n=m.vertices_count
                assert m.lightmap_vertices_count in (0,n) and len(raw)>=n*32+m.lightmap_vertices_count*8
                positions=[struct.unpack_from('<3f',raw,i*32) for i in range(n)]
                uvs=[struct.unpack_from('<2f',raw,i*32+24) for i in range(n)]
                colors=[]
                for i in range(n):
                    uv=struct.unpack_from('<2h',raw,n*32+i*8+4) if m.lightmap_vertices_count else (0,0)
                    if lightmap and m.lightmap_vertices_count and not overlays[mi]:
                        x=min(lightmap.width-1,max(0,round(uv[0]/32767*lightmap.width-.5)))
                        y=min(lightmap.height-1,max(0,round(uv[1]/32767*lightmap.height-.5)))
                        colors.append(lightmap.getpixel((x,y)))
                    else:colors.append((255,255,255))
                for face in raw_tris[m.surfaces:m.surfaces+m.surface_count]:
                    p=[positions[v] for v in face];center=[sum(v[a] for v in p)/3 for a in range(3)]
                    tri=[]
                    for v in face:
                        x,y,z=positions[v];u,t=uvs[v]
                        if overlays[mi]:
                            nx,ny,nz=decompress_normal32(struct.unpack_from('<I',raw,v*32+12)[0])
                            x+=nx/32;y+=ny/32;z+=nz/32
                        tri.append((round(x*256),round(z*256),round(-y*256),*colors[v],round(u*1024),round(t*1024)))
                    # Wizard's compact room keeps most fine cells visible at
                    # once. Coarser bins share corners and reduce CPU/RSP
                    # submissions without changing source triangle geometry.
                    groups[(mi,math.floor(center[0]/8),math.floor(center[1]/8),math.floor(center[2]/4))].append(tri)
        vertices=[];chunks=[];indices=[]
        for key,tris in sorted(groups.items(),key=lambda kv:(overlays[kv[0][0]],*kv[0])):
            for batch in indexed_terrain(tris):
                first=len(vertices);unique=batch['vertices'];vertices.extend(unique)
                bounds=[math.floor(min(v[a] for v in unique)/8) for a in range(3)]+[math.ceil(max(v[a] for v in unique)/8) for a in range(3)]
                start=len(indices);indices.extend(batch['indices']);count=len(batch['indices'])
                while len(indices)%4:indices.append(0)
                chunks.append((first,len(unique),key[0],*bounds,start,count))
                if len(vertices)%2:vertices.append(vertices[-1])
        assert len(chunks)<=512 and len(indices)<65536 and len(materials)<=32
        vp=[]
        for a,b in zip(vertices[::2],vertices[1::2]):
            rgba=lambda v:(v[3]<<24)|(v[4]<<16)|(v[5]<<8)|255
            vp.append((*a[:3],0,*b[:3],0,rgba(a),rgba(b),*a[6:],*b[6:]))
        blocks=bsp.collision_bsp.STEPTREE;assert len(blocks)==1;data={}
        fmts={'bsp3d_nodes':'3i','planes':'4f','leaves':'Hhi','bsp2d_references':'2i','bsp2d_nodes':'3f2i','surfaces':'2iBBh','edges':'6i','vertices':'3fi'}
        for name,fmt in fmts.items():data[name]=list(struct.iter_unpack('<'+fmt,bytes(getattr(blocks[0],name).STEPTREE)))
        check(data)
        corners=[(v[0],v[2],-v[1]) for v in data['vertices']];faces=[];flags=[]
        for surface,poly in zip(data['surfaces'],polygons(data)):
            plane=data['planes'][surface[0]&0x7fffffff];sign=-1 if surface[0]<0 else 1
            normal=(plane[0]*sign,plane[2]*sign,-plane[1]*sign)
            for j in range(1,len(poly)-1):
                face=[poly[0],poly[j],poly[j+1]];a,b,c=[corners[k] for k in face]
                ab=[b[k]-a[k] for k in range(3)];ac=[c[k]-a[k] for k in range(3)]
                cross=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])
                if sum(cross[k]*normal[k] for k in range(3))<0:face[1],face[2]=face[2],face[1]
                faces.append(face);flags.append(int(normal[1]>0 and normal[1]*normal[1]>=.38*sum(v*v for v in normal))| (2 if surface[2]&4 else 0))
        lo=[min(v[k] for v in corners)-.01 for k in (0,2)];hi=[max(v[k] for v in corners)+.01 for k in (0,2)];size=[(hi[k]-lo[k])/24 for k in range(2)];cells=[[] for _ in range(576)]
        for i,face in enumerate(faces):
            points=[corners[v] for v in face]
            limits=[(max(0,math.floor((min(p[a] for p in points)-lo[k])/size[k])),min(23,math.floor((max(p[a] for p in points)-lo[k])/size[k]))) for k,a in enumerate((0,2))]
            for z in range(limits[1][0],limits[1][1]+1):
                for x in range(limits[0][0],limits[0][1]+1):cells[z*24+x].append(i)
        grid=[];grid_indices=[]
        for cell in cells:grid.append((len(grid_indices),len(cell)));grid_indices.extend(cell)
        def eligible(row):return any(row['type_'+str(i)] in ('slayer','all_games','all_games_except_ctf','all_games_except_ctf_and_race') for i in range(4))
        spawns=[(*s['position'].values(),s['facing'],s['team_index']) for s in sc['player_starting_locations']]
        spawns=[(x,z,-y,yaw,team) for x,y,z,yaw,team in spawns]
        spawnflags=[int(eligible(s)) for s in sc['player_starting_locations']]
        def collection(path):return tag_values(meta(path,'item_collection'))
        start=next(s for s in sc['starting_equipments'] if eligible(s));weapons=[]
        for i in range(1,7):
            name=start['item_collection_'+str(i)]
            if name:weapons.append(KINDS[collection(name)['item_permutations'][0]['item']])
        weapons=(weapons+[-1,-1])[:2];grenades=[0,0] if start['flags']['no_grenades'] else [4,0]
        if start['flags']['plasma_grenades']:grenades=[0,sum(grenades)]
        items=[]
        for item in sc['netgame_equipments']:
            if not eligible(item):continue
            col=collection(item['item_collection']);perms=col['item_permutations'];assert 0<len(perms)<=2
            kinds=[KINDS[p['item']] for p in perms];weights=[round(p['weight']) for p in perms];pos=item['position']
            items.append((pos['x'],pos['z'],-pos['y'],-item['facing'],item['spawn_time'] or col['spawn_time'] or 30,*(kinds+[-1])[:2],weights[0],sum(weights)))
        teleport=[]
        for f in sc['netgame_flags']:
            if f['type']!='teleport_from':continue
            dest=next(d for d in sc['netgame_flags'] if d['type']=='teleport_to' and d['team_index']==f['team_index'])
            a=f['position'];b=dest['position'];teleport.append((a['x'],a['z'],-a['y'],b['x'],b['z'],-b['y'],dest['facing']))
        pixels=[]
        for i,image in enumerate(images):pixels.append(tuple(((r>>3)<<11)|((g>>3)<<6)|((b>>3)<<1)|int(not overlays[i] or max(r,g,b)>=24) for r,g,b in image.get_flattened_data()))
        world,layout=world_bank(data,[(int(m.unknown)>>16)&65535 for m in bsp.collision_materials.STEPTREE])
        (output/'wizard-world.bin').write_bytes(world)
    sections=[packed('3hH3hHII4h',vp),packed('IHH6hHH',chunks),packed('H',[(i,) for i in indices]),packed('1024H',pixels),
              bytes([32]*len(images)),bytes(len(images)),bytes(map(int,overlays)),bytes(32),packed('3f',corners),packed('3H',faces),bytes(flags),
              packed('2H',grid),packed('H',[(i,) for i in grid_indices]),packed('4f',[(*lo,*size)]),packed('4fi',spawns),bytes(spawnflags),
              packed('4fH2b2B2x',items),packed('4i',[(*weapons,*grenades)]),packed('7f',teleport),b'',sky,packed('4f',[(0,0,0,-12.5)]),layout]
    info=bank(output/'wizard.map64',10,sections)
    info.update(render_triangles=len(raw_tris),collision_triangles=len(faces),materials=list(materials),chunks=len(chunks),spawns=len(spawns),eligible_slayer_spawns=sum(spawnflags),items=len(items),vehicles=0,teleporters=len(teleport),climbable_triangles=sum(bool(f&2) for f in flags),world_bytes=len(world),starting_weapons=weapons,starting_grenades=grenades,source_sha256=hashlib.sha256(cache.read_bytes()).hexdigest(),lighting='Original compressed lightmap UVs sampled into vertex RGB; base textures BOX-filtered to32px; geometry retained.')
    return info

def main(output):
    output.mkdir(parents=True,exist_ok=True)
    bg,sky=blood(output);wiz=wizard(output,sky)
    paths=[Path(__file__),ROOT/'port/n64/map_format.h',ROOT/'port/n64/pack_terrain.py',ROOT/'port/n64/scenario.inc',ROOT/'port/n64/game.c']
    paths += [ROOT/'build/n64/generated'/name for name in ('render_data.c','terrain_data.c','pickup_data.c','sky_data.c','vehicle_data.c','vehicle-report.json','asset-report.json')]
    report={'maps':{'bloodgulch':bg,'wizard':wiz},'inputs':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.suffix in ('.map64','.bin','.c')}}
    (output/'maps-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:{n:v[n] for n in ('bytes','render_triangles','collision_triangles','spawns','items','vehicles','teleporters','world_bytes')} for k,v in report['maps'].items()},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=ROOT/'halo64-assets/generated/maps');main(p.parse_args().output)
