"""Verify the emitted FP vertex loads fit shared segmented animation buffers.

Tiny3D encodes the segment at bit 26. Its RSP addresses the segment-table
entry with address>>24, adds that entry, then DMA uses the low 24 bits.
Check every generated batch against the exact direct-address equivalent,
including the highest possible base addresses in 4 MiB and 8 MiB RDRAM.
"""
from runtime_source import read_runtime
import argparse
from pathlib import Path
import re


def verify(path):
    source = read_runtime(path)
    capacity = int(re.search(r'bg_fp_max_vertices\s*=\s*(\d+)', source)[1])
    body = re.search(r'bg_fp_models\[BG_FP_WEAPONS\]\s*=\s*\{(.*?)\n\};', source, re.S)[1]
    models = re.findall(r'\{(\w+),(\d+),[^,]+,(\w+),(\w+),(\d+),(\d+)\}', body)
    assert len(models) == 9 and capacity % 2 == 0
    checked = 0
    for name, count, batches_name, _, batch_count, _ in models:
        count, batch_count = int(count), int(batch_count)
        assert 0 < count <= capacity
        batch_body = re.search(r'\b' + batches_name + r'\[\]\s*=\s*\{(.*?)\n\};', source, re.S)[1]
        batches = [tuple(map(int, row)) for row in re.findall(r'\{(\d+),(\d+),(\d+),(\d+)\}', batch_body)]
        assert len(batches) == batch_count
        for first, vertices, index_first, indices in batches:
            padded = (vertices + 1) & ~1
            assert first % 2 == 0 and index_first % 4 == 0
            assert 0 < padded <= 60 and 0 < indices <= 120 and indices % 3 == 0
            assert first + padded <= count <= capacity, name
            # T3DVertPacked is 32 bytes per pair, so first/2 scales by 32.
            relative = first * 16
            encoded = ((1 << 26) + relative) & 0x1fffffff
            assert encoded >> 24 == 4  # byte offset of SEGMENT_TABLE[1]
            for memory_size in (4 << 20, 8 << 20):
                last_base = memory_size - capacity * 16
                bases = [0, 16, last_base]
                bases.extend(range(0x10000, last_base, 0x1fff0))
                for base in bases:
                    assert base % 16 == 0
                    resolved = (encoded + base) & 0xffffff
                    assert resolved == base + relative
                    assert resolved % 16 == 0
                    assert resolved + padded * 16 <= base + capacity * 16 <= memory_size
                    checked += 1
    return len(models), checked


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('generated', nargs='?', type=Path,
                        default=Path('build/n64/generated/firstperson_data.c'))
    args = parser.parse_args()
    models, checked = verify(args.generated)
    print(f'Segmented FP addressing: {models} slots, {checked} exact batch/address checks; '
          'all DMA ranges fit 4 MiB/8 MiB buffers')
