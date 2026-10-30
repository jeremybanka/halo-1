"""Preserve the local appraisal privately without committing, pushing or including ROMs."""
import gzip,hashlib,json,shutil
from pathlib import Path
from run import ROOT,HERE,OUT,CASES
ARCHIVE=ROOT/'halo64-assets/assets/vehicle-lods';VIEW=ROOT.parents[2]/'build/n64-vehicle-lods'
def copy(source,target):
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
def compressed(source,target):
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(gzip.compress(source.read_bytes(),mtime=0))
def main():
    ARCHIVE.mkdir(parents=True,exist_ok=True)
    for name in ('reduced.json','distance-lods.blend','silhouettes.json','asset-checks.json','input-validation.json','opacity-check.json','photos.json','results.json','provenance.json','frozen-preview.json','host-projection.log','configurations.log','rejected-unprotected.json','rejected-unprotected-silhouettes.json'):
        copy(OUT/name,ARCHIVE/name)
    copy(OUT/'bank/vehicle_distance_data.c',ARCHIVE/'bank/vehicle_distance_data.c')
    copy(ROOT/'build/pve-vehicles/ares.bml',ARCHIVE/'ares.bml')
    inputs={}
    for name in CASES:
        manifest=next((OUT/name).glob('*.build.json'));m=json.loads(manifest.read_text())
        compressed(manifest,ARCHIVE/'manifests'/(name+'.json.gz'))
        compressed(OUT/(name+'-build.log'),ARCHIVE/'build-logs'/(name+'.log.gz'))
        if not name.endswith('play'):compressed(OUT/(name+'-native.log'),ARCHIVE/'logs'/(name+'.log.gz'))
        inputs[name]={}
        # Save exact headers/source adapters; unchanged art lives in the pinned base archive.
        for group in ('sources','headers','included_data','generated_adapters'):
            inputs[name][group]={}
            for path,digest in m[group].items():
                p=ROOT/path;data=p.read_bytes();assert hashlib.sha256(data).hexdigest()==digest,(name,path)
                dst=ARCHIVE/'inputs'/(digest+'.gz')
                if not dst.exists():dst.parent.mkdir(exist_ok=True);dst.write_bytes(gzip.compress(data,mtime=0))
                inputs[name][group][path]=digest
    (ARCHIVE/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
    shutil.copytree(VIEW,ARCHIVE/'evidence',dirs_exist_ok=True,ignore=shutil.ignore_patterns('*.z64'))
    page=ARCHIVE/'evidence/comparison.html';page.write_text(page.read_text().replace('<a href="halo64-vehicle-lods.z64">Playable candidate ROM</a> · ',''))
    shutil.copytree(OUT/'failed-disk-full',ARCHIVE/'failed-disk-full',dirs_exist_ok=True)
    for p in HERE.glob('*.py'):copy(p,ARCHIVE/'scripts'/p.name)
    copy(ROOT/'port/n64/VEHICLE_DISTANCE_LODS.md',ARCHIVE/'VEHICLE_DISTANCE_LODS.md')
    assert not any(p.suffix in ('.map','.map64','.z64') for p in ARCHIVE.rglob('*'))
    hashes={str(p.relative_to(ARCHIVE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ARCHIVE.rglob('*')) if p.is_file() and p.name not in ('SHA256.json','README.md')}
    (ARCHIVE/'SHA256.json').write_text(json.dumps(hashes,indent=2)+'\n')
    (ARCHIVE/'README.md').write_text('''# Wraith / Shade distance LODs — local appraisal

Local, unpushed candidate against public 031e79f5 / private 39a541d. Restore
the existing enemy-vehicles archive to build/pve-vehicles first, copy that bank
to build/vehicle-lods/bank, then add bank/vehicle_distance_data.c from here.
All 33 prior bank files are byte-identical. The source art reference remains
in the earlier enemy-vehicles/source archive; no owned map or ROM is included.

distance-lods.blend and reduced.json are the final Blender-authored meshes.
The rejected-unprotected files document the failed first reduction separately.
The public report and reproduction scripts are in port/n64/VEHICLE_DISTANCE_LODS.md
and port/n64/benchmarks/vehicle-lods. evidence/comparison.html opens the native
photos, silhouette filters and fresh performance table locally.

Native logs preserve complete RGBA5551 framebuffer payloads. All 27 manifests
and exact source/header/adapter inputs are retained: inputs.json maps each
original path to inputs/<sha256>.gz; hash decompressed bytes against that key.
Failed disk-full output remains under failed-disk-full and is excluded from
the passing measurements. Source snapshots allow reproduction while the public
runtime edits are still uncommitted for appraisal.

SHA256.json covers payloads except itself and this README. The archive script
does not commit or push. Timings are native N64 programs in Ares v148, not
cartridge measurements. No optimization to AI/clearance/physics is included.
''')
    print('Private local archive:',len(hashes),'verified payloads',sum(p.stat().st_size for p in ARCHIVE.rglob('*') if p.is_file()),'bytes')
if __name__=='__main__':main()
