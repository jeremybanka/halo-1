"""Check the streamed bank, frame boundaries, timings, bounds and hatch endpoints."""
import ast,hashlib,json,re
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
G=ROOT/'build/n64/generated'
r=json.loads((G/'interaction-report.json').read_text())
for name,want in {**r['inputs'],**r['files']}.items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==want,name
source=(G/'interaction_assets.c').read_text();bank=(ROOT/'build/n64/frontend-files/interactions.bin').read_bytes()
def array(name):
 text=re.search(r'const bg_rom_pose '+name+r'[^=]*=([^;]+);',source).group(1)
 return ast.literal_eval(re.sub(r'(?<=\d)f\b','',text).replace('{','[').replace('}',']'))
def poses(node):
 if isinstance(node[0],int):yield node
 else:
  for child in node:yield from poses(child)
checked=0;maximum=0
for name in ['bg_seat_poses','bg_seat_grips','bg_body_ready_poses','bg_body_ready_grip','bg_ready_poses','bg_ready_needles','bg_ready_ar_digits','bg_ready_scope','bg_hatch_poses']:
 for offset,stride,vertices,frames,duration,bounds in poses(array(name)):
  assert offset%16==stride%16==0 and vertices*6<=stride and stride-vertices*6<16
  assert 0<frames<=65 and duration>0 and offset+frames*stride<=len(bank)
  scale=4096 if any(s in name for s in ['grip','digits','scope','hatch']) else 256 if name in ['bg_ready_poses','bg_ready_needles'] else 128
  allpoints=[]
  for frame in range(frames):
   points=np.frombuffer(bank,dtype='>i2',count=vertices*3,offset=offset+stride*frame).reshape(-1,3)/scale
   assert np.all(points>=np.array(bounds[0])-1e-6) and np.all(points<=np.array(bounds[1])+1e-6)
   assert not any(bank[offset+stride*frame+vertices*6:offset+stride*(frame+1)])
   allpoints.append(points)
  maximum=max(maximum,stride*2);checked+=frames
assert maximum==r['scratch_bytes'] and maximum<8192
for definition,pair in zip(r['body_clips'],array('bg_seat_poses')):
 for state in [1,2]:
  assert pair[state][0][3]==pair[state][1][3]==definition[state]['frames']
  assert abs(pair[state][0][4]-definition[state]['seconds'])<1e-6
for clip,definition in zip(array('bg_ready_poses')[:8],r['ready'].values()):
 assert clip[3]==definition['frames'] and abs(clip[4]-definition['seconds'])<1e-6
# The terminal closed canopy/hatch returns to the approved model transform.
for pair in array('bg_hatch_poses'):
 offset,stride,vertices,frames,*_=pair[1]
 terminal=np.frombuffer(bank,dtype='>i2',count=12,offset=offset+stride*(frames-1)).reshape(4,3)
 expected=np.vstack([np.zeros(3),np.eye(3)*4096])
 assert np.max(np.abs(terminal-expected))<=1,(terminal,expected)
assert [len(row) for row in r['seats']]==[3,1,5,1] and r['hold_ticks']==7
print(f'PASS: {checked} ROM frames, aligned DMA ranges, exact source one-shot frame counts/timings, conservative bounds, closed hatch transforms, {maximum} bytes scratch')
