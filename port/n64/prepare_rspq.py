#!/usr/bin/env python3
"""Generate a local libdragon CPU queue override without modifying the SDK.

Only the low-priority allocation size and optional CPU-side profiling change.
The original queue switch, signal, synchronization and RSP microcode remain.
Link the generated object before libdragon.a to replace its rspq.o member.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Unsupported libdragon rspq.c: expected one patch site: ' + old[:70])
    return text.replace(old, new, 1)


def generate(source, sdk, output, buffer_kib):
    if buffer_kib not in (2, 4, 8, 16, 32):
        raise ValueError('Queue buffer must be 2, 4, 8, 16 or 32 KiB')
    headers = {}
    for name in ('rspq.h', 'rspq_constants.h', 'rdpq_constants.h'):
        original = (source / 'include' / name).read_bytes()
        installed = (sdk / 'mips64-elf/include' / name).read_bytes()
        if original != installed:
            raise ValueError(f'Installed SDK and source disagree: {name}')
        headers[name] = hashlib.sha256(original).hexdigest()
    constants = (source / 'include/rspq_constants.h').read_text()
    match = re.search(r'^#define RSPQ_DRAM_LOWPRI_BUFFER_SIZE\s+(\w+)', constants, re.M)
    if not match or int(match[1], 0) != 512:
        raise ValueError('Unsupported libdragon baseline: expected 2 KiB low-priority buffers')
    source_path = source / 'src/rspq/rspq.c'
    original = source_path.read_text()
    result = replace_once(original,
        'rspq_init_context(&lowpri, RSPQ_DRAM_LOWPRI_BUFFER_SIZE);',
        f'rspq_init_context(&lowpri, {buffer_kib * 256}); /* Local {buffer_kib} KiB queue. */')
    result = replace_once(result, '#include "rspq_internal.h"',
        '#include "rspq_internal.h"\n#include "rspq_metrics.h"')
    metrics = '''
/* Local instrumentation; never changes queue synchronization. */
static bg_rspq_metrics bg_queue_metrics;
void bg_rspq_get_metrics(bg_rspq_metrics *result) {
    *result = bg_queue_metrics;
    if (lowpri.buffers[lowpri.buf_idx]) {
        const volatile uint32_t *cursor = rspq_ctx == &lowpri ? rspq_cur_pointer : lowpri.cur;
        result->words += cursor - (const uint32_t*)lowpri.buffers[lowpri.buf_idx];
    }
}

'''
    result = replace_once(result, '/** @brief Buffers that hold outgoing RDP commands (generated via RSP). */',
        metrics + '/** @brief Buffers that hold outgoing RDP commands (generated via RSP). */')
    result = replace_once(result,
        '    // We are about to switch buffer. If the debugging engine is activate,',
        '''#ifdef BG_PROFILE
    if (rspq_ctx == &lowpri) {
        bg_queue_metrics.words += rspq_cur_pointer - (uint32_t*)lowpri.buffers[lowpri.buf_idx] + 2;
        bg_queue_metrics.switches++;
    }
#endif

    // We are about to switch buffer. If the debugging engine is activate,''')
    result = replace_once(result,
        '    if (!(*SP_STATUS & rspq_ctx->sp_status_bufdone)) {\n        rspq_flush_internal();',
        '''    if (!(*SP_STATUS & rspq_ctx->sp_status_bufdone)) {
#ifdef BG_PROFILE
        uint64_t bg_wait_started = get_ticks_us();
#endif
        rspq_flush_internal();''')
    result = replace_once(result,
        '''            if (*SP_STATUS & rspq_ctx->sp_status_bufdone)
                break;
        }
    }
    MEMORY_BARRIER();''',
        '''            if (*SP_STATUS & rspq_ctx->sp_status_bufdone)
                break;
        }
#ifdef BG_PROFILE
        if (rspq_ctx == &lowpri) {
            bg_queue_metrics.stall_us += get_ticks_us() - bg_wait_started;
            bg_queue_metrics.waits++;
        }
#endif
    }
    MEMORY_BARRIER();''')
    output.mkdir(parents=True, exist_ok=True)
    generated = output / 'rspq_override.c'
    generated.write_text(result)
    report = {
        'source': str(source_path.resolve()),
        'source_sha256': hashlib.sha256(original.encode()).hexdigest(),
        'generated_sha256': hashlib.sha256(result.encode()).hexdigest(),
        'matching_headers': headers,
        'low_priority_buffer_count': 2,
        'low_priority_buffer_bytes': buffer_kib * 1024,
        'additional_ram_bytes': (buffer_kib - 2) * 2048,
        'rdp_dynamic_buffers_unchanged': True,
        'rsp_microcode_unchanged': True,
    }
    (output / 'provenance.json').write_text(json.dumps(report, indent=2) + '\n')
    return generated


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--sdk', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--buffer-kib', required=True, type=int)
    args = parser.parse_args()
    print(generate(args.source, args.sdk, args.output, args.buffer_kib))
