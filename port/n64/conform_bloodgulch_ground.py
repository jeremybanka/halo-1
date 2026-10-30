"""Restore source Blood Gulch ground in an isolated appraisal map bank."""
import argparse,struct,json,hashlib,math
from pathlib import Path
import numpy as np
from pack_terrain import indexed_terrain

def conform(source,out):
 data=source.read_bytes()
 def section(i):
  off,n,size=struct.unpack_from('>3I',data,16+i*12);return n,size,data[off:off+n*size]
 def rows(i,fmt):return list(struct.iter_unpack('>'+fmt,section(i)[2]))
 vertices=[]
 for p in rows(0,'3hH3hHII4h'):
  for xyz,rgba,uv in ((p[:3],p[8],p[10:12]),(p[4:7],p[9],p[12:14])):vertices.append(np.array([*xyz,(rgba>>24)&255,(rgba>>16)&255,(rgba>>8)&255,*uv],float))
 indices=[x[0] for x in rows(2,'h')];chunks=rows(1,'IHH6hHH');groups=[]
 for ci,ch in enumerate(chunks):
  first,count,mat=ch[:3]
  if mat==2:continue
  start,n=ch[-2:];ids=indices[start:start+n] if n else list(range(count));tris=[]
  for j in range(0,len(ids)-2,3):tris.append([vertices[first+ids[j+k]].copy() for k in range(3)])
  groups.append([mat,tris])
 # Restore the owned source render ground, whose triangles match its source
 # collision planes. All other material geometry and every nonrender section
 # remain unchanged. This is an appraisal candidate, not an adopted map edit.
 from collections import defaultdict
 from pack_assets import position,normal
 raw_path=Path(__file__).resolve().parents[2]/'halo64-assets/assets/bloodgulch-raw.json'
 raw=json.loads(raw_path.read_text());ground=defaultdict(list)
 for g in raw['groups']:
  if g['material']!=2:continue
  for face in g['faces']:
   points=[position(g['vertices'][i]) for i in face];n=normal(points);light=.60+.40*max(0,sum(a*b for a,b in zip(n,[.25,.83,.49])));rgb=[round(255*light)]*3
   center=[sum(p[k] for p in points)/3 for k in range(3)];key=(int(center[0]//12),int(center[2]//12))
   ground[key].append([np.array([*[round(v*256) for v in p],*rgb,*[round(u*2048) for u in g['uv'][i]]],float) for i,p in zip(face,points)])
 groups.extend([2,t] for key,t in sorted(ground.items()));groups.sort(key=lambda g:g[0])
 history=[{'original_ground_triangles':sum(len(t) for m,t in groups if m==2),'source_sha256':hashlib.sha256(raw_path.read_bytes()).hexdigest()}]
 verts=[];ix=[];newchunks=[]
 for mat,tris in groups:
  packed=[[tuple(int(round(v)) for v in p) for p in t] for t in tris]
  for batch in indexed_terrain(packed,uv_period=2048 if mat==2 else 1024):
   v=batch['vertices'];local=batch['indices'];first=len(verts);count=len(v);start=len(ix);verts.extend(v);ix.extend(local)
   while len(ix)%4:ix.append(0)
   bounds=[math.floor(min(p[k] for p in v)/8) for k in range(3)]+[math.ceil(max(p[k] for p in v)/8) for k in range(3)]
   newchunks.append((first,count,mat,*bounds,start,len(local)))
   if len(verts)%2:verts.append(verts[-1])
 payload=bytearray()
 for i in range(0,len(verts),2):
  a,b=verts[i:i+2];rgba=lambda p:(p[3]<<24)|(p[4]<<16)|(p[5]<<8)|255
  payload+=struct.pack('>3hH3hHII4h',*a[:3],0,*b[:3],0,rgba(a),rgba(b),*a[6:],*b[6:])
 replacement={0:(len(verts)//2,32,bytes(payload)),1:(len(newchunks),24,b''.join(struct.pack('>IHH6hHH',*c) for c in newchunks)),2:(len(ix),2,struct.pack('>'+str(len(ix))+'h',*ix))}
 result=bytearray(data[:16+23*12])
 for i in range(23):
  while len(result)%16:result.append(0)
  n,size,payload=replacement.get(i,section(i));struct.pack_into('>3I',result,16+i*12,len(result),n,size);result+=payload
 struct.pack_into('>I',result,12,len(result));out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(result)
 for i in range(3,23):
  off,n,size=struct.unpack_from('>3I',result,16+i*12);assert result[off:off+n*size]==section(i)[2]
 report={'baseline_sha256':hashlib.sha256(data).hexdigest(),'candidate_sha256':hashlib.sha256(result).hexdigest(),'history':history,'vertices_before':len(vertices),'vertices_after':len(verts),'chunks_before':len(chunks),'chunks_after':len(newchunks),'triangles_after':sum(len(t) for _,t in groups),'unchanged_sections':list(range(3,23))}
 out.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();conform(a.source,a.output)
