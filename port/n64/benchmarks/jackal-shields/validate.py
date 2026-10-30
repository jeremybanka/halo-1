"""Validate final captured ROM inputs and archived native/photo evidence."""
import hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
OUT=ROOT/'build/jackal-shields';VIEW=ROOT.parents[2]/'build/n64-jackal-shields'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
provenance=json.loads((HERE/'provenance.json').read_text());assert len(provenance['cases'])==24
assert len(provenance['matched'])==12
seen=set();names=[*provenance['cases'],'before-photos','after-photos','before-roster-photos','after-roster-photos','after-play']
for name in names:
    manifest=next((OUT/name).glob('*.build.json'));m=json.loads(manifest.read_text())
    assert sha(Path(m['rom']['path']))==m['rom']['sha256'],(name,'ROM')
    if name in provenance['cases']:
        assert sha(manifest)==provenance['cases'][name]['manifest_sha256']
        assert sha(OUT/(name+'-native.log'))==provenance['cases'][name]['log_sha256']
    for group in ('sources','headers','included_data','generated_adapters'):
        for name,digest in m[group].items():
            path=Path(name);path=path if path.is_absolute() else ROOT/path
            if (path,digest) in seen:continue
            assert sha(path)==digest,(path,'input changed since build');seen.add((path,digest))
assert sha(ROOT/'port/n64/build.py')==provenance['build_script_sha256']
for filename in ('pixel-checks.json','roster-pixel-checks.json','results.json'):
    assert (HERE/filename).read_bytes()==(VIEW/filename).read_bytes()
rom=next((OUT/'after-play').glob('*.z64'));assert sha(rom)==sha(VIEW/'halo64-jackal-shields.z64')
html=(VIEW/'comparison.html').read_text()
for target in re.findall(r'href="([^"]+)"',html):
    if ':' not in target:assert (VIEW/target).is_file(),target
for folder,count in [('before',72),('after',72),('diff',72),('roster-before',46),('roster-after',46),('roster-diff',46)]:
    assert len(list((VIEW/folder).glob('*.png')))==count,(folder,count)
script=OUT/'viewer-check.js';script.write_text(re.search(r'<script>([\s\S]+)</script>',html)[1])
nodes=sorted(Path('/Users/jem/.local/share/mise/installs/node').glob('*/bin/node'))
assert nodes,'Need installed Node binary for viewer syntax check'
subprocess.run([str(nodes[-1]),'--check',str(script)],check=True)
archive=ROOT/'halo64-assets/assets/jackal-shields'
records=json.loads((archive/'SHA256.json').read_text())
for name,digest in records.items():assert sha(archive/name)==digest,name
result={'built_roms_verified':len(names),'timing_cases':24,'matched_pairs':12,'unique_input_hashes_verified':len(seen),'private_payloads_verified':len(records),'viewer_links_and_js_syntax':True,'browser_render_verified':False}
(HERE/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
