"""Recheck available-seat entry without overwriting the original vehicle matrix."""
import argparse, hashlib, importlib.util, json, shutil, subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
OUT=ROOT/'build/pve-vehicles';REV=OUT/'ce-entry'
PYTHON=ROOT/'build/n64-python/bin/python'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def build():
    base=[str(PYTHON),'port/n64/build.py','--pve-crunch','--pve-roster','--pve-jackal-shields',
          '--pve-model-bank','build/pve-vehicles/bank','--enemy-vehicle-bank','build/pve-vehicles/bank',
          '--map-bank-override','build/pve/ground/bloodgulch.map64',
          '--sdk','/Users/jem/dojo/n64-2048/.build/libdragon',
          '--tiny3d','/Users/jem/dojo/halo-1/build/n64-sidewinder-throughput/tiny3d-unlit']
    cases=[('play',['--firefight','--preset','release']),
           ('photos',['--pve-squad','--pve-players','4','--enemy-vehicle-qa']),
           ('stress-4',['--pve-squad','--pve-players','4','--pve-qa','8','--profile','--collision-profile','--pve-prep-profile'])]
    for name,flags in cases:
        with (REV/(name+'-build.log')).open('w') as log:
            subprocess.run(base+flags+['--output-dir',str(REV/name)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
        rom=next((REV/name).glob('*.z64'));print(name,rom.name,rom.stat().st_size,flush=True)

def capture():
    for name,script,limit in [('photos','covenant-models',['--frames','42']),
                              ('stress-4','firefight-performance',['--observations','45'])]:
        subprocess.run([str(PYTHON),str(HERE.parent/script/'capture.py'),str(next((REV/name).glob('*.z64'))),
                        str(OUT/'ares.bml'),str(REV/(name+'-native.log')),*limit],cwd=ROOT,check=True)

def collect():
    spec=importlib.util.spec_from_file_location('ff',HERE.parent/'firefight-limited/collect.py')
    ff=importlib.util.module_from_spec(spec);spec.loader.exec_module(ff)
    spec=importlib.util.spec_from_file_location('photos',HERE.parent/'covenant-models/compare.py')
    photos=importlib.util.module_from_spec(spec);spec.loader.exec_module(photos)
    import numpy as np
    before=photos.decode(OUT/'final-photos-native.log',REV/'before',42)
    after=photos.decode(REV/'photos-native.log',REV/'after',42)
    changes=[];outside_hint=[]
    # The occupied-Ghost prompt disappears from the first three pages. Its
    # four exact HUD rectangles are excluded only from the scene-pixel check;
    # full-frame differences remain recorded and visible in the viewer.
    for i,(a,b) in enumerate(zip(before,after)):
        changed=np.any(a!=b,axis=2);changes.append(int(changed.sum()))
        mask=np.zeros(changed.shape,dtype=bool)
        if i<3:
            for x,y in ((26,107),(186,107),(26,227),(186,227)):mask[y:y+10,x:x+108]=True
        outside_hint.append(int((changed&~mask).sum()))
    assert len(changes)==42 and changes[:3]==[1399]*3 and not any(changes[3:]),changes
    assert not any(outside_hint),outside_hint
    log=REV/'stress-4-native.log';raw=log.read_text()
    assert not any(x in raw.lower() for x in ('assertion failed','assertf','exception at','rdpq error','rdpq warning'))
    perf=ff.summarize(log);assert perf['observations']==45
    collision=[ff.fields(line) for line in raw.splitlines() if line.startswith('COLLISION ')]
    ticks=sum(row['ticks'] for row in collision)
    perf['cpu_ms_per_simulation_tick']={k:round(sum(r[k] for r in collision)/ticks/1000,3)
        for k in ('tick_us','director_us','humans_us','vehicle_ai_us','vehicles_us','actors_us','projectiles_us','after_us')}
    manifests={}
    for name in ('play','photos','stress-4'):
        manifest=next((REV/name).glob('*.build.json'));rom=next((REV/name).glob('*.z64'))
        manifests[name]={'manifest_sha256':sha(manifest),'rom_sha256':sha(rom)}
    result={'description':'Available-seat-only revision: no occupied-seat hijacking. Fresh host vehicle/Firefight tests, 42 native pages and one 45-observation four-player overload capture. Original 1–4-player matrix and all-map cycle predate this correction and are preserved separately.',
            'changed_pixels':changes,'changed_pixels_outside_removed_hint':outside_hint,
            'removed_hint_rectangles_xywh':[[26,107,108,10],[186,107,108,10],[26,227,108,10],[186,227,108,10]],
            'frames':42,'stress_4':perf,'manifests':manifests,
            'log_sha256':{p.name:sha(p) for p in [REV/'host-tests.log',REV/'host-match.log',REV/'photos-native.log',log]}}
    (REV/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    shutil.copyfile(REV/'results.json',HERE/'ce-entry.json')
    for name in ('host-tests.log','host-match.log','stress-4-native.log'):
        shutil.copyfile(REV/name,HERE/('ce-entry-'+name))
    print(json.dumps({'frames':42,'changed_pixels':sum(changes),'stress_4_engaged':perf['living_players_and_landed_enemies'],
                      'stress_4_min_free_bytes':perf['min_free_bytes']},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['build','capture','collect']);a=p.parse_args()
    REV.mkdir(exist_ok=True);globals()[a.action]()
