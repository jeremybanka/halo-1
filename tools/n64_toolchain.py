"""Locked SDK/Python setup. Every download and build stays under the cache."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import uuid


def run(argv, **kwargs):
    print('+ ' + ' '.join(map(str, argv)), flush=True)
    subprocess.run(list(map(str, argv)), check=True, **kwargs)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()


def download(record, cache):
    if not record['url'].startswith('https://'):
        raise ValueError('Dependency downloads must use HTTPS')
    cache = Path(cache); cache.mkdir(parents=True, exist_ok=True)
    target = cache/(record['sha256'] + '-' + record['filename'])
    if target.exists():
        if sha(target) != record['sha256']:
            raise ValueError('Corrupt dependency archive: ' + str(target))
        return target
    temporary = target.with_name(target.name + '.partial-' + uuid.uuid4().hex)
    run(['curl', '--fail', '--location', '--silent', '--show-error', '--proto', '=https',
         '--output', temporary, record['url']])
    if sha(temporary) != record['sha256']:
        raise ValueError('Dependency checksum mismatch: ' + record['filename'])
    temporary.rename(target)
    return target


def unpack(archive, target):
    target = Path(target)
    target.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive) as t:
        # Reject escaping paths, external symlinks and device files.
        t.extractall(target, filter='data')
    return target


def deb_payload(archive, target):
    """Read the small ar container directly; no system package install needed."""
    target = Path(target); target.mkdir(exist_ok=False)
    with Path(archive).open('rb') as stream:
        if stream.read(8) != b'!<arch>\n':
            raise ValueError('Invalid compiler package')
        while header := stream.read(60):
            if len(header) != 60 or header[58:] != b'`\n':
                raise ValueError('Invalid compiler package member')
            size = int(header[48:58].strip())
            name = header[:16].decode().strip().rstrip('/')
            if name.startswith('data.tar.') and '/' not in name and size > 0:
                output = target/name
                with output.open('xb') as f:
                    left = size
                    while left:
                        b = stream.read(min(left, 1024*1024))
                        if not b: raise ValueError('Truncated compiler package')
                        f.write(b); left -= len(b)
                return unpack(output, target/'files')
            stream.seek(size + (size % 2), 1)
    raise ValueError('Compiler package has no payload')


def source(record, cache, downloads):
    target = Path(cache)/record['revision']
    marker = target/'.halo64-source.json'
    if marker.exists():
        if json.loads(marker.read_text()) != record:
            raise ValueError('Dependency source lock changed')
        return target
    if target.exists():
        raise ValueError('Incomplete dependency source; preserve it and choose a fresh cache: ' + str(target))
    archive = download(record['archive'], downloads)
    stage = unpack(archive, target.with_name(target.name + '.partial-' + uuid.uuid4().hex))
    children = list(stage.iterdir())
    if len(children) != 1 or not children[0].is_dir():
        raise ValueError('Expected one source archive directory')
    target.parent.mkdir(parents=True, exist_ok=True)
    children[0].rename(target)
    marker.write_text(json.dumps(record, sort_keys=True) + '\n')
    return target


def revision(path):
    marker = Path(path)/'.halo64-source.json'
    if marker.is_file():
        return json.loads(marker.read_text())['revision']
    return subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()


def validate_sdk(sdk, libdragon, tiny, lock):
    version = subprocess.check_output([str(sdk/'bin/mips64-elf-gcc'), '-dumpfullversion'], text=True).strip()
    if version != lock['gcc'] or revision(libdragon) != lock['libdragon']['revision'] or revision(tiny) != lock['tiny3d']['revision']:
        raise ValueError('SDK does not match bootstrap-lock.json')
    for source_dir in (libdragon, tiny):
        if not (source_dir/'.halo64-source.json').exists():
            if subprocess.check_output(['git', '-C', str(source_dir), 'diff', 'HEAD', '--name-only'], text=True).strip():
                raise ValueError('SDK dependency source has local changes: '+str(source_dir))
    files = [sdk/'bin'/n for n in ('mips64-elf-gcc', 'mkdfs', 'n64tool', 'n64sym', 'n64elfcompress')]
    files += [sdk/'mips64-elf/lib'/n for n in ('libdragon.a', 'libdragonsys.a', 'libc.a', 'libm.a')]
    files += [tiny/'build/libt3d.a']
    return {str(p): sha(p) for p in files}


def toolchain(lock, cache, *, sdk=None, libdragon=None, tiny=None, jobs=2):
    if any(p is not None for p in (sdk, libdragon, tiny)):
        if not all(p is not None for p in (sdk, libdragon, tiny)):
            raise ValueError('Supply --sdk, --libdragon-source and --tiny3d together (or their environment variables)')
        paths = tuple(Path(p).resolve() for p in (sdk, libdragon, tiny))
        return (*paths, validate_sdk(*paths, lock))
    cache = Path(cache); downloads = cache/'downloads'
    receipt = cache/'sdk.json'
    if receipt.is_file():
        record = json.loads(receipt.read_text())
        paths = tuple(Path(record[n]) for n in ('sdk', 'libdragon', 'tiny3d'))
        hashes = validate_sdk(*paths, lock)
        if hashes != record['files']:
            raise ValueError('Managed SDK was modified')
        return (*paths, hashes)
    sdk = cache/'sdk'
    libdragon = source(lock['libdragon'], cache/'sources', downloads)
    tiny = source(lock['tiny3d'], cache/'sources', downloads)
    env = {**os.environ, 'N64_INST': str(sdk), 'JOBS': str(jobs),
           'BUILD_PATH': str(cache/'compiler-build'), 'DOWNLOAD_PATH': str(downloads)}
    host = platform.system().lower() + '-' + ('arm64' if platform.machine() in ('arm64', 'aarch64') else 'x86_64')
    if host in lock['compiler_packages']:
        archive = download(lock['compiler_packages'][host], downloads)
        stage = cache/'compiler-package'
        files = deb_payload(archive, stage)
        candidates = list(files.rglob('bin/mips64-elf-gcc'))
        if len(candidates) != 1:
            raise ValueError('Compiler package has an unexpected layout')
        candidates[0].parent.parent.rename(sdk)
    elif platform.system() == 'Darwin':
        # OS packages are a documented prerequisite, never silently installed.
        for package in ('gmp', 'mpfr', 'libmpc', 'gsed', 'isl', 'make', 'python3', 'texinfo'):
            run(['brew', '--prefix', package], stdout=subprocess.DEVNULL)
        for record in lock['compiler_sources']:
            path = download(record, downloads)
            named = downloads/record['filename']
            if not named.exists():
                os.link(path, named)
        original = (libdragon/'tools/build-toolchain.sh').read_text()
        install = '    brew install -q gmp mpfr libmpc gsed isl make python3 texinfo'
        if original.count(install) != 1:
            raise ValueError('Pinned compiler setup script changed')
        script = cache/'build-compiler.sh'
        script.write_text(original.replace(install, '    : # host prerequisites checked by bootstrap'))
        run(['bash', script], cwd=cache, env=env)
    else:
        raise ValueError('Unsupported host for automatic SDK setup: ' + host)
    run(['make', '-j'+str(jobs), 'install-mk'], cwd=libdragon, env=env)
    run(['make', '-j'+str(jobs), 'libdragon', 'tools'], cwd=libdragon, env=env)
    run(['make', 'install', 'tools-install'], cwd=libdragon, env=env)
    run(['make', '-j'+str(jobs)], cwd=tiny, env=env)
    hashes = validate_sdk(sdk, libdragon, tiny, lock)
    receipt.write_text(json.dumps({'sdk': str(sdk), 'libdragon': str(libdragon),
                                  'tiny3d': str(tiny), 'files': hashes}, indent=2)+'\n')
    return sdk, libdragon, tiny, hashes


def python_environment(lock, requirements, cache, *, python=None, uv=None):
    cache = Path(cache); cache.mkdir(parents=True, exist_ok=True)
    if python:
        p = Path(python).resolve()
        actual = subprocess.check_output([str(p), '-c', 'import sys; print(".".join(map(str,sys.version_info[:3])))'], text=True).strip()
        if actual != lock['python']:
            raise ValueError('Python must be ' + lock['python'])
    else:
        p = None
    if uv:
        u = Path(uv).resolve()
        version = subprocess.check_output([str(u), '--version'], text=True).split()[1]
        if version != lock['uv_version']:
            raise ValueError('uv must be ' + lock['uv_version'])
    else:
        host = platform.system().lower() + '-' + ('arm64' if platform.machine() in ('arm64','aarch64') else 'x86_64')
        archive = download(lock['uv_packages'][host], cache/'downloads')
        directory = cache/'uv'
        if not directory.exists():
            unpack(archive, directory)
        u = next(directory.rglob('uv'))
    env = {**os.environ, 'UV_CACHE_DIR': str(cache/'uv-cache'),
           'UV_PYTHON_INSTALL_DIR': str(cache/'python'), 'UV_PYTHON_BIN_DIR': str(cache/'bin')}
    if p is None:
        run([u, 'python', 'install', '--no-bin', lock['python']], env=env)
        p = Path(subprocess.check_output([str(u), 'python', 'find', '--managed-python', lock['python']], env=env, text=True).strip())
    venv = cache/'venv'
    if not (venv/'bin/python').exists():
        run([u, 'venv', '--python', p, '--no-python-downloads', venv], env=env)
    run([u, 'pip', 'install', '--python', venv/'bin/python', '--require-hashes', '--no-deps',
         '-r', Path(requirements).with_name('requirements-build.lock.txt')], env=env)
    run([u, 'pip', 'sync', '--python', venv/'bin/python', '--require-hashes',
         '--no-build-isolation', requirements], env=env)
    return venv/'bin/python'
