#!/usr/bin/env python3
"""Collect paired native NPC preparation profiles; retain counter scope and provenance."""
import argparse,hashlib,importlib.util,json,statistics,shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('collision',HERE.parent/'firefight-collision/collect.py')
collision=importlib.util.module_from_spec(spec);spec.loader.exec_module(collision)
prior=collision.prior
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def summarize(log):
    result=collision.summarize(log);rows=[];pending=None
    for line in log.read_text().splitlines():
        if line.startswith('NPC_PREP '):pending=prior.fields(line)
        if line.startswith('PERF views='):
            assert pending is not None;rows.append(pending);pending=None
    used=rows[5:];totals={k:sum(r[k] for r in used) for k in used[0]}
    result['npc_preparation']={
        'sampled_frames':len(used),
        'ms_per_sampled_frame':{k[:-3]:round(v/len(used)/1000,4) for k,v in totals.items() if k.endswith('_us')},
        'mean_counts':{k:round(v/len(used),3) for k,v in totals.items() if not k.endswith('_us')},
        'totals':{k:v for k,v in totals.items() if not k.endswith('_us')},
        'motion_pair_hit_percent':round(100*totals['pair_hits']/max(1,totals['pair_requests']),2),
        'shared_pose_percent':round(100*totals['shared_poses']/max(1,totals['pose_requests']),2)}
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
                assert not m['options']['collision_baseline'] and m['options']['pve_prep_profile']
                assert not m['options']['pve_prep_baseline'] and m['options']['pve_crunch']
                assert bool(m['options']['pve_crunch_baseline'])==(version=='baseline')
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
                    for field in ('output_dir','pve_crunch_baseline'):options.pop(field)
                assert bo==co,(kind,players,'options')
                assert prior.inputs(b)==prior.inputs(c),(kind,players,'inputs')
                assert b['included_data']==c['included_data']
                matched[f'{kind}-{players}']='Identical runtime sources, headers, geometry, rules and assets; only pve-crunch-baseline body/gun LOD-selection control differs'
                print(kind,players,cases[f'baseline-{kind}-{players}']['living_players_and_landed_enemies'],cases[f'candidate-{kind}-{players}']['living_players_and_landed_enemies'])
    (a.output/'results.json').write_text(json.dumps({'schema':1,'gpu_serialized':a.gpu,'cases':cases},indent=2)+'\n')
    if not archived:(a.output/'provenance.json').write_text(json.dumps({'schema':1,'gpu_serialized':a.gpu,'emulator':'Ares v148, NTSC 320x240, 8 MiB, audio on','settings_sha256':sha(a.capture/'ares.bml'),'cases':provenance,'matched':matched},indent=2)+'\n')
if __name__=='__main__':main()
