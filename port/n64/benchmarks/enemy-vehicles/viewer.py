"""Native framebuffer appraisal; no synthetic screenshots or browser claims."""
import hashlib,importlib.util,json,re,shutil
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
OUT=ROOT/'build/pve-vehicles';VIEW=ROOT.parents[2]/'build/n64-enemy-vehicles'
spec=importlib.util.spec_from_file_location('photos',HERE.parent/'covenant-models/compare.py')
photos=importlib.util.module_from_spec(spec);spec.loader.exec_module(photos)
VIEW.mkdir(parents=True,exist_ok=True)
before=photos.decode(OUT/'hud-only-photos-native.log',VIEW/'before',42)
after=photos.decode(OUT/'ce-entry/photos-native.log',VIEW/'after',42)
states=[]
for p in [OUT/'hud-only-photos-native.log',OUT/'ce-entry/photos-native.log']:
    states.append(re.findall(r'^MODEL_PHOTO .*$',p.read_text(),re.M)[:42])
assert len(states[0])==42 and states[0]==states[1]
checks=[];labels=[]
for folder in ('diff','lod-diff'):(VIEW/folder).mkdir(exist_ok=True)
for i,(a,b) in enumerate(zip(before,after)):
    delta=np.abs(a.astype(int)-b.astype(int));changed=int(np.any(delta,axis=2).sum());assert changed==(1399 if i<3 else 0)
    Image.fromarray(np.minimum(delta*4,255).astype('uint8')).save(VIEW/'diff'/f'{i:02}.png')
    near=i-i%3 if i<36 else i
    loddelta=np.abs(after[near].astype(int)-b.astype(int))
    Image.fromarray(np.minimum(loddelta*4,255).astype('uint8')).save(VIEW/'lod-diff'/f'{i:02}.png')
    if i<36:label=f'{["Ghost","Banshee","Wraith","Shade"][i//9]} Elite — {["seated","entering","exiting"][(i%9)//3]} — {["near","far","crunch"][i%3]}'
    else:label=f'{"Shade" if i<39 else "Wraith"} Spartan — {["seated","entering","exiting"][(i-36)%3]}'
    labels.append(label);checks.append({'page':i,'state':states[1][i],'update_changed_pixels':changed,'lod_changed_pixels_including_caption':int(np.any(loddelta,axis=2).sum())})
payload=json.dumps({'frames':42,'views_per_frame':4,'exact_frames':39,'removed_hint_only_frames':3,'pages':checks},indent=2)+'\n'
for p in (VIEW/'photos.json',OUT/'photos.json',HERE/'photos.json'):p.write_text(payload)
results=json.loads((OUT/'results.json').read_text());shutil.copyfile(OUT/'results.json',VIEW/'results.json')
revision=json.loads((OUT/'ce-entry/results.json').read_text());shutil.copyfile(OUT/'ce-entry/results.json',VIEW/'ce-entry.json')
rom=next((OUT/'ce-entry/play').glob('*.z64'));shutil.copyfile(rom,VIEW/'halo64-enemy-vehicles.z64')
data=json.dumps({'labels':labels,'results':results,'revision':revision})
html='''<!doctype html><meta charset="utf-8"><title>Enemy vehicles — native appraisal</title>
<style>[hidden]{display:none!important}body{max-width:1200px;margin:30px auto;padding:0 20px;background:#111b25;color:#edf4f7;font:16px/1.5 system-ui}h1{font-size:32px}a{color:#85dbfc}select,button{font:inherit;padding:8px;margin:4px;background:#243c50;color:white;border:1px solid #5a7c94}button{cursor:pointer}.pair{display:flex;gap:14px}figure{margin:0;flex:1}img{width:100%;image-rendering:pixelated}#single{max-width:900px;margin:auto}.note{color:#bdcad6}table{border-collapse:collapse}td,th{text-align:left;padding:9px 16px;border-bottom:1px solid #415567}.callout{padding:14px;border:1px solid #8b7853}</style>
<h1>Enemy vehicles</h1><p>Elite-driven Ghosts, Banshees, Wraiths and Shade turrets. Source steering, physics, weapon parameters and rider clips, adapted to the demake’s actor and navigation services.</p>
<p><a href="halo64-enemy-vehicles.z64">Playable Firefight ROM</a> · <a href="results.json">Original 1–4-player measurements</a> · <a href="ce-entry.json">Available-seat revision checks</a> · <a href="photos.json">Exact photo states and pixel checks</a></p>
<p class="callout">Press Use near a vacant seat to enter immediately. Occupied seats cannot be taken, including by holding Use. Killing the pilot frees its seat. The earlier hijacking prototype has been removed. Vehicles begin in wave 2; the opening remains infantry.</p>
<select id="page"></select><button id="prev">Previous</button><button id="next">Next</button>
<div><button data-mode="after">Native candidate</button><button data-mode="lod">Near / selected LOD</button><button data-mode="lod-diff">LOD difference ×4</button><button data-mode="pair">Before / after updates</button><button data-mode="diff">Update difference ×4</button></div>
<h2 id="label"></h2><div class="pair" id="pair" hidden><figure><figcaption id="leftLabel"></figcaption><img id="left"></figure><figure><figcaption>Candidate</figcaption><img id="right"></figure></div><div id="single"><img id="one"></div>
<p class="note">42 native 320×240 frames × four cameras. Three Elite body LODs, seated/entry/exit poses and human Shade/Wraith seats. Actors are staged above terrain; entry/exit is frozen halfway through its source clip. The Wraith pilot is hidden by the original seat flags. LOD comparisons intentionally exaggerate distant meshes at inspection distance. Differences include the LOD caption.</p>
<p>Thirty-nine frames remain pixel-identical. The other three only lose the occupied-Ghost “Hold to board” hints: 1,399 pixels per frame. All scene pixels outside the four documented HUD rectangles are unchanged. The available-seat revision also has a separate comparison against the immediately preceding candidate. This is a memory-lifetime check, not a claim that the new vehicles are pixel-identical to the Xbox game.</p>
<h2>Native performance</h2><p id="revisionPerf"></p><p>The table below preserves the preceding candidate’s original 1–4-player measurements. Only the four-player overload was rerun for the available-seat correction.</p><div id="perf"></div><p class="note">Mean engaged FPS with sample count: at least one living player and enemy, no arrival underway. Each capture has 45 observations; five warm-ups discarded. Real deaths and respawns remain active. Stress fixtures restart at tick 600. Ares v148, NTSC, 8 MiB, audio enabled, uncapped diagnostics. These are not cartridge measurements or directly matched comparisons with the previous infantry-only workload.</p>
<h2>Source fidelity and boundaries</h2><p>The original movement/throttle functions and tag values drive the vehicles. The goal, path, perception and collision environment is still the N64 adapter. Wraiths use mortar arcs; Banshee secondary-fire rules exclude players on foot. Wraith/Shade art and canonical collision are retained, with their source fire sounds and a simplified engine loop.</p>
<p>Splatter uses the source post-impulse speed and relative-speed thresholds, with the 90-tick own-vehicle exit protection. Host tests cover boundary values, live human/Covenant contacts, available-seat ownership, vehicle destruction, and full 1–4-player Firefight progression. Full campaign AI, H2 melee boarding, exact Wraith barrel counter-articulation and the complete source sound graph are outside this candidate.</p>
<script>const DATA=__DATA__;const $=x=>document.getElementById(x);let index=0,mode='after';const file=i=>String(i).padStart(2,'0')+'.png';DATA.labels.forEach((label,i)=>{let o=document.createElement('option');o.value=i;o.textContent=label;$('page').append(o)});function show(){let pair=mode==='pair'||mode==='lod';$('label').textContent=DATA.labels[index];$('page').value=index;$('pair').hidden=!pair;$('single').hidden=pair;if(pair){$('leftLabel').textContent=mode==='lod'?'Near LOD':'Before memory/seat updates';$('left').src=mode==='lod'?'after/'+file(index<36?index-index%3:index):'before/'+file(index);$('right').src='after/'+file(index)}else $('one').src=mode+'/'+file(index)}document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>{mode=b.dataset.mode;show()});$('page').onchange=e=>{index=+e.target.value;show()};$('prev').onclick=()=>{index=(index+41)%42;show()};$('next').onclick=()=>{index=(index+1)%42;show()};let t=document.createElement('table');t.innerHTML='<tr><th>Players</th><th>One Ghost + infantry</th><th>Four vehicles + infantry</th><th>Four-vehicle lowest free RAM</th></tr>';for(let p=1;p<=4;p++){let a=DATA.results.cases['final-9-'+p],b=DATA.results.cases['final-8-'+p];let fmt=c=>{let r=c.living_players_and_landed_enemies;return r.fps_mean.toFixed(2)+' FPS ('+r.observations+')'};let tr=document.createElement('tr');tr.innerHTML='<td>'+p+'</td><td>'+fmt(a)+'</td><td>'+fmt(b)+'</td><td>'+(b.min_free_bytes/1024).toFixed(0)+' KiB</td>';t.append(tr)}$('perf').append(t);let r=DATA.revision.stress_4.living_players_and_landed_enemies;$('revisionPerf').textContent='Fresh available-seat revision: four vehicles + infantry, 4P — '+r.fps_mean.toFixed(2)+' FPS ('+r.observations+' engaged samples; 45 total observations). 39 pages match exactly; three only remove the occupied-seat HUD hints. Scene pixels are unchanged.';show();</script>'''
(VIEW/'comparison.html').write_text(html.replace('__DATA__',data));print(VIEW/'comparison.html')
