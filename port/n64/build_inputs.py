"""Restore immutable build inputs without modifying an asset revision.

Expanded caches are disposable. The compressed sources, sizes and hashes belong
to the private asset history. No local archive or another checkout is consulted.
"""
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import uuid

PACKAGE = 'assets/build-inputs/pr18'
MAPS = {'bloodgulch-decompressed.map', 'a30-decompressed.map',
        'b40-decompressed.map', 'ui.map', 'bloodgulch.map'}
MAX_CHUNK = 32 * 1024 * 1024


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for b in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def safe_name(name):
    p = PurePosixPath(name)
    if not isinstance(name, str) or not name or p.is_absolute() or '..' in p.parts or '\\' in name:
        raise ValueError('Unsafe input path: ' + str(name))
    return name


def verify(path, record):
    if not Path(path).is_file() or Path(path).stat().st_size != record['bytes'] or digest(path) != record['sha256']:
        raise ValueError('Missing or changed build input: ' + str(path))


class PackageReader:
    def __init__(self, *, bank=None, repository=None, revision=None):
        self.bank = Path(bank) if bank is not None else None
        self.repository, self.revision = repository, revision
        if self.bank is None and (repository is None or not re.fullmatch('[0-9a-f]{40}', revision or '')):
            raise ValueError('An immutable package source is required')

    def read(self, name):
        safe_name(name)
        if self.bank is not None:
            path = self.bank/name
            if path.is_symlink() or not path.resolve().is_relative_to(self.bank.resolve()):
                raise ValueError('Package input escapes the asset checkout: ' + name)
            return path.read_bytes()
        return subprocess.check_output(['git', '-C', str(self.repository), 'cat-file',
                                        'blob', self.revision + ':' + name])


def manifest(reader, expected_sha256):
    raw = reader.read(PACKAGE + '/manifest.json')
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('Build-input package does not match the lock file')
    m = json.loads(raw)
    if m.get('schema') != 1 or set(m.get('maps', {})) != MAPS:
        raise ValueError('Unsupported build-input manifest')
    for name, row in m['maps'].items():
        safe_name(name)
        if not isinstance(row.get('bytes'), int) or not 0 < row['bytes'] <= 512*1024*1024:
            raise ValueError('Invalid input size: ' + name)
        if not re.fullmatch('[0-9a-f]{64}', row.get('sha256', '')):
            raise ValueError('Invalid input checksum')
        if sum(p['raw_bytes'] for p in row['parts']) != row['bytes']:
            raise ValueError('Incomplete input chunks: ' + name)
        for p in row['parts']:
            safe_name(p['path'])
            if not isinstance(p['raw_bytes'], int) or not 0 < p['raw_bytes'] <= MAX_CHUNK:
                raise ValueError('Invalid chunk size')
            for key in ('sha256', 'raw_sha256'):
                if not re.fullmatch('[0-9a-f]{64}', p.get(key, '')):
                    raise ValueError('Invalid chunk checksum')
    return m


def restore(reader, cache, expected_sha256):
    """Publish a checksum-addressed cache only after checking every chunk."""
    m = manifest(reader, expected_sha256)
    final = Path(cache)/expected_sha256
    if final.is_symlink():
        raise ValueError('Input cache must not be a symlink')
    if final.exists():
        for name, row in m['maps'].items():
            verify(final/name, row)
        return final, m
    final.parent.mkdir(parents=True, exist_ok=True)
    temporary = final.with_name(final.name + '.partial-' + uuid.uuid4().hex)
    temporary.mkdir()
    for name, row in m['maps'].items():
        with (temporary/name).open('xb') as stream:
            for part in row['parts']:
                compressed = reader.read(PACKAGE + '/' + part['path'])
                if len(compressed) != part['bytes'] or hashlib.sha256(compressed).hexdigest() != part['sha256']:
                    raise ValueError('Corrupt compressed source chunk: ' + part['path'])
                with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as gz:
                    data = gz.read(part['raw_bytes'] + 1)
                if len(data) != part['raw_bytes'] or hashlib.sha256(data).hexdigest() != part['raw_sha256']:
                    raise ValueError('Corrupt expanded source chunk: ' + part['path'])
                stream.write(data)
        verify(temporary/name, row)
    (temporary/'receipt.json').write_text(json.dumps({'package_sha256': expected_sha256,
        'maps': {n: {k: r[k] for k in ('bytes', 'sha256')} for n, r in m['maps'].items()}}, indent=2)+'\n')
    temporary.rename(final)
    return final, m


def connect(root, restored, m):
    """Refuse conflicting files and links to old worktrees, including parents."""
    root, restored = Path(root).resolve(), Path(restored).resolve()
    if not restored.is_relative_to(root/'build'):
        raise ValueError('Restored inputs must belong to this checkout')
    pending = []
    for name, row in m['maps'].items():
        dest = (root/'halo64-assets/assets'/name if name.endswith('-decompressed.map')
                else root/'build/assets/halo-retail/maps'/name)
        if not dest.resolve().is_relative_to(root):
            raise ValueError('Build input points outside this checkout: ' + str(dest))
        if os.path.lexists(dest):
            verify(dest, row)
        else:
            pending.append((dest, restored/name))
    for dest, source in pending:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.symlink_to(os.path.relpath(source, dest.parent))


def enemy_bank(bank, output, m):
    """Assemble the expanded roster solely from the checked-out asset pin."""
    bank, output = Path(bank), Path(output)
    for name, row in m['enemy_bank'].items():
        if PurePosixPath(name).name != name:
            raise ValueError('Invalid enemy-bank filename')
        safe_name(row['path'])
        verify(bank/row['path'], row)
    if output.exists():
        for name, row in m['enemy_bank'].items():
            verify(output/name, row)
        return output
    output.mkdir(parents=True)
    for name, row in m['enemy_bank'].items():
        shutil.copyfile(bank/row['path'], output/name)
        verify(output/name, row)
    return output
