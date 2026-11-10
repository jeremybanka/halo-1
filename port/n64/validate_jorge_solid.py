"""Verify actual geometry, fixed animated rims, assembled coverage and GLB motion."""
import bpy, json, math, struct, hashlib, sys
import numpy as np
from collections import Counter, deque
from mathutils import Vector
from mathutils.kdtree import KDTree
import jorge_solid_reduce as task
import jorge_animation_proof as animation
import validate_jorge_detail_pass as common
from validate_jorge_tactical import points
from validate_jorge_ce_materials import actions_for

OUT=task.OUT

def load_reference():
    with bpy.data.libraries.load(str(task.SOURCE),link=False) as (src,dst):dst.scenes=[n for n in src.scenes if n.startswith('Jorge - colors and surgical detail pass')]
    scene=dst.scenes[0];return scene,next(o for o in scene.objects if o.type=='ARMATURE')

def inventory():
    raw=(OUT/(task.NAME+'.glb')).read_bytes();n=struct.unpack_from('<I',raw,12)[0];d=json.loads(raw[20:20+n]);rows=[]
    build=json.loads((OUT/'reduction-report.json').read_text());by_key={r['component']:r for r in build['components']}
    for node in d['nodes']:
        if 'mesh' not in node:continue
        key=node['extras']['source_component'];ps=d['meshes'][node['mesh']]['primitives']
        row={'component':key,'exported_vertices':sum(d['accessors'][p['attributes']['POSITION']]['count'] for p in ps),'triangles':sum(d['accessors'][p['indices']]['count']//3 for p in ps)}
        assert row['triangles']==by_key[key]['triangles'],(key,row,by_key[key]['triangles'])
        rows.append(row)
    assert len(rows)==len(build['components'])
    report={'body_vertices':sum(r['exported_vertices'] for r in rows),'body_triangles':sum(r['triangles'] for r in rows),'body_components':len(rows),
            'bones':len(d['skins'][0]['joints']),'animations':[a['name'] for a in d['animations']],'materials':len(d['materials']),'images':len(d['images']),'components':rows}
    assert report['bones']==85 and len(report['animations'])==4 and report['materials']==2 and report['images']==1
    (OUT/'export-inventory.json').write_text(json.dumps(report,indent=2)+'\n');print('INVENTORY',{k:v for k,v in report.items() if k!='components'},flush=True)

def geometry_motion():
    scene,rig=task.proof_scene();reference,ref_rig=load_reference();obs=task.body(scene);refs={o['source_component']:o for o in task.body(reference)}
    report={'components':[],'clips':{}};build=json.loads((OUT/'reduction-report.json').read_text());rows={r['component']:r for r in build['components']}
    assert hashlib.sha256(task.SOURCE.read_bytes()).hexdigest()==build['source_sha256'];report['source_preserved']=True
    assert {o['source_component'] for o in obs}==set(refs)-set(task.CULL)
    for a,b in zip(rig.data.bones,ref_rig.data.bones):assert a.name==b.name and a.matrix_local==b.matrix_local and (a.parent.name if a.parent else None)==(b.parent.name if b.parent else None)
    rim_pairs={};maps={}
    for ob in obs:
        key=ob['source_component'];src=refs[key];me=ob.data;src.data.calc_loop_triangles();row=rows[key];health=task.topology(ob)
        assert task.boundary_error(row['original_health'],health)<1e-7
        assert health['euler']==row['original_health']['euler'] and health['nonmanifold_internal_edges']<=row['original_health']['nonmanifold_internal_edges']
        assert not(health['zero_area_faces'] or health['loose_vertices'] or health['wire_edges'])
        assert all(.99<n.vector.length<1.01 for n in me.corner_normals)
        assert all(math.isfinite(x) and 0<=x<=1 for uv in me.uv_layers.active.data for x in uv.uv)
        names={g.index:g.name for g in ob.vertex_groups if g.name in rig.data.bones};max_weight_error=max(abs(sum(g.weight for g in v.groups if g.group in names)-1) for v in me.vertices)
        assert max_weight_error<1e-6 and max(sum(g.weight>0 for g in v.groups if g.group in names) for v in me.vertices)<=4
        def tree(o):
            t=KDTree(len(o.data.vertices))
            for v in o.data.vertices:t.insert(v.co,v.index)
            t.balance();return t
        old=tree(src);new=tree(ob);pairs=[]
        for p in {tuple(p) for e in row['original_health']['boundary_segments'] for p in e}:
            a,ai,ad=old.find(p);b,bi,bd=new.find(p);assert max(ad,bd)<1e-7;pairs.append((ai,bi))
        rim_pairs[key]=pairs
        tris=[tuple(t.vertices) for t in src.data.loop_triangles]
        ids=np.array([tris[a.value] for a in me.attributes['lod_parent_triangle'].data]);bary=np.array([a.vector for a in me.attributes['lod_parent_barycentric'].data]);maps[key]=(ids,bary)
        report['components'].append({'component':key,'triangles':len(me.polygons),'vertices':task.count(ob),'fixed_rim_vertices':len(pairs),'euler':health['euler'],'boundary_edges':health['boundary_edges'],'volume_ratio':row['volume_ratio'],'surface_error':row['surface_error'],'max_weight_sum_error':max_weight_error})
    actions=actions_for(rig);ra=actions_for(ref_rig)
    for arm in (rig,ref_rig):arm.data.pose_position='POSE';arm.animation_data.use_nla=False
    for clip in animation.CLIPS:
        count=round(actions[clip]['duration_seconds']*30)+1;rim_error=pose_error=surface_error=0.
        for f in range(count):
            bpy.context.window.scene=scene;rig.animation_data.action=actions[clip];scene.frame_set(f);a=points(scene,obs);pa=np.array([b.matrix for b in rig.pose.bones])
            bpy.context.window.scene=reference;ref_rig.animation_data.action=ra[clip];reference.frame_set(f);b=points(reference,[refs[k] for k in a]);pb=np.array([b.matrix for b in ref_rig.pose.bones]);pose_error=max(pose_error,float(np.abs(pa-pb).max()))
            for key in a:
                assert np.isfinite(a[key]).all()
                for ai,bi in rim_pairs[key]:rim_error=max(rim_error,float(np.linalg.norm(a[key][bi]-b[key][ai])))
                ids,bary=maps[key];expected=(b[key][ids]*bary[:,:,None]).sum(axis=1);surface_error=max(surface_error,float(np.linalg.norm(a[key]-expected,axis=1).max()))
        assert rim_error<1e-6 and pose_error==0,(clip,rim_error,pose_error)
        report['clips'][clip]={'samples':count,'bone_pose_change':pose_error,'maximum_rim_motion_change_m':rim_error,'maximum_surface_correspondence_error_m':surface_error};print('MOTION',clip,report['clips'][clip],flush=True)
    (OUT/'geometry-motion-validation.json').write_text(json.dumps(report,indent=2)+'\n')

def mesh_data(scene,obs,quantized=False):
    bpy.context.window.scene=scene;dep=bpy.context.evaluated_depsgraph_get();vertices=[];faces=[];classes=[];ids=[];offset=0
    keys=sorted(o['source_component'] for o in obs)
    for ob in obs:
        ev=ob.evaluated_get(dep);me=ev.to_mesh();me.calc_loop_triangles();p=np.array([ev.matrix_world@v.co for v in me.vertices])
        if quantized:p=np.round(p/(animation.SCALE/128))*(animation.SCALE/128)
        vertices.extend(p);faces.extend([[i+offset for i in t.vertices] for t in me.loop_triangles]);offset+=len(p)
        category=1 if ob['group'] in ('body-10','arms-10','arms-08') else 2
        classes.extend([category]*len(me.loop_triangles));ids.extend([keys.index(ob['source_component'])+1]*len(me.loop_triangles));ev.to_mesh_clear()
    return np.array(vertices),np.array(faces),np.array(classes),np.array(ids),keys

def raster(data,direction,width=256,height=320):
    vertices,faces,classes,ids,keys=data;eye=np.array(direction,dtype=float);eye/=np.linalg.norm(eye)
    right=np.cross((0,0,1),eye);right/=np.linalg.norm(right);up=np.cross(eye,right)
    centered=vertices-np.array((0,0,1.15));p=np.stack((centered@right,centered@up,centered@eye),axis=1)
    p[:,:2]*=height/2.95;p[:,0]+=width/2;p[:,1]=height/2-p[:,1]
    depth=np.full((height,width),-np.inf);labels=np.zeros((height,width),dtype=np.int16);parts=np.zeros_like(labels)
    for fi,face in enumerate(faces):
        a,b,c=p[face];xmin=max(0,int(math.floor(min(a[0],b[0],c[0]))));xmax=min(width-1,int(math.ceil(max(a[0],b[0],c[0]))));ymin=max(0,int(math.floor(min(a[1],b[1],c[1]))));ymax=min(height-1,int(math.ceil(max(a[1],b[1],c[1]))))
        if xmax<xmin or ymax<ymin:continue
        det=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(det)<1e-9:continue
        y,x=np.mgrid[ymin:ymax+1,xmin:xmax+1];x=x+.5;y=y+.5
        u=((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/det;v=((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/det;w=1-u-v;z=u*a[2]+v*b[2]+w*c[2]
        view=depth[ymin:ymax+1,xmin:xmax+1];hit=(u>=-1e-7)&(v>=-1e-7)&(w>=-1e-7)&(z>view);view[hit]=z[hit]
        labels[ymin:ymax+1,xmin:xmax+1][hit]=classes[fi];parts[ymin:ymax+1,xmin:xmax+1][hit]=ids[fi]
    return labels,parts

def erode(mask,pixels):
    out=mask.copy()
    for _ in range(pixels):
        old=out;out=np.zeros_like(old);out[1:-1,1:-1]=old[1:-1,1:-1]&old[:-2,1:-1]&old[2:,1:-1]&old[1:-1,:-2]&old[1:-1,2:]
    return out

def enclosed_background(mask):
    """Background disconnected from the image border is an actual screen hole."""
    h,w=mask.shape;outside=np.zeros_like(mask);queue=deque()
    for y,x in [(0,x) for x in range(w)]+[(h-1,x) for x in range(w)]+[(y,0) for y in range(h)]+[(y,w-1) for y in range(h)]:
        if not mask[y,x] and not outside[y,x]:outside[y,x]=True;queue.append((y,x))
    while queue:
        y,x=queue.popleft()
        for ny,nx in ((y-1,x),(y+1,x),(y,x-1),(y,x+1)):
            if 0<=ny<h and 0<=nx<w and not mask[ny,nx] and not outside[ny,nx]:outside[ny,nx]=True;queue.append((ny,nx))
    return ~mask&~outside

def new_holes(before,after):
    """Separate newly opened holes from a changed outline of an existing gap.

    Bent arms and legs legitimately enclose background. A candidate gap that
    overlaps a source gap is an outline change, already measured by core loss.
    """
    enclosed=enclosed_background(after>0);remaining=set(zip(*np.nonzero(enclosed)));new=np.zeros_like(enclosed)
    while remaining:
        start=remaining.pop();region=[start];pending=[start]
        while pending:
            y,x=pending.pop()
            for p in ((y-1,x),(y+1,x),(y,x-1),(y,x+1)):
                if p in remaining:remaining.remove(p);region.append(p);pending.append(p)
        if not any(before[y,x]==0 for y,x in region):
            for y,x in region:new[y,x]=True
    return new&erode(before>0,1),enclosed&erode(before>0,1)

def largest_region(mask):
    remaining=set(zip(*np.nonzero(mask)));largest=0
    while remaining:
        pending=[remaining.pop()];size=0
        while pending:
            y,x=pending.pop();size+=1
            for p in ((y-1,x),(y+1,x),(y,x-1),(y,x+1)):
                if p in remaining:remaining.remove(p);pending.append(p)
        largest=max(largest,size)
    return largest

def coverage():
    scene,rig=task.proof_scene();reference,ref_rig=load_reference();obs=task.body(scene);refs=[o for o in task.body(reference) if o['source_component'] not in task.CULL]
    actions=actions_for(rig);ra=actions_for(ref_rig)
    for arm in (rig,ref_rig):arm.animation_data.use_nla=False
    directions=[(math.sin(i*math.pi/4),-math.cos(i*math.pi/4),.12) for i in range(8)]+[(.7,-1,.65),(-.7,1,.65)]
    samples=[(c,f) for c,fs in [('idle',(0,.5,1)),('run',(0,.25,.5,.75,1)),('fire',(0,.5,1)),('reload',(0,.2,.4,.6,.8,1))] for f in fs]
    rows=[];body_losses=Counter();armor_losses=Counter();worst=[]
    for clip,fraction in samples:
        f=actions[clip]['duration_seconds']*30*fraction
        bpy.context.window.scene=scene;rig.animation_data.action=actions[clip];scene.frame_set(int(f),subframe=f-int(f));after=mesh_data(scene,obs)
        bpy.context.window.scene=reference;ref_rig.animation_data.action=ra[clip];reference.frame_set(int(f),subframe=f-int(f));before=mesh_data(reference,refs)
        for vi,direction in enumerate(directions):
            a,parts=raster(before,direction);b,_=raster(after,direction)
            missing=erode(a>0,1)&(b==0);armor=erode(a==2,2)&(b!=2)
            holes,gap_growth=new_holes(a,b)
            row={'clip':clip,'fraction':fraction,'view':vi,'missing_body_core_pixels':int(missing.sum()),'lost_armor_core_pixels':int(armor.sum()),'new_enclosed_hole_pixels':int(holes.sum()),'largest_new_hole_pixels':largest_region(holes),'enclosed_gap_core_growth_pixels':int(gap_growth.sum())};rows.append(row)
            body_losses.update({before[-1][i-1]:int((parts[missing]==i).sum()) for i in np.unique(parts[missing]) if i})
            armor_losses.update({before[-1][i-1]:int((parts[armor]==i).sum()) for i in np.unique(parts[armor]) if i})
            if missing.any() or armor.any():worst.append((row,a,b,missing,armor))
        print('COVERAGE',clip,fraction,'max body',max(r['missing_body_core_pixels'] for r in rows[-10:]),'armor',max(r['lost_armor_core_pixels'] for r in rows[-10:]),flush=True)
    report={'resolution':[256,320],'pixel_size_m':2.95/320,'scope':'59 retained components including joints; intentionally removed straps/connector excluded from both sides; weapon excluded',
            'body_core_margin_pixels':1,'armor_core_margin_pixels':2,'views':rows,'body_loss_by_component':dict(body_losses),'armor_loss_by_component':dict(armor_losses),
            'max_missing_body_core_pixels':max(r['missing_body_core_pixels'] for r in rows),'max_lost_armor_core_pixels':max(r['lost_armor_core_pixels'] for r in rows),
            'max_new_enclosed_hole_pixels':max(r['new_enclosed_hole_pixels'] for r in rows),
            'largest_new_hole_pixels':max(r['largest_new_hole_pixels'] for r in rows)}
    (OUT/'coverage-validation.json').write_text(json.dumps(report,indent=2)+'\n')
    # Diagnostics for the views with the largest interior coverage loss.
    for index,(row,a,b,missing,armor) in enumerate(sorted(worst,key=lambda x:-(x[0]['missing_body_core_pixels']*10+x[0]['lost_armor_core_pixels']))[:12]):
        np.savez_compressed(OUT/f'coverage-diagnostic-{index:02d}.npz',before=a,after=b,missing=missing,armor=armor,description=json.dumps(row))
    print('COVERAGE COMPLETE',report['max_missing_body_core_pixels'],report['max_lost_armor_core_pixels'],dict(body_losses),dict(armor_losses),flush=True)

def quantized_coverage():
    scene,rig=task.proof_scene();reference,ref_rig=load_reference();obs=task.body(scene);refs=[o for o in task.body(reference) if o['source_component'] not in task.CULL]
    actions=actions_for(rig);ra=actions_for(ref_rig);rows=[]
    for arm in (rig,ref_rig):arm.animation_data.use_nla=False
    directions=[(math.sin(i*math.pi/4),-math.cos(i*math.pi/4),.12) for i in range(8)]+[(.7,-1,.65),(-.7,1,.65)]
    for clip,fraction in [('idle',.5),('run',.25),('run',.75),('fire',.5),('reload',.4),('reload',.8)]:
        f=actions[clip]['duration_seconds']*30*fraction
        bpy.context.window.scene=scene;rig.animation_data.action=actions[clip];scene.frame_set(int(f),subframe=f-int(f));a=mesh_data(scene,obs,True)
        bpy.context.window.scene=reference;ref_rig.animation_data.action=ra[clip];reference.frame_set(int(f),subframe=f-int(f));b=mesh_data(reference,refs,True)
        for vi,direction in enumerate(directions):
            after,_=raster(a,direction);before,_=raster(b,direction);holes,_=new_holes(before,after)
            rows.append({'clip':clip,'fraction':fraction,'view':vi,'new_enclosed_hole_pixels':int(holes.sum()),'largest_new_hole_pixels':largest_region(holes),'missing_body_core_pixels':int((erode(before>0,1)&(after==0)).sum())})
        print('QUANTIZED',clip,fraction,max(r['new_enclosed_hole_pixels'] for r in rows[-10:]),flush=True)
    report={'grid_m':animation.SCALE/128,'scope':'Both source and reduced posed body vertices rounded to the port Spartan position grid; six representative poses, ten views each. This is a geometry diagnostic, not runtime integration.',
            'max_new_enclosed_hole_pixels':max(r['new_enclosed_hole_pixels'] for r in rows),'largest_new_hole_pixels':max(r['largest_new_hole_pixels'] for r in rows),'views':rows}
    (OUT/'quantized-coverage-validation.json').write_text(json.dumps(report,indent=2)+'\n')

def hole_probe():
    scene,rig=task.proof_scene();reference,rr=load_reference();obs=task.body(scene);refs=[o for o in task.body(reference) if o['source_component'] not in task.CULL]
    for clip,fraction,direction in [('idle',0,(.7,-1,.65)),('run',.75,(-1,0,.12))]:
        for arm in (rig,rr):arm.animation_data.use_nla=False
        bpy.context.window.scene=scene;rig.animation_data.action=actions_for(rig)[clip];f=rig.animation_data.action['duration_seconds']*30*fraction;scene.frame_set(int(f),subframe=f-int(f));a=mesh_data(scene,obs)
        bpy.context.window.scene=reference;rr.animation_data.action=actions_for(rr)[clip];reference.frame_set(int(f),subframe=f-int(f));b=mesh_data(reference,refs)
        after,_=raster(a,direction);before,parts=raster(b,direction);holes,_=new_holes(before,after)
        print('HOLE PARTS',clip,Counter(b[-1][i-1] for i in parts[holes]),list(zip(*np.nonzero(holes))),flush=True)
        np.savez_compressed(OUT/('hole-probe-'+clip+'.npz'),before=before,after=after,holes=holes)

if __name__=='__main__':
    common.OUT=OUT;common.task=task;common.load_reference=load_reference
    if '--inventory' in sys.argv:inventory()
    if '--geometry' in sys.argv:geometry_motion()
    if '--roundtrip' in sys.argv:common.roundtrip()
    if '--coverage' in sys.argv:coverage()
    if '--quantized' in sys.argv:quantized_coverage()
    if '--hole-probe' in sys.argv:hole_probe()
