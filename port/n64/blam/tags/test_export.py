#!/usr/bin/env python3
"""Validate every exported scalar against its original little-endian cache byte range."""
import argparse,hashlib,json,struct,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]


def test(output):
    manifest=json.loads((output/'manifest.json').read_text());bank=(output/'gameplay-tags.bgtg').read_bytes()
    magic,version,count,records,reloc_count,reloc_offset,payload_offset,payload_size=struct.unpack_from('>8I',bank)
    assert magic==0x42475447 and version==1 and payload_offset+payload_size==len(bank)
    assert not manifest['unknown_nonzero_ranges'] and not manifest['omitted_payloads']
    sources={}
    for name,info in manifest['sources'].items():
        raw=Path(info['path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==info['sha256'];sources[name]=raw
    runtime=0
    for field in manifest['scalar_fields']:
        raw=sources[field['tag'].split(':')[0]];size=field['bytes'];src=field['source_file_offset'];dst=payload_offset+field['offset']
        assert bank[dst:dst+size]==raw[src:src+size][::-1],field
        runtime+=field['runtime']
    assert runtime>0
    assert count==len(manifest['records']) and reloc_count==len(manifest['relocations'])
    previous=0
    for i,(at,target) in enumerate(manifest['relocations']):
        assert at>previous and at%4==0 and at+4<=payload_size and 0<target<payload_size
        assert struct.unpack_from('>2I',bank,reloc_offset+i*8)==(at,target)
        assert struct.unpack_from('>I',bank,payload_offset+at)[0]==target;previous=at
    binary=output/'test_tag_store'
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-g','-O1','-fsanitize=address,undefined',
        '-fno-omit-frame-pointer',str(Path(__file__).with_name('test_tag_store.c')),
        str(Path(__file__).with_name('tag_store.c')),'-o',str(binary)],check=True,cwd=ROOT)
    result=subprocess.run([str(binary),str(output/'gameplay-tags.bgtg')],check=True,text=True,capture_output=True,cwd=ROOT)
    report={'source_scalar_fields':len(manifest['scalar_fields']),'native_runtime_fields':runtime,
        'payload_bytes':payload_size,'relocations':reloc_count,'loader_tests':result.stdout.strip()}
    (output/'test-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'build/n64/blam-tags')
    test(p.parse_args().output)
