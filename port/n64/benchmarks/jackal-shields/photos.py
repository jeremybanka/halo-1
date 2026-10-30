"""Decode paired native readbacks and check shield absence, recovery and depth."""
import hashlib,importlib.util,json,re
from pathlib import Path
import numpy as np
from PIL import Image,ImageFilter
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent;OUT=ROOT/'build/jackal-shields'
VIEW=ROOT.parents[2]/'build/n64-jackal-shields';VIEW.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('native',HERE.parent/'covenant-models/compare.py');native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
images={};states={};provenance={};sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for version in ('before','after'):
    log=OUT/(version+'-photos-native.log');text=log.read_text();assert not any(s in text.lower() for s in ('assertion failed','rdpq error','rdpq warning'))
    images[version]=native.decode(log,VIEW/version,72)
    states[version]=re.findall(r'^MODEL_PHOTO .*$',text,re.M)[:72]
    rom=next((OUT/(version+'-photos')).glob('*.z64'))
    provenance[version]={'log_sha256':sha(log),'rom_sha256':sha(rom),'frames':72}
assert states['before']==states['after'],'Unmatched camera/pose/shield states'
(VIEW/'diff').mkdir(exist_ok=True);changes=[];checks=[];cameras=[]
for i,(a,b) in enumerate(zip(images['before'],images['after'])):
    delta=np.abs(a.astype(int)-b.astype(int));Image.fromarray(np.minimum(delta*4,255).astype('uint8')).save(VIEW/'diff'/f'{i:02}.png')
    n=int(np.any(delta,axis=2).sum());changes.append({'page':i,'changed_pixels':n})
    if i%12 in (3,4,9,11):assert n==0,(i,n,'inactive shield changed pixels')
    else:assert n>0,(i,'missing active shield')
    floor=float(re.search(r'pos=0,([^,]+),4',states['after'][i])[1]);center=[0,floor+.38,4]
    cameras.append({'state':states['after'][i],'target':center,'eyes':[[round(c+d*1.25,6) for c,d in zip(center,v)] for v in [(1,.16,0),(-1,.16,0),(.3,.16,1),(.3,-.25,-1)]]})
def changed(a,b):return np.any(a!=b,axis=2)
def erode(mask):return np.array(Image.fromarray(mask.astype('uint8')*255).filter(ImageFilter.MinFilter(5)))>0
for base in range(0,72,12):
    before=images['before'][base:base+12];after=images['after'][base:base+12]
    assert np.array_equal(after[0][:224],after[5][:224]),(base,'recharged appearance differs')
    assert np.array_equal(after[3][:224],after[4][:224]),(base,'shield returned before delay')
    # Front camera only, excluding HUD/edge pixels. A foreground opaque actor
    # must cover the shield; an actor behind must remain visible through it.
    roi=np.zeros((240,320),bool);roi[32:110,35:145]=True
    shield=changed(before[0],after[0])&roi
    front=erode(changed(before[3],before[11]))&shield
    front_changed=int((changed(after[10],after[11])&front).sum())
    behind=erode(changed(before[3],before[9]))&shield
    through=behind&changed(after[8],after[0])&changed(after[8],after[9])
    assert front.sum()>10 and front_changed==0,(base,int(front.sum()),front_changed)
    # The coarse body's silhouette leaves only a few rear-actor samples in
    # this deliberately eroded overlap. Require actual transmitted detail at
    # every tier, rather than an arbitrary minimum area for a changed mesh.
    assert behind.sum()>0 and through.sum()>0,(base,int(behind.sum()),int(through.sum()))
    checks.append({'rank':base//36,'lod':(base//12)%3,'opaque_foreground_overlap_pixels':int(front.sum()),'incorrect_shield_over_foreground_pixels':front_changed,
                   'rear_actor_visible_through_shield_pixels':int(through.sum()),'recharged_matches_full_outside_caption':True,'delay_matches_depleted_outside_caption':True})
result={'provenance':provenance,'frames_per_version':72,'views_per_frame':4,'matching_states':True,'depleted_frames_pixel_identical':24,
        'checks':checks,'changes':changes,'cameras':cameras,'alpha_note':'CPU-derived masks select native pixel samples. Transparency is tested in the front camera; the four native angles remain available for inspection.'}
(OUT/'pixel-checks.json').write_text(json.dumps(result,indent=2)+'\n');(HERE/'pixel-checks.json').write_text(json.dumps(result,indent=2)+'\n');(VIEW/'pixel-checks.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(checks,indent=2))
