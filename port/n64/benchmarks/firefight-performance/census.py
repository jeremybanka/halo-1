#!/usr/bin/env python3
"""Reproduce model submission counts and verify the seven extracted CE bodies."""
import hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'port/n64'))
from test_render_matrix import function

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    private=ROOT/'halo64-assets/generated';models={};inputs={}
    for name in ('models_data.c','pve/pve_data.c','micro_data.c'):
        path=private/name;text=path.read_text();inputs[str(path.relative_to(ROOT))]=digest(path)
        batches={}
        for symbol,body in re.findall(r'(?:const|static const) bg_mesh_batch (\w+)\[.*?\]\s*=\s*\{(.*?)\};',text,re.S):
            rows=[tuple(map(int,x.split(','))) for x in re.findall(r'\{([\d, ]+)\}',body)]
            batches[symbol]=[len(rows),sum((b[1]+1)&~1 for b in rows)]
        for symbol,verts,batch,indices,count,tris in re.findall(r'\{(\w+),(\d+),[\d.]+f,(\w+),(\w+),(\d+),(\d+)\}',text):
            if not any(k in symbol for k in ('spartan','warthog','ghost','scorpion','banshee','pve_')):continue
            assert batches[batch][0]==int(count)
            models[symbol]={'triangles':int(tris),'packed_vertices':int(verts),'vertex_loads':batches[batch][1],'batches':int(count)}
    functions=[(f'actor_type_{s}.c',f'{s}_decide_action') for s in ('grunt','elite','jackal','hunter')]+[('actions.c',f'actor_action_{s}') for s in ('handle_panic_transition','consider_grenade','handle_grenade_throwing')]
    extracted=private/'pve/pve_source_decisions.inc';inputs[str(extracted.relative_to(ROOT))]=digest(extracted)
    checks=[]
    for filename,name in functions:
        source=ROOT/'source/ai'/filename;original=function(source.read_text(),name);copy=function(extracted.read_text(),name)
        assert original==copy,name
        checks.append({'function':name,'source':str(source.relative_to(ROOT)),'body_sha256':hashlib.sha256(original.encode()).hexdigest(),'identical':True})
    inputs['halo64-assets/generated/pve/pve_collision.c']=digest(private/'pve/pve_collision.c')
    inputs['halo64-assets/generated/pve/pve_nav.c']=digest(private/'pve/pve_nav.c')
    collision=(private/'pve/pve_collision.c').read_text()
    hits={n:int(t) for n,t in re.findall(r'\{pve_hit_(\w+)_triangles,pve_hit_\w+_materials,(\d+),',collision)}
    nav=(private/'pve/pve_nav.c').read_text()
    h=re.search(r'bg_pve_nav_heights\[.*?\]\s*=\s*\{(.*?)\};',nav,re.S)[1]
    vals=[float.fromhex(v.strip().removesuffix('f')) for v in h.split(',') if v.strip()]
    result={'schema':1,'models':models,'hit_mesh_triangles':hits,'source_function_checks':checks,'inputs':inputs,'nav_valid_height_nodes':sum(v>-999 for v in vals),'nav_addressable_nodes':len(vals),'notes':['Loads sum (batch.count+1)&~1, matching scene.c model_load_count. Packed vertices are not unique geometric points.','Body only: guns, first-person arms, projectiles, shield effects and riders excluded; Jackal shield mesh is included.','Hunter and Spirit far entries alias their near model. Vehicles also have smaller micro LODs; visible articulated near parts may be culled independently.']}
    (Path(__file__).parent/'census.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
