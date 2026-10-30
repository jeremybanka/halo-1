"""Bind the completed measurements and private appraisal to their exact builds."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'build/player-aim'
HERE = Path(__file__).resolve().parent
PRIVATE = ROOT / 'halo64-assets/assets/player-aim-appraisal'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    PRIVATE.mkdir(parents=True, exist_ok=True)
    builds = {}
    for name in ('baseline', 'candidate', 'controlled-baseline', 'controlled-candidate', 'photos', 'photos-baseline', 'release'):
        folder = OUT / name
        # A rebuilt fixture can leave an older ROM variant beside it.
        manifests = sorted(folder.glob('*.build.json'), key=lambda p: p.stat().st_mtime)
        manifest = json.loads(manifests[-1].read_text())
        assert sha(Path(manifest['rom']['path'])) == manifest['rom']['sha256']
        builds[name] = manifest
    for group in ('controlled', 'photos'):
        a, b = [builds[n] for n in (('controlled-baseline', 'controlled-candidate') if group == 'controlled' else ('photos-baseline', 'photos'))]
        for key in ('headers', 'included_data'):
            assert a[key] == b[key], (group, key)
        # The one selected scene source is the intended difference.
        sources = []
        for build in (a,b):
            prefix = str(Path(build['rom']['path']).parent)
            sources.append({name.replace(prefix, 'BUILD'): value for name,value in build['sources'].items()
                            if not name.endswith(('scene.c','baseline-scene.c'))})
        assert sources[0] == sources[1], group
    provenance = dict(source_base='f40fefee4027b6de8eadf63cc0ba477801173ce0',
                      settings_sha256=sha(OUT/'ares.bml'), builds=builds)
    (PRIVATE/'builds.json').write_text(json.dumps(provenance, indent=2)+'\n')
    for name in ('controlled-baseline', 'controlled-candidate', 'baseline-1', 'candidate-1'):
        log = OUT / (name+'-native.log')
        text = log.read_text(errors='replace')
        assert 'BENCH ' in text and 'assertion failed' not in text.lower()
        (HERE/(name+'.log')).write_text(text)
    for variant in ('photos','photos-baseline'):
        text = (OUT/variant/'native.log').read_text(errors='replace')
        assert text.count('FF_PHOTO_END') == 51
        assert not re.search(r'assertion failed|\[RDPQ_VALIDATION\].*(?:ERROR|WARNING)', text, re.I)
    sizes = {}
    for name in ('baseline','candidate','release'):
        elf = Path(builds[name]['rom']['path']).with_suffix('.elf')
        output = subprocess.check_output(['/Users/jem/dojo/n64-2048/.build/libdragon/bin/mips64-elf-size', str(elf)], text=True)
        values = list(map(int, output.splitlines()[-1].split()[:4]))
        sizes[name] = dict(zip(('text','data','bss','resident_total'),values), rom_bytes=Path(builds[name]['rom']['path']).stat().st_size)
    (HERE/'storage.json').write_text(json.dumps(sizes,indent=2)+'\n')
    (HERE/'pixel-checks.json').write_bytes((PRIVATE/'pixel-checks.json').read_bytes())
    (HERE/'provenance.json').write_text(json.dumps(dict(
        source_base=provenance['source_base'], settings_sha256=provenance['settings_sha256'],
        private_builds_sha256=sha(PRIVATE/'builds.json'),
        source_files={str(p.relative_to(ROOT)):sha(p) for p in
            [ROOT/'port/n64'/n for n in ('player_aim.c','player_aim.h','player_aim_qa.h','extract_player_aim.py','scene.c','combat_geometry.c','game.c','build.py')]}
    ),indent=2)+'\n')
    print('PASS matched fixture inputs, complete native captures and build/log provenance')


if __name__ == '__main__': main()
