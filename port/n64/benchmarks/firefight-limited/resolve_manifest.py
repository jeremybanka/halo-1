#!/usr/bin/env python3
"""Reconstruct hash-identical build manifests from shared evidence sections."""
import argparse,hashlib,json
from pathlib import Path

def resolve(path):
    data=json.loads(path.read_text())
    for key,value in data.items():
        if isinstance(value,dict) and set(value)=={'$ref'}:
            shared=(path.parent/value['$ref']).resolve()
            if not shared.is_relative_to(path.parent.resolve()):raise ValueError('Reference escapes evidence directory')
            data[key]=json.loads(shared.read_text())
    return (json.dumps(data,indent=2)+'\n').encode()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('manifest',type=Path);p.add_argument('--output',type=Path);a=p.parse_args();payload=resolve(a.manifest)
    if a.output:a.output.write_bytes(payload)
    print(hashlib.sha256(payload).hexdigest())
