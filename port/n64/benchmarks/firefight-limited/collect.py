#!/usr/bin/env python3
"""Summarize bounded native Firefight captures; never use lifecycle QA as perf."""
import argparse,hashlib,json,re,statistics,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]

def fields(line):
    return {k:float(v) if '.' in v else int(v) for k,v in re.findall(r'(\w+)=(-?\d+(?:\.\d+)?)',line)}

def summarize(path):
    rows=[];pending={}
    for line in path.read_text(errors='replace').splitlines():
        if line.startswith(('PHASE ','PVE ','FF_STATE ','PVE_PHASE ')):
            kind=line.split()[0];pending[kind]=fields(line)
        elif line.startswith('PERF views='):
            rows.append({**pending,'PERF':fields(line)});pending={}
    if len(rows)<10:raise ValueError(f'Incomplete capture: {path}')
    used=rows[5:];fps=[r['PERF']['fps'] for r in used]
    engaged=[r['PERF']['fps'] for r in used if r['FF_STATE']['living']>0 and r['FF_STATE']['enemies']>0 and r['FF_STATE']['arriving']==0]
    active=dict(observations=len(engaged),fps_mean=round(statistics.mean(engaged),2),fps_min=min(engaged),fps_max=max(engaged)) if engaged else None
    def mean(group,key):return statistics.mean(r[group][key] for r in used if key in r.get(group,{}))
    return dict(living_players_and_landed_enemies=active,observations=len(rows),warmup_discarded=5,used=len(used),fps_mean=round(statistics.mean(fps),2),fps_min=min(fps),fps_max=max(fps),
        min_free_bytes=min(r['PERF']['free'] for r in rows),
        living_range=[min(r['FF_STATE']['living'] for r in used),max(r['FF_STATE']['living'] for r in used)],
        enemy_range=[min(r['FF_STATE']['enemies'] for r in used),max(r['FF_STATE']['enemies'] for r in used)],
        cpu_ms={k:round(mean('PVE_PHASE',k)/1000,3) for k in ('sim','prep','draw')},
        ai_ms=round(mean('PVE','ai_us')/1000,3),movement_combat_ms=round(mean('PVE','move_us')/1000,3),
        npc_prepare_ms=round(mean('PVE','pve_render_us')/1000,3),vertex_loads=round(mean('PVE_PHASE','vertices')),
        samples=rows)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    cases={}
    for name in ('perf-1','perf-2','perf-3','perf-4','opening-1','opening-4'):
        log=a.capture/(name+'-native.log');cases[name]=summarize(log)
        rom=next((a.capture/name).glob('*.z64'));manifest=next((a.capture/name).glob('*.build.json'))
        cases[name].update(log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),rom_sha256=hashlib.sha256(rom.read_bytes()).hexdigest(),build_manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest())
    out=dict(schema=1,description='Ares NTSC 320x240, 8 MiB, uncapped diagnostic; real combat, deterministic input. Integer one-second FPS samples. Lifecycle QA excluded.',cases=cases)
    a.output.write_text(json.dumps(out,indent=2)+'\n')
    for n,c in cases.items():print(n,c['fps_mean'],c['fps_min'],c['fps_max'],c['cpu_ms'],c['min_free_bytes'])
