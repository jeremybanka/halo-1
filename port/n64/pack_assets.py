#!/usr/bin/env python3
"""Pack reduced local assets into endian-independent C arrays for Tiny3D."""
import argparse
import collections
import json
import math
from pathlib import Path
from pack_terrain import TEXTURE_SIZE, UV_PERIOD, indexed_terrain

ORIGIN = (68., -118., 0.)
SCALE = 32
GRID = 24


def position(p, origin=ORIGIN):
    return [p[0]-origin[0], p[2]-origin[2], -(p[1]-origin[1])]


def normal(points):
    a,b,c=points
    u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)]
    n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
    length=math.sqrt(sum(x*x for x in n))
    return [x/length for x in n] if length>1e-9 else [0,1,0]


def floats(values):
    return '{'+','.join(f'{v:.7f}f' for v in values)+'}'


def pack(source, output):
    from PIL import Image
    data=json.loads(source.read_text())
    output.mkdir(parents=True,exist_ok=True)
    groups=collections.defaultdict(list)
    for tri in data['triangles']:
        p=[position(v) for v in tri['p']]
        center=[sum(v[i] for v in p)/3 for i in range(3)]
        groups[(tri['material'],int(center[0]//12),int(center[2]//12))].append((tri,p))
    vertices,chunks,terrain_indices=[],[],[]

    def append_tri(tri,p,model=None,global_uv=False):
        n=normal(p)
        light=.60+.40*max(0,sum(a*b for a,b in zip(n,[.25,.83,.49])))
        uv=tri['uv']
        offset=[math.floor(min(v[i] for v in uv)) for i in range(2)]
        for point,tex in zip(p,uv):
            pos=[round(v*SCALE) for v in point]
            if not all(-32768<=v<=32767 for v in pos):raise ValueError('Packed position overflow')
            st=[round((tex[i]-offset[i])*UV_PERIOD) for i in range(2)]
            if not all(-32768<=v<=32767 for v in st):raise ValueError('Packed UV overflow')
            if global_uv:
                absolute=[round(tex[i]*UV_PERIOD) for i in range(2)]
                # Preserve the old quantizer exactly, modulo whole32x32 repeats.
                if any(absolute[i]-st[i]!=offset[i]*UV_PERIOD for i in range(2)):
                    raise ValueError('Terrain UV rounding is not integer-wrap equivalent')
                st=absolute
            rgb=[round(255*light)]*3
            if model=='spartan' and point[1]>.56 and point[0]>.025:rgb=[238,181,59]
            if model=='rifle':rgb=[round(v*light) for v in [104,112,107]]
            vertices.append((pos,rgb,st))

    for key,triangles in sorted(groups.items()):
        first=len(vertices)
        for tri,p in triangles:append_tri(tri,p,global_uv=True)
        expanded=vertices[first:];del vertices[first:]
        packed=[tuple(v for attribute in corner for v in attribute) for corner in expanded]
        # Material and spatial-cell boundaries remain unchanged. The helper
        # preserves triangle order and checks every merged original corner.
        for batch in indexed_terrain([packed[i:i+3] for i in range(0,len(packed),3)]):
            first=len(vertices)
            unique=[(list(v[:3]),list(v[3:6]),list(v[6:])) for v in batch['vertices']]
            local=batch['indices'];vertices.extend(unique);count=len(unique)
            xyz=[v[0] for v in unique]
            bounds=[min(v[i] for v in xyz) for i in range(3)]+[max(v[i] for v in xyz) for i in range(3)]
            index_first=len(terrain_indices);terrain_indices.extend(local)
            while len(terrain_indices)%4:terrain_indices.append(0)
            if index_first>65535:raise ValueError('Terrain index-offset capacity exceeded')
            chunks.append((first,count,key[0],bounds,index_first,len(local)))
            if len(vertices)%2:vertices.append(vertices[-1])
    world_vertices=len(vertices)
    model_ranges={}
    for model,triangles in data['models'].items():
        first=len(vertices)
        for tri in triangles:append_tri(tri,[position(v,(0,0,0)) for v in tri['p']],model)
        model_ranges[model]=(first,len(vertices)-first)
        if len(vertices)%2:vertices.append(vertices[-1])
    lines=['/* Generated from local game data. Do not commit. */','#include <t3d/t3d.h>','#include "world.h"']
    lines.append('T3DVertPacked bg_vertices[] __attribute__((aligned(16))) = {')
    def rgba(rgb):return (rgb[0]<<24)|(rgb[1]<<16)|(rgb[2]<<8)|255
    for i in range(0,len(vertices),2):
        a,b=vertices[i:i+2]
        xyz=lambda p:'{'+','.join(map(str,p))+'}'
        lines.append('{'+f'{xyz(a[0])},0,{xyz(b[0])},0,0x{rgba(a[1]):08x},0x{rgba(b[1]):08x},{xyz(a[2])},{xyz(b[2])}'+'},')
    lines+=['};',f'const unsigned bg_vertex_count={world_vertices}, bg_chunk_count={len(chunks)}, bg_material_count={len(data["materials"])};']
    lines+=['const bg_chunk bg_chunks[]={']
    for first,count,material,bounds,index_first,index_count in chunks:
        lines.append('{'+f'{first},{count},{material},'+'{'+','.join(map(str,bounds))+'},'+f'{index_first},{index_count}'+'},')
    lines+=['};']
    lines.append('int16_t bg_chunk_indices[] __attribute__((aligned(16)))={'+','.join(map(str,terrain_indices))+'};')
    for name,(first,count) in model_ranges.items():
        lines.append(f'T3DVertPacked *bg_{name} = &bg_vertices[{first//2}];')
        lines.append(f'const unsigned bg_{name}_vertices={count};')
    lines.append('uint16_t bg_textures[][32*32] __attribute__((aligned(16)))={')
    for mat in data['materials']:
        if mat['texture']:
            texture=Image.open(mat['texture']).convert('RGB')
            if texture.size!=(TEXTURE_SIZE,TEXTURE_SIZE):
                raise ValueError('Terrain repeat-preserving packing requires32x32 textures')
            pixels=list(texture.get_flattened_data())
        else:
            color=(135,144,125)
            if 'red' in mat['name']:color=(235,68,54)
            if 'blue' in mat['name']:color=(50,108,234)
            if 'green' in mat['name'] or 'shield' in mat['name']:color=(70,219,133)
            if 'black' in mat['name']:color=(45,50,46)
            pixels=[color]*1024
        lines.append('{'+','.join(hex(((r>>3)<<11)|((g>>3)<<6)|((b>>3)<<1)|1) for r,g,b in pixels)+'},')
    lines.append('};')
    (output/'render_data.c').write_text('\n'.join(lines)+'\n')

    # Collision uses exactly the reduced visible surface, avoiding hovering
    # over the original high-resolution terrain after simplification.
    collision=[[position(p) for p in t['p']] for t in data['triangles']]
    lo=[min(p[i] for t in collision for p in t)-.01 for i in (0,2)]
    hi=[max(p[i] for t in collision for p in t)+.01 for i in (0,2)]
    size=[(hi[i]-lo[i])/GRID for i in range(2)]
    cells=[[] for _ in range(GRID*GRID)]
    for i,tri in enumerate(collision):
        bounds=[]
        for j,axis in enumerate((0,2)):
            bounds.append((max(0,int((min(p[axis] for p in tri)-lo[j])/size[j])),min(GRID-1,int((max(p[axis] for p in tri)-lo[j])/size[j]))))
        for z in range(bounds[1][0],bounds[1][1]+1):
            for x in range(bounds[0][0],bounds[0][1]+1):cells[z*GRID+x].append(i)
    indices=[i for cell in cells for i in cell]
    if len(indices)>65535:raise ValueError('Collision grid index capacity exceeded')
    # Share byte-identical emitted float corners, without quantizing/moving a
    # single collision surface. This pays for the original base architecture.
    collision_vertices=[];collision_lookup={};collision_faces=[]
    for tri in collision:
        face=[]
        for p in tri:
            key=floats(p)
            if key not in collision_lookup:
                collision_lookup[key]=len(collision_vertices);collision_vertices.append(key)
            face.append(collision_lookup[key])
        collision_faces.append(face)
    lines=['/* Generated from local game data. Do not commit. */','#include "world.h"',
           f'const unsigned bg_collision_count={len(collision)};',
           'static const float collision_vertices[][3]={',
           ',\n'.join(collision_vertices),'};',
           'const bg_triangle bg_collision[]={']
    for face in collision_faces:lines.append('{{'+','.join(f'collision_vertices[{v}]' for v in face)+'}},')
    lines+=['};',f'const float bg_grid_origin[2]={floats(lo)}, bg_grid_size[2]={floats(size)};',
            'const bg_cell bg_grid[BG_GRID*BG_GRID]={']
    offset=0
    for cell in cells:lines.append(f'{{{offset},{len(cell)}}},');offset+=len(cell)
    lines+=['};','const uint16_t bg_grid_indices[]={'+','.join(map(str,indices))+'};']
    lines+=['const bg_spawn bg_spawns[]={']
    for spawn in data['spawns']:
        lines.append('{'+floats(position(spawn['position']))+f',{spawn["yaw"]:.7f}f,{spawn["team"]}'+'},')
    lines+=['};',f'const unsigned bg_spawn_count={len(data["spawns"])};']
    (output/'collision_data.c').write_text('\n'.join(lines)+'\n')
    report={'source_sha256':data['source_sha256'],'original_triangles':data['original_triangles'],
            'architecture_triangles':data.get('architecture_triangles',0),
            'render_triangles':len(collision),'chunks':len(chunks),'world_vertex_bytes':world_vertices*16,
            'world_unique_vertices':sum(c[1] for c in chunks),'world_corner_count':len(collision)*3,
            'world_index_bytes':len(terrain_indices)*2,
            'world_color_max_delta':8,'world_uv_period':UV_PERIOD,'world_max_batch_indices':max(c[5] for c in chunks),
            'textures':len(data['materials']),'texture_bytes':len(data['materials'])*2048,
            'collision_bytes':len(collision)*12+len(collision_vertices)*12+len(indices)*2+GRID*GRID*4,
            'collision_shared_vertices':len(collision_vertices),
            'collision_corner_bytes_saved':len(collision)*24-len(collision_vertices)*12,
            'collision_max_cell':max(map(len,cells)),
            'spartan_triangles':model_ranges['spartan'][1]//3,'rifle_triangles':model_ranges['rifle'][1]//3}
    (output/'asset-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path)
    p.add_argument('--output',type=Path,default=Path('build/n64/generated'))
    a=p.parse_args();pack(a.source,a.output)
