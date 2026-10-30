"""Add new distance tiers while retaining every original bank file byte for byte."""
import json,sys,shutil,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'port/n64'))
from pack_assets import position
from pack_mesh import indexed_mesh,emit_batches
from model_colors import load_images,bake_triangle
import pack_bounds
from pack_enemy_vehicles import B,F
OUT=ROOT/'build/vehicle-lods';BANK=OUT/'bank';BASE=ROOT/'build/pve-vehicles/bank'
shutil.copytree(BASE,BANK,dirs_exist_ok=True)
raw=json.loads((ROOT/'build/pve-vehicles/source/extended-raw.json').read_text())
reduced=json.loads((OUT/'reduced.json').read_text())
lines=['#include "asset_models.h"'];assets=[];rigs=[];unions=[];report={}
for name,m in raw['models'].items():
    row=[];rigrow=[];partboxes=[];report[name]=[];images=load_images(m['textures'])
    original=reduced['models'][name]['rig']
    for tier,parts in enumerate(reduced['models'][name]['tiers']):
        triangles=[];ranges=[]
        for part in parts:
            begin=len(triangles)*3;tris=part['triangles'];triangles.extend(tris)
            if len(tris)%2:
                t=tris[-1];triangles.append({'p':[t['p'][-1]]*3,'uv':[t['uv'][-1]]*3,'material':t['material']})
            ranges.append((begin,len(triangles)*3-begin))
        vertices=[];colors=[];materials=[]
        for tri in triangles:
            vertices.extend([[round(v*1024) for v in position(p,(0,0,0))] for p in tri['p']])
            colors.extend(bake_triangle(tri,images,m));materials.extend([tri['material']]*3)
        mesh=indexed_mesh(vertices,colors,[0]*len(vertices),segments=ranges,reorder_static=True,
                          color_tolerance=16 if tier==0 else 24,material_keys=materials)
        sym='distance_'+name+'_'+str(tier)
        lines.append('static T3DVertPacked '+sym+'[] __attribute__((aligned(16)))={')
        for a,b in zip(mesh['vertices'][::2],mesh['vertices'][1::2]):
            rgba=lambda c:hex((c[0]<<24)|(c[1]<<16)|(c[2]<<8)|255)
            lines.append(B([B(a[0]),0,B(b[0]),0,rgba(a[1]),rgba(b[1]),'{0,0}','{0,0}'])+',')
        lines.append('};');emit_batches(lines,sym,mesh)
        box,radius=pack_bounds.model_bounds({'triangles':triangles},1024)
        row.append(B([sym,len(mesh['vertices']),F(radius),sym+'_batches',sym+'_indices',len(mesh['batches']),len(triangles)]))
        lines.append('static const bg_vehicle_part '+sym+'_parts[]={');boxes=[]
        for part,(first,count),segment in zip(original['parts'],ranges,mesh['segments']):
            bounds,_=pack_bounds.model_bounds({'triangles':triangles[first//3:(first+count)//3]},1024)
            boxes.append(bounds)
            lines.append(B([first,count,part['kind'],B(map(F,part['pivot'])),*segment,pack_bounds.initializer(bounds)])+',')
        lines.append('};');rigrow.append(B([sym+'_parts',len(parts),B(map(F,original['turret_pivot']))]));partboxes.append(boxes)
        report[name].append({'triangles':len(triangles),'vertex_loads':sum(b[1] for b in mesh['batches']),
                             'stored_vertices':len(mesh['vertices']),'parts':len(parts),'bounds':box})
    assets.append(B(row));rigs.append(B(rigrow))
    boxes=[]
    for a,b in zip(*partboxes):
        boxes.append(pack_bounds.initializer(pack_bounds.union(a,b)))
    unions.append(B(boxes))
lines+=['const bg_model_asset bg_vehicle_distance_assets[2][2]='+B(assets)+';',
        'const bg_vehicle_rig bg_vehicle_distance_rigs[2][2]='+B(rigs)+';',
        'const bg_bounds bg_vehicle_distance_part_bounds[2][7]='+B(unions)+';']
(BANK/'vehicle_distance_data.c').write_text('\n'.join(lines)+'\n')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
unchanged={p.name:sha(p) for p in BASE.iterdir() if p.is_file()}
assert all(sha(BANK/n)==v for n,v in unchanged.items())
(OUT/'asset-checks.json').write_text(json.dumps({'unchanged_bank_files':unchanged,'new_models':report,'new_data_sha256':sha(BANK/'vehicle_distance_data.c')},indent=2)+'\n')
print(json.dumps(report,indent=2))
