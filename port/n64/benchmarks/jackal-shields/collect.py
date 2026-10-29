"""Matched shield-off/on native results, with raw counters and build hashes."""
import argparse,hashlib,importlib.util,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent;OUT=ROOT/'build/jackal-shields'
spec=importlib.util.spec_from_file_location('prior',HERE.parent/'covenant-crunch/collect.py');prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
p=argparse.ArgumentParser();p.add_argument('--logs-only',action='store_true');a=p.parse_args()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
saved=json.loads((HERE/'provenance.json').read_text()) if a.logs_only else None
cases={};proof={};matched={}
def inputs(m):
    result={}
    for section in ('sources','headers','included_data','generated_adapters'):
        for name,digest in m[section].items():
            for prefix,replacement in ((m['options']['pve_model_bank']+'/','bank/'),(m['options']['output_dir']+'/','build/'),(str(ROOT)+'/','')):
                if name.startswith(prefix):name=replacement+name[len(prefix):];break
            result[name]=digest
    return result
for suite in ('control','roster','ordinary'):
    for n in range(1,5):
        manifests={}
        for version in ('before','after'):
            name=f'{version}-{suite}-{n}';log=(HERE if a.logs_only else OUT)/(name+'-native.log')
            if not log.exists() or log.read_text().count('PERF views=')!=45:continue
            text=log.read_text();assert not any(s in text.lower() for s in ('assertion failed','rdpq error','rdpq warning'))
            cases[name]=prior.summarize(log)
            if a.logs_only:
                assert sha(log)==saved['cases'][name]['log_sha256'];continue
            manifest=next((OUT/name).glob('*.build.json'));rom=next((OUT/name).glob('*.z64'));m=json.loads(manifest.read_text());manifests[version]=m
            assert sha(rom)==m['rom']['sha256'],(name,'ROM changed since build')
            assert m['options']['pve_qa']=={'control':4,'roster':7,'ordinary':3}[suite] and m['options']['pve_players']==n
            assert m['options']['pve_jackal_shields']==(version=='after')
            proof[name]={'rom_sha256':sha(rom),'rom_bytes':rom.stat().st_size,'manifest_sha256':sha(manifest),'log_sha256':sha(log),
                         'inputs':inputs(m),'options':m['options'],'toolchain':m['toolchain'],
                         'parent_source_commit':m['runtime_commit'],'parent_asset_commit':m['asset_commit'],
                         'map_sha256':m['render_bank_experiment']['sha256']}
            shutil.copyfile(log,HERE/log.name)
        if len(manifests)==2:
            before,after=manifests['before'],manifests['after'];bo,ao=dict(before['options']),dict(after['options'])
            for d in (bo,ao):
                for field in ('output_dir','pve_model_bank','pve_jackal_shields'):d.pop(field)
            assert bo==ao,(suite,n,'different options')
            bi,ai=inputs(before),inputs(after);diff={k:(bi.get(k),ai.get(k)) for k in bi.keys()|ai.keys() if bi.get(k)!=ai.get(k)}
            assert set(diff)=={'bank/pve_jackal_shield.c'},(suite,n,diff)
            matched[f'{suite}-{n}']='Same source/header inputs and original bank; shield flag and one additional source-derived shield asset only.'
result={'schema':1,'scope':'Ares v148, NTSC 320x240, 8 MiB, audio enabled, uncapped; 45 observations per case minus 5 warmup. Engaged FPS means at least one human and enemy alive, no arrival underway. CPU counters retain their separate scopes.','cases':cases}
for path in (OUT/'results.json',HERE/'results.json'):path.write_text(json.dumps(result,indent=2)+'\n')
if not a.logs_only:
    provenance={'cases':proof,'matched':matched,'settings_sha256':sha(OUT/'ares.bml'),'build_script_sha256':sha(ROOT/'port/n64/build.py')}
    for path in (OUT/'provenance.json',HERE/'provenance.json'):path.write_text(json.dumps(provenance,indent=2)+'\n')
for key,r in cases.items():print(key,r['living_players_and_landed_enemies'],'free',r['min_free_bytes'])
