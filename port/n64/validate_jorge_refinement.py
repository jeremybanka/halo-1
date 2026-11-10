"""Check symmetry, source preservation, colors, rigging and coverage after polish."""
import bpy,json,hashlib,math,struct,csv
import numpy as np
from mathutils.kdtree import KDTree
import refine_jorge as refinement
import validate_jorge_solid as coverage
import jorge_solid_reduce as solid
from validate_jorge_coverage_repair import load
from validate_jorge_ce_materials import actions_for

refinement.configure();task=refinement.task;OUT=refinement.OUT
def run():
    scene,rig=task.proof_scene();ref,rr=load(refinement.SOURCE,'Jorge - playable half budget')
    report=json.loads((OUT/'refinement-report.json').read_text());assert hashlib.sha256(refinement.SOURCE.read_bytes()).hexdigest()==report['source_sha256']
    obs=task.body(scene);refs={o['source_component']:o for o in task.body(ref)}
    health=[];symmetry=[];changed={r['component'] for r in report['changes']}
    for o in obs:
        key=o['source_component'];h=solid.topology(o);old=solid.topology(refs[key])
        assert not(h['zero_area_faces'] or h['loose_vertices'] or h['wire_edges']),(key,h)
        assert h['nonmanifold_internal_edges']<=old['nonmanifold_internal_edges'],(key,h['nonmanifold_internal_edges'],old['nonmanifold_internal_edges'])
        assert all(abs(sum(g.weight for g in v.groups)-1)<1e-5 for v in o.data.vertices),key
        assert all(.99<n.vector.length<1.01 for n in o.data.corner_normals),key
        if key in changed:
            tree=KDTree(len(o.data.vertices))
            for v in o.data.vertices:tree.insert(v.co,v.index)
            tree.balance();error=max(tree.find((-v.co.x,v.co.y,v.co.z))[2] for v in o.data.vertices)
            assert error<1e-6,(key,error);symmetry.append({'component':key,'maximum_mirror_error_m':error})
        assert all(0<=v<=1 for c in o.data.color_attributes[refinement.COLOR].data for v in c.color_srgb)
        health.append({'component':key,**{k:v for k,v in h.items() if k!='boundary_coordinates'}})
    # All original bones, rest transforms and gameplay animations are retained.
    assert len(rig.data.bones)==len(rr.data.bones)==85
    for a,b in zip(rig.data.bones,rr.data.bones):assert a.name==b.name and a.matrix_local==b.matrix_local
    actions=actions_for(rig);oldactions=actions_for(rr)
    dirs=[(math.sin(i*math.pi/4),-math.cos(i*math.pi/4),.12) for i in range(8)]+[(.7,-1,.65),(-.7,1,.65)]
    rows=[];patches={};bone_error=0
    for name,fraction in [('idle',0),('idle',.5),('run',.25),('run',.75),('fire',.5),('reload',.4),('reload',.8)]:
        matrices=[]
        for s,r,acts in ((scene,rig,actions),(ref,rr,oldactions)):
            bpy.context.window.scene=s;r.animation_data.use_nla=False;r.animation_data.action=acts[name]
            f=r.animation_data.action['duration_seconds']*30*fraction;s.frame_set(int(f),subframe=f-int(f))
            matrices.append(np.array([b.matrix for b in r.pose.bones]))
        bone_error=max(bone_error,float(abs(matrices[0]-matrices[1]).max()))
        a=coverage.mesh_data(ref,task.body(ref));b=coverage.mesh_data(scene,obs);grid=3.048/512
        a=(np.round(a[0]/grid)*grid,*a[1:]);b=(np.round(b[0]/grid)*grid,*b[1:])
        for vi,d in enumerate(dirs):
            for height in (64,96):
                before,_=coverage.raster(a,d,width=height,height=height);after,_=coverage.raster(b,d,width=height,height=height);holes,_=coverage.new_holes(before,after)
                if holes.any():
                    _,ids=coverage.raster((a[0],a[1],a[2],np.arange(len(a[1]))+1,a[4]),d,width=height,height=height)
                    for fi in np.unique(ids[holes])-1:
                        key=a[4][a[3][fi]-1];local=int((a[3][:fi]==a[3][fi]).sum());patches.setdefault(key,set()).add(local)
                rows.append({'clip':name,'fraction':fraction,'view':vi,'height':height,'new_hole_pixels':int(holes.sum()),'silhouette_iou':float(((before>0)&(after>0)).sum()/((before>0)|(after>0)).sum())})
        print('COVERAGE',name,fraction,flush=True)
    assert bone_error==0
    result={'source_preserved':True,'bone_pose_change':bone_error,'symmetry':symmetry,'health':health,'views':rows,'maximum_new_hole_pixels':max(r['new_hole_pixels'] for r in rows),'source_faces_at_new_gaps':{k:sorted(v) for k,v in patches.items()}}
    (OUT/'refinement-validation.json').write_text(json.dumps(result,indent=2)+'\n')
    raw=(OUT/(refinement.NAME+'.glb')).read_bytes();gltf=json.loads(raw[20:20+struct.unpack_from('<I',raw,12)[0]]);inventory=[]
    for node in gltf['nodes']:
        if 'mesh' not in node:continue
        ps=gltf['meshes'][node['mesh']]['primitives'];assert all('COLOR_0' in p['attributes'] for p in ps)
        inventory.append({'component':node['extras']['source_component'],'vertices':sum(gltf['accessors'][p['attributes']['POSITION']]['count'] for p in ps),'triangles':sum(gltf['accessors'][p['indices']]['count']//3 for p in ps)})
    counts={'vertices':sum(r['vertices'] for r in inventory),'triangles':sum(r['triangles'] for r in inventory),'bones':len(gltf['skins'][0]['joints']),'clips':len(gltf['animations']),'components':inventory,'materials':len(gltf['materials']),'all_components_have_vertex_colors':True}
    assert counts['bones']==85 and counts['clips']==39 and len(inventory)==49
    (OUT/'export-inventory.json').write_text(json.dumps(counts,indent=2)+'\n')
    with (OUT/'component-budgets.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=['component','vertices','triangles'],lineterminator='\n');w.writeheader();w.writerows(inventory)
    print('COUNTS',{k:v for k,v in counts.items() if k!='components'},flush=True)
    print('GAPS',result['maximum_new_hole_pixels'],result['source_faces_at_new_gaps'],flush=True)
if __name__=='__main__':run()
