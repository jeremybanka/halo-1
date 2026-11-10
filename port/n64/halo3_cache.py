"""Small read-only reader for retail Xbox 360 Halo 3: ODST cache data.

File-format references: Gravemind2401/Reclaimer's Halo3 cache, render-model,
resource-layout and resource-gestalt definitions. Offsets are format facts;
this reader deliberately has no dependency on its Windows viewer.
"""
import mmap
import struct
import zlib
from pathlib import Path


class OdstCache:
    STRING_NAMESPACES = ((0x519, 0xD4B), (0, 0x519), (0, 0xBA3),
                         (0, 0xC3E), (0, 0xCE2), (0, 0xC96),
                         (0, 0xCF7), (0, 0xD26), (0, 0xD3E))

    def __init__(self, path):
        self.path = Path(path)
        self.handle = self.path.open('rb')
        self.data = mmap.mmap(self.handle.fileno(), 0, access=mmap.ACCESS_READ)
        if self.data[:8] != b'head\0\0\0\x0b':
            raise ValueError('Expected retail Xbox 360 gen-3 cache')
        self.build = self.string(284)
        if 'atlas' not in self.build:
            raise ValueError('Only retail ODST cache layouts are supported')
        self.section_offsets = self.unpack('4I', 1132)
        meta_offset = (self.u32(1164) + self.section_offsets[2]) & 0xFFFFFFFF
        self.magic = self.u32(744) - meta_offset
        self.index = self.pointer(self.u32(16))
        classes_count, classes_ptr, count, tags_ptr = self.unpack('4I', self.index)
        classes = self.pointer(classes_ptr)
        tags = self.pointer(tags_ptr)
        names_data = self.header_pointer(self.u32(696))
        names_index = self.header_pointer(self.u32(704))
        self.tags = []
        for i in range(count):
            cls, _, pointer = self.unpack('hhI', tags + i * 8)
            name_offset = self.i32(names_index + i * 4)
            self.tags.append({'id': i,
                'class': self.data[classes + cls * 16:classes + cls * 16 + 4].decode('ascii') if 0 <= cls < classes_count else '',
                'path': self.string(names_data + name_offset) if name_offset >= 0 else '',
                'offset': self.pointer(pointer) if cls >= 0 else 0})
        self.by_class = {}
        for tag in self.tags:
            self.by_class.setdefault(tag['class'], []).append(tag)
        nstrings = self.u32(344)
        string_index = self.header_pointer(self.u32(352))
        string_data = self.header_pointer(self.u32(356))
        self.strings = [self.string(string_data + off) if off >= 0 else ''
                        for off in self.unpack(f'{nstrings}i', string_index)]
        self.page_cache = {}

    def close(self):
        self.data.close()
        self.handle.close()

    def unpack(self, fmt, offset):
        if offset < 0 or offset + struct.calcsize('>' + fmt) > len(self.data):
            raise ValueError(f'Cache read out of bounds at {offset:#x}: {fmt}')
        return struct.unpack_from('>' + fmt, self.data, offset)

    def u32(self, offset):
        return self.unpack('I', offset)[0]

    def i32(self, offset):
        return self.unpack('i', offset)[0]

    def pointer(self, value):
        return value - self.magic

    def header_pointer(self, value):
        return (value + self.section_offsets[0]) & 0xFFFFFFFF

    def string(self, offset):
        if not 0 <= offset < len(self.data):
            raise ValueError('String pointer out of bounds')
        end = self.data.find(b'\0', offset, min(offset + 4096, len(self.data)))
        if end < 0:
            raise ValueError('Unterminated cache string')
        return self.data[offset:end].decode('utf8', errors='replace')

    def sid(self, value):
        index, namespace = value & 0xFFFF, (value >> 16) & 0xFF
        if namespace >= len(self.STRING_NAMESPACES):
            raise ValueError('Unknown string-id namespace')
        minimum, start = self.STRING_NAMESPACES[namespace]
        index = index if index < minimum else index - minimum + start
        return self.strings[index]

    def block(self, offset, stride):
        count, ptr, _ = self.unpack('iII', offset)
        if count < 0 or count > 1_000_000:
            raise ValueError(f'Invalid block count {count}')
        if not count:
            return []
        start = self.pointer(ptr)
        if start < 0 or start + count * stride > len(self.data):
            raise ValueError('Tag block out of bounds')
        return [start + i * stride for i in range(count)]

    def tag_ref(self, offset):
        ident = self.u32(offset + 12)
        return None if ident == 0xFFFFFFFF else self.tags[ident & 0xFFFF]

    def resource_info(self, ident):
        zone = self.by_class['zone'][0]['offset']
        play = self.by_class['play'][0]['offset']
        entries = self.block(zone + 88, 64)
        entry = entries[ident & 0xFFFF]
        fixup_offset, fixup_size = self.unpack('II', entry + 20)
        fixup_start = self.pointer(self.u32(zone + 328)) + fixup_offset
        fixups = [self.u32(p + 4) & 0x0FFFFFFF for p in self.block(entry + 40, 8)]
        segment_id = self.unpack('h', entry + 34)[0]
        if segment_id < 0:
            raise ValueError('Resource has no data segment')
        segment = self.block(play + 48, 16)[segment_id]
        pri, sec, pri_offset, sec_offset = self.unpack('hhii', segment)
        pages = self.block(play + 24, 88)
        page_index, segment_offset = (sec, sec_offset) if sec >= 0 else (pri, pri_offset)
        if page_index < 0 or segment_offset < 0:
            raise ValueError('Missing resource page')
        page = pages[page_index]
        if self.i32(page + 8) < 0 or not self.u32(page + 12):
            page_index, segment_offset = pri, pri_offset
            page = pages[page_index]
        shared_index = self.unpack('h', page + 4)[0]
        path = self.path
        if shared_index >= 0:
            shared = self.block(play + 12, 264)[shared_index]
            name = self.string(shared).replace('\\', '/').split('/')[-1]
            path = self.path.with_name(name)
        return {'entry': entry, 'fixup_start': fixup_start,
                'fixup_size': fixup_size, 'fixups': fixups,
                'path': path, 'page': page_index,
                'segment_offset': segment_offset,
                'data_offset': self.u32(page + 8),
                'compressed_size': self.u32(page + 12),
                'decompressed_size': self.u32(page + 16)}

    def resource(self, ident):
        info = self.resource_info(ident)
        key = (info['path'], info['page'])
        if key not in self.page_cache:
            with info['path'].open('rb') as handle:
                handle.seek(1136)
                base = struct.unpack('>I', handle.read(4))[0]
                handle.seek(base + info['data_offset'])
                compressed = handle.read(info['compressed_size'])
            if len(compressed) != info['compressed_size']:
                raise ValueError('Truncated resource page')
            data = zlib.decompress(compressed, -15)
            if len(data) != info['decompressed_size']:
                raise ValueError('Resource decompressed size mismatch')
            self.page_cache[key] = data
        return info, self.page_cache[key][info['segment_offset']:]
