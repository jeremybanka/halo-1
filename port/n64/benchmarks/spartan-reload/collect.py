#!/usr/bin/env python3
"""Record native reload comparison provenance and the ordinary 2P smoke run."""
import argparse, hashlib, importlib.util, json, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def normalized_sources(m):
    output=(ROOT/m['options']['output_dir']).resolve();result={}
    for name,digest in m['sources'].items():
        p=Path(name)
        key='scene.c' if p.name in ('scene.c','before-scene.c') else str(p.relative_to(output)) if p.is_relative_to(output) else str(p)
        result[key]=digest
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('capture',type=Path);p.add_argument('--output',type=Path,default=HERE);a=p.parse_args();out=a.capture.resolve();a.output.mkdir(parents=True,exist_ok=True)
    result={'schema':1,'note':'Both photos use the final bank and same frozen fixture; only scene.c differs. Parent revisions plus file hashes identify measured working-tree inputs.',
            'emulator':'Ares v148, NTSC 320x240, 8 MiB, audio enabled','settings_sha256':sha(out/'ares.bml'),'cases':{}}
    for name in ('before','after','opening-2','playable'):
        manifest=next((out/name).glob('*.build.json'));m=json.loads(manifest.read_text());rom=next((out/name).glob('*.z64'))
        row={'local_manifest':str(manifest),'manifest_sha256':sha(manifest),'rom_sha256':sha(rom),'rom_bytes':rom.stat().st_size,
             'parent_runtime_commit':m['runtime_commit'],'parent_asset_commit':m['asset_commit'],'options':m['options'],'toolchain':m['toolchain'],
             'sources':m['sources'],'headers':m['headers'],'included_data':m['included_data'],'render_bank':m['render_bank_experiment']}
        log=out/(name+'-native.log')
        if log.exists():row['log_sha256']=sha(log)
        result['cases'][name]=row
    for name in ('before','after'):
        text=(out/(name+'-native.log')).read_text();assert text.count('FF_PHOTO_END')==72
        assert not any(s in text.lower() for s in ('assertion failed','assertf','rdpq error','rdpq warning'))
    b,c=[result['cases'][v] for v in ('before','after')];assert b['headers']==c['headers'] and b['included_data']==c['included_data']
    x,y=normalized_sources(b),normalized_sources(c);assert {k for k in x.keys()|y.keys() if x.get(k)!=y.get(k)}=={'scene.c'}
    result['memory']={}
    for name in ('interactions.bin','player-hits.bin'):
        path=ROOT/'build/n64/frontend-files'/name;before=out/('before-'+name)
        result['memory'][name]={'before_bytes':before.stat().st_size,'after_bytes':path.stat().st_size,'before_sha256':sha(before),'after_sha256':sha(path)}
    result['memory'].update(pose_pair_bytes=8736,cache_allocation_bytes=70912)
    spec=importlib.util.spec_from_file_location('firefight_collect',HERE.parent/'firefight-limited/collect.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    perf=module.summarize(out/'opening-2-native.log');assert perf['observations']==75
    (a.output/'opening-2-results.json').write_text(json.dumps(perf,indent=2)+'\n')
    (a.output/'provenance.json').write_text(json.dumps(result,indent=2)+'\n')
    for name in ('host-motion.log','host-firefight.log','assets-test.log','reload-assets-test.log','deferred-test.log','configs-test.log','opening-2-native.log'):
        if (out/name).resolve()!=(a.output/name).resolve():shutil.copyfile(out/name,a.output/name)
    print('PASS 72 matched frames per version; only scene.c differs; ordinary 2P:',perf['living_players_and_landed_enemies'])

if __name__=='__main__':main()
