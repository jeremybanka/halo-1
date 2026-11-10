"""Add dense-node allocation counts without changing certified graph geometry."""
import argparse,hashlib,json,struct
from pathlib import Path


def run(source,output):
    output.mkdir(parents=True,exist_ok=True);reports=[]
    for path in sorted(source.glob('autonav-*.bin')):
        data=path.read_bytes();assert data[:4]==b'GNV1';p=28;live=nodes=0
        while p<len(data):
            code=struct.unpack_from('>H',data,p)[0];p+=2;count=code&32767;nodes+=count
            if not code&32768:live+=count;p+=count*3
        assert p==len(data) and 0<live<65535
        target=output/path.name;target.write_bytes(b'GNV2'+data[4:28]+struct.pack('>2H',live,0)+data[28:])
        reports.append(dict(file=path.name,source_sha256=hashlib.sha256(data).hexdigest(),sha256=hashlib.sha256(target.read_bytes()).hexdigest(),geometry_payload_unchanged=True,grid_slots=nodes,walk_nodes=live,search_resident_bytes=nodes*2+live*15,bytes=target.stat().st_size))
    assert len(reports)==13
    (output/'navigation-report.json').write_text(json.dumps(dict(maps=reports,inputs='Production map collision floors and swept human capsule clearance; six height layers; reversible walk edges; original directed portals at load time',baker_sha256=hashlib.sha256(Path(__file__).with_name('bake_autopilot_nav.c').read_bytes()).hexdigest()),indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();run(a.source,a.output)
