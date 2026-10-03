"""Conservative deterministic edge collapse for rigid vehicle meshes.

The original far recipe runs first. This pass merges only short edges whose
entire accumulated source-vertex cluster remains within a world-space radius.
It preserves triangle winding, rigid articulation groups and explicitly locked
material faces. The radius is derived from an eight-view projected extent;
this is a vertex-motion bound, not a guarantee about rasterized silhouettes.
"""
from collections import defaultdict
import math

VIEWS = ((1,.02,0),(0,.02,1),(-1,.02,0),(0,.02,-1),
         (1,.40,1),(-1,.40,-1),(.001,1,.001),(1,.16,-1))


def sub(a,b): return tuple(x-y for x,y in zip(a,b))
def dot(a,b): return sum(x*y for x,y in zip(a,b))
def cross(a,b): return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def unit(v):
    length=math.sqrt(dot(v,v))
    return tuple(x/length for x in v)


def reference_span(original):
    """Smallest maximum 2D extent in the established eight audit directions."""
    points=[(p[0],p[2],-p[1]) for p in original['vertices']]
    spans=[]
    for direction in VIEWS:
        look=unit(direction)
        up=(0,1,0) if abs(look[1])<.98 else (0,0,-1)
        right=unit(cross(up,look));up=cross(look,right)
        spans.append(max(max(dot(p,a) for p in points)-min(dot(p,a) for p in points)
                         for a in (right,up)))
    return min(spans)


def rigid_group(name,triangle):
    weights=defaultdict(float)
    for influence in triangle['weights']:
        for bone,weight in influence: weights[bone]+=weight
    bone=max(weights,key=weights.get)
    if name=='warthog':
        if bone in (14,15,16,17,1): return bone
        return 8 if bone in (8,13,7) else 0
    if name=='scorpion':
        if bone in (9,10): return 10
        return 7 if bone in (7,8) else 0
    return 0


def reduce_bounded(name,model,original,settings):
    if name not in ('warthog','ghost','scorpion','banshee'):
        raise ValueError('Bounded collapse is for rigid vehicles only')
    pixel_limit=float(settings['max_pixel_displacement'])
    extent=float(settings.get('reference_extent_pixels',20))
    if not 0<pixel_limit<=1 or extent<=0:
        raise ValueError('Invalid bounded-collapse displacement')
    radius=reference_span(original)/extent*pixel_limit
    radius2=radius*radius
    protected=set(settings.get('preserve_materials',[]))
    triangles=model['triangles'];lookup={};positions=[];faces=[];locked=set()
    for triangle in triangles:
        face=[];part=rigid_group(name,triangle)
        for point in triangle['p']:
            key=(part,*(round(v,6) for v in point))
            if key not in lookup:
                lookup[key]=len(positions);positions.append(tuple(point))
            face.append(lookup[key])
        faces.append(face)
        if triangle['material'] in protected: locked.update(face)
    source=positions.copy();clusters={i:[i] for i in range(len(source))}
    active=[len(set(f))==3 for f in faces];collapses=0
    while True:
        edges={tuple(sorted((f[i],f[(i+1)%3])))
               for f,live in zip(faces,active) if live for i in range(3)}
        choices=[]
        for a,b in edges:
            if a==b or a in locked or b in locked: continue
            center=tuple((x+y)/2 for x,y in zip(positions[a],positions[b]))
            cluster=clusters[a]+clusters[b]
            if any(dot(sub(source[i],center),sub(source[i],center))>radius2 for i in cluster):
                continue
            delta=sub(positions[a],positions[b])
            choices.append((dot(delta,delta),a,b,center,cluster))
        accepted=False
        # Explicit index tie breaks avoid set-iteration/host-version dependence.
        for _,a,b,center,cluster in sorted(choices,key=lambda c:c[:3]):
            valid=True
            for face,live in zip(faces,active):
                if not live or (a not in face and b not in face): continue
                new=[a if i==b else i for i in face]
                if len(set(new))<3: continue
                before=[positions[i] for i in face]
                after=[center if i==a else positions[i] for i in new]
                n0=cross(sub(before[1],before[0]),sub(before[2],before[0]))
                n1=cross(sub(after[1],after[0]),sub(after[2],after[0]))
                if dot(n0,n1)<=0:
                    valid=False;break
            if not valid: continue
            positions[a]=center;clusters[a]=cluster;del clusters[b]
            for fi,face in enumerate(faces):
                if active[fi]:
                    faces[fi]=[a if i==b else i for i in face]
                    active[fi]=len(set(faces[fi]))==3
            collapses+=1;accepted=True;break
        if not accepted: break
    result=[];max_motion=0.
    for triangle,face,live in zip(triangles,faces,active):
        if not live: continue
        points=[list(positions[i]) for i in face]
        for a,b in zip(triangle['p'],points): max_motion=max(max_motion,math.sqrt(dot(sub(a,b),sub(a,b))))
        if triangle['material'] in protected:
            # Preserve the exact source corner values, including duplicates
            # whose connectivity key differs only below six decimal places.
            points=triangle['p']
        result.append({**triangle,'p':points})
    stats={'before':len(triangles),'triangles':len(result),'collapses':collapses,
           'world_displacement_limit':radius,'actual_max_world_displacement':max_motion,
           'reference_extent_pixels':extent,'max_pixel_displacement':pixel_limit,
           'preserved_materials':sorted(protected)}
    return {**model,'triangles':result},stats


def reduce_near_bounded(name,model,original,settings):
    """Preserve near-vehicle features and original articulated membership.

    The authored-LOD reduction runs first. Feature faces pin their vertices;
    any surviving face that crosses a nearest-source skinning boundary is
    pinned too, then the deterministic collapse restarts. This retains the
    original rig classification without depending on a saved candidate mesh.
    The distant recipe intentionally remains separate and unchanged.
    """
    from vehicle_parts import triangle_groups
    if name not in ('warthog','ghost','scorpion'):
        raise ValueError('No reviewed near-vehicle recipe for '+name)
    radius=float(settings['max_world_displacement'])
    if not math.isfinite(radius) or radius<=0:
        raise ValueError('Invalid near-vehicle displacement')
    materials=set(settings.get('preserve_materials',[]))
    groups=set(settings.get('preserve_rigid_groups',[]))
    tips=settings.get('preserve_tips',[])
    triangles=model['triangles'];locked=set()
    for i,t in enumerate(triangles):
        group=rigid_group(name,t)
        if t['material'] in materials or group in groups or any(
            group==tip['rigid_group'] and
            max(p[tip['axis']] for p in t['p'])>tip['above'] for tip in tips):
            locked.add(i)
    feature_locks=set(locked);expected=triangle_groups(name,model,original)
    sentinel=max(t['material'] for t in triangles)+1
    collapse_settings={'max_pixel_displacement':radius*20/reference_span(original),
                       'reference_extent_pixels':20,'preserve_materials':[sentinel]}
    for attempt in range(len(triangles)+1):
        working={**model,'triangles':[
            {**t,'_bounded_source':i,'material':sentinel if i in locked else t['material']}
            for i,t in enumerate(triangles)]}
        reduced,stats=reduce_bounded(name,working,original,collapse_settings)
        for t in reduced['triangles']:
            index=t['_bounded_source'];t['material']=triangles[index]['material']
            if index in locked:
                assert {k:v for k,v in t.items() if k!='_bounded_source'}==triangles[index]
        actual=triangle_groups(name,reduced,original)
        changed={t['_bounded_source'] for t,g in zip(reduced['triangles'],actual)
                 if expected[t['_bounded_source']]!=g}
        if not changed:break
        if changed<=locked:raise ValueError('Locked vehicle face changed rigid group')
        locked.update(changed)
    else:raise ValueError('Vehicle rigid-boundary preservation did not converge')
    for t in reduced['triangles']:del t['_bounded_source']
    stats.update({'preserved_materials':sorted(materials),
                  'preserved_rigid_groups':sorted(groups),'preserved_tips':tips,
                  'feature_locked_triangles':len(feature_locks),
                  'boundary_locked_source_triangles':sorted(locked-feature_locks),
                  'rigid_boundary_passes':attempt+1,'rigid_membership_preserved':True})
    return reduced,stats
