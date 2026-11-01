"""Verify every serialized pose, source trajectory, socket, batch and bound."""
import json,struct,hashlib,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];A=ROOT/'halo64-assets';OUT=A/'assets/jorge/playable-half'
def validate(report,bank):
    global OUT
    OUT=ROOT/report.get('source_directory',str(OUT.relative_to(ROOT)));source=np.load(OUT/'gameplay-poses.npz');packed=np.load(OUT/'packed-preview.npz');n=report['vertices'];scale=report['position_scale']
    assert report.get('bank_offset',0)+report['rom_bytes']<=len(bank) and len(report['clips'])==39
    assert hashlib.sha256((OUT/(report.get('source_name','jorge-playable-half')+'.blend')).read_bytes()).hexdigest()==report['source_blend_sha256']
    assert len(packed['positions'])==n and len(packed['triangles'])==report['triangles']
    assert packed['triangles'].min()>=0 and packed['triangles'].max()<n
    if 'batches' in packed:
        start=report['bank_offset'];triangles=0
        for i,(first,count,offset,indices) in enumerate(packed['batches']):
            assert (first%2,count%2,offset%4,indices%3)==(0,0,0,0)
            assert first+count<=n and count<=60 and indices<=120
            actual=struct.unpack_from('>4H',bank,start+report['batches_offset']+i*8)
            assert actual==(first,count,offset,indices)
            values=np.frombuffer(bank,dtype='>i2',count=indices,offset=start+report['indices_offset']+int(offset)*2)
            assert values.min()>=0 and values.max()<count
            assert np.array_equal(values,packed['indices'][offset:offset+indices])
            triangles+=indices//3
        assert triangles==report['triangles']
    max_quat_error=0
    for i,c in enumerate(report['clips']):
        expected=np.rint(source['frames_'+str(i)]*scale).astype(np.int16)[:,packed['sources']]
        assert c['offset']%16==0 and c['stride']%16==0
        assert c['offset']+c['frames']*c['stride']<=len(bank)
        assert c['frames']==len(expected)
        actual=[]
        for f in range(c['frames']):
            off=c['offset']+f*c['stride'];p=np.frombuffer(bank,dtype='>i2',count=n*3,offset=off).reshape(n,3)
            assert np.array_equal(p,expected[f]);actual.append(p)
            hand=np.frombuffer(bank,dtype='>f4',count=7,offset=off+n*6)
            assert np.array_equal(hand,source['grips_'+str(i)][f]) and np.isfinite(hand).all()
            max_quat_error=max(max_quat_error,abs(np.linalg.norm(hand[3:])-1))
            assert np.all(hand[:3]>=np.array(c['grip_bounds'][0])-1e-6) and np.all(hand[:3]<=np.array(c['grip_bounds'][1])+1e-6)
        actual=np.array(actual)/scale
        assert np.all(actual>=np.array(c['bounds'][0])-1e-6) and np.all(actual<=np.array(c['bounds'][1])+1e-6)
    assert max_quat_error<1e-5
    result={'bank_sha256':hashlib.sha256(bank).hexdigest(),'clips':len(report['clips']),'frames':sum(c['frames'] for c in report['clips']),'all_serialized_positions_and_sockets_exact':True,'all_bounds_contain_all_frames':True,'maximum_socket_quaternion_length_error':float(max_quat_error),'position_scale':scale,'vertices':n,'triangles':report['triangles']}
    (OUT/'bank-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(report.get('lod','single'),result)
    return source

def run():
    if '--candidate' in sys.argv:
        folder=A/'assets/jorge/playable-lods/compiled'
        report=json.loads((folder/'jorge-report.json').read_text());bank=(folder/'jorge.bin').read_bytes()
    else:
        report=json.loads((A/'generated/jorge-report.json').read_text());bank=(A/'frontend-files/jorge.bin').read_bytes()
    assert len(bank)==report['rom_bytes']
    if report.get('format')==2:
        near,far=report['lods'];assert far['vertices']<near['vertices']
        sources=[validate(r,bank) for r in report['lods']]
        for i,(a,b) in enumerate(zip(near['clips'],far['clips'])):
            assert (a['name'],a['duration'],a['frames'])==(b['name'],b['duration'],b['frames'])
            assert np.array_equal(sources[0]['grips_'+str(i)],sources[1]['grips_'+str(i)])
        assert report['frame_cache_bytes']==max(r['frame_cache_bytes'] for r in report['lods'])
        print('PASS: distinct near/far banks; all 39 shared clocks and grip trajectories match')
    else:validate(report,bank)
if __name__=='__main__':run()
