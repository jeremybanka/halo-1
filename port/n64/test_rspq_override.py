"""Check the real SDK's 2 KiB/16 KiB override differs only in allocation size."""
import argparse
from pathlib import Path
import tempfile

from prepare_rspq import generate, replace_once


def verify(source, sdk):
    with tempfile.TemporaryDirectory(prefix='halo-rspq-') as temporary:
        root = Path(temporary)
        baseline = generate(source, sdk, root/'baseline', 2).read_text()
        candidate = generate(source, sdk, root/'candidate', 16).read_text()
        assert baseline.replace(
            'rspq_init_context(&lowpri, 512); /* Local 2 KiB queue. */',
            'rspq_init_context(&lowpri, 4096); /* Local 16 KiB queue. */') == candidate
        original = (source/'src/rspq/rspq.c').read_text()
        for begin, end in (
                ('    RSP_WAIT_LOOP(200) {\n            if (*SP_STATUS', '\n        }'),
                ('    // Switch current buffer', '\n    rspq_flush_internal();'),
                ('void rspq_syncpoint_wait(', '\nvoid rspq_wait('),
                ('void rspq_block_free(', '\nvoid rspq_block_run(')):
            start = original.index(begin)
            finish = original.index(end, start) + len(end)
            assert original[start:finish] in candidate, begin
        assert candidate.count('malloc_uncached(RDPQ_DYNAMIC_BUFFER_SIZE)') == 2
        assert candidate.count('bg_queue_metrics.stall_us +=') == 1
        for invalid in ('absent', 'xx'):
            try:
                replace_once('xx xx', invalid, 'replacement')
            except ValueError:
                pass
            else:
                raise AssertionError('Ambiguous or missing patch site accepted')
    print('Queue overrides differ only by 2/16 KiB allocation; synchronization, '
          'RDP allocation and block lifetimes preserved; patch-site guards pass')


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=root.parent/'n64-2048/.build/libdragon-src')
    parser.add_argument('--sdk', type=Path, default=root.parent/'n64-2048/.build/libdragon')
    args = parser.parse_args()
    verify(args.source, args.sdk)
