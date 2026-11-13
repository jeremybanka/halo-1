#!/usr/bin/env python3
"""Bounded native combat soak with activity gates; use the workspace run guard."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

COVERAGE_REVISION=2

def rows(text):
    overlap={int(m.group(1)):m.group(0) for m in re.finditer(r'^COMBAT_OVERLAP tick=(\d+) .+$',text,re.M)}
    result=[]
    for line in re.findall(r'^COMBAT_SOAK (.*)$',text,re.M):
        row={}
        for pair in line.split():
            k,v=pair.split('=',1)
            row[k]=float(v) if '.' in v else int(v)
        if row['tick'] in overlap:
            for pair in overlap[row['tick']].split()[2:]:
                k,v=pair.split('=',1);row[k]=int(v)
        result.append(row)
    return result


def coverage(samples):
    last=samples[-1];minutes=last['tick']/1800
    per_minute={'human_fire':400,'enemy_fire':100,'frags':7,'plasma':5,
                'explosions':20,'enemy_deaths':3,'aboard':360,'moving_aboard':180,
                'travel':40,'zoom_edges':40}
    failures=[f'{key}: {last[key]} < {minimum*minutes:.1f}'
              for key,minimum in per_minute.items() if last[key]<minimum*minutes]
    for key,minimum in {'projectiles':24,'grenades':3,'live':8}.items():
        if last[key]<minimum:failures.append(f'peak {key}: {last[key]} < {minimum}')
    for key,minimum in {'moving_aboard_projectiles':12,'busy_aboard':450,'busy_scoped':100,'explosion_zoom_edges':5}.items():
        if last.get(key,0)<minimum:failures.append(f'overlap {key}: {last.get(key,0)} < {minimum}')
    previous={key:0 for key in last}
    for sample in samples:
        if sample['tick']-previous['tick']<1800:continue
        minimums={'human_fire':100,'enemy_fire':30,'explosions':5,'enemy_deaths':1,
                  'zoom_edges':10}
        for key,minimum in minimums.items():
            delta=sample[key]-previous[key]
            if delta<minimum:failures.append(f'ticks {previous["tick"]}-{sample["tick"]}: {key} {delta} < {minimum}')
        grenade_delta=sum(sample[k]-previous[k] for k in ['frags','plasma'])
        if grenade_delta<3:failures.append(f'tick {sample["tick"]}: quiet grenade interval')
        previous=sample
    previous={key:0 for key in last}
    for sample in samples:
        if sample['tick']-previous['tick']<3600:continue
        if sample['moving_aboard']-previous['moving_aboard']<30:
            failures.append(f'ticks {previous["tick"]}-{sample["tick"]}: no recovered three-player drive')
        previous=sample
    return failures


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,required=True)
    p.add_argument('--settings',type=Path,required=True,help='Known Ares NTSC/8 MiB/Homebrew settings')
    p.add_argument('--ares',type=Path,default=Path('/Applications/ares.app/Contents/MacOS/ares'))
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--ticks',type=int,default=18000)
    p.add_argument('--timeout',type=int,default=1800)
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    assert not (out/'native.log').exists(),'Choose a fresh output'
    settings=a.settings.read_text()
    settings=re.sub(r'(?m)^  AutoSaveMemory:.*$','  AutoSaveMemory: false',settings)
    settings=re.sub(r'(?m)^  Mute:.*$','  Mute: true',settings)
    (out/'ares.bml').write_text(settings)
    started=time.monotonic();progress=0;status='timeout';samples=[]
    with (out/'native.log').open('w') as log:
        proc=subprocess.Popen([str(a.ares),'--settings-file',str(out/'ares.bml'),
                               '--no-file-prompt',str(a.rom.resolve())],stdout=log,stderr=subprocess.STDOUT)
        print('Owned Ares PID',proc.pid,flush=True)
        try:
            while proc.poll() is None and time.monotonic()-started<a.timeout:
                time.sleep(1)
                text=(out/'native.log').read_text(errors='replace');samples=rows(text)
                if re.search(r'assertion failed|CPU EXCEPTION|uncaught exception|recursive assertion',text,re.I):
                    status='native_crash';print('Native crash:',text[-3500:],flush=True);break
                if samples and samples[-1]['tick']>=progress+300:
                    progress=samples[-1]['tick'];print('PROGRESS',samples[-1],flush=True)
                if samples and samples[-1]['tick']>=a.ticks and 'explosion_zoom_edges' in samples[-1]:status='complete';break
            else:
                if proc.poll() is not None:status='emulator_exit'
        finally:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
    failures=coverage(samples) if status=='complete' else [status]
    result={'status':'pass' if not failures else 'fail','capture_status':status,
            'coverage_revision':COVERAGE_REVISION,
            'wall_seconds':round(time.monotonic()-started,2),'activity_failures':failures,
            'last_sample':samples[-1] if samples else None,'samples':samples,
            'rom':str(a.rom.resolve()),'rom_sha256':hashlib.sha256(a.rom.read_bytes()).hexdigest(),
            'event_count_caveat':'Newly queued events only; counters are lower bounds if the presentation queue saturates.',
            'fixture_support':'Ammunition, renewable production-cap enemies and boarding placement. Humans/transport restored during 40-second driving intervals; ordinary deaths/destruction during the other 20 seconds. No direct enemy kills or fabricated effects.'}
    (out/'combat-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('COMBAT_QA',result['status'].upper(),failures,flush=True)
    if failures:raise SystemExit(1)


if __name__=='__main__':main()
