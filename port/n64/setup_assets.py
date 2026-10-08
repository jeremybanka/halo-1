#!/usr/bin/env python3
"""Connect a private Halo64 asset checkout to the established N64 build paths."""
import argparse
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BANK = ROOT/'halo64-assets'
BUILD = ROOT/'build/n64'
NAMES = ('assets', 'generated', 'frontend-files')


def verify_bank():
    manifest = json.loads((BANK/'bank-manifest.json').read_text())
    for item in manifest['files']:
        p = BANK/item['path']
        if not p.is_file() or p.stat().st_size != item['bytes'] or hashlib.sha256(p.read_bytes()).hexdigest() != item['sha256']:
            raise RuntimeError('Asset snapshot mismatch: '+item['path'])
    return len(manifest['files'])


def connect_assets(required=True, archive_existing=None):
    if not all((BANK/name).is_dir() for name in NAMES):
        if required:
            raise RuntimeError('Initialize the private bank: git submodule update --init halo64-assets')
        return False
    BUILD.mkdir(parents=True, exist_ok=True)
    pending = []
    for name in NAMES:
        path, target = BUILD/name, BANK/name
        if path.is_symlink():
            if path.resolve() != target.resolve():
                raise RuntimeError('Unexpected asset symlink: '+str(path))
            continue
        if path.exists():
            if archive_existing is None:
                raise RuntimeError('Existing asset directory must be archived explicitly: '+str(path))
            destination = Path(archive_existing)/name
            if destination.exists():
                raise RuntimeError('Refusing to overwrite previous asset archive: '+str(destination))
            # Validate before any move; preserve additional raw caches/logs too.
            manifest = json.loads((BANK/'bank-manifest.json').read_text())
            for item in manifest['files']:
                if not item['path'].startswith(name+'/'):
                    continue
                old = path/item['path'].split('/',1)[1]
                if not old.is_file() or hashlib.sha256(old.read_bytes()).hexdigest() != item['sha256']:
                    raise RuntimeError('Existing bank differs; refusing adoption: '+str(old))
            pending.append((path, target, destination))
        else:
            pending.append((path, target, None))
    for path, target, destination in pending:
        if destination:
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.rename(path, destination)
        path.symlink_to(target, target_is_directory=True)
    # Locally retained source cache links are ignored by the private repository.
    source_caches = BUILD/'_asset-snapshots/initial/assets'
    if source_caches.is_dir():
        for source in source_caches.rglob('*.map'):
            dest = BANK/'assets'/source.relative_to(source_caches)
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.symlink_to(source.resolve())
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive-existing', type=Path, help='Preserve matching existing directories here before linking')
    parser.add_argument('--verify', action='store_true', help='Verify every file against the asset snapshot manifest')
    args = parser.parse_args()
    connect_assets(archive_existing=args.archive_existing)
    if args.verify:
        print('Verified',verify_bank(),'private asset files')
    print('Connected private Halo64 asset bank to',BUILD)


if __name__ == '__main__':
    main()
