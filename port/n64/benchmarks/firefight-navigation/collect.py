#!/usr/bin/env python3
"""Reproduce paired perf summaries and validate matched build inputs."""
import argparse,hashlib,importlib.util,json,statistics,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('firefight_limited_collect',HERE.parent/'firefight-limited/collect.py')
legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
summarize,fields=legacy.summarize,legacy.fields

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inputs(d):
    out=d['options']['output_dir']
    root=next(k[:-len('port/n64/main.c')] for k in d['sources'] if k.endswith('/port/n64/main.c'))
    def normalize(k):
        if '/halo64-assets/' in k:return 'halo64-assets/'+k.split('/halo64-assets/',1)[1]
        if k.startswith(out+'/'):return 'build/'+k[len(out)+1:]
        if k.startswith(root):return k[len(root):]
        return k
    return {normalize(k):v for section in ['sources','headers','included_data','generated_adapters'] for k,v in d[section].items()}

def main():
    p=argparse.ArgumentParser();p.add_argument('capture',type=Path);p.add_argument('--output',type=Path,default=HERE);p.add_argument('--logs-only',action='store_true',help='Reanalyze archived logs, validating their saved hashes without local ROMs');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    archived=json.loads((a.capture/'provenance.json').read_text()) if a.logs_only else None
    results={};provenance={};comparisons={}
    for kind in ['opening','perf']:
        for n in range(1,5):
            manifests={}
            for version in ['baseline','candidate']:
                name=f'{version}-{kind}-{n}';log=a.capture/(name+'-native.log');r=summarize(log)
                expected=75 if kind=='opening' else 45;assert r['observations']==expected,(name,r['observations'])
                rows=r.pop('samples');used=rows[5:];all_alive=[x for x in used if x['FF_STATE']['living']==n and x['FF_STATE']['enemies']>0 and x['FF_STATE']['arriving']==0]
                r['all_humans_and_landed_enemies']={'observations':len(all_alive),'fps_mean':round(statistics.mean(x['PERF']['fps'] for x in all_alive),2),'fps_min':min(x['PERF']['fps'] for x in all_alive),'fps_max':max(x['PERF']['fps'] for x in all_alive)} if all_alive else None
                r['max_reported_frame_ms']=round(max(x['PHASE']['frame_max'] for x in used)/1000,3)
                nav=[fields(l) for l in log.read_text().splitlines() if l.startswith('NAV ')]
                if version=='candidate':
                    assert len(nav)==expected and all(x['max_work']<=256 for x in nav)
                    # Stress resets its encounter every 600 ticks. Only subtract
                    # adjacent observations inside the same monotonic interval.
                    intervals=[(x,y) for x,y in zip(nav,nav[1:]) if y['tick']>x['tick'] and y['total_us']>=x['total_us']]
                    ticks=sum(y['tick']-x['tick'] for x,y in intervals)
                    elapsed=sum(y['total_us']-x['total_us'] for x,y in intervals)
                    completed=sum(y['completed']-x['completed'] for x,y in intervals)
                    waits=sum(y['wait_ticks']-x['wait_ticks'] for x,y in intervals)
                    r['navigation']={'sampled_frame_mean_ms':round(statistics.mean(x['us'] for x in nav[5:])/1000,4),'max_reported_service_tick_ms':round(max(x['max_us'] for x in nav)/1000,4),'max_reported_wait_ticks':max(x['max_wait'] for x in nav),'max_work':max(x['max_work'] for x in nav),'continuous_intervals':{'ticks':ticks,'service_us':elapsed,'mean_service_ms_per_tick':round(elapsed/ticks/1000,4),'completed_requests':completed,'mean_completion_ticks':round(waits/completed,3) if completed else None,'expanded':sum(y['expanded']-x['expanded'] for x,y in intervals),'committed':sum(y['committed']-x['committed'] for x,y in intervals)},'last_observation':nav[-1]}
                results[name]=r
                if a.logs_only:
                    assert archived['cases'][name]['log_sha256']==sha(log),name
                    continue
                manifest=next((a.capture/name).glob('*.build.json'));m=json.loads(manifest.read_text());manifests[version]=m;rom=next((a.capture/name).glob('*.z64'))
                provenance[name]={'source_commit':m['runtime_commit'],'asset_commit':m['asset_commit'],'log_sha256':sha(log),'rom_sha256':sha(rom),'manifest_sha256':sha(manifest),'local_manifest':str(manifest.resolve()),'local_rom':str(rom.resolve()),'toolchain':m['toolchain'],'render_bank_sha256':m['render_bank_experiment']['sha256']}
            x=results[f'baseline-{kind}-{n}']['living_players_and_landed_enemies'];y=results[f'candidate-{kind}-{n}']['living_players_and_landed_enemies']
            print(kind,n,x['fps_mean'],y['fps_mean'],round((y['fps_mean']/x['fps_mean']-1)*100,1),results[f'candidate-{kind}-{n}']['navigation'])
            if a.logs_only:continue
            b,c=manifests['baseline'],manifests['candidate'];bo=dict(b['options']);co=dict(c['options']);bo.pop('output_dir');co.pop('output_dir');assert bo==co
            assert b['asset_commit']==c['asset_commit'] and b['render_bank_experiment']['sha256']==c['render_bank_experiment']['sha256']
            bi,ci=inputs(b),inputs(c);changes={k:{'baseline':bi.get(k),'candidate':ci.get(k)} for k in sorted(bi.keys()|ci.keys()) if bi.get(k)!=ci.get(k)}
            allowed={'port/n64/main.c','port/n64/pve.h','port/n64/pve_nav.inc','port/n64/pve_tick.inc','port/n64/pve_routes.inc','port/n64/firefight_game.inc'}
            assert set(changes)==allowed,(kind,n,list(changes))
            comparisons[f'{kind}-{n}']={'options_identical_except_output_directory':True,'private_assets_and_render_bank_identical':True,'runtime_differences':changes}
    (a.output/'results.json').write_text(json.dumps({'schema':1,'cases':results},indent=2)+'\n')
    if not a.logs_only:
        (a.output/'provenance.json').write_text(json.dumps({'schema':1,'emulator':'Ares v148, NTSC 320x240, 8 MiB, audio enabled, uncapped diagnostic','settings_sha256':sha(a.capture/'ares.bml'),'cases':provenance,'matched_inputs':comparisons},indent=2)+'\n')
if __name__=='__main__':main()
