"""Separate simulation-tick attribution, live FPS, frozen pixels and GPU controls."""
import hashlib,importlib.util,json,re,shutil,statistics,subprocess
from pathlib import Path
import numpy as np
from PIL import Image
from run import ROOT,HERE,OUT,CASES
VIEW=ROOT.parents[2]/'build/n64-vehicle-costs'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
ff=module('ff',HERE.parent/'firefight-limited/collect.py')
def rgb(raw):return np.stack([((raw>>n)&31)*255//31 for n in (11,6,1)],axis=2).astype('uint8')
def decode(log,output,tick):
    blocks=re.findall(r'FF_PHOTO_BEGIN.*?FF_PHOTO_END',log.read_text(),re.S);assert len(blocks)==9
    output.mkdir(parents=True,exist_ok=True);frames=[]
    for page,block in enumerate(blocks):
        assert int(re.search(r'tick=(\d+)',block)[1])==tick
        pixels=np.zeros(320*240,dtype='>u2');covered=np.zeros(320*240,dtype=bool)
        for first,data in re.findall(r'^FF_PIX (\d+) ([0-9a-f]+)$',block,re.M):
            first=int(first);chunk=np.frombuffer(bytes.fromhex(data),dtype='>u2');last=first+len(chunk)
            assert last<=len(pixels) and not covered[first:last].any();pixels[first:last]=chunk;covered[first:last]=True
        assert covered.all();frame=pixels.reshape(240,320);frames.append(frame);Image.fromarray(rgb(frame)).save(output/f'{page:02}.png')
    return frames
def rows(raw,prefix):return [ff.fields(line) for line in raw.splitlines() if line.startswith(prefix+' ')]
def sums(data,denominator,exclude=('tick','ticks','kind','max_tick_us')):
    return {k:sum(r[k] for r in data)/denominator for k in data[0] if k not in exclude} if data else {}

def main():
    VIEW.mkdir(parents=True,exist_ok=True);(HERE/'logs').mkdir(exist_ok=True)
    results={'description':'Diagnostic attribution, not an optimization. Ares v148 NTSC, 8 MiB, audio on. Live captures:45 observations, first5 discarded for FPS. CPU totals integrate complete 30-tick windows, including startup/restarts; inclusive child buckets overlap. Frozen timings serialize category drains; they are not gameplay FPS or independent RSP/RDP occupancies.', 'live':{},'frozen':{}}
    provenance={};images={};validation={}
    generators=[OUT/'live-generator.py',OUT/'draw-generator.py',ROOT/'port/n64/vehicle_cost_audit_source.py']
    generator_hashes={sha(p):p.name for p in generators if p.is_file()}
    for name in CASES:
        log=OUT/(name+'-native.log');raw=log.read_text()
        assert not any(x in raw.lower() for x in ('assertion failed','assertf','exception at','rdpq error','rdpq warning')),name
        manifest=next((OUT/name).glob('*.build.json'));m=json.loads(manifest.read_text());rom=Path(m['rom']['path'])
        assert sha(rom)==m['rom']['sha256']
        for path,digest in m['vehicle_cost_audit']['sources'].items():assert sha(Path(path))==digest,path
        assert m['vehicle_cost_audit']['generator_sha256'] in generator_hashes,name
        verified=0;historical=[]
        for group in ('sources','headers','included_data','generated_adapters'):
            for path,digest in m[group].items():
                source=ROOT/path
                if not source.is_file() or sha(source)!=digest:
                    relative=str(source.relative_to(ROOT))
                    blob=subprocess.run(['git','show',m['runtime_commit']+':'+relative],cwd=ROOT,capture_output=True,check=True).stdout
                    assert hashlib.sha256(blob).hexdigest()==digest,(name,group,path)
                    historical.append({'path':relative,'commit':m['runtime_commit'],'sha256':digest})
                verified+=1
        validation[name]={'verified_manifest_inputs':verified,'historical_inputs':historical,
                          'generator':generator_hashes[m['vehicle_cost_audit']['generator_sha256']]}
        provenance[name]={'rom_sha256':sha(rom),'manifest_sha256':sha(manifest),'log_sha256':sha(log),
                          'runtime_commit':m['runtime_commit'],'asset_commit':m['asset_commit'],
                          'options':m['options'],'diagnostic':m['vehicle_cost_audit']}
        (HERE/'logs'/(name+'.log')).write_text('\n'.join(x for x in raw.splitlines() if not x.startswith(('FF_PIX','FF_PHOTO')))+'\n')
        if name.startswith('live-'):
            perf=ff.summarize(log);assert perf['observations']==45
            phases=rows(raw,'COLLISION');ticks=sum(r['ticks'] for r in phases)
            ai=rows(raw,'VA_AI');physics=rows(raw,'VA_PHYS')
            perf['profiled_ticks']=ticks;perf['cpu_us_per_tick']=sums(phases,ticks)
            perf['worst_tick_us']=max(r['max_tick_us'] for r in phases)
            perf['ai_per_tick']={str(k):sums([r for r in ai if r['kind']==k],ticks) for k in (1,3,4,5)}
            perf['physics_per_tick']={str(k):sums([r for r in physics if r['kind']==k],ticks) for k in (1,3,4,5)}
            # Keep call-weighted active-vehicle figures distinct from whole-run cost.
            perf['physics_per_step']={str(k):sums([r for r in physics if r['kind']==k],sum(r['steps'] for r in physics if r['kind']==k)) for k in (1,3,4,5) if sum(r['steps'] for r in physics if r['kind']==k)}
            results['live'][name]=perf
        else:
            arr=decode(log,VIEW/name,m['options']['pve_photo_tick']);images[name]=arr
            state=[x for x in raw.splitlines() if x.startswith(('VA_STATE ','VA_CAMERA ','VA_HULL '))]
            timing=[]
            for line in raw.splitlines():
                if line.startswith('VA_DRAW '):timing.append({**ff.fields(line),'category':re.search(r'category=(\w+)',line)[1]})
            assert len(timing)==28,(name,len(timing))
            data={'state':state,'hulls':rows(raw,'VA_HULL'),'categories':timing,
                  'baseline_changed_pixels':{str(i):int((arr[0]!=arr[i]).sum()) for i in (1,7,8)}}
            if not name.startswith('empty'):
                assert not any(data['baseline_changed_pixels'].values()),(name,data['baseline_changed_pixels'])
                data['omission_pixels']={}
                for i in range(2,7):
                    delta=arr[0]!=arr[i];bounds=[]
                    for y,x in ((0,0),(0,160),(120,0),(120,160)):
                        ys,xs=np.where(delta[y:y+120,x:x+160]);bounds.append([int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)] if len(xs) else None)
                    data['omission_pixels'][str(i)]={'all_cameras':int(delta.sum()),'per_camera':[int(delta[y:y+120,x:x+160].sum()) for y,x in ((0,0),(0,160),(120,0),(120,160))],'per_camera_bbox':bounds}
                    Image.fromarray(np.minimum(np.abs(rgb(arr[0]).astype(int)-rgb(arr[i]).astype(int))*4,255).astype('uint8')).save(VIEW/name/f'diff-{i}.png')
            results['frozen'][name]=data
    for name in ('timing-60','empty-60'):
        assert results['frozen']['photo-60']['state']==results['frozen'][name]['state'],name
        a=results['frozen']['photo-60']['categories'];b=results['frozen'][name]['categories']
        assert [(r['view'],r['category'],r['vertices'],r['triangles']) for r in a]==[(r['view'],r['category'],r['vertices'],r['triangles']) for r in b],name
    assert np.array_equal(images['photo-60'][0],images['timing-60'][0])
    for filename,data in [('results.json',results),('provenance.json',provenance),('validation.json',validation)]:
        payload=json.dumps(data,indent=2)+'\n';(HERE/filename).write_text(payload);(OUT/filename).write_text(payload);(VIEW/filename).write_text(payload)
    labels=['Full scene','Full scene / category timing','Ghost hull omitted','Banshee hull omitted','Wraith hull omitted','Shade hull omitted','All vehicle hulls omitted','Full-scene repeat','Full-scene repeat']
    html='''<!doctype html><meta charset="utf-8"><title>Firefight vehicle cost audit</title><style>body{max-width:1100px;margin:32px auto;padding:0 20px;background:#14202b;color:#edf3f8;font:16px/1.5 system-ui}a{color:#8ed7ff}select,button{font:inherit;padding:8px;margin:4px;background:#243e50;color:white;border:1px solid #59778b}.pair{display:flex;gap:16px}figure{flex:1;margin:0}img{width:100%;image-rendering:pixelated}</style>
<h1>Firefight: where vehicle time goes</h1><p>Frozen native four-camera inspection. Omitting a hull shows its contribution to this image; its pilot and gameplay remain. This is diagnostic evidence, not an adopted visibility shortcut.</p>
<p><a href="results.json">Counters, camera states and pixel checks</a> · <a href="provenance.json">Build provenance</a></p><select id="route"><option value="photo-1">Tick 1</option><option value="photo-60">Tick 60</option><option value="photo-180">Tick 180</option></select><select id="page"></select><button id="diff">Difference ×4</button><h2 id="label"></h2><div class="pair"><figure><figcaption>Full scene</figcaption><img id="before"></figure><figure><figcaption id="caption">Diagnostic</figcaption><img id="after"></figure></div>
<p>Native 320×240 framebuffer readbacks. The ordinary route, serialized timing and empty-scissor controls have matching state and load records at tick 60. Empty-scissor pixels are excluded from visibility claims. Live FPS and per-tick CPU results are separate from these frozen graphics spans. No gameplay or geometry optimization is adopted.</p>
<script>const labels=__LABELS__;const $=x=>document.getElementById(x);let diff=false;labels.forEach((t,i)=>{let o=document.createElement('option');o.textContent=t;o.value=i;$('page').append(o)});function show(){let r=$('route').value,p=+$('page').value;let use=diff&&p>=2&&p<=6;$('before').src=r+'/00.png';$('after').src=r+'/'+(use?'diff-'+p+'.png':String(p).padStart(2,'0')+'.png');$('label').textContent=labels[p];$('caption').textContent=use?'Difference ×4':'Diagnostic'}$('route').onchange=$('page').onchange=show;$('diff').onclick=()=>{diff=!diff;show()};show();</script>'''
    (VIEW/'comparison.html').write_text(html.replace('__LABELS__',json.dumps(labels)))
    for name,data in results['live'].items():print(name,data['living_players_and_landed_enemies'],data['cpu_ms'],data['cpu_us_per_tick']['tick_us'])
    for name in ('timing-60','empty-60'):
        print(name,{c:round(sum(r['span'] for r in results['frozen'][name]['categories'] if r['category']==c)/1000,3) for c in ('world','vehicles','covenant','players','pickups','effects','firstperson')})
    print(VIEW/'comparison.html')
if __name__=='__main__':main()
