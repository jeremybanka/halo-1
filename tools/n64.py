#!/usr/bin/env python3
"""One-command N64 setup and release build, including immutable historical refs."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

DRIVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DRIVER/'tools'))
sys.path.insert(0, str(DRIVER/'port/n64'))
from workspace_storage import Policy, StorageRun, atomic_json, build_entry, main_root, run_command
from build_inputs import PackageReader, connect, digest, enemy_bank, restore
from n64_toolchain import python_environment, run, toolchain


def policy(root):
    # The current controller owns the policy even when the target is an older
    # standalone checkout (as in CI), just as it does for managed worktrees.
    return Policy(root, shared_root=main_root(DRIVER))


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def require_clean(root):
    if git(root, 'diff', '--name-only') or git(root, 'diff', '--cached', '--name-only'):
        raise ValueError('Commit or preserve source changes before using the locked bootstrap')


def locked_bank(root, cache, pin, repository):
    bank = root/'halo64-assets'
    if (bank/'.git').exists():
        if git(bank, 'rev-parse', 'HEAD') != pin or git(bank, 'status', '--porcelain'):
            raise ValueError('Existing asset checkout differs from the source pin; preserve its work before updating it')
        return bank
    if bank.exists() and any(bank.iterdir()):
        raise ValueError('Refusing to replace an existing asset directory')
    mirror = package_repository(cache, repository, pin)
    payload = cache/('asset-files-' + uuid.uuid4().hex)
    payload.mkdir()
    with subprocess.Popen(['git', '-C', str(mirror), 'archive', '--format=tar', pin], stdout=subprocess.PIPE) as p:
        try:
            run(['tar', '-xf', '-', '-C', payload], stdin=p.stdout)
        finally:
            p.stdout.close()
        if p.wait():
            raise ValueError('Asset extraction failed')
    # All bulk writes were staged under the guarded cache. The transfer to the
    # actual submodule uses same-volume renames and immutable Git pack hardlinks.
    run(['git', 'init', bank])
    gitdir = Path(git(bank, 'rev-parse', '--absolute-git-dir'))
    if (mirror/'objects/info/alternates').exists():
        raise ValueError('Asset object store must be self-contained')
    # Git ignores --local for shallow clones and would duplicate the pack outside
    # the reservation. Link only immutable, hash-named objects, never alternates.
    for directory in (mirror/'objects').iterdir():
        if not directory.is_dir() or directory.is_symlink():
            continue
        if directory.name == 'pack':
            files = [p for p in directory.iterdir() if re.fullmatch(r'pack-[0-9a-f]{40}\.(pack|idx|rev)', p.name)]
        elif re.fullmatch('[0-9a-f]{2}', directory.name):
            files = [p for p in directory.iterdir() if re.fullmatch('[0-9a-f]{38}', p.name)]
        else:
            continue
        dest = gitdir/'objects'/directory.name
        dest.mkdir(exist_ok=True)
        for p in files:
            if p.is_symlink() or not p.is_file():
                raise ValueError('Invalid Git object file')
            os.link(p, dest/p.name)
    if (mirror/'shallow').is_file():
        shutil.copyfile(mirror/'shallow', gitdir/'shallow')
    for p in payload.iterdir():
        if p.name == '.git' or os.path.lexists(bank/p.name):
            raise ValueError('Asset checkout collision')
        p.rename(bank/p.name)
    git(bank, 'update-ref', '--no-deref', 'HEAD', pin)
    git(bank, 'read-tree', pin)
    git(bank, 'remote', 'add', 'origin', repository)
    if git(bank, 'status', '--porcelain'):
        raise ValueError('Fresh asset checkout does not match the pinned tree')
    return bank


def package_repository(cache, repository, revision):
    mirror = cache/'asset-objects.git'
    if not mirror.exists():
        run(['git', 'init', '--bare', mirror])
        git(mirror, 'remote', 'add', 'origin', repository)
    if git(mirror, 'config', '--get', 'remote.origin.url') != repository:
        raise ValueError('Asset object store remote changed')
    exists = subprocess.run(['git', '-C', str(mirror), 'cat-file', '-e', revision+'^{commit}'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    if not exists:
        run(['git', '-C', mirror, 'fetch', '--no-tags', '--depth=1', '--no-auto-maintenance', 'origin', revision])
    git(mirror, 'update-ref', 'refs/heads/pin-'+revision, revision)
    return mirror


def verify_bank(bank, pin, lock):
    snapshot = json.loads((bank/'bank-manifest.json').read_text())
    exceptions = lock.get('historical_snapshot_corrections', {}).get(pin, {})
    applied = []
    for row in snapshot['files']:
        p = bank/row['path']
        if not p.resolve().is_relative_to(bank.resolve()) or not p.is_file():
            raise ValueError('Asset snapshot file missing or escaping checkout: '+row['path'])
        actual = digest(p)
        if p.stat().st_size != row['bytes'] or actual != row['sha256']:
            correction = exceptions.get(row['path'])
            if (not correction or correction['recorded_sha256'] != row['sha256']
                    or correction['published_sha256'] != actual or p.stat().st_size != row['bytes']):
                raise ValueError('Asset snapshot mismatch: '+row['path'])
            applied.append({'path': row['path'], **correction})
            print('Applying locked historical metadata correction:', row['path'], flush=True)
    return {'files': len(snapshot['files']), 'historical_corrections': applied}


def reject_external_links(root):
    for repo in (root, root/'halo64-assets'):
        for entry in subprocess.check_output(['git', '-C', str(repo), 'ls-files', '--stage', '-z']).split(b'\0'):
            if entry and entry.startswith(b'120000 '):
                name = os.fsdecode(entry.split(b'\t', 1)[1])
                if not (repo/name).resolve().is_relative_to(root):
                    raise ValueError('Versioned asset link escapes checkout: '+name)
    build = root/'build/n64'
    if build.exists() and not build.resolve().is_relative_to(root):
        raise ValueError('Legacy build/n64 points outside this checkout; preserve and retire that link before using the bootstrap')


def worker(args, root, cache, lock):
    cache.mkdir(parents=True, exist_ok=True)
    with (cache/'bootstrap.lock').open('a+') as mutex:
        fcntl.flock(mutex, fcntl.LOCK_EX)
        source = git(root, 'rev-parse', 'HEAD')
        require_clean(root)
        pin = git(root, 'rev-parse', 'HEAD:halo64-assets')
        bank = locked_bank(root, cache, pin, lock['asset_repository'])
        reject_external_links(root)
        snapshot = verify_bank(bank, pin, lock)
        package = lock['historical_input_package']
        if (bank/package['path']/'manifest.json').is_file():
            reader = PackageReader(bank=bank)
        else:
            if pin not in package['compatible_asset_pins']:
                raise ValueError('No locked supplemental input package for historical asset pin '+pin)
            repo = package_repository(cache, lock['asset_repository'], package['asset_revision'])
            reader = PackageReader(repository=repo, revision=package['asset_revision'])
        inputs, m = restore(reader, cache/'inputs', package['manifest_sha256'])
        connect(root, inputs, m)
        # Use the target ref's link layout, without changing its source files.
        spec = importlib.util.spec_from_file_location('target_setup_assets', root/'port/n64/setup_assets.py')
        setup = importlib.util.module_from_spec(spec); spec.loader.exec_module(setup)
        setup.connect_assets()
        requirements = DRIVER/'port/n64/requirements.lock.txt'
        if digest(requirements) != lock['requirements_lock_sha256']:
            raise ValueError('Python dependency lock was modified without updating bootstrap-lock.json')
        if digest(requirements.with_name('requirements-build.lock.txt')) != lock['build_requirements_lock_sha256']:
            raise ValueError('Python build-backend lock does not match bootstrap-lock.json')
        if digest(root/'port/n64/requirements.txt') != lock['requirements_source_sha256']:
            raise ValueError('Historical Python requirements need a matching lock entry')
        python = python_environment(lock, requirements, cache/'python-env', python=args.python, uv=args.uv)
        sdk, sdk_source, tiny, hashes = toolchain(lock, cache/'toolchain', sdk=args.sdk,
                                                libdragon=args.libdragon_source, tiny=args.tiny3d, jobs=args.jobs)
        run_id = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())+'-'+uuid.uuid4().hex[:8]
        run_dir = cache/'runs'/run_id
        run_dir.mkdir(parents=True)
        (run_dir/'scratch').mkdir()
        output = args.output_dir.resolve() if args.output_dir else run_dir/'rom'
        if not output.is_relative_to(root/'build') or output.exists():
            raise ValueError('ROM output must be a fresh directory under this checkout/build')
        command = [python, Path(__file__), '--build-worker', '--checkout', root,
                   '--sdk', sdk, '--tiny3d', tiny, '--libdragon-source', sdk_source,
                   '--preset', 'release', '--output-dir', output]
        if args.expanded:
            overlay = enemy_bank(bank, inputs/'enemy-bank', m)
            command += ['--pve-model-bank', overlay, '--pve-crunch', '--pve-roster',
                        '--pve-jackal-shields', '--enemy-vehicle-bank', overlay, '--vehicle-distance-lods']
        with (run_dir/'build.log').open('w') as log:
            print('Building N64 release; log:', run_dir/'build.log', flush=True)
            try:
                run(command, cwd=root, stdout=log, stderr=subprocess.STDOUT,
                    env={**os.environ, 'GIT_CEILING_DIRECTORIES': str(root),
                         'TMPDIR': str(run_dir/'scratch')})
            except subprocess.CalledProcessError:
                text = (run_dir/'build.log').read_text(errors='replace')
                if os.environ.get('CI'):
                    # Keep compiler source excerpts and extracted payload data
                    # out of the public workflow log/artifacts.
                    text = '\n'.join(line for line in text.splitlines() if 'error:' in line)[-3000:]
                else:
                    text = text[-12000:]
                print(text, file=sys.stderr)
                raise
        mf = next(output.glob('*.build.json')); built = json.loads(mf.read_text())
        rom = output/Path(built['rom']['path']).name
        if digest(rom) != built['rom']['sha256'] or built['runtime_commit'] != source or built['asset_commit'] != pin:
            raise ValueError('Built ROM does not match source/asset manifest')
        require_clean(root)
        if git(bank, 'status', '--porcelain'):
            raise ValueError('Build changed versioned assets')
        result = {'source': source, 'assets': pin, 'snapshot': snapshot,
                  'input_package': package, 'toolchain_files': hashes,
                  'bootstrap_lock_sha256': digest(DRIVER/'port/n64/bootstrap-lock.json'),
                  'rom': built['rom'], 'build_manifest': str(mf), 'log': str(run_dir/'build.log')}
        atomic_json(run_dir/'result.json', result)
        print('Built', rom, '\nSHA256', built['rom']['sha256'], '\nReport', run_dir/'result.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout', type=Path, default=DRIVER)
    parser.add_argument('--ref', help='Build this immutable source ref in a new managed external worktree')
    parser.add_argument('--sdk', type=Path, default=os.environ.get('N64_INST'))
    parser.add_argument('--tiny3d', type=Path, default=os.environ.get('TINY3D_DIR'))
    parser.add_argument('--libdragon-source', type=Path, default=os.environ.get('LIBDRAGON_SOURCE'))
    parser.add_argument('--python', type=Path, help='Select an already installed locked Python interpreter')
    parser.add_argument('--uv', type=Path, help='Select an already installed locked uv')
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--expanded', action='store_true', help='Build the expanded Firefight roster')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = args.checkout.resolve()
    if args.ref:
        if args.worker:
            parser.error('Historical worktree must be created before launching the worker')
        revision = git(root, 'rev-parse', '--verify', '--end-of-options', args.ref+'^{commit}')
        task = 'n64-'+revision[:10]+'-'+uuid.uuid4().hex[:6]
        shared = main_root(root)
        run([sys.executable, DRIVER/'tools/workspace.py', '--root', shared, 'worktree-add', task,
             '--owner', 'n64-bootstrap', '--base', revision, '--peak-gib', '0.25'])
        root = shared.with_name(shared.name+'-worktrees')/task
        # install-guards can project a shim onto an old ref. Keep the exact remote
        # source; this controller supplies the guard externally instead.
        changed = git(root, 'diff', '--name-only').splitlines()
        if set(changed) - {'port/n64/build.py'}:
            raise ValueError('Unexpected changes in new historical worktree')
        if changed:
            (root/'port/n64/build.py').write_bytes(subprocess.check_output(['git','-C',str(root),'show','HEAD:port/n64/build.py']))
    lock = json.loads((DRIVER/'port/n64/bootstrap-lock.json').read_text())
    cache = root/'build/n64-bootstrap'
    if args.worker:
        if not os.environ.get('HALO_WORKSPACE_PARENT_RUN'):
            parser.error('Worker requires an active storage reservation')
        worker(args, root, cache, lock)
        return
    # Account for downloads, staging, restored maps, Python, compiler scratch and
    # the complete ROM. Reusing verified inputs reduces the actual workload.
    peak = 1.5
    if not (root/'halo64-assets/.git').exists(): peak += 3.5
    if not args.sdk and not (cache/'toolchain/sdk.json').exists():
        peak += 14 if sys.platform=='darwin' else 2
    if not (cache/'python-env/venv/bin/python').exists(): peak += 0.5
    child = [sys.executable, Path(__file__), '--worker', '--checkout', root, '--jobs', str(args.jobs)]
    for flag in ('sdk','tiny3d','libdragon_source','python','uv','output_dir'):
        value = getattr(args, flag)
        if value is not None: child += ['--'+flag.replace('_','-'), value]
    if args.expanded: child += ['--expanded']
    with StorageRun(policy(root), cache, peak_gib=peak) as reservation:
        reservation.command(list(map(str, child)), cwd=root)


def build_worker():
    # Execute the target ref's build code verbatim. Only storage supervision is
    # injected, so refs predating the policy work too.
    argv = sys.argv[2:]; pos = argv.index('--checkout'); root = Path(argv[pos+1]).resolve()
    del argv[pos:pos+2]
    sys.path.insert(0, str(root/'port/n64'))
    spec = importlib.util.spec_from_file_location('target_n64_build', root/'port/n64/build.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module._storage_run_command = run_command
    sys.argv = [str(root/'port/n64/build.py'), *map(str, argv)]
    output = Path(argv[argv.index('--output-dir')+1])
    with StorageRun(policy(root), output, kind='n64-build'):
        module.main()


if __name__ == '__main__':
    try:
        if sys.argv[1:2] == ['--build-worker']: build_worker()
        else: main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit('n64: '+str(error))
