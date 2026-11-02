"""Bind accepted ODST authoring/decoder evidence to the production asset files."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
A=ROOT/'halo64-assets';F=A/'assets/odst-policy';G=A/'generated/odst'
STAGE=F/'helmet-budget';REVIEW=F/'review-helmet-budget'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run():
    for name in ('test_odst_runtime.py','test_odst_firstperson.py'):
        subprocess.run([sys.executable,str(ROOT/'port/n64'/name)],check=True)
    from audit_odst_helmet import check_helmet,check_packed
    data=json.loads((STAGE/'solid.json').read_text())
    symmetry=check_helmet(data,json.loads((F/'game-scale/solid.json').read_text()))
    symmetry['packed']=check_packed(data,G)
    assert symmetry==json.loads((REVIEW/'helmet-symmetry.json').read_text())
    surface=json.loads((REVIEW/'helmet-source-surface.json').read_text())
    assert len(surface)==2 and all(r['fitted']['sampled_p95_error_m']<.025 and r['mesh_sha256']==sha(STAGE/'solid.json') for r in surface)
    review_inputs=json.loads((REVIEW/'review-inputs.json').read_text())
    assert review_inputs['candidate_sha256']==sha(STAGE/'solid.json') and review_inputs['packed_report_sha256']==sha(G/'odst-report.json')
    assert review_inputs['baseline_report_sha256']==sha(F/'game-scale/packed-reference/odst-report.json')
    coverage=json.loads((REVIEW/'coverage.json').read_text())
    assert len(coverage)==128 and max(c['new_enclosed_pixels'] for c in coverage)==0
    clearance=json.loads((REVIEW/'armor-clearance.json').read_text())
    assert len(clearance)==96 and not any(c['broad_front_backing_in_front_pixels'] for c in clearance)
    rig=json.loads((STAGE/'library/rig-validation.json').read_text())
    assert all(c['samples']==454 and c['maximum_coordinate_error']<1e-5 for c in rig)
    exported=json.loads((STAGE/'library/export-validation.json').read_text())
    assert len(exported)==2 and all(len(l['clips'])==39 for l in exported)
    assert all(c['authored_key_samples']==5 and c['interpolated_samples']==5 and max(c['export_to_native_error_m'],c['native_to_export_error_m'])<1e-3 for l in exported for c in l['clips'])
    assert all(sha(STAGE/f"library/odst-{l['lod']}.glb")==l['sha256'] for l in exported)
    report=json.loads((G/'odst-report.json').read_text())
    assert sha(G/'odst.bin')==report['bank_sha256'] and sha(STAGE/'solid.json')==report['source_sha256']
    assert sha(F/'game-scale/solid.json')==data['helmet_parent_sha256']
    inputs=[ROOT/'port/n64'/n for n in ('asset_odst.h','odst_firstperson.h','pack_odst.py','pack_odst_firstperson.py','reduce_odst_game.py','repair_odst.py','odst_game_coverage_faces.json','audit_odst_clearance.py','odst_library.py','validate_odst_exports.py','review_odst.py','odst_helmet.py','refine_odst_helmet.py','audit_odst_helmet.py','odst_helmet_lods.py','odst_colors.py')]
    files=[*G.glob('*'),A/'frontend-files/odst.bin',STAGE/'solid.json',STAGE/'poses-0.npz',STAGE/'poses-1.npz',STAGE/'helmet-refinement.json',REVIEW/'coverage.json',REVIEW/'armor-clearance.json',REVIEW/'helmet-symmetry.json',REVIEW/'helmet-source-surface.json',REVIEW/'review-inputs.json',STAGE/'library/rig-validation.json',STAGE/'library/export-validation.json',F/'firstperson/firstperson-validation.json',F/'game-scale/solid.json',F/'game-scale/poses-0.npz',F/'game-scale/poses-1.npz',*(F/'game-scale/packed-reference').glob('*')]
    fingerprint=lambda ps:{str(p.relative_to(ROOT)):sha(p) for p in sorted(ps) if p.is_file() and p.name!='odst-validation.json'}
    result=dict(schema=1,inputs=fingerprint(inputs),files=fingerprint(files),bank_sha256=report['bank_sha256'],helmet_symmetry=symmetry,coverage_probes=128,new_enclosed_pixels=0,armor_clearance_probes=96,broad_front_backing_pixels=0,rig_samples_per_lod=454,glb_authored_key_samples=390,glb_clock_samples=390,c_decode_cases=4680,firstperson_pose_cases=1409)
    (G/'odst-validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: ODST assets and acceptance evidence certified')
if __name__=='__main__':run()
