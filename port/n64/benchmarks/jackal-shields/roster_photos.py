"""Repeat the original route; distinguish opaque identity from cloak dithering."""
import hashlib,importlib.util,json,re
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent;OUT=ROOT/'build/jackal-shields'
VIEW=ROOT.parents[2]/'build/n64-jackal-shields'
spec=importlib.util.spec_from_file_location('native',HERE.parent/'covenant-models/compare.py');native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
logs={'original':ROOT/'build/firefight-roster/photos-native.log','before':OUT/'before-roster-photos-native.log','after':OUT/'after-roster-photos-native.log'}
frames={};states={}
for version,log in logs.items():
    text=log.read_text();assert not any(s in text.lower() for s in ('assertion failed','rdpq error','rdpq warning'))
    frames[version]=native.decode(log,(OUT/'roster-original') if version=='original' else VIEW/('roster-'+version),46)
    states[version]=re.findall(r'^MODEL_PHOTO .*$',text,re.M)[:46]
assert states['original']==states['before']==states['after']
(VIEW/'roster-diff').mkdir(exist_ok=True);rows=[];opaque=cloaked=0
for i,(a,b,c) in enumerate(zip(frames['original'],frames['before'],frames['after'])):
    difference=np.abs(b.astype(int)-c.astype(int));n=int(np.any(difference,axis=2).sum())
    repeat=int(np.any(a!=b,axis=2).sum())
    cloak=float(re.search(r' camo=([\d.]+)',states['after'][i])[1])>0
    if i in (12,13,14):assert n>0
    elif cloak:
        cloaked+=1
        # Alpha-compare noise is an existing feature. Its individual coverage
        # pixels need not match after a different history of RDP submissions.
        # Record both comparisons; do not label this a pixel-identity pass.
    else:
        assert n==repeat==0,(i,n,repeat,'opaque non-Jackal changed');opaque+=1
    rows.append({'page':i,'cloaked':cloak,'changed_pixels':n,'original_to_fresh_baseline_changed_pixels':repeat})
    Image.fromarray(np.minimum(difference*4,255).astype('uint8')).save(VIEW/'roster-diff'/f'{i:02}.png')
assert opaque==35 and cloaked==8
checks={'matched_states':True,'unchanged_opaque_non_jackal_pages':opaque,'stochastic_cloak_pages':cloaked,'changes':rows,
        'log_sha256':{k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in logs.items()},
        'note':'35 opaque non-Jackal pages are pixel-identical across original/fresh baseline/candidate. Eight cloak pages use the existing noise alpha comparison: per-pixel identity is not asserted. Their exact states, images and both difference counts are retained for inspection.'}
for path in (HERE/'roster-pixel-checks.json',OUT/'roster-pixel-checks.json',VIEW/'roster-pixel-checks.json'):path.write_text(json.dumps(checks,indent=2)+'\n')
print(json.dumps(checks,indent=2))
