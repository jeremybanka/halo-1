"""Source-located small returns, using exact existing candidate skin trajectories."""
from collections import defaultdict
import copy
import numpy as np


def hull2(points):
    ids=sorted(range(len(points)),key=lambda i:tuple(points[i]));low=[];high=[]
    def turn(a,b,c):
        x,y=points[b]-points[a];u,v=points[c]-points[a];return x*v-y*u
    for i in ids:
        while len(low)>1 and turn(low[-2],low[-1],i)<=1e-10:low.pop()
        low.append(i)
    for i in reversed(ids):
        while len(high)>1 and turn(high[-2],high[-1],i)<=1e-10:high.pop()
        high.append(i)
    return low[:-1]+high[:-1]


def source_seams(model,face_ids,lod,triangles,colors=None):
    candidates=[];seen=set()
    for ti,t in enumerate(triangles):
        if t['component'].startswith('helmet'):continue
        for ci,(p,ws,uv,record) in enumerate(zip(t['p'],t['weights'],t['uv'],t['source_faces'])):
            key=(tuple(p),tuple(map(tuple,ws)))
            if key not in seen:seen.add(key);candidates.append((np.array(p),ws,t['component'],t['material'],uv,record,colors[ti][0][ci] if colors else None,colors[ti][1][ci] if colors else None))
    positions=np.array([v[0] for v in candidates]);patches=[];ledger=[];groups=defaultdict(list)
    for fi in face_ids:
        material=model['materials'][fi];region=model['regions'][fi]
        if region=='head' or material in (44,45,130,131,139):continue
        groups[(region,material)].append(fi)
    for (region,material),indices in groups.items():
        edges=defaultdict(set)
        for fi in indices:
            for vi in model['faces'][fi]:edges[tuple(round(v,5) for v in model['vertices'][vi])].add(fi)
        remaining=set(indices);clusters=[]
        while remaining:
            seed=remaining.pop();cluster={seed};todo=[seed]
            while todo:
                fi=todo.pop()
                for vi in model['faces'][fi]:
                    for other in edges[tuple(round(v,5) for v in model['vertices'][vi])]&remaining:remaining.remove(other);cluster.add(other);todo.append(other)
            clusters.append(sorted(cluster))
        for ci,cluster in enumerate(clusters):
            source=np.array([[model['vertices'][i] for i in model['faces'][fi]] for fi in cluster]);centroid=source.mean((0,1));normal=np.cross(source[:,1]-source[:,0],source[:,2]-source[:,0]).sum(0);length=np.linalg.norm(normal)
            if length<1e-12:continue
            normal/=length;axis=np.eye(3)[np.argmin(abs(normal))];u=np.cross(normal,axis);u/=np.linalg.norm(u);v=np.cross(normal,u);ids=set()
            for p in source.reshape(-1,3):
                order=np.argsort(np.linalg.norm(positions-p,axis=1))
                for i in order[:3]:
                    if np.linalg.norm(positions[i]-p)<.016:ids.add(int(i))
            if len(ids)<3:continue
            ids=sorted(ids);planar=np.array([[(positions[i]-centroid)@u,(positions[i]-centroid)@v] for i in ids]);ring=[ids[i] for i in hull2(planar)]
            if len(ring)<3:continue
            name=f'seam-{region}-{material}-{ci}';cloth=material in (5,87);family='torso' if region=='body' else 'shoulder-'+region.split('_')[1] if 'shoulder' in region else 'chest-parafoil' if region=='flair_chest_a' else 'right-forearm' if region=='arms' else name;count=0
            for i in range(1,len(ring)-1):
                corners=[candidates[j] for j in (ring[0],ring[i],ring[i+1])];p=np.array([c[0] for c in corners])
                if np.dot(np.cross(p[1]-p[0],p[2]-p[0]),normal)<0:corners.reverse()
                t=dict(p=[c[0].tolist() for c in corners],uv=[c[4] for c in corners],weights=[c[1] for c in corners],material=material,component='garment-'+name if cloth else name,color_family=family,source_components=[region+' / local audit seam'],source_faces=[{**copy.deepcopy(c[5]),'existing_candidate_corner':True} for c in corners],gap_locator_source_faces=cluster,construction='new local return through existing weighted contour vertices; original donor correspondence retained; separate source faces locate and orient the seam')
                if cloth:t['color_override']=[44,49,51]
                if colors:t['corner_color_override']=[c[6] for c in corners];t['corner_mask_override']=[c[7] for c in corners]
                patches.append(t);count+=1
                reverse={**t,'p':t['p'][::-1],'weights':t['weights'][::-1],'uv':t['uv'][::-1],'source_faces':t['source_faces'][::-1],'return_reverse':True}
                if colors:reverse['corner_color_override']=t['corner_color_override'][::-1];reverse['corner_mask_override']=t['corner_mask_override'][::-1]
                patches.append(reverse);count+=1
            ledger.append(dict(lod=lod,id=name,actual=count,source_faces=cluster,existing_candidate_vertices=ring,maximum_search_overlap_m=.016*3.048,decision='local source-located return sharing exact existing skin trajectories'))
    return patches,ledger
