#!/usr/bin/env python3
"""Exact Xbox collision surfaces in the demake's compact spatial-grid adapter."""
import contextlib,hashlib,json,math,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'port/n64/blam/tags'))
from export_collision import decode,check,polygons

def main():
 out=ROOT/'build/n64/generated';src=ROOT/'build/n64/assets/bloodgulch-decompressed.map'
 with (out/'terrain-extraction.log').open('w') as log,contextlib.redirect_stdout(log):data,spawns=decode(src)
 check(data);vertices=[(v[0]-68,v[2],-v[1]-118) for v in data['vertices']]
 triangles=[];flags=[]
 for surface,poly in zip(data['surfaces'],polygons(data)):
  plane=data['planes'][surface[0]&0x7fffffff];sign=-1 if surface[0]<0 else 1
  normal=(plane[0]*sign,plane[2]*sign,-plane[1]*sign)
  for i in range(1,len(poly)-1):
   face=[poly[0],poly[i],poly[i+1]];a,b,c=[vertices[v] for v in face]
   ab=[b[k]-a[k] for k in range(3)];ac=[c[k]-a[k] for k in range(3)]
   n=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])
   if sum(n[k]*normal[k] for k in range(3))<0:face[1],face[2]=face[2],face[1]
   triangles.append(face);flags.append(int(normal[1]>0 and normal[1]*normal[1]>=.38*sum(n*n for n in normal)))
 lo=[min(v[k] for v in vertices)-.01 for k in (0,2)];hi=[max(v[k] for v in vertices)+.01 for k in (0,2)];size=[(hi[k]-lo[k])/24 for k in range(2)];cells=[[]for _ in range(576)]
 for i,f in enumerate(triangles):
  p=[vertices[j]for j in f]
  bounds=[(max(0,math.floor((min(v[k]for v in p)-lo[a])/size[a])),min(23,math.floor((max(v[k]for v in p)-lo[a])/size[a])))for a,k in enumerate((0,2))]
  for z in range(bounds[1][0],bounds[1][1]+1):
   for x in range(bounds[0][0],bounds[0][1]+1):cells[z*24+x].append(i)
 indices=[];ranges=[]
 for c in cells:ranges.append((len(indices),len(c)));indices.extend(c)
 assert len(indices)<65536 and len(triangles)<65536
 f=lambda v:float(v).hex()+'f'
 lines=['/* Generated exact Xbox collision surfaces. Private owned assets. */','#include "world.h"','static const float terrain_vertices[][3]={']
 lines+=['{'+','.join(map(f,v))+'},'for v in vertices];lines+=['};','const bg_triangle bg_collision[]={']
 lines+=['{{'+','.join('terrain_vertices[%d]'%v for v in t)+'}},'for t in triangles];lines+=['};','const uint8_t bg_collision_flags[]={'+','.join(map(str,flags))+'};',f'const unsigned bg_collision_count={len(triangles)};', 'const bg_cell bg_grid[BG_GRID*BG_GRID]={']
 lines+=['{%d,%d},'%r for r in ranges];lines+=['};','const uint16_t bg_grid_indices[]={'+','.join(map(str,indices))+'};','const float bg_grid_origin[2]={'+','.join(map(f,lo))+'};','const float bg_grid_size[2]={'+','.join(map(f,size))+'};']
 # Preserve existing scenario spawn ordering/yaw/team, not re-derived defaults.
 old=(out/'collision_data.c').read_text();lines.append(old[old.index('const bg_spawn bg_spawns'):])
 dest=out/'terrain_data.c';dest.write_text('\n'.join(lines)+'\n')
 report={'triangles':len(triangles),'vertices':len(vertices),'grid_indices':len(indices),'bytes':len(triangles)*13+len(vertices)*12+len(indices)*2+576*4,'inputs':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in [src,Path(__file__),ROOT/'port/n64/blam/tags/export_collision.py',out/'collision_data.c']},'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()}
 (out/'terrain-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
