"""Audit shared-motion reuse and record the next Jorge reduction milestone.

This does not retarget animation or modify the accepted mesh. The mapping is an
explicit correspondence proposal for the animation proof, not a validated rig.
"""
from pathlib import Path
import json,hashlib

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'halo64-assets/assets/jorge/animation-preflight'

def main():
    source=ROOT/'halo64-assets/assets/extended-raw.json'
    cleaned=ROOT/'halo64-assets/assets/jorge/full-cleanup/jorge-cleaned.json'
    ce=json.loads(source.read_text());jorge=json.loads(cleaned.read_text())
    core={'pelvis':'pelvis','spine':'spine1','spine1':'spine3','neck':'neck0','head':'head'}
    for side in ('l','r'):
        for ce_name,reach_name in [('thigh','thigh'),('calf','calf'),('foot','foot'),('clavicle','clav'),('upperarm','upperarm'),('forearm','forearm'),('hand','hand')]:
            core[f'{side} {ce_name}']=f'{side}_{reach_name}'
    target_names={n['name'] for n in jorge['nodes']};direct=[]
    for i,n in enumerate(ce['models']['spartan']['nodes']):
        name='b_'+core[n['name'].removeprefix('bip01 ')]
        assert name in target_names
        direct.append({'ce_index':i,'ce_bone':n['name'],'reach_bone':name,'status':'correspondence only; bind axes and motion not yet validated'})
    assert len(direct)==19 and len({r['reach_bone'] for r in direct})==19
    driven={r['reach_bone'] for r in direct};extras=[]
    for n in jorge['nodes']:
        if n['name'] in driven:continue
        name=n['name'];policy='inherit parent motion while retaining authored bind offset; inspect'
        if 'fixup' in name or 'jiggle' in name:policy='explicit correction/twist review required; do not assume runtime Reach controllers exist'
        elif any(part in name for part in ('thumb','index','middle','ring','pinky')):policy='retain authored finger chain; establish a weapon grip pose because CE has no finger channels'
        elif name=='b_spine2':policy='distribute torso bend between the two shared spine channels without changing Jorge proportions'
        elif name=='b_neck1':policy='distribute neck/head motion and check collar clearance'
        elif name=='b_pedestal':policy='separate world/root motion from pelvis motion; avoid applying locomotion twice'
        elif name in ('b_backpack','b_neckguard'):policy='rigid authored offset on torso; validate shoulder and weapon clearance'
        elif 'shoulderpad' in name:policy='upper-arm/clavicle motion review for bulky asymmetric shoulder clearance'
        extras.append({'reach_bone':name,'parent':jorge['nodes'][n['parent']]['name'] if n['parent']>=0 else None,'proposed_policy':policy})
    def height(model):return max(v[2] for v in model['vertices'])-min(v[2] for v in model['vertices'])
    budget=[('Helmet and visor',110),('Torso and pelvis',110),('Shoulders',100),('Arms and hands',90),('Legs and boots',150),('Backpack',90),('Visible undersuit and joints',50)]
    assert sum(n for _,n in budget)==700
    report={
        'status':'Preflight complete; animation retarget and reduction not implemented in this step',
        'source_sha256':{'ce':hashlib.sha256(source.read_bytes()).hexdigest(),'jorge_cleaned':hashlib.sha256(cleaned.read_bytes()).hexdigest()},
        'current_triangles':len(jorge['faces']),'eventual_target_triangles':700,'current_components':len(set(jorge['component_ids'])),
        'reach_bones':len(jorge['nodes']),'ce_bones':len(ce['models']['spartan']['nodes']),
        'clips':{name:{'type':clip['type'],'frames':len(clip['frames']),'duration_seconds':clip['duration']} for name,clip in ce['animations'].items()},
        'raw_source_frames':sum(len(c['frames']) for c in ce['animations'].values()),
        'bind_mesh_height_ratio_jorge_to_ce':height(jorge)/height(ce['models']['spartan']),
        'core_correspondence':direct,'extra_bone_review':extras,
        'next_milestone':{
            'name':'Shared-animation proof on the accepted full-detail baseline',
            'first_clips':['idle','run','fire','reload'],
            'checks':['Align bind-pose axes without silently reshaping Jorge to CE proportions','Compose fire overlay against idle using the existing CE convention','Verify feet, elbows, asymmetric shoulders and backpack through motion','Derive the weapon socket from the retargeted hand; verify support-hand contact','Preserve clip names, durations and runtime sampling contract','Validate remaining seven clips before motion-based deletion'],
            'runtime_path':'Retarget offline and bake Jorge vertex trajectories into the existing animation ABI. The authoring rig need not be forced to 19 bones.',
            'preview_requirement':'Include the current character vertex-color rendering path; Blender normal-map detail is not used by the existing N64 character packer.'},
        'following_reduction_steps':['Build per-component visibility and silhouette evidence across shared clips and viewpoints','Cull confidently occluded backing geometry with joint/pose margins','Consolidate adjacent parts that share motion, preserving major original plate contours','Reduce bevel strips and secondary layer interfaces; soften unnecessary candidate locks','Trial intermediate budgets around 5000, 2500 and 1000 before approximately 700'],
        'provisional_700_allocation':[{'region':name,'triangles':n} for name,n in budget],
        'allocation_status':'Planning envelope only; not measured per-region feasibility or a requirement to hit each number',
        'evidence_files':['port/n64/rig_odst.py','port/n64/extract_odst.py','port/n64/reduce_extended.py','port/n64/pack_odst.py','port/n64/asset_models.h']}
    OUT.mkdir(exist_ok=True);(OUT/'rig-and-reduction-plan.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'current_triangles':report['current_triangles'],'core_correspondences':len(direct),'extra_bones_to_review':len(extras),'clips':list(report['clips']),'source_frames':report['raw_source_frames'],'height_ratio':report['bind_mesh_height_ratio_jorge_to_ce'],'target':700},indent=2))

if __name__=='__main__':main()
