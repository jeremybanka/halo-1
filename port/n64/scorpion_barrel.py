"""Preserve a readable, closed Scorpion cannon after tactical reduction.

The original source supplies the cannon node/axis and muzzle position. A small
inward-wound tapered tube replaces the collapsed cannon sheets. It overlaps the
remaining turret housing, without moving the muzzle or adding a separate sleeve mesh.
UVs/materials come from the pre-adjustment reduced near cannon. This is an
intentional N64 silhouette adjustment, not an exact source-geometry export.
"""
import math
from vehicle_parts import node_positions


def cannon_faces(model, bone):
    result=[]
    for i,t in enumerate(model['triangles']):
        touches=any(b==bone and w>0 for c in t['weights'] for b,w in c)
        if not touches:continue
        if any(any(b!=bone and w>1e-6 for b,w in c) or
               sum(w for b,w in c if b==bone)<1-1e-6 for c in t['weights']):
            raise ValueError('Scorpion cannon must remain a separate rigid surface')
        result.append(i)
    if not result:raise ValueError('No reduced Scorpion cannon geometry')
    return result


def replace_cannon(model, original, reference, settings):
    """Return a new model; preserve non-cannon faces and all source inputs."""
    if 'scorpion_cannon' in model.get('feature_adjustments',{}):
        raise ValueError('Scorpion cannon adjustment already applied')
    bone=next(i for i,n in enumerate(original['nodes']) if n['name']=='frame cannon')
    pivot=node_positions(original['nodes'])[bone]
    ids=set(cannon_faces(model,bone));ref=[reference['triangles'][i] for i in cannon_faces(reference,bone)]
    lo=min(p[0] for t in ref for p in t['p']);hi=max(p[0] for t in ref for p in t['p'])
    root=settings['root_cross_section'];muzzle=settings['muzzle_cross_section'];overlap=float(settings['housing_overlap'])
    if not (all(math.isfinite(v) and 0<v<=.3 for v in (*root,*muzzle)) and 0<=overlap<=.5):
        raise ValueError('Invalid Scorpion cannon cross section')
    # The bright sleeve is a separate original material between root and tip.
    sleeve=[p[0] for t in ref if t['material']==1 for p in t['p'] if p[0]<hi-1e-5]
    if not sleeve:raise ValueError('Missing source cannon sleeve')
    band_limits=(min(sleeve),max(sleeve))
    coords=[]
    for x in (lo-overlap,*band_limits,hi):
        t=(x-(lo-overlap))/(hi-(lo-overlap))
        width,height=[a+(b-a)*t for a,b in zip(root,muzzle)]
        w,h=width/2,height/2;y,z=pivot[1:]
        coords.extend([[x,y-w,z-h],[x,y+w,z-h],[x,y+w,z+h],[x,y-w,z+h]])
    # All normals point inside the closed box, matching the original emitted
    # model winding and the renderer's T3D_FLAG_CULL_FRONT convention.
    quads=[(0,1,2,3),(15,14,13,12)]
    for k in (0,4,8):
        quads.extend(((k,k+4,k+5,k+1),(k+1,k+5,k+6,k+2),
                      (k+2,k+6,k+7,k+3),(k+3,k+7,k+4,k)))
    shell=[]
    for qi,q in enumerate(quads):
        is_sleeve=6<=qi<10
        material=1 if qi<2 or is_sleeve else 0
        for face in ((q[0],q[1],q[2]),(q[0],q[2],q[3])):
            points=[coords[i].copy() for i in face];uv=[];sources=[]
            for index,p in zip(face,points):
                color_mat=material
                # Atlas boundary pixels bleed the sleeve into the shaft (or
                # darken the sleeve). Its original face interiors retain the
                # distinct source materials at both sleeve boundaries.
                samples=[([sum(c[j] for c in ft['p'])/3 for j in range(3)],
                          [sum(c[j] for c in ft['uv'])/3 for j in range(2)])
                         for ft in ref if ft['material']==color_mat
                         and (not is_sleeve or max(sp[0] for sp in ft['p'])<hi-1e-5)]
                if not samples:raise ValueError('Missing original cannon material')
                tuv=min(samples,key=lambda v:sum((v[0][j]-p[j])**2 for j in range(3)))[1]
                uv.append(tuv.copy());sources.append(color_mat)
            shell.append({'p':points,'uv':uv,'material':material,'sample_uv_direct':True,
                          'color_source_materials':sources,
                          'weights':[[[bone,1.0]] for _ in range(3)],'part':ref[0]['part']})
    metadata={'method':'closed tapered cannon; original muzzle/axis and sampled UVs',
              'removed_triangles':len(ids),'replacement_triangles':28,'sleeve_limits_x':band_limits,'source_root_x':lo,
              'muzzle_x':hi,'axis_yz':pivot[1:],'settings':settings}
    return {**model,'triangles':[t for i,t in enumerate(model['triangles']) if i not in ids]+shell,
            'feature_adjustments':{**model.get('feature_adjustments',{}),'scorpion_cannon':metadata}}


def apply_recipe(data, raw, settings):
    """Run after near/far reduction, before packing; mutate only these two entries."""
    reference=data['models']['scorpion']
    for key,profile in (('models','near'),('vehicle_lods','far')):
        data[key]['scorpion']=replace_cannon(data[key]['scorpion'],raw['models']['scorpion'],reference,settings[profile])
        if 'reduction' in data:
            name='scorpion' if profile=='near' else 'scorpion_lod'
            data['reduction'][name]['triangles']=len(data[key]['scorpion']['triangles'])
            data['reduction'][name]['cannon']=data[key]['scorpion']['feature_adjustments']['scorpion_cannon']
