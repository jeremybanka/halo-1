"""Matched native framebuffer comparisons and fresh live/serialized timing results."""
import argparse,hashlib,importlib.util,json,re,shutil,statistics
from pathlib import Path
import numpy as np
from PIL import Image
from run import ROOT,HERE,OUT,CASES
VIEW=ROOT.parents[2]/'build/n64-vehicle-lods'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('ff',HERE.parent/'firefight-limited/collect.py');ff=importlib.util.module_from_spec(spec);spec.loader.exec_module(ff)
def rgb(raw):return np.stack([((raw>>n)&31)*255//31 for n in (11,6,1)],axis=2).astype('uint8')
def decode(name,count):
    text=(OUT/(name+'-native.log')).read_text();blocks=re.findall(r'FF_PHOTO_BEGIN.*?FF_PHOTO_END',text,re.S);assert len(blocks)==count,(name,len(blocks))
    dest=VIEW/name;dest.mkdir(parents=True,exist_ok=True);frames=[]
    for page,block in enumerate(blocks):
        pixels=np.zeros(320*240,dtype='>u2');covered=np.zeros(320*240,dtype=bool)
        for first,data in re.findall(r'^FF_PIX (\d+) ([0-9a-f]+)$',block,re.M):
            first=int(first);chunk=np.frombuffer(bytes.fromhex(data),dtype='>u2');last=first+len(chunk)
            assert last<=len(pixels) and not covered[first:last].any();pixels[first:last]=chunk;covered[first:last]=True
        assert covered.all(),(name,page)
        image=pixels.reshape(240,320);frames.append(image);Image.fromarray(rgb(image)).save(dest/f'{page:02}.png')
    return frames,text
def difference(a,b,path):
    Image.fromarray(np.minimum(np.abs(rgb(a).astype(int)-rgb(b).astype(int))*4,255).astype('uint8')).save(path)
    return int((a!=b).sum())
def photo_checks():
    VIEW.mkdir(parents=True,exist_ok=True);(VIEW/'diff').mkdir(exist_ok=True)
    before,log0=decode('before-photos',36);after,log1=decode('after-photos',36)
    states=[re.findall(r'^LOD_PHOTO .*$',s,re.M)[:36] for s in (log0,log1)];assert states[0]==states[1] and len(states[0])==36
    photos=[]
    for i,(a,b) in enumerate(zip(before,after)):
        changed=difference(a,b,VIEW/'diff'/f'{i:02}.png')
        assert np.array_equal(a,before[i-i%3]),('Reference repeat',i)
        if i%3==0:assert changed==0,('Near changed',i,changed)
        center=[float(v) for v in re.search(r'center=([^ ]+)',states[0][i])[1].split(',')]
        radius=float(re.search(r'radius=([^ ]+)',states[0][i])[1]);angles=(i%6)//3
        directions=(((1,.22,0),(-1,.22,0),(0,.22,1),(0,.22,-1)),((1,.55,1),(-1,.55,-1),(1,.55,-1),(-1,.55,1)))[angles]
        photos.append({'page':i,'state':states[0][i],'changed_pixels':changed,
                       'camera_eye':[[center[a]+d[a]*radius for a in range(3)] for d in directions],
                       'camera_target':center,'pilot_animation_time':.5,'pilot_seat_state':0,
                       'reference_forced_tier':'detailed','candidate_tier':i%3})
    (OUT/'photos.json').write_text(json.dumps(photos,indent=2)+'\n');(VIEW/'photos.json').write_text(json.dumps(photos,indent=2)+'\n')
    shutil.copytree(OUT/'silhouettes',VIEW/'silhouettes',dirs_exist_ok=True)
    shutil.copyfile(OUT/'silhouettes.json',VIEW/'silhouettes.json')
    print('PASS 36 matched native pages ×4 angles; all 12 near pages and all detailed reference repeats exact')
    return photos
def rows(raw,prefix):return [ff.fields(line) for line in raw.splitlines() if line.startswith(prefix+' ')]
def all_checks():
    photos=photo_checks();results={'live':{},'frozen':{},'photos':photos};provenance={};(HERE/'logs').mkdir(exist_ok=True)
    for name in CASES:
        manifest=next((OUT/name).glob('*.build.json'));m=json.loads(manifest.read_text());rom=Path(m['rom']['path']);assert sha(rom)==m['rom']['sha256']
        for group in ('sources','headers','included_data','generated_adapters'):
            for path,want in m[group].items():assert sha(ROOT/path)==want,(name,group,path)
        provenance[name]={'manifest_sha256':sha(manifest),'rom_sha256':sha(rom),'options':m['options'],'runtime_commit':m['runtime_commit'],'asset_commit':m['asset_commit']}
        if name.endswith('play'):continue
        log=OUT/(name+'-native.log');raw=log.read_text();provenance[name]['log_sha256']=sha(log)
        assert not any(word in raw.lower() for word in ('assertion failed','assertf','rdpq error','rdpq warning','exception at')),name
        (HERE/'logs'/(name+'.log')).write_text('\n'.join(line for line in raw.splitlines() if not line.startswith(('FF_PIX','FF_PHOTO')))+'\n')
        if re.fullmatch(r'(before|after)-[89]-[1-4]',name):
            summary=ff.summarize(log);assert summary['observations']==45
            collision=rows(raw,'COLLISION');ticks=sum(r['ticks'] for r in collision)
            summary['profiled_ticks']=ticks
            summary['cpu_us_per_tick']={k:sum(r[k] for r in collision)/ticks for k in collision[0] if k not in ('tick','ticks','max_tick_us')}
            summary['all_players_alive']={}
            alive=[r['PERF']['fps'] for r in summary['samples'][5:] if r['FF_STATE']['living']==int(name[-1]) and r['FF_STATE']['enemies']>0 and r['FF_STATE']['arriving']==0]
            if alive:summary['all_players_alive']={'observations':len(alive),'fps_mean':round(statistics.mean(alive),2),'fps_min':min(alive),'fps_max':max(alive)}
            results['live'][name]=summary
        elif not name.endswith('photos'):
            frames,raw=decode(name,9)
            assert all(np.array_equal(frames[0],frames[i]) for i in (1,7,8)),name
            cameras=re.findall(r'^VA_(?:STATE|CAMERA) .*$',raw,re.M)
            hulls=re.findall(r'^VA_HULL .*$',raw,re.M)
            timings=[{**ff.fields(line),'category':re.search(r'category=(\w+)',line)[1]} for line in raw.splitlines() if line.startswith('VA_DRAW ')]
            assert len(timings)==28
            results['frozen'][name]={'cameras':cameras,'hulls':hulls,'timings':timings,'full_repeats_exact':True}
    for tick in (1,60,180):
        before=results['frozen'][f'before-route-{tick}'];after=results['frozen'][f'after-route-{tick}']
        assert before['cameras']==after['cameras'],('Camera/state mismatch',tick)
        poses=lambda data:[re.sub(r' lod=\d+ vertices=\d+ triangles=\d+','',line) for line in data['hulls']]
        assert poses(before)==poses(after),('Hull pose mismatch',tick)
        a,_=decode(f'before-route-{tick}',9);b,_=decode(f'after-route-{tick}',9)
        after['changed_pixels']=difference(a[0],b[0],VIEW/'diff'/f'route-{tick}.png')
        # Removing all hulls isolates the unchanged remainder of the scene.
        assert np.array_equal(a[6],b[6]),('Non-vehicle scene changed',tick)
        after['all_hulls_omitted_exact']=True
    for variant in ('before','after'):
        a,_=decode(variant+'-route-60',9);b,_=decode(variant+'-timing',9)
        assert np.array_equal(a[0],b[0]),variant
        assert results['frozen'][variant+'-route-60']['cameras']==results['frozen'][variant+'-timing']['cameras']
    for name,data in [('results.json',results),('provenance.json',provenance)]:
        text=json.dumps(data,indent=2)+'\n'
        for folder in (HERE,OUT,VIEW):(folder/name).write_text(text)
    return results
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--photos-only',action='store_true');args=p.parse_args()
    if args.photos_only:photo_checks()
    else:
        data=all_checks()
        for name,row in data['live'].items():print(name,row['living_players_and_landed_enemies'],row['cpu_ms'],row['vertex_loads'])
