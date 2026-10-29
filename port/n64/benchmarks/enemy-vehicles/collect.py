"""Preserve complete native samples and separate frame costs from tick costs."""
import hashlib, importlib.util, json, re, shutil, statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
OUT=ROOT/'build/pve-vehicles'
spec=importlib.util.spec_from_file_location('ff_collect',HERE.parent/'firefight-limited/collect.py')
ff=importlib.util.module_from_spec(spec);spec.loader.exec_module(ff)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def scope(rows,players):
    selected=[r for r in rows[5:] if r['FF_STATE']['living']==players and r['FF_STATE']['enemies']>0 and not r['FF_STATE']['arriving']]
    return {'observations':len(selected),'fps_mean':round(statistics.mean(r['PERF']['fps'] for r in selected),2) if selected else None}

def main():
    cases={};provenance={};logs=HERE/'logs';logs.mkdir(exist_ok=True)
    for fixture,players in [(f,p) for f in (8,9) for p in (1,2,3,4)]+[(7,4)]:
        name=f'final-{fixture}-{players}';log=OUT/(name+'-native.log');text=log.read_text()
        assert 'assertion failed' not in text.lower() and 'exception at' not in text.lower(),name
        result=ff.summarize(log);assert result['observations']==45,(name,result['observations'])
        result['all_players_alive']=scope(result['samples'],players)
        result['fixture']=fixture;result['players']=players
        result['cache_pressure_reclaims']=text.count('PVE_CACHE_PRESSURE')
        collision=[ff.fields(line) for line in text.splitlines() if line.startswith('COLLISION ')]
        ticks=sum(r['ticks'] for r in collision);assert ticks>0
        result['profiled_ticks']=ticks
        result['cpu_ms_per_simulation_tick']={k:round(sum(r[k] for r in collision)/ticks/1000,3) for k in ('tick_us','director_us','humans_us','vehicle_ai_us','vehicles_us','actors_us','projectiles_us','after_us')}
        vehicles=[ff.fields(line) for line in text.splitlines() if line.startswith('ENEMY_VEHICLE ')]
        result['max_shots_by_vehicle']={str(k):max(r['shots'] for r in vehicles if r['kind']==k) for k in sorted({r['kind'] for r in vehicles})}
        result['collision_samples']=collision
        manifest=next((OUT/name).glob('*.build.json'));rom=next((OUT/name).glob('*.z64'))
        provenance[name]={'log_sha256':sha(log),'manifest_sha256':sha(manifest),'rom_sha256':sha(rom)}
        shutil.copyfile(log,logs/log.name);cases[name]=result
    data={'schema':1,'description':'Ares v148, NTSC 320x240, 8 MiB, audio on; uncapped diagnostic. Nine complete 45-observation captures, first five FPS samples discarded. Real damage/deaths; engaged means at least one human and enemy alive and no pending arrival. Fixtures 7/8 restart at simulation tick 600; restarted intervals remain in the sample. No cartridge timing claim.','fixtures':{'7':'Full Covenant roster memory regression, no piloted enemy vehicles','8':'Ghost, Banshee, Wraith and Shade together, infantry to the 6/8/10/12 actor cap','9':'One Ghost, infantry to the 6/8/10/12 actor cap'},'cases':cases}
    for filename,value in [('results.json',data),('provenance.json',{'cases':provenance,'build_script_sha256':sha(ROOT/'port/n64/build.py')})]:
        payload=json.dumps(value,indent=2)+'\n';(OUT/filename).write_text(payload);(HERE/filename).write_text(payload)
    lines=['## Native measurements','',data['description'],'',
           '| Players | One Ghost + infantry | Four vehicles + infantry | Stress minimum free RAM |',
           '|---|---:|---:|---:|']
    for p in (1,2,3,4):
        a=cases[f'final-9-{p}'];b=cases[f'final-8-{p}'];fmt=lambda c:f"{c['living_players_and_landed_enemies']['fps_mean']:.2f} FPS ({c['living_players_and_landed_enemies']['observations']} samples)"
        lines.append(f"| {p} | {fmt(a)} | {fmt(b)} | {b['min_free_bytes']/1024:.1f} KiB |")
    lines+=['','These are deliberately crowded encounters at the actor cap, not a promise',
            'of a particular frame rate throughout a full match. Three-player results need',
            'not sit between two/four-player results: enemies, targets, deaths, viewports',
            'and visible LODs differ. The playable release ROM is capped at 30 FPS; the',
            'diagnostic ROMs are uncapped. The table uses engaged samples, not post-death',
            'idle frames. All-human-alive scope and ranges are in results.json.','',
            '| Four-player fixture | All humans alive FPS / samples | CPU simulation / prep / drawing per rendered frame | Submitted vertex loads, all views |',
            '|---|---:|---:|---:|']
    for f in (9,8,7):
        c=cases[f'final-{f}-4'];a=c['all_players_alive'];cpu=c['cpu_ms']
        lines.append(f"| {data['fixtures'][str(f)]} | {a['fps_mean']} / {a['observations']} | {cpu['sim']:.2f} / {cpu['prep']:.2f} / {cpu['draw']:.2f} ms | {c['vertex_loads']:,} |")
    lines+=['','Drawing is measured elapsed CPU time around submission; it can include queue',
            'stalls and is not an independent RSP/RDP occupancy measurement. Frame counters',
            'may contain several simulation ticks. The following disjoint simulation',
            'partition is normalized per tick; do not add nested terrain/hit counters.','',
            '| Four-player fixture | Human simulation | Vehicle AI | Vehicle physics/contact | Infantry AI/combat | Projectiles | Total tick |',
            '|---|---:|---:|---:|---:|---:|---:|']
    for f in (9,8,7):
        c=cases[f'final-{f}-4']['cpu_ms_per_simulation_tick'];values=[c[k] for k in ('humans_us','vehicle_ai_us','vehicles_us','actors_us','projectiles_us','tick_us')]
        lines.append('| '+str(f)+' | '+' | '.join(f'{v:.2f} ms' for v in values)+' |')
    lines+=['','The four-vehicle overload adds substantial vehicle physics and clearance/AI',
            'work while still submitting large actor/hull meshes to four cameras. Long',
            'frames then accumulate multiple fixed simulation ticks. This candidate',
            'delivers the mechanics; it does not meet four-player 30 FPS. The next',
            'performance pass should separate per-vehicle clearance/solver costs and',
            'bound the simultaneous expensive vehicles, alongside vehicle screen-size',
            'LOD work. Do not interpret lower polygon count as sufficient on its own.','']
    report=ROOT/'port/n64/PVE_VEHICLES.md';marker='<!-- MEASUREMENTS -->'
    report.write_text(report.read_text().split(marker)[0]+marker+'\n\n'+'\n'.join(lines))
    for name,c in cases.items():print(name,c['living_players_and_landed_enemies'],c['all_players_alive'],c['min_free_bytes'],c['cpu_ms_per_simulation_tick'])

if __name__=='__main__':main()
