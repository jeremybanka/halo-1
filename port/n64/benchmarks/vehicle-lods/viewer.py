"""Local appraisal viewer: native matched photos, silhouette filters and measured FPS."""
import json,shutil
from pathlib import Path
from run import ROOT,HERE,OUT
VIEW=ROOT.parents[2]/'build/n64-vehicle-lods';VIEW.mkdir(parents=True,exist_ok=True)
results=json.loads((OUT/'results.json').read_text()) if (OUT/'results.json').is_file() else None
assets=json.loads((OUT/'asset-checks.json').read_text())['new_models']
labels=[]
for page in range(36):
    name='Wraith' if page<18 else 'Shade';pose=['level','gun turned / hatch opening','pitched hull / gun lowered'][(page%18)//6]
    labels.append(f'{name} · {pose} · {"oblique" if (page%6)//3 else "cardinal"} angles · {["detailed","middle","coarse"][page%3]}')
payload=json.dumps({'labels':labels,'assets':assets,'results':results})
html='''<!doctype html><meta charset="utf-8"><title>Wraith and Shade distance LOD appraisal</title>
<style>[hidden]{display:none!important}body{max-width:1200px;margin:30px auto;padding:0 20px;background:#111b25;color:#edf4f7;font:16px/1.5 system-ui}a{color:#85dbfc}select,button{font:inherit;padding:8px;margin:4px;background:#243c50;color:white;border:1px solid #5a7c94}button{cursor:pointer}.pair{display:flex;gap:14px}figure{margin:0;flex:1}img{width:100%;image-rendering:pixelated}td,th{text-align:left;padding:8px 14px;border-bottom:1px solid #415567}.note{color:#bdcad6}.callout{padding:14px;border:1px solid #587d82}h1{font-size:30px}</style>
<h1>Wraith and Shade: make distance do the sacrificing</h1>
<p>Two articulated distance tiers. Source near geometry, collision, movement, weapon parameters, seat markers and audio are retained. Full projected bounds select middle below 72 pixels and coarse below 28; zoom and near-plane views retain the detailed model.</p>
<p><a href="halo64-vehicle-lods.z64">Playable candidate ROM</a> · <a href="results.json">Native measurements</a> · <a href="photos.json">Photo states and exact checks</a> · <a href="silhouettes.json">Eight-angle silhouette measurements</a></p>
<p class="callout">Local appraisal candidate. The coarse models intentionally lose fine detail. Inspection photos force each tier at close range to expose compromises; gameplay-route photos show normal selection. The Shade's legs and barrel outline received extra protection after an initial reduction collapsed them.</p>
<div><button data-section="native">Native multi-angle photos</button><button data-section="route">Gameplay-distance photos</button><button data-section="shape">Clean silhouette inspection</button></div>
<div id="nativeControls"><select id="page"></select><button id="prev">Previous</button><button id="next">Next</button></div>
<div id="routeControls" hidden><select id="tick"><option>1</option><option selected>60</option><option>180</option></select></div>
<div id="shapeControls" hidden><select id="model"><option value="wraith">Wraith</option><option value="shade">Shade</option></select><select id="tier"><option value="1">Middle</option><option value="2" selected>Coarse</option></select><select id="angle"></select></div>
<div><button id="pairButton">Before / after</button><button id="diffButton">Difference filter</button></div><h2 id="label"></h2>
<div class="pair" id="pair"><figure><figcaption id="beforeLabel">Detailed reference</figcaption><img id="before"></figure><figure><figcaption id="afterLabel">Candidate</figcaption><img id="after"></figure></div>
<div id="single" hidden><img id="diff"></div><p class="note" id="explain"></p>
<h2>Rendering budgets</h2><div id="budgets"></div><p>Near: Wraith 1,320 loads; Shade 1,348. New tiers share the existing current part matrices, preserving gun/hatch movement. The previous static far representation did not articulate those parts. Collision is independent of render detail.</p>
<h2>Native 1–4-player performance</h2><div id="perf"></div><p class="note">Fresh paired uncapped Ares v148 N64 captures, NTSC 320×240, 8 MiB, audio enabled. Each case has 45 observations; the first five are discarded for FPS. Engaged means a living player and enemy with no pending arrival. Real damage/deaths and stress restarts remain. These are emulator results, not cartridge or whole-match averages. Different frame rates can sample different combat windows.</p>
<h2>What was checked</h2><p>36 native pages × four cameras: eight angles, three poses and three tiers for both hulls. All 12 detailed pages are bit-identical to the reference; repeated detailed reference pages are also identical. Three gameplay routes retain matching cameras and hull poses. The report distinguishes complete scene differences from the underlying geometric silhouette measurements.</p>
<p class="note">Native differences amplify RGB changes ×4; equality checks use all 16 framebuffer bits. Clean silhouettes are offline quantized-mesh renders, not N64 screenshots: gray is shared coverage, red is lost coverage, cyan is added coverage. Their large inspection size exaggerates the intended small-screen tradeoffs.</p>
<script>const DATA=__DATA__, $=x=>document.getElementById(x);let section='native',index=0,diff=false;
DATA.labels.forEach((label,i)=>{let o=document.createElement('option');o.value=i;o.textContent=label;$('page').append(o)});
['front','back','left','right','front oblique','back oblique','top','below oblique'].forEach((s,i)=>{let o=document.createElement('option');o.value=i;o.textContent=s;$('angle').append(o)});
function show(){for(const s of ['native','route','shape'])$(s+'Controls').hidden=s!==section;$('pair').hidden=diff;$('single').hidden=!diff;
let before,after,delta,label,note;if(section==='native'){let f=String(index).padStart(2,'0')+'.png';before='before-photos/'+f;after='after-photos/'+f;delta='diff/'+f;label=DATA.labels[index];note='Native forced-tier inspection. The reference uses detailed articulated geometry at the same pose and camera. Reduced tiers are intentionally shown closer than normal.'}
else if(section==='route'){let t=$('tick').value;before='before-route-'+t+'/00.png';after='after-route-'+t+'/00.png';delta='diff/route-'+t+'.png';label='Gameplay route — simulation tick '+t;note='Native automatic LOD selection. Differences include the new distant part articulation. All-hulls-omitted controls isolate the unchanged rest of the scene.'}
else{let m=$('model').value,t=$('tier').value,a=$('angle').value;before='silhouettes/'+m+'-'+a+'-source.png';after='silhouettes/'+m+'-'+a+'-'+(t==='1'?'middle':'coarse')+'.png';delta='silhouettes/'+m+'-'+a+'-diff-'+t+'.png';label=m+' — '+(t==='1'?'middle':'coarse')+' silhouette';note='Offline quantized geometry, not native screenshots. Gray shared; red removed; cyan added. Source textures are baked to vertex colors.'}
$('page').value=index;$('before').src=before;$('after').src=after;$('diff').src=delta;$('label').textContent=label;$('explain').textContent=note;}
document.querySelectorAll('[data-section]').forEach(b=>b.onclick=()=>{section=b.dataset.section;show()});$('page').onchange=()=>{index=+$('page').value;show()};$('prev').onclick=()=>{index=(index+35)%36;show()};$('next').onclick=()=>{index=(index+1)%36;show()};for(let id of ['tick','model','tier','angle'])$(id).onchange=show;$('pairButton').onclick=()=>{diff=false;show()};$('diffButton').onclick=()=>{diff=true;show()};
let budget='<table><tr><th>Hull</th><th>Middle loads / triangles</th><th>Coarse loads / triangles</th></tr>';for(let [name,tiers]of Object.entries(DATA.assets))budget+='<tr><td>'+name+'</td>'+tiers.map(t=>'<td>'+t.vertex_loads+' / '+t.triangles+'</td>').join('')+'</tr>';$('budgets').innerHTML=budget+'</table>';
if(DATA.results){let t='<table><tr><th>Players</th><th>Four vehicles: before → after</th><th>One Ghost control: before → after</th></tr>';for(let p=1;p<=4;p++){t+='<tr><td>'+p+'</td>';for(let f of [8,9]){let a=DATA.results.live['before-'+f+'-'+p].living_players_and_landed_enemies,b=DATA.results.live['after-'+f+'-'+p].living_players_and_landed_enemies;t+='<td>'+a.fps_mean.toFixed(2)+' → '+b.fps_mean.toFixed(2)+' FPS ('+a.observations+'/'+b.observations+')</td>'}t+='</tr>'}$('perf').innerHTML=t+'</table>'}else $('perf').textContent='Measurements are still running.';show();</script>'''
(VIEW/'comparison.html').write_text(html.replace('__DATA__',payload))
rom=next((OUT/'after-play').glob('*.z64'));shutil.copyfile(rom,VIEW/'halo64-vehicle-lods.z64')
print(VIEW/'comparison.html')
