#!/usr/bin/env python3
"""Prepare original Blam storage sources with bounded N64/host ABI adaptations.

Original files stay unchanged. Every replacement is checked, and source hashes
and adaptations are recorded beside the generated sources in ignored build/.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]


def prepare(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    records=[]
    for name in ('data.c','data.h','memory_pool.c','memory_pool.h'):
        source=ROOT/'source/memory'/name
        text=source.read_text();original=text;changes=[]
        def replace(before,after,count=1):
            nonlocal text
            actual=text.count(before)
            if actual!=count:raise RuntimeError(f'{source}: expected {count} occurrences, found {actual}: {before}')
            text=text.replace(before,after);changes.append({'before':before,'after':after,'count':count})
        if name=='data.h':
            replace('#include "tag_files.h"','#define TAG_STRING_LENGTH 31')
            replace('typedef char data_iterator_size_assert[\n\tsizeof(struct data_iterator) == 0x10 ? 1 : -1];',
                    '#if UINTPTR_MAX == UINT32_MAX\ntypedef char data_iterator_size_assert[\n\tsizeof(struct data_iterator) == 0x10 ? 1 : -1];\n#endif')
        elif name=='data.c':
            replace('csstrncpy((char *)&data->next_identifier, data->name, sizeof(data->next_identifier));',
                    'data->next_identifier = (short)((uint8_t)data->name[0] | ((uint16_t)(uint8_t)data->name[1] << 8));')
            replace('header->identifier<<16','((uint32_t)(uint16_t)header->identifier<<16)',4)
            replace('result = identifier<<16','result = (uint32_t)(uint16_t)identifier<<16')
            replace('header = (struct datum_header *)((byte *)header-data->size);\n\t\t}\n\t\twhile (absolute_index-->=0);',
                    'if (!absolute_index) break;\n\t\t\theader = (struct datum_header *)((byte *)header-data->size);\n\t\t}\n\t\twhile (--absolute_index>=0);')
        elif name=='memory_pool.c':
            # Native pointers are 8-byte aligned in host tests. N64 remains 4.
            replace('actual_size&3','actual_size&BLAM_POOL_ALIGNMENT_MASK')
            replace('(actual_size|3)+1','(actual_size|BLAM_POOL_ALIGNMENT_MASK)+1')
            replace('size&3','size&BLAM_POOL_ALIGNMENT_MASK')
            replace('(size|3)+1','(size|BLAM_POOL_ALIGNMENT_MASK)+1')
        target=output/name
        target.write_text('/* Generated from '+str(source.relative_to(ROOT))+'; see source-manifest.json. */\n'+text)
        records.append({'source':str(source.relative_to(ROOT)),
                        'sha256':hashlib.sha256(original.encode()).hexdigest(),'adaptations':changes})
    (output/'cseries.h').write_text('''#ifndef BLAM_N64_CORE_CSERIES_H
#define BLAM_N64_CORE_CSERIES_H
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
typedef unsigned char byte;
typedef unsigned char boolean;
#define TRUE 1
#define FALSE 0
#define NONE (-1)
#define BLAM_POOL_ALIGNMENT_MASK ((long)sizeof(void *)-1)
#define csmemset memset
#define csmemcpy memcpy
#define csmemmove memmove
#define csstrncpy strncpy
extern char blam_core_temporary[256];
#define temporary blam_core_temporary
#define csprintf(dst,...) snprintf((dst),256,__VA_ARGS__)
void blam_core_assert(const char *file,int line,const char *expression);
#define match_assert(file,line,condition) do { if (!(condition)) blam_core_assert((file),(line),#condition); } while (0)
#define match_vassert(file,line,condition,message) do { if (!(condition)) blam_core_assert((file),(line),#condition); } while (0)
#define match_malloc(file,line,size) malloc(size)
#define match_free(file,line,pointer) free(pointer)
#endif
''')
    source=ROOT/'source/objects/objects.c';text=source.read_text()
    # Exact complete functions, including their original static declarations.
    begin=text.index('static long object_header_new(\n')
    end=text.index('boolean object_header_block_allocate(\n',begin)
    fragment=text[begin:end]
    if fragment.count('static long object_header_new(')!=1 or fragment.count('static void object_header_delete(')!=1:
        raise RuntimeError('original object header source boundaries changed')
    (output/'object_headers.c').write_text('/* Exact functions from source/objects/objects.c. */\n'+fragment)
    records.append({'source':str(source.relative_to(ROOT)),
                    'sha256':hashlib.sha256(text.encode()).hexdigest(),
                    'retained_functions':['object_header_new','object_header_delete'],
                    'adaptations':[]})
    (output/'source-manifest.json').write_text(json.dumps(records,indent=2)+'\n')
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'build/n64/blam-core')
    print(prepare(parser.parse_args().output))
