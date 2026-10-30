"""Validate native input provenance and matched state/pixels; summarize tick costs."""
import hashlib,importlib.util,json,re,statistics,shutil
from pathlib import Path
import numpy as np
from PIL import Image
from run import ROOT,HERE,OUT,CASES,rom_bytes
VIEW=ROOT.parents[2]/'build/n64-vehicle-simulation'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('ff',HERE.parent/'firefight-limited/collect.py');ff=importlib.util.module_from_spec(spec);spec.loader.exec_module(ff)
def rows(raw,prefix):return [ff.fields(line) for line in raw.splitlines() if line.startswith(prefix+' ')]
def sums(data,ticks):return {k:sum(r[k] for r in data)/ticks for k in data[0] if k not in ('tick','ticks','kind','max_tick_us')} if data else {}
def rgb(a):return np.stack([((a>>n)&31)*255//31 for n in (11,6,1)],axis=2).astype('uint8')
def photos(raw,name):
 blocks=re.findall(r'FF_PHOTO_BEGIN.*?FF_PHOTO_END',raw,re.S);assert len(blocks)==9
 frames=[];dest=VIEW/name;dest.mkdir(parents=True,exist_ok=True)
 for page,block in enumerate(blocks):
  a=np.zeros(320*240,dtype='>u2');covered=np.zeros(len(a),dtype=bool)
  for first,data in re.findall(r'^FF_PIX (\d+) ([0-9a-f]+)$',block,re.M):
   first=int(first);values=np.frombuffer(bytes.fromhex(data),dtype='>u2');end=first+len(values);assert end<=len(a) and not covered[first:end].any();a[first:end]=values;covered[first:end]=True
  assert covered.all();a=a.reshape(240,320);frames.append(a);Image.fromarray(rgb(a)).save(dest/f'{page:02}.png')
 assert all(np.array_equal(frames[0],frames[i]) for i in (1,7,8))
 return frames
def main():
 VIEW.mkdir(parents=True,exist_ok=True);(HERE/'logs').mkdir(exist_ok=True);results={'live':{},'verification':{},'photos':{}};provenance={};images={};traces={}
 for name in CASES:
  manifest=next((OUT/name).glob('*.build.json'));m=json.loads(manifest.read_text());assert hashlib.sha256(rom_bytes(Path(m['rom']['path']))).hexdigest()==m['rom']['sha256']
  verified=0
  for group in ('sources','headers','included_data','generated_adapters'):
   for path,want in m[group].items():assert sha(ROOT/path)==want,(name,group,path);verified+=1
  if m['vehicle_cost_audit']:
   for path,want in m['vehicle_cost_audit']['sources'].items():assert sha(Path(path))==want,(name,path)
  provenance[name]={'rom_sha256':m['rom']['sha256'],'manifest_sha256':sha(manifest),'verified_inputs':verified,'options':m['options']}
  if name.endswith('play'):continue
  log=OUT/(name+'-native.log');raw=log.read_text();provenance[name]['log_sha256']=sha(log)
  assert not any(x in raw.lower() for x in ('assertion failed','assertf','exception at','rdpq error','rdpq warning')),name
  (HERE/'logs'/(name+'.log')).write_text('\n'.join(x for x in raw.splitlines() if not x.startswith(('FF_PIX','FF_PHOTO')))+'\n')
  if '-photo-' in name:
   images[name]=photos(raw,name)
   results['photos'][name]={'state':re.findall(r'^VA_(?:STATE|CAMERA|HULL) .*$',raw,re.M),'repeat_exact':True}
  elif name.endswith('verify'):
   traces[name]=re.findall(r'^QUERY_TRACE .*$',raw,re.M);assert len(traces[name])==40
   images[name]=photos(raw,name)
   results['verification'][name]={'windows':len(traces[name]),'last':traces[name][-1]}
  else:
   result=ff.summarize(log);assert result['observations']==45
   data=rows(raw,'COLLISION');ticks=sum(r['ticks'] for r in data);result['profiled_ticks']=ticks;result['cpu_us_per_tick']=sums(data,ticks)
   ai=rows(raw,'VA_AI');physics=rows(raw,'VA_PHYS')
   result['ai_per_tick']={str(k):sums([r for r in ai if r['kind']==k],ticks) for k in (1,3,4,5)}
   result['physics_per_tick']={str(k):sums([r for r in physics if r['kind']==k],ticks) for k in (1,3,4,5)}
   alive=[r['PERF']['fps'] for r in result['samples'][5:] if r['FF_STATE']['living']==int(name[-1]) and r['FF_STATE']['enemies']>0 and r['FF_STATE']['arriving']==0]
   result['all_players_alive']={'observations':len(alive),'fps_mean':round(statistics.mean(alive),2) if alive else None}
   results['live'][name]=result
 n=min(map(len,traces.values()));assert traces['before-verify'][:n]==traces['after-verify'][:n],'Native per-tick state/shot divergence'
 assert all(np.array_equal(a,b) for a,b in zip(images['before-verify'],images['after-verify'])),'Tick1200 native pixels changed'
 results['verification']['matched_ticks']=n*30;results['verification']['matched_trace']=traces['before-verify'][:n]
 for tick in (60,180):
  before=f'before-photo-{tick}';after=f'after-photo-{tick}';assert results['photos'][before]['state']==results['photos'][after]['state']
  a=images[before];b=images[after];assert all(np.array_equal(x,y) for x,y in zip(a,b)),tick
  results['photos'][after]['changed_pixels']=0
  diff=np.minimum(np.abs(rgb(a[0]).astype(int)-rgb(b[0]).astype(int))*4,255).astype('uint8');Image.fromarray(diff).save(VIEW/f'diff-{tick}.png')
 for name,data in [('results.json',results),('provenance.json',provenance)]:
  for folder in (HERE,OUT,VIEW):(folder/name).write_text(json.dumps(data,indent=2)+'\n')
 for name,result in results['live'].items():print(name,result['living_players_and_landed_enemies'],result['cpu_us_per_tick']['tick_us'])
 for n in ('host-strict.json','host-target.json'):shutil.copyfile(HERE/n,VIEW/n)
 return results
if __name__=='__main__':main()
