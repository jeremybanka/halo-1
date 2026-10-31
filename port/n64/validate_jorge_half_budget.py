"""Validate separate budgets, geometry, skinning, runtime AR and GLB motion."""
import bpy,json,math,struct,hashlib,sys
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import jorge_half_budget as task
import jorge_animation_proof as animation
import validate_jorge_detail_pass as common
from validate_jorge_tactical import points
from validate_jorge_ce_materials import actions_for

OUT=task.OUT

def load_reference():
    with bpy.data.libraries.load(str(task.SOURCE),link=False) as (src,dst):dst.scenes=[n for n in src.scenes if n.startswith('Jorge - colors and surgical detail pass')]
    scene=dst.scenes[0];return scene,next(o for o in scene.objects if o.type=='ARMATURE')

def inventory():
    def read(name):
        raw=(OUT/name).read_bytes();size=struct.unpack_from('<I',raw,12)[0];return json.loads(raw[20:20+size]),len(raw)
    d,size=read(task.NAME+'.glb');prims=[p for m in d['meshes'] for p in m['primitives']];report={'body_vertices':sum(d['accessors'][p['attributes']['POSITION']]['count'] for p in prims),'body_triangles':sum(d['accessors'][p['indices']]['count']//3 for p in prims),'body_components':len(d['meshes']),'bones':len(d['skins'][0]['joints']),'materials':len(d['materials']),'images':len(d['images']),'animations':[a['name'] for a in d['animations']],'glb_bytes':size}
    assert report['body_components']==64 and report['body_triangles']<=2136 and report['bones']==85
    assert report['materials']==2 and report['images']==1 and len(report['animations'])==4
    component_report={r['component']:r for r in json.loads((OUT/'reduction-report.json').read_text())['components']}
    rows=[]
    for node in d['nodes']:
        if 'mesh' not in node:continue
        key=node['extras']['source_component'];ps=d['meshes'][node['mesh']]['primitives'];n=sum(d['accessors'][p['indices']]['count']//3 for p in ps)
        assert n==component_report[key]['actual_triangles'] and n<=task.BUDGETS[key]
        assert node['extras']['parent_triangle_count']==component_report[key]['source_triangles']
        rows.append({'component':key,'budget':task.BUDGETS[key],'exported_triangles':n,'exported_vertices':sum(d['accessors'][p['attributes']['POSITION']]['count'] for p in ps)})
    armed,_=read(task.NAME+'-with-rifle.glb');node=next(n for n in armed['nodes'] if n.get('extras',{}).get('n64_weapon')=='ar');ps=armed['meshes'][node['mesh']]['primitives']
    report['weapon']={'triangles':sum(armed['accessors'][p['indices']]['count']//3 for p in ps),'vertices':sum(armed['accessors'][p['attributes']['POSITION']]['count'] for p in ps),'unlit':all('KHR_materials_unlit' in armed['materials'][p['material']].get('extensions',{}) for p in ps)}
    assert report['weapon']['triangles']==140 and report['weapon']['unlit']
    blob=(OUT/(task.NAME+'-with-rifle.glb')).read_bytes();binary_start=28+struct.unpack_from('<I',blob,12)[0]
    def accessor(index):
        a=armed['accessors'][index];v=armed['bufferViews'][a['bufferView']];dims={'SCALAR':1,'VEC3':3,'VEC4':4}[a['type']];fmt={5121:'B',5123:'H',5125:'I',5126:'f'}[a['componentType']];width=struct.calcsize('<'+fmt*dims);stride=v.get('byteStride',width);start=binary_start+v.get('byteOffset',0)+a.get('byteOffset',0)
        values=np.array([struct.unpack_from('<'+fmt*dims,blob,start+i*stride) for i in range(a['count'])])
        if a.get('normalized'):values=values/({5121:255,5123:65535}[a['componentType']])
        return values
    raw_ar=json.loads(task.AR_SOURCE.read_text())['ar'];p=ps[0];indices=accessor(p['indices']).ravel().astype(int);positions=accessor(p['attributes']['POSITION'])[indices];colors=accessor(p['attributes']['COLOR_0'])[indices,:3]
    # glTF Y-up weapon coordinates equal the N64 packed axes, scaled to meters.
    error=float(np.linalg.norm(positions-np.array(raw_ar['positions'])*animation.SCALE,axis=1).max());srgb=np.where(colors<=.0031308,colors*12.92,1.055*np.power(np.maximum(colors,0),1/2.4)-.055);rgb_error=float(np.abs(srgb*255-np.array(raw_ar['colors'])).max())
    assert error<1e-6 and rgb_error<.5,(error,rgb_error)
    report['weapon'].update({'glb_to_runtime_position_error_m':error,'glb_rgb_max_channel_error_255':rgb_error,'glb_quantized_rgb_bytes_exact':True})
    report['components']=rows;(OUT/'export-inventory.json').write_text(json.dumps(report,indent=2)+'\n');print('EXPORT INVENTORY',{k:v for k,v in report.items() if k!='components'},flush=True)

def geometry_motion():
    scene,rig=task.proof_scene();reference,ref_rig=load_reference();objects=task.body(scene);refs={o['source_component']:o for o in task.body(reference)};actions=actions_for(rig);ra=actions_for(ref_rig);report={'components':[],'clips':{}};mapping={}
    reduction=json.loads((OUT/'reduction-report.json').read_text());assert hashlib.sha256(task.SOURCE.read_bytes()).hexdigest()==reduction['source_sha256'];report['parent_preserved']=True
    assert {o['source_component'] for o in objects}==set(refs)==set(task.BUDGETS)
    for a,b in zip(rig.data.bones,ref_rig.data.bones):assert a.name==b.name and a.matrix_local==b.matrix_local and (a.parent.name if a.parent else None)==(b.parent.name if b.parent else None)
    rig.data.pose_position='REST';ref_rig.data.pose_position='REST'
    for ob in objects:
        key=ob['source_component'];src=refs[key];me=ob.data;me.calc_loop_triangles();src.data.calc_loop_triangles();polys=[t.vertices[:] for t in me.loop_triangles];sp=[t.vertices[:] for t in src.data.loop_triangles]
        assert len(polys)<=task.BUDGETS[key] and len(polys)>0
        tree=BVHTree.FromPolygons([v.co for v in me.vertices],polys,all_triangles=True);st=BVHTree.FromPolygons([v.co for v in src.data.vertices],sp,all_triangles=True)
        distances=[tree.find_nearest(v.co)[3] for v in src.data.vertices]+[tree.find_nearest(sum((src.data.vertices[i].co for i in f),Vector())/3)[3] for f in sp]
        reverse=[st.find_nearest(sum((me.vertices[i].co for i in f),Vector())/3)[3] for f in polys];h=common.health(ob);assert not(h['zero_area_faces'] or h['loose_vertices'] or h['wire_edges'])
        assert all(.99<n.vector.length<1.01 for n in me.corner_normals);assert all(math.isfinite(x) and 0<=x<=1 for uv in me.uv_layers.active.data for x in uv.uv)
        bones={g.index for g in ob.vertex_groups if g.name in rig.data.bones};weight_error=0.;max_influences=0
        for v in me.vertices:
            weights=[g.weight for g in v.groups if g.group in bones and g.weight>0];weight_error=max(weight_error,abs(sum(weights)-1));max_influences=max(max_influences,len(weights))
        assert weight_error<1e-6 and max_influences<=4
        indices=np.array([sp[a.value] for a in me.attributes['lod_parent_triangle'].data]);bary=np.array([a.vector for a in me.attributes['lod_parent_barycentric'].data]);mapping[key]=(indices,bary)
        report['components'].append({'component':key,'budget':task.BUDGETS[key],'triangles':len(polys),'source_to_reduced_max_m':max(distances),'source_to_reduced_p95_m':float(np.percentile(distances,95)),'source_to_reduced_mean_m':float(np.mean(distances)),'reduced_centers_to_source_max_m':max(reverse),'max_weight_sum_error':weight_error,'max_influences':max_influences,**h})
    rig.data.pose_position='POSE';ref_rig.data.pose_position='POSE';rig.animation_data.use_nla=False;ref_rig.animation_data.use_nla=False
    for name in animation.CLIPS:
        samples=round(actions[name]['duration_seconds']*30)+1;errors=[];minimum_z=100;pose_error=0.
        for frame in range(samples):
            bpy.context.window.scene=scene;rig.animation_data.action=actions[name];scene.frame_set(frame);a=points(scene,objects);pa=np.array([b.matrix for b in rig.pose.bones])
            bpy.context.window.scene=reference;ref_rig.animation_data.action=ra[name];reference.frame_set(frame);b=points(reference,list(refs.values()));pb=np.array([b.matrix for b in ref_rig.pose.bones]);pose_error=max(pose_error,float(np.abs(pa-pb).max()))
            for key,p in a.items():
                ids,bary=mapping[key];expected=(b[key][ids]*bary[:,:,None]).sum(axis=1);assert np.isfinite(p).all();errors.extend(np.linalg.norm(p-expected,axis=1).tolist());minimum_z=min(minimum_z,float(p[:,2].min()))
        assert pose_error==0
        report['clips'][name]={'samples':samples,'bone_pose_change':pose_error,'surface_correspondence_max_m':max(errors),'surface_correspondence_p95_m':float(np.percentile(errors,95)),'minimum_z_m':minimum_z};print('MOTION',name,report['clips'][name],flush=True)
    report['metric_note']='Correspondence errors include intended rest-surface approximation; GLB round-trip is validated separately.'
    weapon=next(o for o in scene.objects if o.get('n64_weapon')=='ar');raw=json.loads(task.AR_SOURCE.read_text())['ar'];maximum=rgb_error=0.
    for face in weapon.data.polygons:
        for corner,li in enumerate(face.loop_indices):
            p=raw['positions'][face.index*3+corner];expected=Vector((p[0],-p[2],p[1]))*animation.SCALE;actual=weapon.data.vertices[weapon.data.loops[li].vertex_index].co;maximum=max(maximum,(actual-expected).length)
            rgb=weapon.data.color_attributes['N64 packed RGB'].data[li].color_srgb[:3];rgb_error=max(rgb_error,max(abs(rgb[i]*255-raw['colors'][face.index*3+corner][i]) for i in range(3)))
    # Blender's float sRGB conversion is approximate. Require exactly the same
    # quantized RGB bytes; sub-byte conversion error does not alter port colors.
    assert maximum<1e-6 and rgb_error<.5,(maximum,rgb_error)
    assert hashlib.sha256(task.AR_SOURCE.read_bytes()).hexdigest()==reduction['weapon']['sha256']
    report['port_ar']={'triangles':len(weapon.data.polygons),'packed_position_max_error_m':maximum,'packed_rgb_max_channel_error_255':rgb_error,'quantized_rgb_bytes_exact':True,'source_unchanged':True};(OUT/'geometry-motion-validation.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':
    common.OUT=OUT;common.task=task;common.load_reference=load_reference
    if '--inventory' in sys.argv:inventory()
    if '--geometry' in sys.argv:geometry_motion()
    if '--roundtrip' in sys.argv:common.roundtrip()
    if '--silhouettes' in sys.argv:common.silhouettes()
