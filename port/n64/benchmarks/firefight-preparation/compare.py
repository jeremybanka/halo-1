#!/usr/bin/env python3
"""Require exact native RDP pixels, matching poses and matching photo build inputs."""
import argparse,hashlib,importlib.util,json,re,shutil,struct
from pathlib import Path
import numpy as np
from PIL import Image
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('models',HERE.parent/'covenant-models/compare.py');models=importlib.util.module_from_spec(spec);spec.loader.exec_module(models)
spec=importlib.util.spec_from_file_location('nav',HERE.parent/'firefight-navigation/collect.py');nav=importlib.util.module_from_spec(spec);spec.loader.exec_module(nav)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('capture',type=Path);p.add_argument('output',type=Path);p.add_argument('--evidence',type=Path,default=HERE);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);a.evidence.mkdir(parents=True,exist_ok=True)
    images={};states={};raw={};provenance={};manifests={}
    for version in ('before','after'):
        log=a.capture/('photo-'+version+'-native.log');text=log.read_text()
        assert not any(x in text.lower() for x in ('assertion failed','assertf','rdpq error','rdpq warning'))
        images[version]=models.decode(log,a.output/version)
        blocks=re.findall(r'FF_PHOTO_BEGIN.*?FF_PHOTO_END',text,re.S)
        raw[version]=[b''.join(bytes.fromhex(data) for _,data in re.findall(r'^FF_PIX (\d+) ([0-9a-f]+)$',block,re.M)) for block in blocks]
        assert len(raw[version])==52 and all(len(b)==320*240*2 for b in raw[version])
        states[version]=re.findall(r'^MODEL_PHOTO .*$',text,re.M)[:52]
        manifest=next((a.capture/('photo-'+version)).glob('*.build.json'));rom=next(manifest.parent.glob('*.z64'));m=manifests[version]=json.loads(manifest.read_text())
        assert m['options']['pve_model_qa'] and m['options']['validate'] and not m['options']['profile']
        assert bool(m['options']['pve_prep_baseline'])==(version=='before')
        provenance[version]={'log_sha256':sha(log),'rom_sha256':sha(rom),'manifest_sha256':sha(manifest),'options':m['options'],'inputs':nav.inputs(m),'parent_source_commit':m['runtime_commit'],'asset_commit':m['asset_commit'],'toolchain':m['toolchain']}
    assert states['before']==states['after'] and len(states['before'])==52
    b,c=[manifests[v] for v in ('before','after')];bo,co=dict(b['options']),dict(c['options'])
    for options in (bo,co):
        for k in ('output_dir','pve_prep_baseline'):options.pop(k)
    assert bo==co and nav.inputs(b)==nav.inputs(c)
    changes=[];(a.output/'diff').mkdir(exist_ok=True)
    for i,(before,after) in enumerate(zip(images['before'],images['after'])):
        delta=np.abs(before.astype(int)-after.astype(int));Image.fromarray(np.minimum(delta*4,255).astype('uint8')).save(a.output/'diff'/f'{i:02}.png')
        exact=int(np.count_nonzero(np.frombuffer(raw['before'][i],dtype='>u2')!=np.frombuffer(raw['after'][i],dtype='>u2')))
        changes.append({'page':i,'changed_rgba16_pixels':exact,'changed_rgb_pixels':int(np.any(delta,axis=2).sum()),'before_sha256':hashlib.sha256(raw['before'][i]).hexdigest(),'after_sha256':hashlib.sha256(raw['after'][i]).hexdigest(),'state':states['before'][i]})
    checks={'schema':1,'frames':52,'views_per_frame':4,'pixel_format':'RDP RGBA16, all 16 bits compared','changed_pixels':sum(r['changed_rgba16_pixels'] for r in changes),'frames_checked':changes}
    (a.evidence/'pixel-checks.json').write_text(json.dumps(checks,indent=2)+'\n');(a.evidence/'photo-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    (a.output/'photos.json').write_text(json.dumps(checks,indent=2)+'\n')
    assert checks['changed_pixels']==0,'Native images changed; inspect the diff before accepting'
    labels=[re.sub(r'^MODEL_PHOTO ','',s) for s in states['before']]
    results=json.loads((a.evidence/'results.json').read_text()) if (a.evidence/'results.json').exists() else None
    data=json.dumps({'labels':labels,'perf':results})
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Firefight NPC preparation appraisal</title><style>[hidden]{display:none!important}body{max-width:1150px;margin:32px auto;padding:0 22px;background:#111b22;color:#e7f0f0;font:16px/1.6 system-ui}a{color:#8fddcc}h1{font-size:34px;line-height:1.2}button,select{font:inherit;background:#243841;color:#edf7f5;border:1px solid #55747a;padding:8px;margin:4px;max-width:100%}.pair{display:flex;gap:12px}.pair figure{margin:0;flex:1}img{width:100%;image-rendering:pixelated}#single{max-width:800px;margin:auto}.muted{color:#adc2c5}td,th{padding:10px 18px;text-align:left;border-bottom:1px solid #36505b}table{border-collapse:collapse}</style>
<p class="muted">N64 Firefight · preparation reuse · prototype for appraisal</p><h1>Same poses and pixels.<br>Less repeated preparation.</h1><p>Shared ROM sample cache, exact same-frame pose sharing and aligned packed position writes. Animation timing, geometry, LOD selection, attachments and hit meshes are unchanged.</p><p><strong>52 native frames × four cameras: every RGBA16 pixel matches.</strong> The difference filter is black throughout. No animation decimation or coarser time quantization is used.</p>
<select id="page"></select><button id="prev">Previous</button><button id="next">Next</button><div><button data-mode="pair">Side by side</button><button data-mode="before">Before</button><button data-mode="after">After</button><button data-mode="diff">Difference ×4</button><button id="blink">Blink</button></div><p id="label"></p><div class="pair" id="pair"><figure><figcaption>Before</figcaption><img id="before"></figure><figure><figcaption>After</figcaption><img id="after"></figure></div><div id="single" hidden><img id="one"></div><p class="muted">Original 52-state inspection route, both LODs, Hunter/Spirit articulation, Jackal shield states/occlusion and Grunt/Elite movement. Models are suspended to expose feet and undersides. Existing missing Jackal shield visuals remain unchanged.</p>
<h2>Native performance</h2><div id="perf"></div><p>Four-player NPC preparation falls <strong>13.99 → 7.69 ms opening</strong> and <strong>25.69 → 14.77 ms crowded</strong>, at a cost of 112.48 KiB additional fixed RAM. In the crowded subset with <strong>all four humans alive, FPS stays 3.95 → 3.95</strong>. The broader mean below does not establish a sustained full-party FPS gain.</p><p class="muted">Ares v148 · 320×240 NTSC · 8 MiB · audio on. Active-combat means after warm-up; one capture per case. Both sides use the same opt-in Hunter/Spirit bank and collision optimization. These are emulator measurements. Identical scenarios can produce different sampled combat windows.</p>
<p><a href="report.md">Full report and profiling</a> · <a href="halo64-preparation-appraisal.z64">Playable appraisal ROM</a> · <a href="https://github.com/jeremybanka/halo-1/pull/12">Draft PR #12</a></p>
<script>const DATA=__DATA__;let index=0,mode='pair',timer=null;const $=x=>document.getElementById(x);DATA.labels.forEach((x,i)=>{let o=document.createElement('option');o.value=i;o.textContent=x;$('page').append(o)});function show(){let file=String(index).padStart(2,'0')+'.png';$('label').textContent=DATA.labels[index];$('page').value=index;for(let v of ['before','after'])$(v).src=v+'/'+file;$('pair').hidden=mode!=='pair';$('single').hidden=mode==='pair';if(mode!=='pair')$('one').src=mode+'/'+file}function stop(){clearInterval(timer);timer=null}document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>{stop();mode=b.dataset.mode;show()});$('page').onchange=e=>{index=+e.target.value;show()};$('prev').onclick=()=>{index=(index+51)%52;show()};$('next').onclick=()=>{index=(index+1)%52;show()};$('blink').onclick=()=>{if(timer){stop();return}mode='before';show();timer=setInterval(()=>{mode=mode==='before'?'after':'before';show()},600)};if(DATA.perf){let t=document.createElement('table');t.innerHTML='<tr><th>Players</th><th>Opening FPS</th><th>Crowded FPS</th></tr>';for(let n=1;n<=4;n++){let row='<td>'+n+'</td>';for(let kind of ['opening','perf']){let a=DATA.perf.cases['baseline-'+kind+'-'+n].living_players_and_landed_enemies,b=DATA.perf.cases['candidate-'+kind+'-'+n].living_players_and_landed_enemies;row+='<td>'+a.fps_mean.toFixed(2)+' → '+b.fps_mean.toFixed(2)+'</td>'}let tr=document.createElement('tr');tr.innerHTML=row;t.append(tr)}$('perf').append(t)}show();</script></html>'''.replace('__DATA__',data)
    (a.output/'comparison.html').write_text(html)
    print('PASS 52 matched four-camera frames: zero changed RGBA16 pixels; RDP validation clean; identical build inputs')
if __name__=='__main__':main()
