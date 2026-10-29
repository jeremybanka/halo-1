"""Native pixel comparisons, fixed route provenance and appraisal viewer."""
import argparse,hashlib,importlib.util,json,re,shutil
from pathlib import Path
import numpy as np
from PIL import Image
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('photos',HERE.parent/'covenant-models/compare.py');photos=importlib.util.module_from_spec(spec);spec.loader.exec_module(photos)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('capture',type=Path);p.add_argument('output',type=Path);a=p.parse_args();out=a.output;out.mkdir(parents=True,exist_ok=True);out.joinpath('diff').mkdir(exist_ok=True)
 data={};raw={};states={};provenance={};rows=[];labels=[]
 for version in ('before','after'):
  log=a.capture/f'photo-{version}-native.log';text=log.read_text();data[version]=photos.decode(log,out/version);states[version]=re.findall(r'^MODEL_PHOTO .*$',text,re.M)[:52]
  raw[version]=[np.frombuffer(b''.join(bytes.fromhex(d) for _,d in re.findall(r'^FF_PIX (\d+) ([0-9a-f]+)$',block,re.M)),dtype='>u2') for block in re.findall(r'FF_PHOTO_BEGIN.*?FF_PHOTO_END',text,re.S)]
  provenance[version]={'log_sha256':sha(log),'rom_sha256':sha(next((a.capture/f'photo-{version}').glob('*.z64'))),'manifest':json.loads(next((a.capture/f'photo-{version}').glob('*.build.json')).read_text())}
  assert not any(x in text.lower() for x in ('assertion failed','rdpq error','rdpq warning'))
 norm=lambda x:re.sub(r' lod=\d+','',x)
 assert list(map(norm,states['before']))==list(map(norm,states['after']))
 for i,(b,c) in enumerate(zip(data['before'],data['after'])):
  line=states['before'][i];kind=int(re.search(r'kind=(\d+)',line)[1]);lod=int(re.search(r'lod=(\d+)',line)[1]);clip=int(re.search(r'clip=(\d+)',line)[1]);phase=float(re.search(r'phase=([^ ]+)',line)[1]);delta=np.abs(b.astype(int)-c.astype(int));changes=int(np.any(delta,axis=2).sum());unchanged=lod==0 or kind==4
  # Near/ship images include the original held weapons at this close distance.
  changed16=int(np.count_nonzero(raw['before'][i]!=raw['after'][i]))
  if unchanged:assert changed16==0,(i,changed16)
  label=f'{["Grunt","Elite","Jackal","Hunter","Spirit"][kind]} — {"near unchanged" if lod==0 else "old far → crunchy" if kind!=4 else "ship unchanged"} — {["idle","run","fire","death","flee","melee","throw","evade left","evade right","ride","exit","crouch"][clip]} {phase:g}'
  Image.fromarray(np.minimum(delta*4,255).astype('uint8')).save(out/'diff'/f'{i:02}.png');rows.append({'page':i,'changed_pixels':changes,'changed_rgba16':changed16,'expected_identical':unchanged,'before_state':line,'after_state':states['after'][i]});labels.append(label)
 entries=[{'label':labels[i],'before':f'before/{i:02}.png','after':f'after/{i:02}.png','diff':f'diff/{i:02}.png'} for i in range(52)]
 census_path=a.capture/'checks/photos/results.json';census=json.loads(census_path.read_text()) if census_path.exists() else {}
 for name in ('crowded-1','crowded-60','crowded-180','delivery-300'):
  if 'baseline-'+name not in census:continue
  b,c=[census[v+'-'+name] for v in ('baseline','candidate')]
  assert b['state']==c['state'] and b['cameras']==c['cameras'],name
  strip=lambda actor:{k:v for k,v in actor.items() if k not in ('lod','body','gun','batches','body_in','gun_in')}
  assert [strip(x) for x in b['actors']]==[strip(x) for x in c['actors']],name
  pair=[]
  for version,short in [('baseline','before'),('candidate','after')]:
   src=a.capture/'checks/photos'/(version+'-'+name)/'baseline.png';dst=out/short/(name+'.png');shutil.copyfile(src,dst);pair.append(np.asarray(Image.open(src)))
  delta=np.abs(pair[0].astype(int)-pair[1].astype(int));Image.fromarray(np.minimum(delta*4,255).astype('uint8')).save(out/'diff'/(name+'.png'))
  entries.append({'label':name+' — natural per-camera LOD','before':'before/'+name+'.png','after':'after/'+name+'.png','diff':'diff/'+name+'.png'})
 shutil.copytree(a.capture/'audit',out/'silhouettes',dirs_exist_ok=True)
 for name in ('results.json','silhouette-summary.json','silhouette-audit.json','asset-checks.json'):
  src=a.capture/name
  if src.exists():shutil.copyfile(src,out/name)
 (a.capture/'pixel-checks.json').write_text(json.dumps({'identical_controls':sum(r['expected_identical'] for r in rows),'frames':rows},indent=2)+'\n')
 (out/'photo-checks.json').write_text(json.dumps({'states':rows,'identical_controls':sum(r['expected_identical'] for r in rows),'census':census},indent=2)+'\n');(a.capture/'photo-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
 html='''<!doctype html><meta charset="utf-8"><title>Crunchy Covenant appraisal</title><style>[hidden]{display:none!important}body{max-width:1280px;margin:32px auto;padding:0 20px;background:#101923;color:#e8eef5;font:16px system-ui;line-height:1.55}button,select{font:inherit;background:#23394c;color:white;border:1px solid #57798e;padding:9px;margin:4px;cursor:pointer}a{color:#7bd9ff}.pair{display:flex;gap:12px}figure{margin:0;flex:1}img{width:100%;image-rendering:pixelated}#single{max-width:960px;margin:auto}table{border-collapse:collapse}th,td{padding:8px 15px;border-bottom:1px solid #40505f;text-align:left}.note{color:#b0c2d3}.pill{display:inline-block;padding:7px 12px;background:#234437;border-radius:6px}</style>
<h1>Crunchy Covenant</h1><p class="pill">A third tier for small screen sizes · original animation · original hit meshes</p>
<p>The small-screen tier keeps heads, stances, tanks, shields and spines, with broad armor colors and deliberately angular surfaces. Existing near/far meshes remain available. Enter below a full projected 28-pixel box; leave above 34. Zoom uses the existing detailed tier. The whole animation clip contributes to the bounds.</p>
<select id="page"></select><button id="prev">Previous</button><button id="next">Next</button><div><button data-mode="pair">Side by side</button><button data-mode="before">Before</button><button data-mode="after">After</button><button data-mode="diff">Difference ×4</button><button id="blink">Blink</button></div>
<h2 id="label"></h2><div id="pair" class="pair"><figure><figcaption>Original selection</figcaption><img id="before"></figure><figure><figcaption>Crunchy candidate</figcaption><img id="after"></figure></div><div id="single" hidden><img id="one"></div>
<p class="note">Native 320×240 captures. Model inspection deliberately shows the crunchy tier close up from four angles; combat photos use automatic screen-size selection. The matching near/ship controls remain pixel-identical. Diff colors show all changed pixels, including expected shading changes.</p>
<h2>Small-screen budget</h2><table><tr><th>Actor</th><th>Old far loads</th><th>Crunchy loads</th><th>Triangles</th></tr><tr><td>Grunt</td><td>784</td><td>104</td><td>342 → 84</td></tr><tr><td>Elite</td><td>776</td><td>254</td><td>368 → 176</td></tr><tr><td>Jackal</td><td>920</td><td>238</td><td>449 → 196</td></tr><tr><td>Hunter</td><td>1,464</td><td>304</td><td>1,138 → 260</td></tr></table>
<h2>Native performance</h2><div id="perf"></div><p class="note">Ares v148, NTSC 320×240, 8 MiB, audio on. Live uncapped profiling; both versions use the same bank and runtime sources. Only body/gun LOD selection changes. No new cartridge measurement. Timings and fixed-pose image diagnostics are separate.</p>
<h2>Silhouette review</h2><p>Six CPU orthographic angles, eight poses per species, with 192-, 28- and 16-pixel masks. These supplement the native captures. Sheets show old far, candidate, and silhouette differences: red lost, cyan added. The first Elite/Jackal reductions were rejected after these checks; the final meshes restore limb volume.</p><ul id="silhouettes"></ul>
<p class="note">Known pre-existing issue: the selected Jackal render LODs omit its energy shield mesh. Shield hit behavior remains present. This candidate does not repair that separate defect. Movement, enemy counts, AI, hit meshes, clip samples and weapon grip motion remain unchanged.</p>
<p><a href="photo-checks.json">Camera states and pixel checks</a> · <a href="results.json">Performance details</a> · <a href="silhouette-audit.json">Silhouette metrics</a></p>
<script>const entries=__ENTRIES__,perf=__PERF__;let index=53<entries.length?53:12,mode='pair',timer;const $=x=>document.getElementById(x);entries.forEach((r,i)=>{let o=document.createElement('option');o.value=i;o.textContent=r.label;$('page').append(o)});function show(){let r=entries[index];$('label').textContent=r.label;$('page').value=index;for(let k of ['before','after'])$(k).src=r[k];$('pair').hidden=mode!=='pair';$('single').hidden=mode==='pair';if(mode!=='pair')$('one').src=r[mode]}function stop(){clearInterval(timer);timer=null}document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>{stop();mode=b.dataset.mode;show()});$('page').onchange=e=>{index=+e.target.value;show()};$('prev').onclick=()=>{index=(index+entries.length-1)%entries.length;show()};$('next').onclick=()=>{index=(index+1)%entries.length;show()};$('blink').onclick=()=>{if(timer){stop();return}mode='before';show();timer=setInterval(()=>{mode=mode==='before'?'after':'before';show()},600)};
if(perf){let t=document.createElement('table');t.innerHTML='<tr><th>Fixture</th><th>Players</th><th>Before FPS</th><th>Crunchy FPS</th><th>Gain</th></tr>';for(let kind of ['opening','perf'])for(let n=1;n<=4;n++){let a=perf.cases['baseline-'+kind+'-'+n]?.living_players_and_landed_enemies,b=perf.cases['candidate-'+kind+'-'+n]?.living_players_and_landed_enemies;if(!a||!b)continue;let tr=document.createElement('tr');tr.innerHTML='<td>'+(kind==='opening'?'Ordinary':'Crowded')+'</td><td>'+n+'</td><td>'+a.fps_mean.toFixed(2)+'</td><td>'+b.fps_mean.toFixed(2)+'</td><td>'+((b.fps_mean/a.fps_mean-1)*100).toFixed(1)+'%</td>';t.append(tr)}$('perf').append(t)}else $('perf').textContent='Captures in progress.';
for(let name of ['grunt','elite','jackal','hunter'])for(let [clip,phase] of [['idle',0],['run',.25],['run',.75],['fire',.5],['melee',.5],['death',.75],['flee',.5],['evade_left',.5]]){let li=document.createElement('li'),a=document.createElement('a');a.href='silhouettes/'+name+'-'+clip+'-'+phase+'.png';a.textContent=name+' '+clip+' '+phase;li.append(a);$('silhouettes').append(li)}show();</script>'''
 perf=json.loads((a.capture/'results.json').read_text()) if (a.capture/'results.json').exists() else None
 (out/'comparison.html').write_text(html.replace('__ENTRIES__',json.dumps(entries)).replace('__PERF__',json.dumps(perf)));print(out/'comparison.html')
if __name__=='__main__':main()
