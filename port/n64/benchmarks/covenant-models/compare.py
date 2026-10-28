#!/usr/bin/env python3
"""Decode native model audit frames and assemble the local appraisal viewer."""
import argparse,hashlib,json,re,shutil,struct
from pathlib import Path
import numpy as np
from PIL import Image

def decode(log,output):
    text=log.read_text();blocks=re.findall(r'FF_PHOTO_BEGIN.*?FF_PHOTO_END',text,re.S);assert len(blocks)==52
    output.mkdir(parents=True,exist_ok=True);frames=[]
    for index,block in enumerate(blocks):
        assert int(re.search(r'tick=(\d+)',block)[1])==index
        pixels=[None]*(320*240)
        for first,data in re.findall(r'^FF_PIX (\d+) ([0-9a-f]+)$',block,re.M):
            for i,v in enumerate(struct.unpack('>'+str(len(data)//4)+'H',bytes.fromhex(data))):
                at=int(first)+i;assert pixels[at] is None;pixels[at]=tuple(((v>>q)&31)*255//31 for q in [11,6,1])
        assert all(p is not None for p in pixels);image=Image.new('RGB',(320,240));image.putdata(pixels);image.save(output/f'{index:02}.png');frames.append(np.array(image))
    return frames

def main(capture,out):
    out.mkdir(parents=True,exist_ok=True);images={};provenance={}
    states=[]
    for version in ['before','after']:
        log=capture/('photo-'+version+'-native.log');images[version]=decode(log,out/version)
        provenance[version]={'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),'frames':52,'size':[320,240]}
        states.append(re.findall(r'^MODEL_PHOTO .*$',log.read_text(),re.M)[:52])
    assert len(states[0])==52 and states[0]==states[1], 'Unmatched inspection poses'
    (out/'diff').mkdir(exist_ok=True);changes=[]
    for i,(a,b) in enumerate(zip(images['before'],images['after'])):
        delta=np.abs(a.astype(int)-b.astype(int));Image.fromarray(np.minimum(delta*4,255).astype('uint8')).save(out/'diff'/f'{i:02}.png')
        changes.append({'page':i,'changed_pixels':int(np.any(delta,axis=2).sum())})
    labels=[]
    for i in range(52):
        if i<24:label=f'Hunter — {"near" if i<12 else "far"} — {["idle","run","melee"][(i%12)//4]} — phase {(i%4)/4:g}'
        elif i<32:label=f'Spirit — {"near" if i<28 else "far"} — door {(i%4)/3:.2f}'
        elif i<40:label=f'Jackal — {"near" if i<36 else "far"} — {"idle" if i%4<2 else "fire"} — shield {"up" if i%2==0 else "down"}'
        elif i<48:label=f'{"Grunt" if i<44 else "Elite"} — {"near" if i%4<2 else "far"} — {"run" if i%2 else "idle"}'
        else:label=f'Jackal occlusion — {"near" if i<50 else "far"} — shield {"up" if i%2==0 else "down"}'
        labels.append(label)
    shutil.copytree(capture/'audit',out/'geometry-audit',dirs_exist_ok=True)
    results=json.loads((capture/'results.json').read_text()) if (capture/'results.json').exists() else None
    cameras=[]
    for line in states[0]:
        page,kind,lod,clip=map(int,re.search(r'page=(\d+) kind=(\d+) lod=(\d+) clip=(\d+)',line).groups())
        floor=float(re.search(r'pos=0,([^,]+),4',line)[1])
        center=[0,floor+(6.5 if kind==4 else .52 if kind==3 else .38),4]
        radius=13 if kind==4 else 1.7 if kind==3 else 1.25
        cameras.append({'page':page,'kind':kind,'lod':lod,'clip':clip,'fixture_state':line,
                        'actor_origin':[0,floor+(5 if kind==4 else 0),4],
                        'target':center,'eyes':[[round(c+d*radius,6) for c,d in zip(center,direction)]
                            for direction in [(1,.16,0),(-1,.16,0),(.3,.16,1),(.3,-.25,-1)]],
                        'note':'Fixture log pos uses the staging floor; Spirit origin is five units above it.'})
    (out/'photos.json').write_text(json.dumps({'provenance':provenance,'changes':changes,'labels':labels,'cameras':cameras},indent=2)+'\n')
    data=json.dumps({'labels':labels,'perf':results})
    html='''<!doctype html><meta charset="utf-8"><title>Covenant model appraisal</title>
<style>body{max-width:1280px;margin:28px auto;padding:0 20px;background:#111923;color:#e8eef5;font:16px system-ui;line-height:1.5}h1{font-size:30px}button,select{font:inherit;background:#26394b;color:white;border:1px solid #52738d;padding:8px;margin:4px;cursor:pointer}a{color:#7bd9ff}.pair{display:flex;gap:12px}.pair figure{margin:0;flex:1}img{width:100%;image-rendering:pixelated}figcaption{color:#b8c9d7}#single{max-width:800px;margin:auto}table{border-collapse:collapse}td,th{padding:9px 20px;text-align:left;border-bottom:1px solid #40505f}.muted{color:#b0bdca}</style>
<h1>Covenant models — appraisal candidate</h1>
<p>Hunter and Spirit meshes reduced with protected outlines, articulated boundaries and source color regions. These native frames also audit source two-sided details and transparent energy surfaces. The approved asset bank remains unchanged.</p>
<select id="page"></select><button id="prev">Previous</button><button id="next">Next</button>
<div><button data-mode="pair">Side by side</button><button data-mode="before">Before</button><button data-mode="after">After</button><button data-mode="diff">Difference ×4</button><button id="blink">Blink before/after</button></div>
<h2 id="label"></h2><div class="pair" id="pair"><figure><figcaption>Before</figcaption><img id="before"></figure><figure><figcaption>Candidate</figcaption><img id="after"></figure></div><div id="single" hidden><img id="one"></div>
<p class="muted">Each image contains four matched cameras at native 320×240. Inspection models are suspended above terrain so their feet and undersides remain visible. Far meshes are deliberately shown close enough to inspect. Differences are expected; this is not a pixel-equivalence claim.</p>
<h2>Geometry and character</h2><table><tr><th>Model</th><th>Before loads/camera</th><th>Candidate near / far</th></tr><tr><td>Hunter</td><td>3,378 / 3,378</td><td>1,606 / 1,464</td></tr><tr><td>Spirit</td><td>4,228 / 4,228</td><td>1,232 / 1,084</td></tr></table>
<p>Hunter face, spines, shield outline and weapon silhouette are protected. The Spirit retains its forked hull and working doors. Its candidate uses distance LOD and reuses unchanged door poses. Hit geometry, movement, weak points, AI and encounter rules are unchanged.</p>
<p>Energy surfaces use an alpha-blended approximation, not CE’s complete animated additive shader. Opaque bodies still write depth; energy surfaces only test depth. Original two-sided details are rendered from both sides.</p>
<h2>Native performance</h2><div id="perf"></div><p class="muted">Ares v148, NTSC 320×240, 8 MiB, audio enabled, uncapped profiling ROMs. Ordinary and crowded fixtures use real damage and deaths. Same input scenarios do not guarantee identical visible combat states. These are emulator measurements, not fresh cartridge tests.</p>
<h2>Additional geometry audit</h2><p>CPU orthographic comparisons supplement the native images. Left: before; middle: candidate; right: silhouette changes (red lost, cyan added). They are not native renderer or timing results.</p><ul id="audit"></ul>
<script>const DATA=__DATA__;let index=0,mode='pair',timer=null;const $=x=>document.getElementById(x);DATA.labels.forEach((x,i)=>{let o=document.createElement('option');o.value=i;o.textContent=x;$('page').append(o)});function show(){let file=String(index).padStart(2,'0')+'.png';$('label').textContent=DATA.labels[index];$('page').value=index;for(let v of ['before','after'])$(v).src=v+'/'+file;$('pair').hidden=mode!=='pair';$('single').hidden=mode==='pair';if(mode!=='pair')$('one').src=mode+'/'+file}function stop(){clearInterval(timer);timer=null}document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>{stop();mode=b.dataset.mode;show()});$('page').onchange=e=>{index=+e.target.value;show()};$('prev').onclick=()=>{index=(index+51)%52;show()};$('next').onclick=()=>{index=(index+1)%52;show()};$('blink').onclick=()=>{if(timer){stop();return}mode='before';show();timer=setInterval(()=>{mode=mode==='before'?'after':'before';show()},600)};
for(let name of ['hunter','spirit'])for(let lod of [0,1])for(let [clip,phase] of name==='hunter'?[['idle','0'],['run','0.5'],['melee','0.5']]:[['exit','0'],['exit','0.5'],['exit','1']]){let li=document.createElement('li'),a=document.createElement('a');a.href='geometry-audit/'+name+'-'+lod+'-'+clip+'-'+phase+'.png';a.textContent=name+' '+(lod?'far':'near')+' '+clip+' '+phase;li.append(a);$('audit').append(li)}
if(DATA.perf){let t=document.createElement('table');t.innerHTML='<tr><th>Fixture</th><th>Players</th><th>Before FPS</th><th>Candidate FPS</th><th>Change</th></tr>';for(let kind of ['opening','perf'])for(let n=1;n<=4;n++){let a=DATA.perf.cases['baseline-'+kind+'-'+n].living_players_and_landed_enemies,b=DATA.perf.cases['candidate-'+kind+'-'+n].living_players_and_landed_enemies;let tr=document.createElement('tr');tr.innerHTML='<td>'+(kind==='opening'?'Ordinary':'Crowded')+'</td><td>'+n+'</td><td>'+a.fps_mean.toFixed(2)+'</td><td>'+b.fps_mean.toFixed(2)+'</td><td>'+((b.fps_mean/a.fps_mean-1)*100).toFixed(1)+'%</td>';t.append(tr)}$('perf').append(t)}else $('perf').textContent='Measurements are being collected.';show();</script>'''
    html=html.replace('<style>','<style>[hidden]{display:none!important}')
    html=html.replace('<select id="page">','<p style="padding:12px;border:1px solid #b59d54"><strong>Audit finding: Jackal shield mesh is missing.</strong> Both existing render LODs omit all 76 source shield triangles; shield-up/down frames are identical in both versions. Gameplay shield collision still exists. This predates the reduction and remains unresolved. The alpha pass affects the included Spirit beam and Grunt lights.</p><select id="page">')
    (out/'comparison.html').write_text(html.replace('__DATA__',data))
    print(out/'comparison.html')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('capture',type=Path);p.add_argument('output',type=Path);a=p.parse_args();main(a.capture,a.output)
