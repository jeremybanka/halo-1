"""Archive the shield candidate and native evidence privately, without ROMs/maps."""
import gzip,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
OUT=ROOT/'build/jackal-shields';VIEW=ROOT.parents[2]/'build/n64-jackal-shields'
ARCHIVE=ROOT/'halo64-assets/assets/jackal-shields';EVIDENCE=ARCHIVE/'evidence'
EVIDENCE.mkdir(parents=True,exist_ok=True)
for folder in ('source','bank'):
    for src in (OUT/folder).rglob('*'):
        if not src.is_file() or src.suffix in ('.map','.z64','.log'):continue
        dst=ARCHIVE/folder/src.relative_to(OUT/folder);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
for folder in ('before','after','diff','roster-before','roster-after','roster-diff'):
    shutil.copytree(VIEW/folder,EVIDENCE/folder,dirs_exist_ok=True)
for name in ('comparison.html','pixel-checks.json','roster-pixel-checks.json','results.json'):
    shutil.copyfile(VIEW/name,EVIDENCE/name)
page=EVIDENCE/'comparison.html'
page.write_text(page.read_text().replace('<a href="halo64-jackal-shields.z64">Playable Firefight ROM</a> · ',''))
for name in ('before-photos','after-photos','before-roster-photos','after-roster-photos'):
    (EVIDENCE/(name+'-native.log.gz')).write_bytes(gzip.compress((OUT/(name+'-native.log')).read_bytes(),mtime=0))
original=ROOT/'build/firefight-roster/photos-native.log'
(EVIDENCE/'original-roster-native.log.gz').write_bytes(gzip.compress(original.read_bytes(),mtime=0))
for name in ('asset-checks.json','host.log','memory-symbols.json'):
    shutil.copyfile(OUT/name,HERE/name);shutil.copyfile(OUT/name,EVIDENCE/name)
for name in ('provenance.json','ares.bml'):
    shutil.copyfile(OUT/name,EVIDENCE/name)
manifests=EVIDENCE/'manifests';manifests.mkdir(exist_ok=True)
for name in json.loads((OUT/'provenance.json').read_text())['cases']:
    src=next((OUT/name).glob('*.build.json'))
    (manifests/(name+'.build.json.gz')).write_bytes(gzip.compress(src.read_bytes(),mtime=0))
for name in ('before-photos','after-photos','before-roster-photos','after-roster-photos','after-play'):
    shutil.copyfile(next((OUT/name).glob('*.build.json')),EVIDENCE/(name+'.build.json'))
assert not list(ARCHIVE.rglob('*.map')) and not list(ARCHIVE.rglob('*.z64'))
files={str(p.relative_to(ARCHIVE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in ARCHIVE.rglob('*') if p.is_file() and p.name not in ('SHA256.json','README.md')}
(ARCHIVE/'SHA256.json').write_text(json.dumps(files,indent=2)+'\n')
(ARCHIVE/'README.md').write_text('''# Jackal shield appraisal — 29 October 2026

Private source-derived shield geometry, forearm tracks, texture, packed bank and
native evidence for the opt-in --pve-jackal-shields candidate. Read public
port/n64/JACKAL_SHIELDS.md and benchmarks/jackal-shields/README.md for reproduction,
measurements and shader limits. This extends the local Firefight roster candidate.
The seven original roster bank files are byte-identical; only the shield C asset
is added. Point --pve-model-bank to this bank and enable --pve-roster,
--pve-crunch and --pve-jackal-shields to reproduce the candidate.

The 76 source triangles and rigid frame-shield binding are retained at every body
LOD. Source geometry/UVs, shader parameters, rank colors and recharge values are
preserved in the source records. The rendered shader is a one-pass approximation.
No owned map caches or ROM binaries are included. Source JSON retains provenance
paths from its build location; restore that layout or re-extract before rebaking.

Evidence contains 72 paired shield photo pages, before/after/diffs for the original
46-page roster route, compressed native framebuffer readbacks, settings, checks
and manifests. Timing logs are in the public benchmark directory; provenance.json
records their hashes. SHA256.json covers the archived payloads. The local viewer
also links a playable ROM; that ROM/link is intentionally absent here.
This candidate has not been pushed or adopted.
''')
print(ARCHIVE,'files',len(files),'bytes',sum(p.stat().st_size for p in ARCHIVE.rglob('*') if p.is_file()))
