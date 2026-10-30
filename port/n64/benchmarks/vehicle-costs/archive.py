"""Package verified diagnostic evidence privately; does not commit or push."""
import gzip
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from run import ROOT, HERE, OUT, CASES

ARCHIVE = ROOT / 'halo64-assets/assets/vehicle-costs'
VIEW = ROOT.parents[2] / 'build/n64-vehicle-costs'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_gzip(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(data, mtime=0))


def main():
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    index = {}
    for name in CASES:
        manifest = next((OUT / name).glob('*.build.json'))
        m = json.loads(manifest.read_text())
        write_gzip(ARCHIVE / 'manifests' / (name + '.json.gz'), manifest.read_bytes())
        write_gzip(ARCHIVE / 'logs' / (name + '.log.gz'), (OUT / (name + '-native.log')).read_bytes())
        write_gzip(ARCHIVE / 'build-logs' / (name + '.log.gz'), (OUT / (name + '-build.log')).read_bytes())
        # Deduplicate exact compiler inputs by hash, retaining every path in the index.
        groups = {k: m[k] for k in ('sources', 'headers', 'included_data', 'generated_adapters')}
        groups['vehicle_cost_audit'] = m['vehicle_cost_audit']['sources']
        index[name] = {}
        for group, files in groups.items():
            index[name][group] = {}
            for path, expected in files.items():
                source = ROOT / path
                origin = 'working-file'
                data = source.read_bytes() if source.is_file() else b''
                if digest(data) != expected:
                    relative = str(source.relative_to(ROOT))
                    data = subprocess.run(['git', 'show', m['runtime_commit'] + ':' + relative],
                                          cwd=ROOT, capture_output=True, check=True).stdout
                    origin = 'git:' + m['runtime_commit']
                assert digest(data) == expected, (name, group, path)
                assert source.suffix not in ('.map', '.map64', '.z64'), path
                write_gzip(ARCHIVE / 'inputs' / (expected + '.gz'), data)
                index[name][group][path] = {'sha256': expected, 'origin': origin}
    (ARCHIVE / 'inputs.json').write_text(json.dumps(index, indent=2) + '\n')
    generators = ARCHIVE / 'generators'
    generators.mkdir(exist_ok=True)
    for source in (OUT / 'live-generator.py', OUT / 'draw-generator.py',
                   ROOT / 'port/n64/vehicle_cost_audit_source.py'):
        shutil.copyfile(source, generators / source.name)
    # Current diagnostic/build scripts are public; retain their precise archive versions too.
    for source in (ROOT / 'port/n64/build.py', ROOT / 'port/n64/runtime_config.h',
                   ROOT / 'port/n64/test_runtime_configs.py',
                   ROOT / 'port/n64/pve_draw_audit_source.py', HERE / 'run.py',
                   HERE / 'collect.py', HERE / 'archive.py'):
        target = ARCHIVE / 'scripts' / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    shutil.copytree(VIEW, ARCHIVE / 'evidence', dirs_exist_ok=True)
    shutil.copyfile(ROOT / 'build/pve-vehicles/ares.bml', ARCHIVE / 'ares.bml')
    for name in ('configurations.log', 'results.json', 'provenance.json', 'validation.json'):
        shutil.copyfile(OUT / name, ARCHIVE / name)
    shutil.copyfile(ROOT / 'port/n64/PVE_VEHICLE_COSTS.md', ARCHIVE / 'PVE_VEHICLE_COSTS.md')
    payloads = {str(p.relative_to(ARCHIVE)): digest(p.read_bytes())
                for p in sorted(ARCHIVE.rglob('*'))
                if p.is_file() and p.name not in ('SHA256.json', 'README.md')}
    assert not any(p.suffix in ('.map', '.map64', '.z64') for p in ARCHIVE.rglob('*'))
    (ARCHIVE / 'SHA256.json').write_text(json.dumps(payloads, indent=2) + '\n')
    (ARCHIVE / 'README.md').write_text('''# Vehicle cost audit — 29 October 2026

Diagnostic evidence against public checkpoint 66644065 and private assets
15c2d3c. The normal playable candidate is unchanged. The public report and
reproduction scripts live in port/n64/PVE_VEHICLE_COSTS.md and
port/n64/benchmarks/vehicle-costs. This archive contains no ROM or map cache.

Ten native captures comprise four main live fixtures, one Wraith cooldown
follow-up, three ordinary frozen routes, one serialized timing control and one
zero-area-scissor control. Raw framebuffer payloads and derived PNG comparisons
are private. Numerical summaries and stripped logs are also checked in publicly.
All times are from native N64 programs in Ares v148, not cartridge measurements.
Open evidence/comparison.html for the hull-omission photos and difference filter.

inputs.json maps every source/header/adapter input in each build manifest to a
gzip-compressed blob in inputs/<sha256>.gz. Hash the decompressed content to
verify its original manifest digest. Most inputs match the working files; the
first eight builds use runtime_config.h from 66644065. Empty-scissor and the
cooldown follow-up use the later diagnostic guard, retained here as well.
Generated copies include the local PvE include chain and retained physics.

generators/live-generator.py reproduces the original four live builds;
draw-generator.py has the target printf-format correction used by the frozen
builds. vehicle_cost_audit_source.py adds the cooldown counter used by the final
live follow-up. The per-case generator hashes identify each exact version.
scripts/ freezes the final diagnostic/build/reproduction scripts. Restoring
paths from inputs.json permits exact source recovery; build directories and
SDK/asset paths must be adjusted for another machine. The source vehicle bank
and corrected ground map are restored from the earlier private archives.

SHA256.json covers all payloads except itself and this README. The configurations
log records 45 configurations / 180 target translation units. validation.json
records manifest-input checks; the collector verifies native repeats and matched
state/load controls. No optimization is adopted by this audit.
''')
    for name, expected in payloads.items():
        assert digest((ARCHIVE / name).read_bytes()) == expected, name
    print('Verified', len(payloads), 'private payloads;',
          sum(p.stat().st_size for p in ARCHIVE.rglob('*') if p.is_file()), 'bytes')


if __name__ == '__main__':
    main()
