"""Verify current revision and frozen historical evidence without conflating them."""
import hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
OUT=ROOT/'build/pve-vehicles';VIEW=ROOT.parents[2]/'build/n64-enemy-vehicles'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
provenance=json.loads((HERE/'provenance.json').read_text());assert len(provenance['cases'])==9
seen=set();names=[*provenance['cases'],'final-photo','play','maps-cycle','map-probe']
frozen=OUT/'ce-entry/previous-inputs'
for name,digest in json.loads((OUT/'ce-entry/previous-inputs.json').read_text()).items():
    assert sha(frozen/name)==digest,(name,'frozen input mismatch')
for name in names:
    manifest=next((OUT/name).glob('*.build.json'));m=json.loads(manifest.read_text())
    assert sha(Path(m['rom']['path']))==m['rom']['sha256'],(name,'ROM')
    if name in provenance['cases']:
        assert sha(manifest)==provenance['cases'][name]['manifest_sha256']
        assert sha(OUT/(name+'-native.log'))==provenance['cases'][name]['log_sha256']
    for group in ('sources','headers','included_data','generated_adapters'):
        for filename,digest in m[group].items():
            path=Path(filename);path=path if path.is_absolute() else ROOT/path
            if (path,digest) in seen:continue
            prior=frozen/path.relative_to(ROOT) if path.is_relative_to(ROOT) else None
            historical=prior if prior and prior.is_file() else path
            assert sha(historical)==digest,(path,'historical input mismatch');seen.add((path,digest))
revision=json.loads((HERE/'ce-entry.json').read_text());current=set()
for name,record in revision['manifests'].items():
    manifest=next((OUT/'ce-entry'/name).glob('*.build.json'));m=json.loads(manifest.read_text())
    assert sha(manifest)==record['manifest_sha256']
    assert sha(Path(m['rom']['path']))==record['rom_sha256']==m['rom']['sha256']
    for group in ('sources','headers','included_data','generated_adapters'):
        for filename,digest in m[group].items():
            path=Path(filename);path=path if path.is_absolute() else ROOT/path
            assert sha(path)==digest,(path,'current input changed after build');current.add((path,digest))
for filename,digest in revision['log_sha256'].items():assert sha(OUT/'ce-entry'/filename)==digest
assert revision['frames']==42 and revision['changed_pixels'][:3]==[1399]*3 and not any(revision['changed_pixels'][3:])
assert not any(revision['changed_pixels_outside_removed_hint'])
assert sha(ROOT/'port/n64/build.py')==provenance['build_script_sha256']
maps=(OUT/'maps-cycle-native.log').read_text();assert 'FRONTEND_QA step=223/223 map=12 done=1' in maps
assert not any(x in maps.lower() for x in ('assertion failed','assertf','rdpq error','rdpq warning'))
assert 'CENSUS tick=0 camera=3 ' in (OUT/'map-probe-native.log').read_text()
for filename in ('photos.json','results.json'):assert (HERE/filename).read_bytes()==(VIEW/filename).read_bytes()
assert (HERE/'ce-entry.json').read_bytes()==(VIEW/'ce-entry.json').read_bytes()
assert sha(next((OUT/'ce-entry/play').glob('*.z64')))==sha(VIEW/'halo64-enemy-vehicles.z64')
html=(VIEW/'comparison.html').read_text()
for target in re.findall(r'href="([^"]+)"',html):
    if ':' not in target:assert (VIEW/target).is_file(),target
for folder in ('before','after','diff','lod-diff'):assert len(list((VIEW/folder).glob('*.png')))==42
script=OUT/'viewer-check.js';script.write_text(re.search(r'<script>([\s\S]+)</script>',html)[1])
nodes=sorted(Path('/Users/jem/.local/share/mise/installs/node').glob('*/bin/node'));assert nodes
subprocess.run([str(nodes[-1]),'--check',str(script)],check=True)
archive=ROOT/'halo64-assets/assets/enemy-vehicles';records=json.loads((archive/'SHA256.json').read_text())
for name,digest in records.items():assert sha(archive/name)==digest,name
result={'historical_candidate':{'built_roms_verified':len(names),'timing_cases':9,'timing_observations':405,'native_photo_pages':42,'camera_views':168,'pixel_identical_cache_fix_pages':42,'all_map_residency_cycle':True,'unique_input_hashes_verified':len(seen)},'available_seat_revision':{'built_roms_verified':3,'timing_cases':1,'timing_observations':45,'pixel_identical_photo_pages':39,'removed_hint_only_pages':3,'unchanged_scene_pages':42,'unique_current_input_hashes_verified':len(current)},'private_payloads_verified':len(records),'viewer_links_and_js_syntax':True,'browser_render_verified':False}
for name in ('cache-pixel-check.json','scratch-pixel-check.json'):
    pixels=json.loads((HERE/name).read_text());assert pixels['frames']==42 and not any(pixels['changed_pixels'])
result['historical_candidate']['pixel_identical_scratch_lifetime_pages']=42
(HERE/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
