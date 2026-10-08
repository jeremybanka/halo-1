"""Classify reduced vehicle triangles using original Xbox skinning palettes.

Returns reordered geometry and tiny rigid-part ranges without duplicating a
vehicle's vertex allocation. Degenerate triangles preserve whole-mesh drawing.
"""
import math

VEHICLES=('warthog','ghost','scorpion','banshee')


def node_positions(nodes):
    result=[None]*len(nodes)
    def visit(index):
        if result[index] is not None:return result[index]
        node=nodes[index];x,y,z,w=node['q'];p=node['p']
        r=[[1-2*(y*y+z*z),2*(x*y+z*w),2*(x*z-y*w)],
           [2*(x*y-z*w),1-2*(x*x+z*z),2*(y*z+x*w)],
           [2*(x*z+y*w),2*(y*z-x*w),1-2*(x*x+y*y)]]
        parent=node['parent']
        if parent>=0:
            pr,pp=visit(parent)
            r=[[sum(pr[i][k]*r[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
            p=[pp[i]+sum(pr[i][j]*p[j] for j in range(3)) for i in range(3)]
        result[index]=(r,p);return result[index]
    for index in range(len(nodes)):visit(index)
    return [p for _,p in result]


def _layout(name,original):
    nodes=original['nodes']
    def descendants(index,ancestor):
        while index>=0:
            if index==ancestor:return True
            index=nodes[index]['parent']
        return False
    if name=='warthog':
        # body, four tire hubs, gun-mount yaw, gun/barrel elevation
        roots=[-1,14,15,16,17,1,8];kinds=[0,1,1,1,1,2,3];turret=1
        def group(bone):
            for index,root in enumerate(roots[1:5],1):
                if descendants(bone,root):return index
            if descendants(bone,8):return 6
            if descendants(bone,1):return 5
            return 0
    elif name=='banshee':
        roots=[-1,1];kinds=[0,4];turret=0
        def group(bone):return 1 if descendants(bone,1) else 0
    else:
        # Retail "stand fixed aim-still" rotates node7 about Z (yaw) and
        # node8 about Y (pitch). The broad turret and its gun/cannon children
        # must pitch together; rotating only children9/10 detaches the barrel.
        roots=[-1,7,8,1];kinds=[0,2,3,4];turret=7
        def group(bone):
            if descendants(bone,1):return 3
            if descendants(bone,8):return 2
            if descendants(bone,7):return 1
            return 0
    return roots,kinds,turret,group


def triangle_groups(name,model,original):
    """Original skinning-palette rigid group for each reduced triangle."""
    if name not in ('warthog','scorpion','banshee'):return [0]*len(model['triangles'])
    roots,_,_,group=_layout(name,original)
    source=original['vertices'];weights=original['weights']
    cache={}
    result=[]
    for tri in model['triangles']:
        votes=[0.0]*len(roots)
        for point in tri['p']:
            key=tuple(point)
            if key not in cache:
                nearest=min(range(len(source)),key=lambda i:sum((source[i][j]-point[j])**2 for j in range(3)))
                cache[key]=weights[nearest]
            a,b,w=cache[key]
            if a<0:raise ValueError('Missing vehicle skinning palette')
            votes[group(a)]+=1-w
            if b>=0 and w>0:votes[group(b)]+=w
        result.append(max(range(len(roots)),key=votes.__getitem__))
    return result


def split_vehicle(name,model,original):
    if name not in ('warthog','scorpion','banshee'):
        return model,{'parts':[{'first':0,'count':len(model['triangles'])*3,'kind':0,'pivot':[0,0,0]}],'turret_pivot':[0,0,0]}
    nodes=original['nodes'];pivots=node_positions(nodes)
    roots,kinds,turret,_=_layout(name,original)
    groups=[[] for _ in roots]
    for tri,group in zip(model['triangles'],triangle_groups(name,model,original)):
        groups[group].append(tri)
    ordered=[];parts=[]
    for root,kind,tris in zip(roots,kinds,groups):
        if not tris:continue
        first=len(ordered)*3
        ordered.extend(tris)
        if len(tris)%2:
            last=tris[-1];ordered.append({'p':[last['p'][-1]]*3,'uv':[last['uv'][-1]]*3,'material':last['material']})
        point=pivots[root] if root>=0 else [0,0,0]
        parts.append({'first':first,'count':len(ordered)*3-first,'kind':kind,
                      'pivot':[point[0],point[2],-point[1]]})
    point=pivots[turret]
    return {**model,'triangles':ordered},{'parts':parts,'turret_pivot':[point[0],point[2],-point[1]]}
