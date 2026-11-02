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
    damage=read(F/'review/damage-validation.json')
    assert damage['passed'] and damage['sanitizers_passed'] and damage['cases']==48 and damage['hud_sha256']==sha(ROOT/'port/n64/hud.c')
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
    rear=read(F/'review/rear-armor-validation.json')
    rear_rows=[r for r in clearance['rows'] if r['region']=='back']
    assert rear['passed'] and rear['candidate_sha256']==sha(candidate) and len(rear_rows)==24
    assert rear['clearance_sha256']==sha(F/'review/clearance.json')
    assert max(r['fraction'] for r in rear_rows)<.06, 'Rear armor again loses a broad area to backing'
    shells=read(F/'review/shell-validation.json')
    assert shells['passed'] and shells['candidate_sha256']==sha(candidate)
    assert len(shells['views'])==6 and all(r['coverage_fraction']>=.90 for r in shells['views'])
    optic=read(F/'review/optic-validation.json')
    assert optic['passed'] and optic['candidate_sha256']==sha(candidate)
    assert len(optic['lods'])==2
    for row in optic['lods']:
        assert row['helmet_shell_geometry_unchanged'] and row['closed_convex_shell'] and row['source_art_uv_unchanged'] and row['source_uv_stains_removed']
        assert row['flat_topped_hex_corners']==6 and row['quantized_pose_samples']==454 and row['quantized_optic_degenerate_triangles']==0
    codpiece=[r for r in clearance['rows'] if r['region']=='codpiece']
    assert len(codpiece)==24 and max(r['new_broad_plate_occlusion_pixels'] for r in codpiece)<=3
    faces=read(F/'face-art/faces.json');face_test=read(F/'review/faces-validation.json')
    assert faces['source_candidate_sha256']==face_test['source_candidate_sha256']==sha(candidate)
    assert faces['body_bank_sha256']==face_test['body_bank_sha256']==report['bank_sha256']
    assert face_test['passed'] and face_test['sanitizers_passed'] and face_test['state_cases']==96
    assert face_test['generated_data_sha256']==sha(G/'gungnir_faces_data.c')
    assert face_test['metadata_sha256']==sha(F/'face-art/faces.json')==sha(G/'gungnir-faces.json')
    assert face_test['body_geometry_unchanged'] and face_test['original_alpha_unchanged']
    assert faces['format']=='IA8' and faces['tmem_bytes']==4096
    for row in faces['profiles']:assert sha(F/'face-art'/row['file'])==row['sha256']
    for name,expected in face_test['inputs'].items():assert sha(ROOT/name)==expected,name
    face_native=read(F/'review/faces-native-validation.json')
    assert face_native['passed'] and face_native['generated_data_sha256']==face_test['generated_data_sha256']
    assert face_native['rdp_errors']==face_native['rdp_warnings']==0
    for name,expected in face_native['inputs'].items():assert sha(ROOT/name)==expected,name
    # Preserve observations, including failures. Only an actual review can
    # decide whether remaining projection changes are acceptable in context.
    appearance=F/'review/appearance-validation.json';native=F/'review/native-validation.json'
    accepted=all(p.is_file() and read(p).get('passed') and read(p).get('candidate_sha256')==sha(candidate) for p in (appearance,native))
    inputs=set(ROOT/'port/n64'/n for n in ('character.h','game.h','game.c','controls.h','controls.c','main.c','map.c','hud.c','scene.c','scene_flashlight.inc','frontend_draw.c','runtime_qa.c','combat_geometry.c','combat_geometry.h','camouflage.h','view_layout.h','prepare_gungnir_strategy.py','bake_autopilot_nav.c','demake_gungnir.py','refine_gungnir_contacts.py','fit_gungnir_surfaces.py','recess_gungnir_cloth.py','pack_gungnir.py','pack_gungnir_firstperson.py','gungnir_library.py','validate_gungnir_exports.py','audit_gungnir_clearance.py','review_gungnir.py','certify_gungnir.py','test_gungnir.c','test_gungnir_runtime.py','test_gungnir_firstperson.py'))
    inputs.update(ROOT/'port/n64'/n for n in ('build.py','frontend_qa.c','jorge_field_qa.h','menu_draw.c','test_maps.c','test_maps.py','test_build_defaults.py','test_damage_tiling.py'))
    inputs.update(ROOT/'port/n64'/n for n in ('repair_gungnir_back.py','audit_gungnir_rear.py','repair_gungnir_shells.py','audit_gungnir_shells.py'))
    inputs.update(ROOT/'port/n64'/n for n in ('refine_gungnir_optic.py','audit_gungnir_optic.py'))
    inputs.update(ROOT/'port/n64'/n for n in ('hud_layout.h','test_hud_layout.c'))
    inputs.update(ROOT/'port/n64'/n for n in ('test_gungnir_faces.py','stage_gungnir_bank.py'))
    inputs.update((ROOT/'port/n64').glob('gungnir*.h'));inputs.update((ROOT/'port/n64').glob('gungnir*.c'));inputs.update((ROOT/'port/n64').glob('gungnir*.py'));inputs.update((ROOT/'port/n64').glob('gungnir*.inc'));inputs.update((ROOT/'port/n64').glob('autopilot*.[ch]'))
    inputs.update(ROOT/'source/ai'/n for n in ('actions.c','actor_type_elite.c','actor_type_grunt.c'))
    files=[p for p in F.rglob('*') if p.is_file()]+[p for p in G.iterdir() if p.is_file() and p.name!='gungnir-validation.json']+[A/'frontend-files/gungnir.bin',A/'generated/pve/pve_defs.c']
    fingerprint=lambda paths:{str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
    result=dict(schema=1,quality_state='accepted' if accepted else 'candidate: appearance and native inspection pending',publication_approved=bool(accepted),inputs=fingerprint(inputs),files=fingerprint(files),bank_sha256=report['bank_sha256'],packed_vertices=[r['vertices'] for r in report['lods']],triangles=[r['triangles'] for r in report['lods']],rig_comparisons=sum(r['skin_vertex_comparisons'] for r in library),glb_samples=780,c_decode_cases=4680,firstperson_pose_cases=1409,navigation_maximum_bytes=navigation['maximum_runtime_allocation_bytes'],appearance_observations=dict(body_coverage_probes=coverage['samples'],maximum_new_enclosed_pixels=coverage['maximum_new_enclosed_pixels'],packed_maximum_new_enclosed_pixels=packed['maximum_new_enclosed_pixels'],clearance_probes=clearance['samples'],maximum_new_broad_plate_occlusion_pixels=clearance['maximum_new_broad_plate_occlusion_pixels'],quantized_geometry=shape['geometry']))
    result['face_art']=dict(profiles=[r['file'] for r in faces['profiles']],format='IA8',tmem_bytes=4096,total_texture_bytes=faces['total_texture_bytes'],additional_resident_body_vertices=0,additional_draw_triangles=face_test['overlay_triangles'],additional_vertex_loads=face_test['extra_vertex_loads'],sanitized_state_cases=96,native_rdp_errors=0,native_rdp_warnings=0)
    output.write_text(json.dumps(result,indent=2)+'\n');print('Certified integrity/runtime evidence;',result['quality_state'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True,help='Fresh guarded output; promote to generated/gungnir after verification');a=p.parse_args();run(a.output)
