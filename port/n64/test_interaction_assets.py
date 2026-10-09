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
for name in ['bg_seat_poses','bg_seat_grips','bg_body_ready_poses','bg_body_ready_grip','bg_ready_poses','bg_ready_needles','bg_ready_ar_digits','bg_ready_scope','bg_hatch_poses','bg_service_poses','bg_service_plasma','bg_service_vents','bg_reload_ar_digits']:
 for offset,stride,vertices,frames,duration,bounds in poses(array(name)):
  assert offset%16==stride%16==0 and vertices*6<=stride and stride-vertices*6<16
  assert 0<frames<=126 and duration>0 and offset+frames*stride<=len(bank)
  scale=4096 if any(s in name for s in ['grip','digits','scope','hatch','plasma','vents']) else 256 if name in ['bg_ready_poses','bg_ready_needles','bg_service_poses'] else 128
  allpoints=[]
  for frame in range(frames):
   points=np.frombuffer(bank,dtype='>i2',count=vertices*3,offset=offset+stride*frame).reshape(-1,3)/scale
   assert np.all(points>=np.array(bounds[0])-1e-6) and np.all(points<=np.array(bounds[1])+1e-6)
   assert not any(bank[offset+stride*frame+vertices*6:offset+stride*(frame+1)])
   allpoints.append(points)
  maximum=max(maximum,stride*2);checked+=frames
# The source-profile M6D adds a raised barrel and angled magazine: its two
# ready frames need 8,736 bytes. Keep a bounded 9 KiB budget for this bank.
assert maximum==r['scratch_bytes'] and maximum<9*1024
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

services=array('bg_service_poses')
assert len(services)==7
for pose,definition in zip(services,r['service']):
 assert pose[3]==definition['source_frames']+1
 assert abs(pose[4]-definition['source_frames']/30)<1e-6
assert [d['source_frames'] for d in r['service']]==[87,34,24,9,24,111,125]
print('PASS: complete AR / rocket reloads and plasma enter / loop / exit source frames')
# Dense rebaking must preserve the approved mesh at retained source keyframes.
# This catches wrong joint maps, hand/gun bind recovery, or reordered indices.
import sys
sys.path.insert(0,str(ROOT/'port/n64'))
from pack_firstperson import prepare_model
from pack_assets import position
fp=json.loads((ROOT/'build/n64/assets/firstperson-reduced.json').read_text())
raw=json.loads((ROOT/'build/n64/assets/firstperson-raw.json').read_text())
for name,service in [('ar',0),('rocket',5)]:
 mesh,clips,_=prepare_model(fp['weapons'][name],name)
 pose=services[service];offset,stride,vertices,frames,*_=pose
 assert vertices==len(mesh['vertices'])
 clip=clips['reload'];source_count=len(raw['weapons'][name]['clips']['reload']['frames'])
 for i,f in enumerate(clip['frames']):
  source_frame=round(i*(source_count-1)/(len(clip['frames'])-1))
  if source_frame>=frames-1:continue # Old extractor's synthetic looping frame.
  expected=np.rint(np.array([position(p,(0,0,0)) for p in f])*256)
  actual=np.frombuffer(bank,dtype='>i2',count=vertices*3,offset=offset+stride*source_frame).reshape(-1,3)
  assert np.max(np.abs(expected-actual))<=1,(name,i,np.max(np.abs(expected-actual)))
print('PASS: dense reload skins preserve approved hand/gun geometry at source keyframes')
