"""Coverage, component topology and preserved rig checks for playable Jorge."""
import bpy,json,sys,math,hashlib
import numpy as np
import jorge_playable_reduce as task
import validate_jorge_solid as coverage
import jorge_solid_reduce as solid
from validate_jorge_ce_materials import actions_for
from validate_jorge_coverage_repair import load
OUT=task.OUT

def run():
    scene,rig=task.proof_scene();ref,rr=load(task.SOURCE,task.parent.SCENE);rows=[];patches={};game_rows=[];game_patches={}
    report=json.loads((OUT/'reduction-report.json').read_text());assert hashlib.sha256(task.SOURCE.read_bytes()).hexdigest()==report['source_sha256']
    obs=task.body(scene);refs={o['source_component']:o for o in task.body(ref)}
    health=[]
    for o in obs:
        h=solid.topology(o);old=solid.topology(refs[o['source_component']]);assert not(h['zero_area_faces'] or h['wire_edges'] or h['loose_vertices']);assert h['nonmanifold_internal_edges']<=old['nonmanifold_internal_edges']
        original=refs[o['source_component']].copy();original.data=original.data.copy();ref.collection.objects.link(original)
        task.simplify_rim(original);solid.prepare(original);prepared=solid.topology(original)
        if any(x['component']==o['source_component'] for x in report.get('source_seam_backings',[])):pass
        elif not any(x['component']==o['source_component'] for x in report.get('shell_backings',[])):assert h['euler']==prepared['euler'],o.name
        else:assert h['boundary_edges']<=prepared['boundary_edges'] and h['nonmanifold_internal_edges']<=prepared['nonmanifold_internal_edges'],o.name
        bpy.data.objects.remove(original,do_unlink=True)
        for v in o.data.vertices:assert abs(sum(g.weight for g in v.groups)-1)<1e-5
        health.append({'component':o['source_component'],**{k:v for k,v in h.items() if k!='boundary_coordinates'}})
    directions=[(math.sin(i*math.pi/4),-math.cos(i*math.pi/4),.12) for i in range(8)]+[(.7,-1,.65),(-.7,1,.65)]
    bone_error=0
    for clip,fraction in [('idle',0),('idle',.5),('run',.25),('run',.75),('fire',.5),('reload',.4),('reload',.8)]:
        matrices=[]
        for sc,arm in [(scene,rig),(ref,rr)]:
            bpy.context.window.scene=sc;arm.animation_data.use_nla=False;arm.animation_data.action=actions_for(arm)[clip]
            f=arm.animation_data.action['duration_seconds']*30*fraction;sc.frame_set(int(f),subframe=f-int(f));matrices.append(np.array([b.matrix for b in arm.pose.bones]))
        bone_error=max(bone_error,float(abs(matrices[0]-matrices[1]).max()))
        a=coverage.mesh_data(ref,task.body(ref));b=coverage.mesh_data(scene,obs)
        for vi,d in enumerate(directions):
            before,parts=coverage.raster(a,d);after,_=coverage.raster(b,d);holes,_=coverage.new_holes(before,after)
            if holes.any():
                _,face_ids=coverage.raster((a[0],a[1],a[2],np.arange(len(a[1]))+1,a[4]),d)
                for fi in np.unique(face_ids[holes])-1:
                    key=a[4][a[3][fi]-1];local=int((a[3][:fi]==a[3][fi]).sum());patches.setdefault(key,set()).add(local)
                print("HOLES",clip,fraction,vi,[(a[-1][i-1],int(((parts==i)&holes).sum())) for i in np.unique(parts[holes]) if i],flush=True)
                np.savez_compressed(OUT/f"coverage-{clip}-{fraction}-{vi}.npz",before=before,after=after,holes=holes)
            rows.append({'clip':clip,'fraction':fraction,'view':vi,'new_enclosed_hole_pixels':int(holes.sum()),'silhouette_iou':float(((before>0)&(after>0)).sum()/((before>0)|(after>0)).sum())})
        aq=coverage.mesh_data(ref,task.body(ref));bq=coverage.mesh_data(scene,obs)
        grid=3.048/512
        aq=(np.round(aq[0]/grid)*grid,*aq[1:]);bq=(np.round(bq[0]/grid)*grid,*bq[1:])
        for vi,direction in enumerate(directions):
            for height in (64,96):
                before,_=coverage.raster(aq,direction,width=height,height=height);after,_=coverage.raster(bq,direction,width=height,height=height);holes,_=coverage.new_holes(before,after)
                if holes.any():
                    _,face_ids=coverage.raster((aq[0],aq[1],aq[2],np.arange(len(aq[1]))+1,aq[4]),direction,width=height,height=height)
                    for fi in np.unique(face_ids[holes])-1:
                        key=aq[4][aq[3][fi]-1];local=int((aq[3][:fi]==aq[3][fi]).sum());game_patches.setdefault(key,set()).add(local)
                game_rows.append({'clip':clip,'fraction':fraction,'view':vi,'height':height,'new_enclosed_hole_pixels':int(holes.sum())})
        print('COVERAGE',clip,fraction,flush=True)
    (OUT/'gap-source-faces.json').write_text(json.dumps({k:sorted(v) for k,v in patches.items()},indent=2)+'\n')
    (OUT/'game-gap-source-faces.json').write_text(json.dumps({k:sorted(v) for k,v in game_patches.items()},indent=2)+'\n')
    print('GAME PATCHES',{k:sorted(v) for k,v in game_patches.items()},flush=True)
    print('PATCH FACE COUNT',sum(map(len,patches.values())),flush=True)
    assert bone_error==0
    result={'source_preserved':True,'bone_pose_change':bone_error,'vertices':report['vertices'],'triangles':report['triangles'],'samples':len(rows),'resolution':[256,320],'max_new_enclosed_hole_pixels':max(r['new_enclosed_hole_pixels'] for r in rows),'minimum_silhouette_iou':min(r['silhouette_iou'] for r in rows),'views':rows,'game_scale_views':game_rows,'game_scale_max_new_holes':max(r['new_enclosed_hole_pixels'] for r in game_rows),'health':health}
    (OUT/'coverage-validation.json').write_text(json.dumps(result,indent=2)+'\n');print('RESULT', {k:v for k,v in result.items() if k not in ('views','health','game_scale_views')},flush=True)
if __name__=='__main__':run()
