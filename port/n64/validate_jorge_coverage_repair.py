"""Preservation, garment closure, animation and export checks for local repairs."""
import bpy,json,sys,hashlib,math,struct
import numpy as np
import jorge_coverage_repair as task
import jorge_solid_reduce as solid
import validate_jorge_solid as coverage
import validate_jorge_detail_pass as common
from validate_jorge_ce_materials import actions_for
from validate_jorge_tactical import points

OUT=task.OUT

def load(path,prefix):
    with bpy.data.libraries.load(str(path),link=False) as (src,dst):dst.scenes=[n for n in src.scenes if n.startswith(prefix)]
    s=dst.scenes[0];return s,next(o for o in s.objects if o.type=='ARMATURE')

def inventory():
    raw=(OUT/(task.NAME+'.glb')).read_bytes();n=struct.unpack_from('<I',raw,12)[0];d=json.loads(raw[20:20+n]);rows=[]
    for node in d['nodes']:
        if 'mesh' not in node:continue
        ps=d['meshes'][node['mesh']]['primitives']
        rows.append({'component':node['extras']['source_component'],'exported_vertices':sum(d['accessors'][p['attributes']['POSITION']]['count'] for p in ps),'triangles':sum(d['accessors'][p['indices']]['count']//3 for p in ps)})
    report={'body_vertices':sum(r['exported_vertices'] for r in rows),'body_triangles':sum(r['triangles'] for r in rows),'body_components':len(rows),
            'bones':len(d['skins'][0]['joints']),'animations':[a['name'] for a in d['animations']],'materials':len(d['materials']),'images':len(d['images']),'components':rows}
    build=json.loads((OUT/'repair-report.json').read_text())
    assert report['body_vertices']==build['predicted_export_vertices'] and report['body_triangles']==build['actual_triangles']
    assert report['body_components']==59 and report['bones']==85 and len(report['animations'])==4 and report['materials']==2 and report['images']==1
    (OUT/'export-inventory.json').write_text(json.dumps(report,indent=2)+'\n');print('INVENTORY',{k:v for k,v in report.items() if k!='components'},flush=True)

def geometry_motion():
    scene,rig=task.proof_scene();ref,rr=load(task.SOURCE,solid.SCENE);obs=task.body(scene);refs={o['source_component']:o for o in task.body(ref)}
    build=json.loads((OUT/'repair-report.json').read_text());assert hashlib.sha256(task.SOURCE.read_bytes()).hexdigest()==build['source_sha256']
    rows={r['component']:r for r in build['components']};result={'source_preserved':True,'components':[],'clips':{}}
    assert set(refs)=={o['source_component'] for o in obs}
    for a,b in zip(rig.data.bones,rr.data.bones):
        assert a.name==b.name and a.matrix_local==b.matrix_local and (a.parent.name if a.parent else None)==(b.parent.name if b.parent else None)
    wa=next(o for o in scene.objects if o.name.startswith('CE rifle'));wb=next(o for o in ref.objects if o.name.startswith('CE rifle'))
    assert wa.parent_bone==wb.parent_bone and wa.matrix_basis==wb.matrix_basis
    assert [tuple(v.co) for v in wa.data.vertices]==[tuple(v.co) for v in wb.data.vertices]
    assert [tuple(p.vertices) for p in wa.data.polygons]==[tuple(p.vertices) for p in wb.data.polygons]
    for a,b in zip(wa.data.color_attributes,wb.data.color_attributes):
        assert a.domain==b.domain and [tuple(v.color) for v in a.data]==[tuple(v.color) for v in b.data]
    result['port_ar_geometry_colors_attachment_unchanged']=True
    for ob in obs:
        key=ob['source_component'];src=refs[key];a=ob.data;b=src.data;h=common.health(ob);oldh=common.health(src)
        assert not(h['zero_area_faces'] or h['loose_vertices'] or h['wire_edges'])
        assert h['nonmanifold_internal_edges']<=oldh['nonmanifold_internal_edges']
        if key in ('body-10:001','body-10:002','body-10:003'):assert h['boundary_edges']==0
        if key=='body-10:000':assert h['boundary_edges']==12
        assert [tuple(p.vertices) for p in a.polygons[:len(b.polygons)]]==[tuple(p.vertices) for p in b.polygons]
        assert len(a.materials)==len(b.materials)==1 and all(p.material_index==0 for p in a.polygons)
        assert all(math.isfinite(x) and 0<=x<=1 for u in a.uv_layers.active.data for x in u.uv)
        assert all(.99<n.vector.length<1.01 for n in a.corner_normals)
        changed={v['vertex']:v for c in rows[key]['changes'] for v in c.get('vertices',[])}
        def weights(o,v):return {o.vertex_groups[g.group].name:g.weight for g in v.groups}
        for v,w in zip(a.vertices,b.vertices):
            assert weights(ob,v)==weights(src,w)
            if v.index not in changed:assert v.co==w.co
            else:
                assert np.linalg.norm(np.array(w.co)-np.array(changed[v.index]['before']))<1e-7
                assert np.linalg.norm(np.array(v.co)-np.array(changed[v.index]['after']))<1e-7
        for u,v in zip(a.uv_layers.active.data,b.uv_layers.active.data):assert u.uv==v.uv
        # Blender re-encodes custom normals relative to the new face fan.
        # Permit <0.3 degree on edited meshes; untouched meshes remain exact.
        normal_error=max((n.vector-m.vector).length for n,m in zip(a.corner_normals,b.corner_normals))
        assert normal_error<(2*math.sin(math.radians(.3)/2) if rows[key]['changes'] else 1e-7),(key,normal_error)
        for v in a.vertices:
            ws=weights(ob,v);assert len(ws)<=4 and abs(sum(ws.values())-1)<1e-6
        result['components'].append({'component':key,'native_vertices_added':len(a.vertices)-len(b.vertices),'triangles_added':len(a.polygons)-len(b.polygons),
                                     'boundary_edges_before':oldh['boundary_edges'],'boundary_edges_after':h['boundary_edges'],'normal_roundtrip_error':normal_error,**h})
    ar=actions_for(rig);br=actions_for(rr)
    for arm in (rig,rr):arm.data.pose_position='POSE';arm.animation_data.use_nla=False
    unchanged=[o for o in obs if not rows[o['source_component']]['changes']]
    added={o['source_component']:np.array([tuple(p.vertices) for p in o.data.polygons[len(refs[o['source_component']].data.polygons):]],dtype=int) for o in obs}
    for clip in task.animation.CLIPS:
        samples=round(ar[clip]['duration_seconds']*30)+1;pose_error=surface_error=0.;minimum_added_area=1e9;seam_min=1e9;seam_max=0.
        for f in range(samples):
            bpy.context.window.scene=scene;rig.animation_data.action=ar[clip];scene.frame_set(f);a=points(scene,obs);pa=np.array([b.matrix for b in rig.pose.bones])
            bpy.context.window.scene=ref;rr.animation_data.action=br[clip];ref.frame_set(f);b=points(ref,[refs[o['source_component']] for o in unchanged]);pb=np.array([b.matrix for b in rr.pose.bones])
            pose_error=max(pose_error,float(np.abs(pa-pb).max()))
            for key in b:surface_error=max(surface_error,float(np.linalg.norm(a[key]-b[key],axis=1).max()))
            assert all(np.isfinite(p).all() for p in a.values())
            gap=float(np.linalg.norm(a['body-09:004'][-1]-a['body-10:000'][44]));seam_min=min(seam_min,gap);seam_max=max(seam_max,gap)
            for key,tris in added.items():
                if len(tris):
                    p=a[key][tris];minimum_added_area=min(minimum_added_area,float((np.linalg.norm(np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]),axis=1)/2).min()))
        assert pose_error==0 and surface_error==0
        assert minimum_added_area>1e-10
        assert seam_max-seam_min<1e-6 and seam_max<.0146
        result['clips'][clip]={'samples':samples,'bone_pose_change':pose_error,'untouched_component_motion_change_m':surface_error,'minimum_added_triangle_area_m2':minimum_added_area,'rump_seam_overlap_offset_m':[seam_min,seam_max]};print('MOTION',clip,result['clips'][clip],flush=True)
    (OUT/'geometry-motion-validation.json').write_text(json.dumps(result,indent=2)+'\n')

def repair_coverage():
    """Check that local repairs introduce no new enclosed gaps versus input."""
    s,r=task.proof_scene();ref,rr=load(task.SOURCE,solid.SCENE);rows=[]
    directions=[(math.sin(i*math.pi/4),-math.cos(i*math.pi/4),.12) for i in range(8)]+[(.7,-1,.65),(-.7,1,.65)]
    for clip,fraction in [('idle',0),('idle',.5),('run',.25),('run',.75),('fire',.5),('reload',.4),('reload',.8)]:
        for sc,arm in [(s,r),(ref,rr)]:
            bpy.context.window.scene=sc;arm.animation_data.use_nla=False;arm.animation_data.action=actions_for(arm)[clip]
            f=arm.animation_data.action['duration_seconds']*30*fraction;sc.frame_set(int(f),subframe=f-int(f))
        a=coverage.mesh_data(ref,task.body(ref));b=coverage.mesh_data(s,task.body(s))
        for vi,d in enumerate(directions):
            before,_=coverage.raster(a,d);after,_=coverage.raster(b,d);holes,_=coverage.new_holes(before,after)
            filled=coverage.enclosed_background(before>0)&(after>0)
            rows.append({'clip':clip,'fraction':fraction,'view':vi,'new_enclosed_hole_pixels':int(holes.sum()),'enclosed_background_pixels_filled':int(filled.sum())})
        print('REPAIR COVERAGE',clip,fraction,flush=True)
    result={'reference':'accepted solid-2000 checkpoint','resolution':[256,320],'samples':len(rows),
            'max_new_enclosed_hole_pixels':max(r['new_enclosed_hole_pixels'] for r in rows),
            'total_enclosed_background_pixels_filled':sum(r['enclosed_background_pixels_filled'] for r in rows),'views':rows}
    (OUT/'repair-coverage-validation.json').write_text(json.dumps(result,indent=2)+'\n')
    assert result['max_new_enclosed_hole_pixels']==0,result

if __name__=='__main__':
    if '--inventory' in sys.argv:inventory()
    if '--geometry' in sys.argv:geometry_motion()
    if '--roundtrip' in sys.argv:common.OUT=OUT;common.task=task;common.roundtrip()
    if '--repair-coverage' in sys.argv:repair_coverage()
    if '--coverage' in sys.argv or '--quantized' in sys.argv:
        coverage.OUT=OUT;coverage.task=task;task.CULL=solid.CULL
        coverage.load_reference=lambda:load(solid.SOURCE,solid.source_stage.SCENE)
        if '--coverage' in sys.argv:coverage.coverage()
        if '--quantized' in sys.argv:coverage.quantized_coverage()
