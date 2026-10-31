#!/usr/bin/env python3
"""List or selectively extract files from an owned Xbox 360 GOD data directory.

Unpack the archive's Data0000, Data0001, ... files into a local directory
first. Reads SVOD's interleaved hash tables directly; no intermediate ISO is
needed. Missing/truncated parts and unsafe directory entries fail explicitly.
The SVOD layout is documented by iliazeus/iso2god-rs, src/god/mod.rs.
"""
import argparse
import json
import struct
from pathlib import Path, PurePosixPath


class SvodReader:
    BLOCK = 0x1000
    GROUP_DATA = 0xCC * BLOCK
    PART_DATA = 0xA1C4 * BLOCK

    def __init__(self, directory):
        self.directory = Path(directory)
        self.handles = {}

    def close(self):
        for handle in self.handles.values():
            handle.close()
        self.handles.clear()

    def read_at(self, offset, size):
        if offset < 0 or size < 0:
            raise ValueError('Negative SVOD read')
        result = bytearray()
        while size:
            part, relative = divmod(offset, self.PART_DATA)
            group, within = divmod(relative, self.GROUP_DATA)
            count = min(size, self.GROUP_DATA - within,
                        self.PART_DATA - relative)
            physical = 2 * self.BLOCK + group * (self.GROUP_DATA + self.BLOCK) + within
            if part not in self.handles:
                path = self.directory / f'Data{part:04d}'
                self.handles[part] = path.open('rb')
            handle = self.handles[part]
            handle.seek(physical)
            chunk = handle.read(count)
            if len(chunk) != count:
                raise ValueError(f'Truncated Data{part:04d} at {physical:#x}')
            result.extend(chunk)
            offset += count
            size -= count
        return bytes(result)

    def files(self):
        descriptor = self.read_at(32 * 2048, 2048)
        signature = b'MICROSOFT*XBOX*MEDIA'
        if not descriptor.startswith(signature) or descriptor[-20:] != signature:
            raise ValueError('Missing XDVDFS volume descriptor in SVOD data')
        sector, size = struct.unpack_from('<II', descriptor, 20)
        return self._directory(sector, size, PurePosixPath(), set())

    def _directory(self, sector, size, parent, ancestors):
        if size <= 0 or size > 16 * 1024 * 1024 or sector in ancestors:
            raise ValueError(f'Invalid or cyclic directory: {parent}')
        data = self.read_at(sector * 2048, size)
        visited = set()

        def node(offset):
            if offset in visited or offset + 14 > len(data):
                raise ValueError(f'Invalid directory tree: {parent} at {offset}')
            visited.add(offset)
            left, right, start, length, attrs, name_length = struct.unpack_from('<HHIIBB', data, offset)
            if offset + 14 + name_length > len(data):
                raise ValueError('Truncated directory entry')
            raw = data[offset + 14:offset + 14 + name_length]
            name = raw.decode('ascii')
            if not name or name in ('.', '..') or '/' in name or '\\' in name or '\0' in name:
                raise ValueError('Unsafe XDVDFS filename')
            if left:
                yield from node(left * 4)
            path = parent / name
            if attrs & 0x10:
                yield from self._directory(start, length, path, ancestors | {sector})
            else:
                yield {'path': path.as_posix(), 'sector': start, 'size': length}
            if right:
                yield from node(right * 4)

        yield from node(0)

    def extract(self, entry, output):
        root = Path(output).resolve()
        target = root.joinpath(*PurePosixPath(entry['path']).parts)
        if not target.resolve().is_relative_to(root):
            raise ValueError('Extraction target escapes output directory')
        target.parent.mkdir(parents=True, exist_ok=True)
        remaining = entry['size']
        offset = entry['sector'] * 2048
        temporary = target.with_name(target.name + '.partial')
        try:
            with temporary.open('wb') as handle:
                while remaining:
                    count = min(remaining, 1024 * 1024)
                    handle.write(self.read_at(offset, count))
                    remaining -= count
                    offset += count
            temporary.replace(target)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data_directory', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--file', action='append', default=[], help='Exact volume-relative file to extract; repeatable')
    parser.add_argument('--manifest', type=Path)
    args = parser.parse_args()
    if args.file and args.output is None:
        parser.error('--file requires --output')
    reader = SvodReader(args.data_directory)
    try:
        entries = list(reader.files())
        if args.manifest:
            args.manifest.parent.mkdir(parents=True, exist_ok=True)
            args.manifest.write_text(json.dumps(entries, indent=2) + '\n')
        requested = {name.casefold() for name in args.file}
        available = {entry['path'].casefold(): entry for entry in entries}
        missing = requested - available.keys()
        if missing:
            raise ValueError('Missing volume files: ' + ', '.join(sorted(missing)))
        for entry in entries:
            if not requested:
                print(f"{entry['size']:12,d}  {entry['path']}")
            elif entry['path'].casefold() in requested:
                print('Extracted', reader.extract(entry, args.output), flush=True)
    finally:
        reader.close()


if __name__ == '__main__':
    main()
