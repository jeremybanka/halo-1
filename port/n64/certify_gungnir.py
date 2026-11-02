"""Bind GUNGNIR runtime/export evidence without conflating it with visual approval.

Development banks remain explicitly marked candidate until their independent
appearance review and native inspection have passed. A checksum certificate is
not permission to present an unfinished demake as an accepted release asset.
"""
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];A=ROOT/'halo64-assets';F=A/'assets/gungnir/demake-20261102';G=A/'generated/gungnir'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())

def run(output):
    output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():raise FileExistsError(output)
    candidate=F/'lods/solid.json';report=read(G/'gungnir-report.json');source=read(candidate);assert report['source_sha256']==sha(candidate) and report['bank_sha256']==sha(G/'gungnir.bin')==sha(A/'frontend-files/gungnir.bin')
    assert sha(F/'source/gungnir-original.json')==source['source_sha256']
    runtime=read(F/'review/runtime-validation.json');fp=read(F/'review/firstperson-validation.json');gameplay=read(F/'review/gameplay-validation.json');navigation=read(F/'review/navigation-validation.json')
    assert runtime['bank_sha256']==report['bank_sha256'] and runtime['metadata_sha256']==sha(G/'gungnir-report.json') and runtime['sanitizers_passed'] and runtime['decode_cases']==4680
    assert fp['source_binding_sha256']==sha(G/'gungnir_firstperson_data.c') and fp['runtime_sanitizers_passed'] and fp['total_pose_frames']==1409 and fp['weapon_colors_unchanged']
    assert read(F/'firstperson/firstperson-plates.json')['source_sha256']==sha(candidate)
    assert gameplay['sanitizers_passed'] and gameplay['manual_firing_while_autopilot'] and gameplay['maps']==13 and gameplay['log_sha256']==sha(F/'review/gameplay.log') and gameplay['test_sha256']==sha(ROOT/'port/n64/test_gungnir.c')
    assert navigation['gameplay_log_sha256']==sha(F/'review/gameplay.log') and len(navigation['maps'])==13
    for row in navigation['maps']:
        assert row['sha256']==sha(G/f'autonav-{row["map"]}.bin') and row['map_sha256']==sha(A/f'generated/maps/{row["name"]}.map64') and row['covered']==row['starts']
    for name,expected in navigation['inputs'].items():assert sha(ROOT/name)==expected,name
    library=read(F/'library/library-report.json');exports=read(F/'review/export-validation.json');assert len(library)==len(exports)==2
    for lod,(native,glb) in enumerate(zip(library,exports)):
        assert native['candidate_sha256']==glb['candidate_sha256']==sha(candidate) and native['max_blender_bake_error_m']<.0001
        assert glb['blend_sha256']==sha(F/'library/gungnir.blend') and glb['sha256']==sha(F/f'library/gungnir-{lod}.glb')==native['glb_sha256']
        assert glb['bones']==82 and glb['vertex_colors'] and glb['unlit_materials'] and len(glb['clips'])==39
        assert all(c['authored_key_samples']==5 and c['interpolated_samples']==5 and max(c['export_to_native_error_m'],c['native_to_export_error_m'])<.001 for c in glb['clips'])
    coverage=read(F/'review/coverage.json');packed=read(F/'review/packed-coverage.json');clearance=read(F/'review/clearance.json');shape=read(F/'review/shape-validation.json')
    assert all(r['candidate_sha256']==sha(candidate) for r in (coverage,packed,clearance,shape)) and coverage['samples']==packed['samples']==3744
    assert packed['packed_report_sha256']==sha(G/'gungnir-report.json')
    # Preserve observations, including failures. Only an actual review can
    # decide whether remaining projection changes are acceptable in context.
    appearance=F/'review/appearance-validation.json';native=F/'review/native-validation.json'
    accepted=all(p.is_file() and read(p).get('passed') and read(p).get('candidate_sha256')==sha(candidate) for p in (appearance,native))
    inputs=set(ROOT/'port/n64'/n for n in ('character.h','game.h','game.c','controls.h','controls.c','main.c','map.c','hud.c','scene.c','scene_flashlight.inc','frontend_draw.c','runtime_qa.c','combat_geometry.c','combat_geometry.h','camouflage.h','view_layout.h','prepare_gungnir_strategy.py','bake_autopilot_nav.c','demake_gungnir.py','refine_gungnir_contacts.py','fit_gungnir_surfaces.py','recess_gungnir_cloth.py','pack_gungnir.py','pack_gungnir_firstperson.py','gungnir_library.py','validate_gungnir_exports.py','audit_gungnir_clearance.py','review_gungnir.py','certify_gungnir.py','test_gungnir.c','test_gungnir_runtime.py','test_gungnir_firstperson.py'))
    inputs.update(ROOT/'port/n64'/n for n in ('build.py','frontend_qa.c','jorge_field_qa.h','test_maps.c','test_maps.py','test_build_defaults.py'))
    inputs.update((ROOT/'port/n64').glob('gungnir*.h'));inputs.update((ROOT/'port/n64').glob('gungnir*.c'));inputs.update((ROOT/'port/n64').glob('gungnir*.py'));inputs.update((ROOT/'port/n64').glob('gungnir*.inc'));inputs.update((ROOT/'port/n64').glob('autopilot*.[ch]'))
    inputs.update(ROOT/'source/ai'/n for n in ('actions.c','actor_type_elite.c','actor_type_grunt.c'))
    files=[p for p in F.rglob('*') if p.is_file()]+[p for p in G.iterdir() if p.is_file() and p.name!='gungnir-validation.json']+[A/'frontend-files/gungnir.bin',A/'generated/pve/pve_defs.c']
    fingerprint=lambda paths:{str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
    result=dict(schema=1,quality_state='accepted' if accepted else 'candidate: appearance and native inspection pending',publication_approved=bool(accepted),inputs=fingerprint(inputs),files=fingerprint(files),bank_sha256=report['bank_sha256'],packed_vertices=[r['vertices'] for r in report['lods']],triangles=[r['triangles'] for r in report['lods']],rig_comparisons=sum(r['skin_vertex_comparisons'] for r in library),glb_samples=780,c_decode_cases=4680,firstperson_pose_cases=1409,navigation_maximum_bytes=navigation['maximum_runtime_allocation_bytes'],appearance_observations=dict(body_coverage_probes=coverage['samples'],maximum_new_enclosed_pixels=coverage['maximum_new_enclosed_pixels'],packed_maximum_new_enclosed_pixels=packed['maximum_new_enclosed_pixels'],clearance_probes=clearance['samples'],maximum_new_broad_plate_occlusion_pixels=clearance['maximum_new_broad_plate_occlusion_pixels'],quantized_geometry=shape['geometry']))
    output.write_text(json.dumps(result,indent=2)+'\n');print('Certified integrity/runtime evidence;',result['quality_state'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True,help='Fresh guarded output; promote to generated/gungnir after verification');a=p.parse_args();run(a.output)
