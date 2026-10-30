"""Preserve appraisal inputs/evidence privately; never archive owned cache maps."""
import gzip,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
capture=ROOT/'build/firefight-roster';archive=ROOT/'halo64-assets/assets/firefight-roster'
viewer=ROOT.parents[2]/'build/n64-firefight-roster'
archive.mkdir(parents=True,exist_ok=True)
for folder in ('source','bank'):
    for source in (capture/folder).rglob('*'):
        if not source.is_file() or source.suffix in ('.map','.log'):continue
        target=archive/folder/source.relative_to(capture/folder)
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
evidence=archive/'evidence';evidence.mkdir(exist_ok=True)
for folder in ('photos','diff','audio'):
    shutil.copytree(viewer/folder,evidence/folder,dirs_exist_ok=True)
for name in ('comparison.html','pixel-checks.json','results.json'):
    shutil.copyfile(viewer/name,evidence/name)
# The ROM remains a local build output; remove that link from the archive copy.
page=evidence/'comparison.html';page.write_text(page.read_text().replace('<a href="halo64-firefight-roster.z64">Playable candidate ROM</a> · ',''))
(evidence/'photos-native.log.gz').write_bytes(gzip.compress((capture/'photos-native.log').read_bytes(),mtime=0))
for name in ('asset-checks.json','input-checks.json','host.log','default-host.log','pve-host.log','collision-host.log','map-recertification.log'):
    shutil.copyfile(capture/name,HERE/name);shutil.copyfile(capture/name,evidence/name)
for name in ('provenance.json','ares.bml'):
    shutil.copyfile(capture/name,evidence/name)
for name in ('photos','play'):
    source=next((capture/name).glob('*.build.json'));shutil.copyfile(source,evidence/(name+'.build.json'))
files={str(p.relative_to(archive)):hashlib.sha256(p.read_bytes()).hexdigest() for p in archive.rglob('*') if p.is_file() and p.name not in ('SHA256.json','README.md')}
(archive/'SHA256.json').write_text(json.dumps(files,indent=2)+'\n')
(archive/'README.md').write_text('''# Covenant roster appraisal — 29 October 2026

Private source-derived models, animations, dialogue and native evidence for the
opt-in `--pve-roster` candidate. Read public `port/n64/FIREFIGHT_ROSTER.md` and
`benchmarks/firefight-roster/README.md` for fidelity limits, tests and reproduction.
No owned cache `.map` files are included. SHA256.json covers the archived payloads.
The bank rebuilds the candidate ROM with --pve-model-bank pointing to this bank.
The source directory includes accepted base poses, Blender-baked alternate poses,
original dialogue WAVs and the exact packed signed PCM. Source texture paths in
extraction JSON record the original build location; regenerate extraction there
or restore that layout for rebaking. All source caches are identified by hash.
Photos are native framebuffer readbacks, not generated illustrations. Diffs compare
LODs, and cloak pages also change opacity. Audio previews are packed PCM samples.
The archive intentionally excludes ROM binaries and decompressed campaign maps.
This appraisal has not been pushed or adopted.
''')
assert not list(archive.rglob('*.map'))
print(archive, 'files',len(files),'bytes',sum(p.stat().st_size for p in archive.rglob('*') if p.is_file()))
