"""Local source-fitted undersuit spans beneath the retained Reach armor.

Reach leaves cloth out where its dense armor covers a joint. Cheap armor needs
continuous backing there. Measure directional cross-sections from this source,
keep the original limb proportions, and share the moving joint rings. This is
explicit new continuity geometry, never a claim of untouched source triangles.
"""
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from extract_gungnir import bone_globals


def limb_backing(model,lod,armor=None):
    bind=bone_globals(model['nodes']);names={n['name']:i for i,n in enumerate(model['nodes'])};vertices=np.array(model['vertices']);cloth_faces=[i for i,m in enumerate(model['materials']) if m in (5,87)]
    cloth_ids={v for fi in cloth_faces for v in model['faces'][fi]};all_ids={v for fi,m in enumerate(model['materials']) if m in (4,5,6,87) for v in model['faces'][fi]}
    tree=BVHTree.FromPolygons([Vector(p) for p in vertices],[model['faces'][i] for i in cloth_faces],all_triangles=True);triangles=[];records=[]
    for side in ('l','r'):
        for kind,chain,helper,root in [('arm',('upperarm','forearm','hand'),'elbow_fixup','clav'),('leg',('thigh','calf','foot'),'knee_fixup','pelvis')]:
            bones=[names[f'b_{side}_{n}'] for n in chain];a,b,c=[bind[i][:3,3] for i in bones];upper=b-a;lower=c-b
            family=('clav','shoulder','upperarm','elbow','forearm','wrist','hand') if kind=='arm' else ('hip','thigh','upperleg','knee','calf','foot','toe')
            def relevant(vi):
                return any(w>.1 and model['nodes'][bi]['name'].startswith('b_'+side+'_') and any(n in model['nodes'][bi]['name'] for n in family) for bi,w in model['weights'][vi])
            source_ids=np.array([i for i in sorted(all_ids) if relevant(i)]);cloth=np.array([i for i in source_ids if i in cloth_ids]);assert len(source_ids)>10
            root_bone=names['b_pelvis' if kind=='leg' else f'b_{side}_{root}'];joint_bone=names[f'b_{side}_{helper}']
            centers=[a-upper*.18,a+upper*.45,b,c+lower*.08] if lod==0 else [a-upper*.18,b,c+lower*.08]
            skin=[[(root_bone,.6),(bones[0],.4)],[(bones[0],1.)],[(joint_bone,1.)],[(bones[1],1.)]] if lod==0 else [[(root_bone,.6),(bones[0],.4)],[(joint_bone,1.)],[(bones[1],1.)]]
            fit_trees={};fit_regions={};fit_axes={};labels=[None]*len(centers)
            if armor:
                # Put actual shared rings inside each retained plate's upper
                # and lower rim. A single long cloth quad from knee to ankle
                # can cross a curved calf even when its endpoint radii fit.
                # These extra rings preserve that curvature and the plate's
                # native rigid bone through a bent-joint pose.
                side_name='left' if side=='l' else 'right'
                lower_component=side_name+('-forearm' if kind=='arm' else '-calf')
                lower_weights={}
                for t in armor:
                    if t['component']==lower_component:
                        for ws in t['weights']:
                            for bi,w in ws:lower_weights[bi]=lower_weights.get(bi,0)+w
                lower_bone=max(lower_weights,key=lower_weights.get)
                skin[2 if lod==0 else 1]=[(lower_bone,1.)]
                if lod==0:
                    # The two actual plate-rim sections replace the generic
                    # mid-upper-limb ring, rather than accumulating on it.
                    del centers[1];del skin[1];del labels[1]
                candidates=[]
                total_upper=np.linalg.norm(upper)
                for segment,(start,end,part) in enumerate(((a,b,'upperarm' if kind=='arm' else 'thigh'),(b,c,'forearm' if kind=='arm' else 'calf'))):
                    component=side_name+'-'+part;ts=[t for t in armor if t['component']==component]
                    if not ts:continue
                    ps=np.array([t['p'] for t in ts]);direction=end-start;length=np.linalg.norm(direction);direction/=length;along=(ps-start)@direction;lo=max(.005,float(along.min())+.003);hi=min(length-.005,float(along.max())-.003)
                    if hi<=lo:continue
                    flat=[Vector(p) for p in ps.reshape(-1,3)];fit_trees[component]=BVHTree.FromPolygons(flat,np.arange(len(flat)).reshape(-1,3).tolist(),all_triangles=True)
                    fit_axes[component]=direction.copy()
                    influences={}
                    for t in ts:
                        for ws in t['weights']:
                            for bi,w in ws:influences[bi]=influences.get(bi,0)+w
                    bone=max(influences,key=influences.get);fit_regions[component]=model['nodes'][bone]['name']
                    for offset in ((lo,hi) if lod==0 or segment else ((lo+hi)/2,)):
                        cut=start+direction*offset;section=[]
                        for face in ps:
                            for x,y in zip(face,np.roll(face,-1,axis=0)):
                                sx=(x-cut)@direction;sy=(y-cut)@direction
                                if (sx<0)!=(sy<0):section.append(x+(y-x)*(sx/(sx-sy)))
                        assert section,(component,'empty plate cross-section')
                        # A convex combination of the retained cross-section
                        # lies inside it; the skeletal centerline can lie
                        # outside an asymmetric plate's contour.
                        center=np.mean(section,axis=0);candidates.append((segment*total_upper+offset,center,[(bone,1.)],component))
                base=[]
                for center,ws in zip(centers,skin):
                    along=float((center-a)@(upper/total_upper)) if np.linalg.norm(center-b)>np.linalg.norm(center-a) else total_upper+float((center-b)@(lower/np.linalg.norm(lower)))
                    # The authored chain's endpoints/joint have exact ordering.
                    if np.linalg.norm(center-b)<1e-7:along=total_upper
                    if np.linalg.norm(center-c-lower*.08)<1e-7:along=total_upper+np.linalg.norm(lower)*1.08
                    base.append((along,center,ws,None))
                ordered=sorted(base+candidates,key=lambda item:item[0]);centers=[i[1] for i in ordered];skin=[i[2] for i in ordered];labels=[i[3] for i in ordered]
            count=5 if lod==0 else 4;points=[];weights=[];rings=[]
            for ri,center in enumerate(centers):
                axis=fit_axes[labels[ri]] if labels[ri] else upper if ri==0 else lower if ri==len(centers)-1 else upper+lower
                axis=axis/np.linalg.norm(axis);u=np.array((1.,0,0));u-=axis*np.dot(u,axis);u/=np.linalg.norm(u);v=np.cross(axis,u)
                ring=[];radii=[]
                for angle in np.arange(count)*2*np.pi/count:
                    direction=u*np.cos(angle)+v*np.sin(angle)
                    def sample(ids,band):
                        if not len(ids):return np.array([])
                        delta=vertices[ids]-center;axial=delta@axis;radial=delta-axial[:,None]*axis;length=np.linalg.norm(radial,axis=1)
                        keep=(abs(axial)<band)&(length>.004)&((radial@direction)/np.maximum(length,1e-10)>np.cos(np.pi/count+.18))
                        return length[keep]
                    measured=sample(cloth,.035)
                    if len(measured):radius=float(np.percentile(measured,85));method='nearby original cloth contour'
                    else:
                        measured=sample(source_ids,.045)
                        if not len(measured):measured=sample(source_ids,.09)
                        assert len(measured),(side,kind,ri,angle)
                        radius=float(np.percentile(measured,25))-.004;method='recessed inner armor contour'
                    # Tiny fingers or neighboring large armor pieces cannot
                    # determine the underlayer of the whole limb.
                    radius=max(.012,min(.049 if kind=='leg' else .039,radius+.005))
                    if labels[ri]:
                        hit,_,_,distance=fit_trees[labels[ri]].ray_cast(Vector(center),Vector(direction),.2)
                        if hit is not None:radius=max(.001,min(radius,distance-.002/3.048));method='inside retained source-derived plate at its actual rim'
                    point=center+direction*radius;ring.append(len(points));points.append(point.tolist());weights.append(skin[ri]);radii.append(dict(radius=radius,method=method))
                rings.append(dict(center=center.tolist(),axis=axis.tolist(),samples=radii))
            faces=[]
            for r in range(len(centers)-1):
                for j in range(count):
                    k=(j+1)%count;x=r*count+j;y=r*count+k;z=(r+1)*count+k;w=(r+1)*count+j;faces.extend(([x,y,z],[x,z,w]))
            # Select the outward winding from the measured ring centers.
            for f in faces:
                p=np.array([points[i] for i in f]);center=np.mean([centers[i//count] for i in f],axis=0)
                if np.dot(np.cross(p[1]-p[0],p[2]-p[0]),p.mean(0)-center)<0:f.reverse()
            for offset,reverse in ((0,True),((len(centers)-1)*count,False)):
                cap=list(range(offset,offset+count));cap=cap[::-1] if reverse else cap
                faces.extend([cap[0],cap[i],cap[i+1]] for i in range(1,len(cap)-1))
            component=f'garment-continuity-{side}-{kind}'
            for face in faces:
                tri=dict(p=[points[i] for i in face],weights=[weights[i] for i in face],uv=[],source_faces=[],material=87,component=component,source_components=['original cloth and armor cross-sections for '+side+' '+kind],construction='new local source-fitted undersuit span; shared joint rings',color_override=[44,49,51])
                for i in face:
                    hit,_,fi,distance=tree.find_nearest(Vector(points[i]));source_face=cloth_faces[fi];tri['source_faces'].append(dict(face=source_face,continuity_distance=distance));tri['uv'].append([0,0])
                triangles.append(tri)
            records.append(dict(component=component,bones=[model['nodes'][i]['name'] for i in bones],rings=rings,vertices=len(points),triangles=len(faces),source_vertices=source_ids.tolist(),plate_rim_bones=fit_regions,joint_skinning='shared original fixup joint; added plate-rim rings use the retained plate native bone'))
    return triangles,records


def torso_backing(model,lod):
    """Continuous spine-weighted backing, measured from the original garment.

    The source armpit and neck islands rely on high-resolution plate returns.
    One local cross-section loft replaces those islands; the outer armor stays
    independent. The pelvis ring follows the pelvis, avoiding thigh jiggle.
    """
    nodes={n['name']:i for i,n in enumerate(model['nodes'])};vertices=np.array(model['vertices']);source_faces=[fi for fi,(r,m) in enumerate(zip(model['regions'],model['materials'])) if r=='body' and m==87];ids=sorted({v for fi in source_faces for v in model['faces'][fi]});cloud=vertices[ids]
    levels=[(.375,'b_belt'),(.435,'b_torso'),(.565,'b_torso'),(.59,'b_torso'),(.605,'b_neck0')] if lod==0 else [(.375,'b_belt'),(.55,'b_torso'),(.59,'b_torso'),(.605,'b_neck0')]
    count=6 if lod==0 else 4;points=[];weights=[];records=[]
    for z,bone in levels:
        center=np.array((0.,0.,z));radii=[]
        for angle in np.arange(count)*2*np.pi/count:
            direction=np.array((np.cos(angle),np.sin(angle),0));delta=cloud-center;radius=np.linalg.norm(delta[:,:2],axis=1);cosine=(delta@direction)/np.maximum(radius,1e-10);keep=(abs(delta[:,2])<.025)&(cosine>np.cos(np.pi/count+.14))&(radius>.005)
            values=radius[keep]
            if not len(values):
                keep=(abs(delta[:,2])<.055)&(cosine>np.cos(np.pi/count+.25))&(radius>.005);values=radius[keep]
            measured=float(np.percentile(values,80)) if len(values) else .03
            # Neck, chest and waist each use their own measured cross-section.
            cap=.034 if z>.60 else .075
            value=max(.018,min(cap,max(measured-.002,.067 if z>.54 and z<.60 and direction[0]<-.3 else .018)));p=center+direction*value;p[0]=min(p[0],.04);points.append(p.tolist());weights.append([(nodes[bone],1.)]);radii.append(value)
        records.append(dict(z=z,bone=bone,measured_fit_radii=radii,source_percentile=80,inset_m=.002*3.048,hidden_front_limit_halo_units=.04))
    faces=[]
    for ri in range(len(levels)-1):
        for j in range(count):
            k=(j+1)%count;a=ri*count+j;b=ri*count+k;c=(ri+1)*count+k;d=(ri+1)*count+j;faces.extend(([a,b,c],[a,c,d]))
    for r,reverse in ((0,True),(len(levels)-1,False)):
        ring=[r*count+i for i in range(count)];ring=ring[::-1] if reverse else ring;faces.extend([ring[0],ring[i],ring[i+1]] for i in range(1,count-1))
    tree=BVHTree.FromPolygons([Vector(p) for p in vertices],[model['faces'][i] for i in source_faces],all_triangles=True);triangles=[]
    for face in faces:
        correspondence=[]
        for i in face:
            _,_,fi,distance=tree.find_nearest(Vector(points[i]));correspondence.append(dict(face=source_faces[fi],continuity_distance=distance,changed_topology=True))
        triangles.append(dict(p=[points[i] for i in face],weights=[weights[i] for i in face],uv=[[0,0]]*3,material=87,component='garment-continuity-spine',source_components=['body-87 / original torso, armpit and neck contours'],source_faces=correspondence,construction='new local measured torso/neck continuity loft; original spine and pelvis weights',color_override=[44,49,51]))
    return triangles,dict(component='garment-continuity-spine',rings=records,vertices=len(points),triangles=len(faces),source_vertices=ids)


def connected_backing(model,lod):
    """One connected undersuit cage, fitted to this source's native joints.

    Reach's disconnected garment islands rely on dense overlapping armor.
    Shared branch vertices close the shoulder/hip seams through motion. This
    is new backing only; all visible armor plates remain separate source parts.
    """
    import bpy,bmesh
    bind=bone_globals(model['nodes']);names={n['name']:i for i,n in enumerate(model['nodes'])};points=[];edges=[];skin=[];radii=[];records=[]
    def add(name,position,radius,bone,parent=None):
        index=len(points);points.append(list(position));skin.append(names[bone]);radii.append(radius);records.append(dict(name=name,position=list(position),radius=tuple(v*.66 for v in radius),source_bone=bone))
        if parent is not None:edges.append((parent,index))
        return index
    pelvis=add('pelvis',bind[names['b_pelvis']][:3,3],(.050,.066),'b_pelvis')
    parent=pelvis
    if lod==0:parent=add('waist',(0,0,.435),(.057,.064),'b_torso',parent)
    chest=add('chest',(0,0,.55),(.065,.070),'b_torso',parent)
    neck=add('neck',(0,0,.605),(.026,.029),'b_neck0',chest)
    add('neck / beneath helmet',(0,0,.625),(.025,.026),'b_head',neck)
    for side in ('l','r'):
        parent=chest
        if False:parent=add(side+' clavicle',bind[names[f'b_{side}_clav']][:3,3],(.031,.035),f'b_{side}_clav',parent)
        for name,radius,bone in [('upperarm',(.032,.035),'upperarm'),('forearm',(.030,.032),'elbow_fixup'),('hand',(.024,.027),'hand')]:
            pos=bind[names[f'b_{side}_{name}']][:3,3];parent=add(side+' '+name,pos,radius,f'b_{side}_{bone}',parent)
        hand=bind[names[f'b_{side}_hand']][:3,3];grip=bind[names[f'b_{side}_grip']][:3,3];add(side+' cuff',hand+(grip-hand)*.5,(.023,.025),f'b_{side}_hand',parent)
        parent=pelvis
        for name,radius,bone in [('thigh',(.038,.042),'thigh'),('calf',(.031,.035),'knee_fixup'),('foot',(.029,.033),'foot')]:
            parent=add(side+' '+name,bind[names[f'b_{side}_{name}']][:3,3],radius,f'b_{side}_{bone}',parent)
        foot=bind[names[f'b_{side}_foot']][:3,3];add(side+' ankle / beneath boot',foot+(0,0,-.015),(.026,.030),f'b_{side}_foot',parent)
    me=bpy.data.meshes.new('Source-joint continuous undersuit');me.from_pydata(points,edges,[]);ob=bpy.data.objects.new('Source-joint continuous undersuit',me);bpy.context.scene.collection.objects.link(ob)
    for n in model['nodes']:ob.vertex_groups.new(name=n['name'])
    for i,bone in enumerate(skin):ob.vertex_groups[bone].add([i],1,'REPLACE')
    modifier=ob.modifiers.new('Connected local branch backing','SKIN');modifier.branch_smoothing=0;modifier.use_smooth_shade=False
    layer=me.skin_vertices[0]
    for i,radius in enumerate(radii):layer.data[i].radius=tuple(v*.66 for v in radius)
    layer.data[pelvis].use_root=True
    if lod:
        reduce=ob.modifiers.new('Independent far undersuit budget','DECIMATE');reduce.ratio=.62;reduce.use_collapse_triangulate=True
    ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh();mesh.calc_loop_triangles();xyz=[v.co.copy() for v in mesh.vertices];weights=[]
    for v in mesh.vertices:
        values=[(g.group,g.weight) for g in v.groups if g.weight>1e-7]
        if not values:
            # Skin-created branch vertices have no original vertex group.
            # Interpolate the native source bones on the closest fitted edge.
            p=np.array(v.co);best=None
            for a,b in edges:
                x=np.array(points[a]);d=np.array(points[b])-x;t=float(np.clip((p-x)@d/max(d@d,1e-12),0,1));distance=float(np.linalg.norm(p-x-t*d))
                if best is None or distance<best[0]:best=(distance,a,b,t)
            _,a,b,t=best;combined={}
            for bone,w in ((skin[a],1-t),(skin[b],t)):combined[bone]=combined.get(bone,0)+w
            values=list(combined.items())
        values=sorted(values,key=lambda x:-x[1])[:4];total=sum(w for b,w in values);assert total>0;weights.append([(b,w/total) for b,w in values])
    fs=[list(t.vertices) for t in mesh.loop_triangles];ev.to_mesh_clear();bpy.data.objects.remove(ob,do_unlink=True);bpy.data.meshes.remove(me)
    # Each source joint cross-section was measured in Halo units. Limit local
    # cloth projection to 4 mm, preserving connected topology and overlap.
    vertices=np.array(model['vertices']);source_faces=[i for i,m in enumerate(model['materials']) if m in (5,87)];tree=BVHTree.FromPolygons([Vector(p) for p in vertices],[model['faces'][i] for i in source_faces],all_triangles=True)
    # Fit the connected backing toward the original garment before skin
    # transfer. Four millimeters left bent-joint contours visibly recessed;
    # the same 16 mm local restoration limit used for the plates is retained.
    fit_records=[]
    for p in xyz:
        hit,_,fi,distance=tree.find_nearest(p);amount=min(distance,.016/3.048)
        if distance>1e-10:p+=(hit-p)*(amount/distance)
        fit_records.append(dict(garment_face=source_faces[fi],continuity_distance=distance,fit_displacement_m=amount*3.048))
    # Transfer skin from the closest original body/garment triangle, as in
    # the accepted demake protocol. Native fixups/jiggle weights matter at
    # folded elbows/knees; centerline bone interpolation alone can push cloth
    # through an otherwise unchanged plate in a seated pose.
    from mathutils import interpolate
    from collections import defaultdict
    eligible=[i for i,(r,m) in enumerate(zip(model['regions'],model['materials'])) if r in ('arms','body') and m in (4,5,6,87)]
    weight_tree=BVHTree.FromPolygons([Vector(p) for p in vertices],[model['faces'][i] for i in eligible],all_triangles=True)
    weights=[];skin_records=[]
    for p in xyz:
        hit,_,fi,distance=weight_tree.find_nearest(p);face=eligible[fi];ids=model['faces'][face];bary=np.maximum(0,interpolate.poly_3d_calc([Vector(model['vertices'][i]) for i in ids],hit));bary/=max(1e-12,bary.sum());combined=defaultdict(float)
        for vi,amount in zip(ids,bary):
            for bone,w in model['weights'][vi]:combined[bone]+=amount*w
        values=sorted(((b,w) for b,w in combined.items() if w>1e-7),key=lambda x:-x[1])[:4];total=sum(w for b,w in values);weights.append([(b,w/total) for b,w in values]);skin_records.append(dict(face=face,barycentric=bary.tolist(),weight_transfer_distance=distance))
    report=[]
    for pi,p in enumerate(xyz):
        report.append(dict(**skin_records[pi],**fit_records[pi],changed_topology=True,source_joint_cage=True))
    bm=bmesh.new();bm.verts.ensure_lookup_table()
    for p in xyz:bm.verts.new(p)
    bm.verts.ensure_lookup_table()
    for face in fs:
        try:bm.faces.new([bm.verts[i] for i in face])
        except ValueError:pass
    boundary=[e for e in bm.edges if len(e.link_faces)==1]
    if boundary:bmesh.ops.holes_fill(bm,edges=boundary,sides=0)
    bmesh.ops.triangulate(bm,faces=list(bm.faces));bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.verts.index_update();fs=[[v.index for v in f.verts] for f in bm.faces];open_edges=sum(len(e.link_faces)!=2 for e in bm.edges);assert open_edges==0,('undersuit backing is not closed',open_edges);bm.free()
    triangles=[dict(p=[list(xyz[i]) for i in f],weights=[weights[i] for i in f],uv=[[0,0]]*3,material=87,component='garment-connected-native-cage',source_components=['original Reach garment contours / native shoulder and hip branches'],source_faces=[report[i] for i in f],construction='new connected undersuit backing at measured native joints; shared branch vertices; source-fitted local contours',color_override=[44,49,51]) for f in fs]
    return triangles,dict(component='garment-connected-native-cage',vertices=len(xyz),triangles=len(fs),joints=records,maximum_source_fit_displacement_m=.016,method='shared shoulder/hip branch vertices under original independent armor',cross_section_method='conservative local fits within original garment and plate bounds',skinning_method='nearest original body/garment triangle barycentric transfer after fitting, normalized at most four influences')
