"""Keep source-derived assets and framebuffer payloads private; never push."""
import gzip,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
OUT=ROOT/'build/pve-vehicles';VIEW=ROOT.parents[2]/'build/n64-enemy-vehicles'
ARCHIVE=ROOT/'halo64-assets/assets/enemy-vehicles';EVIDENCE=ARCHIVE/'evidence'
EVIDENCE.mkdir(parents=True,exist_ok=True)
for folder in ('source','bank'):
    for src in (OUT/folder).rglob('*'):
        if not src.is_file() or src.is_symlink() or src.suffix in ('.map','.map64','.z64','.log'):continue
        dst=ARCHIVE/folder/src.relative_to(OUT/folder);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
for folder in ('before','after','diff','lod-diff'):shutil.copytree(VIEW/folder,EVIDENCE/folder,dirs_exist_ok=True)
for name in ('comparison.html','photos.json','results.json','ce-entry.json'):shutil.copyfile(VIEW/name,EVIDENCE/name)
page=EVIDENCE/'comparison.html';page.write_text(page.read_text().replace('<a href="halo64-enemy-vehicles.z64">Playable Firefight ROM</a> · ',''))
for src,name in [(OUT/'hud-only-photos-native.log','before-photos.log.gz'),(OUT/'final-photos-native.log','after-photos.log.gz'),(OUT/'pre-cache-fix/photos-native.log','before-cache-trim-photos.log.gz'),(OUT/'pre-hud-fix/photos-native.log','after-cache-trim-photos.log.gz'),(OUT/'pre-cache-fix/final-8-4-native.log','failed-allocation-4p.log.gz'),(OUT/'failed-map-bank/maps-cycle-native.log','failed-map-allocation.log.gz')]:
    (EVIDENCE/name).write_bytes(gzip.compress(src.read_bytes(),mtime=0))
(EVIDENCE/'failed-map-after-animation-scratch.log.gz').write_bytes(gzip.compress((OUT/'failed-map-bank-scratch/maps-cycle-native.log').read_bytes(),mtime=0))
for name in ('asset-validation.json','cache-pixel-check.json','scratch-pixel-check.json','memory-audit.json','host-tests.log','host-match.log','host-modes.log','host-navigation.log'):
    shutil.copyfile(OUT/name,HERE/name);shutil.copyfile(OUT/name,EVIDENCE/name)
for name in ('provenance.json','ares.bml','maps-ares.bml'):shutil.copyfile(OUT/name,EVIDENCE/name)
shutil.copyfile(OUT/'maps-cycle-native.log',HERE/'logs/maps-cycle-native.log')
shutil.copyfile(OUT/'map-probe-native.log',HERE/'logs/map-probe-native.log')
names=[*json.loads((OUT/'provenance.json').read_text())['cases'],'final-photo','play','maps-cycle','map-probe']
manifests=EVIDENCE/'manifests';manifests.mkdir(exist_ok=True)
for name in names:
    src=next((OUT/name).glob('*.build.json'));(manifests/(name+'.build.json.gz')).write_bytes(gzip.compress(src.read_bytes(),mtime=0))
for name in ('final-photo','final-8-4'):
    src=next((OUT/'pre-cache-fix'/name).glob('*.build.json'));(manifests/('before-'+name+'.build.json.gz')).write_bytes(gzip.compress(src.read_bytes(),mtime=0))
for folder,name in [('hud-only-final-photo','before-scratch-lifetime-photo'),('failed-map-bank/maps-cycle','failed-map-bank'),('failed-map-bank-scratch/maps-cycle','failed-map-after-animation-scratch')]:
    src=next((OUT/folder).glob('*.build.json'));(manifests/(name+'.build.json.gz')).write_bytes(gzip.compress(src.read_bytes(),mtime=0))
revision=EVIDENCE/'ce-entry';revision.mkdir(exist_ok=True)
for name in ('results.json','host-tests.log','host-match.log','stress-4-native.log','previous-inputs.json','previous-validation.json'):
    shutil.copyfile(OUT/'ce-entry'/name,revision/name)
shutil.copytree(OUT/'ce-entry/previous-inputs',revision/'previous-inputs',dirs_exist_ok=True)
(revision/'photos-native.log.gz').write_bytes(gzip.compress((OUT/'ce-entry/photos-native.log').read_bytes(),mtime=0))
for name in ('play','photos','stress-4'):
    src=next((OUT/'ce-entry'/name).glob('*.build.json'))
    (manifests/('ce-entry-'+name+'.build.json.gz')).write_bytes(gzip.compress(src.read_bytes(),mtime=0))
assert not any(p.suffix in ('.map','.map64','.z64') for p in ARCHIVE.rglob('*'))
files={str(p.relative_to(ARCHIVE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in ARCHIVE.rglob('*') if p.is_file() and p.name not in ('SHA256.json','README.md')}
(ARCHIVE/'SHA256.json').write_text(json.dumps(files,indent=2)+'\n')
(ARCHIVE/'README.md').write_text('''# Enemy vehicles — local appraisal, 29 October 2026

Source-derived Wraith/Shade art, physics and weapon metadata, source Elite pilot
clips, human Shade clips, Wraith hatch, canonical hit streams, source sounds and
the additive candidate bank. Existing symmetric Covenant bodies and Jackal
shields remain intact. The source runtime and reproduction steps are documented
in public port/n64/PVE_VEHICLES.md and benchmarks/enemy-vehicles/README.md.

Evidence includes 42 four-camera native pages, LOD differences, pixel-identical
before/after memory-fix comparisons, compressed native readbacks and manifests,
numerical profiling and host checks. The failed allocation capture is preserved
as a failure, not counted as a successful benchmark. No owned map caches or ROMs
are included. Native timings are Ares measurements, not cartridge claims.

The current candidate uses available-seat entry only. Its ce-entry/ evidence
contains fresh host tests, 42 native pages and one four-player overload
capture. Original matrix/manifests are historical; previous-inputs freezes the
runtime files before removal of the occupied-seat hijacking prototype. The
comparison page uses the latest photos and distinguishes the two timing sets.
Thirty-nine pages match exactly; three only remove the occupied-Ghost HUD hint.

To restore the build layout, copy bank/ and source/ to build/pve-vehicles/.
Source extraction records retain their original provenance paths. Re-extraction
requires the existing owned CE caches and earlier private candidate archives.
The playable ROM remains local. This archive has not been pushed or adopted.
''')
print(ARCHIVE,'files',len(files),'bytes',sum(p.stat().st_size for p in ARCHIVE.rglob('*') if p.is_file()))
