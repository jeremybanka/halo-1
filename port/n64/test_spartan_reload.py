"""Check source replacement masks and actual exported gait/action separation."""
import argparse, ast, json, re
from pathlib import Path
import numpy as np
from spartan_motion import replacement_states, BODY_RELOAD_FRAMES

ROOT=Path(__file__).resolve().parents[2]
def arrays(source,name):
    body=re.search(r'const bg_rom_pose '+name+r'[^=]*=([^;]+);',source)[1]
    return ast.literal_eval(re.sub(r'(?<=\d)f\b','',body).replace('{','[').replace('}',']'))
def poses(node):
    if node==[0]:return
    if isinstance(node[0],int):yield node
    else:
        for child in node:yield from poses(child)
def points(bank,pose):
    offset,stride,vertices,frames,*_=pose
    return np.array([np.frombuffer(bank,dtype='>i2',count=vertices*3,offset=offset+i*stride).reshape(vertices,3) for i in range(frames)])

def main():
    p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);a=p.parse_args()
    raw=json.loads((ROOT/'build/n64/assets/extended-raw.json').read_text())
    model=json.loads((ROOT/'build/n64/assets/extended-reduced.json').read_text())
    mapping=json.loads((ROOT/'build/n64/generated/world-mesh-sources.json').read_text())
    nodes=raw['models']['spartan']['nodes'];action=raw['animations']['reload']
    flags={key:action[key+'_flags'] for key in ('rot','trans','scale')}
    assert action['type']=='replacement' and len(model['animations']['reload']['frames'])==BODY_RELOAD_FRAMES
    # Independent channel oracle, including channels absent from the action.
    for base in raw['animations']['run']['frames']:
        for frame in action['frames']:
            result=replacement_states(base,frame,flags)
            for i,(b,r) in enumerate(zip(base,result)):
                for key,mask in [('q',flags['rot']),('p',flags['trans'])]:
                    assert r[key]==(frame[i][key] if (mask>>i)&1 else b[key])
    unaffected=[]
    for i,node in enumerate(nodes):
        bone=i;affected=False
        while bone>=0:
            affected|=bool((flags['rot']|flags['trans'])&(1<<bone));bone=nodes[bone]['parent']
        if not affected:unaffected.append(i)
    assert all(i in unaffected for i,n in enumerate(nodes) if any(x in n['name'] for x in ('pelvis','thigh','calf','foot')))
    text=(ROOT/'build/n64/generated/interaction_assets.c').read_text()
    bank=(ROOT/'build/n64/frontend-files/interactions.bin').read_bytes();atlas=arrays(text,'bg_body_reload_poses')
    checked=0
    for lod,(mesh,indices) in enumerate([(model['models']['spartan'],mapping['spartan']),(model['spartan_lod'],mapping['spartan_lod'])]):
        weights=[w for t in mesh['triangles'] for w in t['weights']]
        lower=[i for i,s in enumerate(indices) if all(b in unaffected or w==0 for b,w in weights[s])]
        assert len(lower)>len(indices)*.2
        for base in range(4):
            reference=points(bank,atlas[base][0][lod])
            altered=0
            for row in atlas[base]:
                actual=points(bank,row[lod]);assert np.array_equal(actual[:,lower],reference[:,lower])
                altered+=np.count_nonzero(actual!=reference);checked+=actual.shape[0]*len(lower)
            assert altered>100, 'Frozen reload arm would also preserve the legs'
    # The crouch locomotion bank is the direct, unlayered base reference.
    locomotion=arrays(text,'bg_locomotion_poses')
    for lod,indices in enumerate([mapping['spartan'],mapping['spartan_lod']]):
        mesh=model['models']['spartan'] if lod==0 else model['spartan_lod'];weights=[w for t in mesh['triangles'] for w in t['weights']]
        lower=[i for i,s in enumerate(indices) if all(b in unaffected or w==0 for b,w in weights[s])]
        for base in range(2):
            expected=points(bank,locomotion[base][lod])[:,lower]
            for row in atlas[base+2]:assert np.array_equal(points(bank,row[lod])[:,lower],expected)
    old=(a.baseline/'before-interaction_assets.c').read_text();old_bank=(a.baseline/'before-interactions.bin').read_bytes()
    unchanged=0
    for name in re.findall(r'const bg_rom_pose (\w+)\[?',old):
        if not re.search(r'const bg_rom_pose '+name+r'[^;]*=',old):continue
        before,after=list(poses(arrays(old,name))),list(poses(arrays(text,name)))
        assert len(before)==len(after)
        for x,y in zip(before,after):
            assert x[1:]==y[1:]
            assert old_bank[x[0]:x[0]+x[1]*x[3]]==bank[y[0]:y[0]+y[1]*y[3]],name
            unchanged+=1
    print('PASS source masked replacement,',checked,'unchanged lower-body vertex samples and',unchanged,'byte-identical existing pose clips (including first-person and firing)')

if __name__=='__main__':main()
