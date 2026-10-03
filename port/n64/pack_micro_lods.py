"""Pack generated tiny far models while preserving existing model-bank aliases.

Run after the ordinary world bank and generate_micro_lods.py. Derived game
content stays under ignored build/; this emits only additional micro files.
"""
from pathlib import Path
import argparse,ast,hashlib,json,math,re,sys
ROOT=Path(__file__).resolve().parents[2]
from pack_mesh import indexed_mesh,emit_batches,model_color_tolerance
node=ast.parse((ROOT/'port/n64/extract_extended.py').read_text());NAMES=next(list(ast.literal_eval(n.value)) for n in node.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MODEL_PATHS' for t in n.targets))
VEHICLES=['warthog','ghost','scorpion','banshee'];PICKUPS=NAMES[:8]+['frag','plasma_grenade','healthpack','overshield','camouflage'];ALLOWED=set(VEHICLES+PICKUPS)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def box(points):
 points=list(points);return [[min(p[a] for p in points) for a in range(3)],[max(p[a] for p in points) for a in range(3)]]
def union(*b):return box(p for bb in b for p in bb)
def initializer(b):return '{'+','.join('{'+','.join(f'{v+(-1e-6 if side==0 else 1e-6):.7f}f' for v in row)+'}' for side,row in enumerate(b))+'}'
def pack(source,out,generated=None):
 source=source.resolve();out=out.resolve();generated=(generated or ROOT/'build/n64/generated').resolve()
 if ROOT/'build' not in out.parents:raise ValueError('Derived game content must stay under ignored build/')
 out.mkdir(parents=True,exist_ok=True);data=json.loads(source.read_text());models=data['models'];assert set(models)<=ALLOWED
 baseline_path=generated/'model-preview.json';baseline=json.loads(baseline_path.read_text());base_sha=sha(baseline_path)
 baseline_c=generated/'models_data.c';baseline_c_sha=sha(baseline_c)
 def original_bounds(symbol,count):
  text=baseline_c.read_text();body=re.search(r'const bg_bounds '+symbol+r'\[[^]]+\]=\{(.*?)\n\};',text,re.S).group(1)
  rows=[row.strip().rstrip(',') for row in body.splitlines() if row.strip()];assert len(rows)==count
  parsed=[[[float(x) for x in re.findall(r'[-+]?(?:[0-9]+\.[0-9]+|[0-9]+)',part)] for part in row.strip('{}').split('},{')] for row in rows]
  assert all(len(b)==2 and all(len(p)==3 for p in b) for b in parsed)
  return parsed,rows
 old_vehicle_bounds,old_vehicle_rows=original_bounds('bg_vehicle_lod_bounds',4)
 old_pickup_bounds,old_pickup_rows=original_bounds('bg_model_cull_bounds',len(NAMES))
 lines=['/* Generated from local game assets; do not commit. */','#include "asset_micro.h"'];report={};preview={};bounds={}
 xyz=lambda p:'{'+','.join(map(str,p))+'}'
 for name,m in models.items():
  pos=m['positions'];col=m['colors'];assert len(pos)==len(col)==m['triangle_count']*3 and len(pos)>0
  assert all(len(p)==3 and all(math.isfinite(v) for v in p) for p in pos)
  positions=[tuple(round(v*1024) for v in p) for p in pos];assert all(-32768<=v<=32767 for p in positions for v in p)
  colors=[tuple(round(v) for v in rgb) for rgb in col];assert all(len(rgb)==3 and all(0<=v<=255 for v in rgb) for rgb in colors)
  material=m['materials'];assert len(material) in (len(pos),m['triangle_count'])
  if len(material)==m['triangle_count']:material=[v for v in material for _ in range(3)]
  mask=m.get('team_mask',[0]*len(pos));assert len(mask)==len(pos) and all(v==0 for v in mask),'No animated/team-colored assets belong in this static micro bank'
  mesh=indexed_mesh(positions,colors,mask,None,None,reorder_static=True,color_tolerance=model_color_tolerance('world',m.get('source_bank',name)),material_keys=material)
  verts=mesh['vertices'];ident='micro_'+name;lines.append(f'static T3DVertPacked {ident}[] __attribute__((aligned(16)))={{')
  rgba=lambda c:(c[0]<<24)|(c[1]<<16)|(c[2]<<8)|255
  for a,b in zip(verts[::2],verts[1::2]):lines.append('{'+f'{xyz(a[0])},0,{xyz(b[0])},0,0x{rgba(a[1]):08x},0x{rgba(b[1]):08x},{{0,0}},{{0,0}}'+'},')
  lines.append('};');emit_batches(lines,ident,mesh)
  radius=max(math.sqrt(sum(v*v for v in p))/1024 for p in positions)
  lines.append(f'static const bg_model_asset asset_{name}={{'+f'{ident},{len(verts)},{radius+1e-6:.7f}f,{ident}_batches,{ident}_indices,{len(mesh["batches"])},{m["triangle_count"]}'+'};')
  bounds[name]=box(tuple(v/1024 for v in p) for p in positions)
  farname=name+'_lod' if name in VEHICLES else name+'_pickup_lod'
  original=baseline[farname];originalbox=box(original['positions'])
  excursion=max(0.,*(originalbox[0][a]-bounds[name][0][a] for a in range(3)),*(bounds[name][1][a]-originalbox[1][a] for a in range(3)))
  assert m['triangle_count']<=original['triangle_count'],(name,'micro cannot cost more than far')
  maxmatrixerror=max((sum(abs(v) for v in p)+1)/65536 for p in positions);assert maxmatrixerror<.5
  expanded=[]
  for first,count,index_first,index_count in mesh['batches']:
   assert first%2==0 and index_first%4==0 and count<=60 and index_count<=120
   expanded += [mesh['vertices'][first+i][0] for i in mesh['indices'][index_first:index_first+index_count]]
  order=[i*3+k for i in mesh['triangle_order'] for k in range(3)];assert expanded==[positions[i] for i in order]
  preview[name]={'positions':[[v/1024 for v in positions[i]] for i in order],'colors':[mesh['colors'][i] for i in order],'triangle_count':m['triangle_count'],'materials':[material[i] for i in order],'team_mask':[0]*len(order)}
  report[name]={'triangles':m['triangle_count'],'vertices':len(verts),'batches':len(mesh['batches']),'old_far_triangles':original['triangle_count'],'bounds':bounds[name],'old_far_bounds':originalbox,'max_far_aabb_excursion_halo_units':excursion,'fixed_matrix_error_bound_render_units':maxmatrixerror,'color_tolerance':model_color_tolerance('world',m.get('source_bank',name))}
 lines.append('const bg_model_asset *const bg_vehicle_micro_lods[4]={')
 lines += [f'&asset_{n},' if n in models else f'&bg_vehicle_lods[{i}],' for i,n in enumerate(VEHICLES)];lines.append('};')
 lines.append('const bg_model_asset *const bg_pickup_micro_lods[BG_M_COUNT]={')
 lines += [f'&asset_{n},' if n in models and n in PICKUPS else f'&bg_pickup_lods[{i}],' for i,n in enumerate(NAMES)];lines.append('};')
 lines.append('const bg_bounds bg_vehicle_micro_gate_bounds[4]={')
 gate_bounds={'vehicles':{},'pickups':{}}
 for i,n in enumerate(VEHICLES):
  old=old_vehicle_bounds[i];b=union(old,bounds.get(n,old));gate_bounds['vehicles'][n]=b;lines.append((old_vehicle_rows[i] if b==old else initializer(b))+',')
 lines.append('};\nconst bg_bounds bg_pickup_micro_gate_bounds[BG_M_COUNT]={')
 for i,n in enumerate(NAMES):
  old=old_pickup_bounds[i];b=union(old,bounds.get(n,old) if n in PICKUPS else old)
  gate_bounds['pickups'][n]=b;lines.append((old_pickup_rows[i] if b==old else initializer(b))+',')
 lines.append('};')
 # Every candidate point is contained by the emitted conservative gate source.
 for n,b in bounds.items():
  gate=gate_bounds['vehicles' if n in VEHICLES else 'pickups'][n]
  assert all(gate[0][a]<=b[0][a]<=b[1][a]<=gate[1][a] for a in range(3))
 (out/'micro_data.c').write_text('\n'.join(lines)+'\n');(out/'micro-preview.json').write_text(json.dumps(preview));
 proof={'source':str(source),'source_sha256':sha(source),'baseline_preview_sha256':base_sha,'baseline_c_sha256':baseline_c_sha,'generated_c_sha256':sha(out/'micro_data.c'),'models':report,'gate_bounds':gate_bounds,'dedicated_arrays':len(models),'aliases':23-len(models),'output_scope':'Additional generated C; original model bank remains byte-identical and links separately'}
 assert sha(baseline_path)==base_sha and sha(baseline_c)==baseline_c_sha
 (out/'micro-report.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps({'micro_models':len(models),'triangles':sum(x['triangles'] for x in report.values()),'vertices':sum(x['vertices'] for x in report.values()),'output':str(out)}))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,default=ROOT/'build/n64/assets/micro-lods.json');p.add_argument('--output',type=Path,default=ROOT/'build/n64/generated');p.add_argument('--generated',type=Path,default=ROOT/'build/n64/generated',help='Existing ordinary world bank and preview');a=p.parse_args();pack(a.source,a.output,a.generated)
