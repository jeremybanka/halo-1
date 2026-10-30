#!/usr/bin/env python3
"""Collect paired native collision profiles; retain counter scope and provenance."""
import argparse,hashlib,importlib.util,json,statistics,shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('prior',HERE.parent/'firefight-navigation/collect.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def summarize(log):
    result=prior.summarize(log);rows=result.pop('samples');used=rows[5:]
    seen=0;collision=[];truncated=0
    lines=log.read_text().splitlines(keepends=True)
    for index,line in enumerate(lines):
        if line.startswith('PERF views='):seen+=1
        if line.startswith('COLLISION ') and seen>=5:
            if not line.endswith('\n'):
                assert index==len(lines)-1
                truncated+=1;continue # Owned emulator may stop midway through its final diagnostic.
            collision.append(prior.fields(line))
    assert collision and all(r['ticks']==30 for r in collision)
    ticks=sum(r['ticks'] for r in collision)
    totals={k:sum(r[k] for r in collision) for k in collision[0] if k not in ('tick','max_tick_us')}
    result['collision']={'intervals':len(collision),'ticks':ticks,'truncated_final_records_excluded':truncated,
        'ms_per_tick':{k[:-3]:round(v/ticks/1000,4) for k,v in totals.items() if k.endswith('_us')},
        'max_tick_ms':round(max(r['max_tick_us'] for r in collision)/1000,3),
        'counts':{k:v for k,v in totals.items() if not k.endswith('_us')},
        'terrain_reuse_percent':round(100*totals['terrain_hits']/max(1,totals['terrain_queries']),2),
        'hit_triangles_per_query':round(totals['hit_triangles']/max(1,totals['hit_queries']),2)}
    result['collision']['max_tick_interval']=max(collision,key=lambda r:r['max_tick_us'])
    result['phase_ms']={k:round(statistics.mean(r['PHASE'][k] for r in used)/1000,3) for k in ('audio','hud','queue','world','objects','fp')}
    result['drain_ms']={k:round(statistics.mean(r['PVE_PHASE'][k] for r in used)/1000,3) for k in ('rsp_wait','rdp_wait')}
    players=rows[0]['PERF']['views']
    alive=[r for r in used if r['FF_STATE']['living']==players and r['FF_STATE']['enemies']>0 and not r['FF_STATE']['arriving']]
    result['all_humans_and_landed_enemies']={'observations':len(alive),'fps_mean':round(statistics.mean(r['PERF']['fps'] for r in alive),2)} if alive else None
    result['max_reported_frame_ms']=round(max(r['PHASE']['frame_max'] for r in used)/1000,3)
    return result
def main():
    p=argparse.ArgumentParser();p.add_argument('capture',type=Path);p.add_argument('--output',type=Path,default=HERE);p.add_argument('--gpu',action='store_true');p.add_argument('--partial',action='store_true');p.add_argument('--logs-only',action='store_true',help='Reanalyze archived logs and verify their saved hashes without local ROMs');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    archived=json.loads((a.capture/'provenance.json').read_text()) if a.logs_only else None
    if archived:assert archived.get('gpu_serialized',False)==a.gpu
    cases={};provenance={};matched={}
    for kind in (['perf'] if a.gpu else ['opening','perf']):
        for players in ([4] if a.gpu else range(1,5)):
            manifests={}
            for version in ('baseline','candidate'):
                name=f'{version}-{kind}-{players}';log=a.capture/(name+'-native.log')
                expected=75 if kind=='opening' else 45
                if a.partial and (not log.exists() or log.read_text().count('PERF views=')!=expected):continue
                r=summarize(log);assert r['observations']==expected,name;cases[name]=r
                if archived:
                    assert archived['cases'][name]['log_sha256']==sha(log),name
                    continue
                manifest=next((a.capture/name).glob('*.build.json'));rom=next((a.capture/name).glob('*.z64'));m=manifests[version]=json.loads(manifest.read_text())
                assert m['options']['collision_profile'] and m['options']['profile']
                assert bool(m['options']['collision_baseline'])==(version=='baseline')
                assert bool(m['options']['gpu_diagnostic'])==a.gpu
                assert m['options']['pve_players']==players and m['options']['pve_qa']==(3 if kind=='opening' else 4)
                bank=Path(m['options']['pve_model_bank']);assert bank.is_dir()
                provenance[name]={'parent_source_commit':m['runtime_commit'],'parent_asset_commit':m['asset_commit'],
                    'log_sha256':sha(log),'rom_sha256':sha(rom),'rom_bytes':rom.stat().st_size,'manifest_sha256':sha(manifest),
                    'toolchain':m['toolchain'],'options':m['options'],'inputs':prior.inputs(m),
                    'model_sha256':sha(bank/'pve_data.c'),'motion_sha256':sha(bank/'pve-motion.bin'),
                    'map_sha256':m['render_bank_experiment']['sha256']}
                target=a.output/log.name
                if target.resolve()!=log.resolve():shutil.copyfile(log,target)
            if len(manifests)==2:
                b,c=[manifests[v] for v in ('baseline','candidate')];bo,co=dict(b['options']),dict(c['options'])
                for options in (bo,co):
                    for field in ('output_dir','collision_baseline'):options.pop(field)
                assert bo==co,(kind,players,'options')
                assert prior.inputs(b)==prior.inputs(c),(kind,players,'inputs')
                assert b['included_data']==c['included_data']
                matched[f'{kind}-{players}']='Identical runtime sources, headers, geometry, rules and assets; only collision-baseline control differs'
                print(kind,players,cases[f'baseline-{kind}-{players}']['living_players_and_landed_enemies'],cases[f'candidate-{kind}-{players}']['living_players_and_landed_enemies'])
    (a.output/'results.json').write_text(json.dumps({'schema':1,'gpu_serialized':a.gpu,'cases':cases},indent=2)+'\n')
    if not archived:(a.output/'provenance.json').write_text(json.dumps({'schema':1,'gpu_serialized':a.gpu,'emulator':'Ares v148, NTSC 320x240, 8 MiB, audio on','settings_sha256':sha(a.capture/'ares.bml'),'cases':provenance,'matched':matched},indent=2)+'\n')
if __name__=='__main__':main()
