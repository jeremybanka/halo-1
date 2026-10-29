"""Native four-angle roster/LOD appraisal; no generated or host-rendered art."""
import argparse,hashlib,importlib.util,json,re,shutil,wave
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent

def main(output):
    capture=ROOT/'build/firefight-roster';output.mkdir(parents=True,exist_ok=True)
    spec=importlib.util.spec_from_file_location('native_photos',HERE.parent/'covenant-models/compare.py')
    photos=importlib.util.module_from_spec(spec);spec.loader.exec_module(photos)
    log=capture/'photos-native.log';frames=photos.decode(log,output/'photos',46)
    # The producer can prepare its next frame before capture terminates it.
    states=re.findall(r'^MODEL_PHOTO .*$',log.read_text(),re.M)[:46];assert len(states)==46
    assert [int(re.search(r'page=(\d+)',s)[1]) for s in states]==list(range(46))
    names=['Major Grunt / plasma pistol','Major Grunt / Needler','Major Elite / plasma rifle','Major Elite / Needler','Major Jackal',
           'Spec Ops Grunt / Needler','Spec Ops Grunt / fuel rod','Spec Ops Elite / plasma rifle','Spec Ops Elite / Needler',
           'Zealot / plasma rifle','Zealot / sword','Cloaked Elite / plasma rifle','Cloaked Major Elite / plasma rifle','Cloaked Major Elite / sword']
    labels=[f'{name} — {tier}' for name in names for tier in ['near','middle','coarse']]+[
            'Zealot sword — melee phase 0.4','Zealot sword — melee phase 0.7','Cloaked sword — melee phase 0.4','Cloaked sword — melee phase 0.7']
    diff=output/'diff';diff.mkdir(exist_ok=True);changes=[];cameras=[]
    for i,frame in enumerate(frames):
        base=i-i%3 if i<42 else i
        delta=np.abs(frame.astype(int)-frames[base].astype(int))
        Image.fromarray(np.minimum(delta*4,255).astype('uint8')).save(diff/f'{i:02}.png')
        changes.append({'page':i,'reference_page':base,'changed_pixels':int(np.any(delta,axis=2).sum()),
                        'note':'LOD audit, not before/after implementation; cloak pages also vary opacity.'})
        floor=float(re.search(r'pos=0,([^,]+),4',states[i])[1]);center=[0,floor+.38,4]
        cameras.append({'state':states[i],'target':center,'eyes':[[round(c+d*1.25,6) for c,d in zip(center,v)] for v in [(1,.16,0),(-1,.16,0),(.3,.16,1),(.3,-.25,-1)]]})
    manifest=next((capture/'photos').glob('*.build.json'));rom=next((capture/'photos').glob('*.z64'))
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    checks={'frames':46,'views_per_frame':4,'size':[320,240],'log_sha256':sha(log),'rom_sha256':sha(rom),'manifest_sha256':sha(manifest),
            'changes':changes,'cameras':cameras,'assertions_or_rdp_errors':bool(re.search(r'assertion failed|assertf|rdpq (?:error|warning)',log.read_text(),re.I))}
    assert not checks['assertions_or_rdp_errors']
    (output/'pixel-checks.json').write_text(json.dumps(checks,indent=2)+'\n')
    (HERE/'pixel-checks.json').write_text(json.dumps(checks,indent=2)+'\n')
    results=json.loads((capture/'results.json').read_text());assert len(results['cases'])==16
    shutil.copyfile(next((capture/'play').glob('*.z64')),output/'halo64-firefight-roster.z64')
    shutil.copyfile(capture/'results.json',output/'results.json')
    sounds=json.loads((capture/'source/roster-source.json').read_text())['sounds']
    (output/'audio').mkdir(exist_ok=True)
    previews=[]
    for kind,event,label in [(0,'spot','Grunt contact'),(1,'spot','Elite contact'),(4,'fuel_fire','Fuel rod discharge'),(4,'sword_swing','Sword attack')]:
        sound=next(s for s in sounds if s['kind']==kind and s['event']==event)
        filename=f'audio/{kind}-{event}.wav';payload=(capture/'source'/sound['file']).read_bytes()
        with wave.open(str(output/filename),'wb') as wav:
            wav.setparams((1,1,11025,0,'NONE','not compressed'));wav.writeframes(bytes((x+128)%256 for x in payload))
        previews.append(f'<p>{label}<br><audio controls preload="none" src="{filename}"></audio></p>')
    data=json.dumps({'labels':labels,'states':states,'perf':results['cases']})
    html='''<!doctype html><meta charset="utf-8"><title>Firefight Covenant roster</title>
<style>[hidden]{display:none!important}body{max-width:1250px;margin:30px auto;padding:0 22px;background:#111923;color:#e8eef5;font:16px system-ui;line-height:1.5}h1{font-size:30px}button,select{font:inherit;background:#26394b;color:white;border:1px solid #52738d;padding:8px;margin:4px;cursor:pointer}a{color:#7bd9ff}.pair{display:flex;gap:16px}.pair figure{flex:1;margin:0;min-width:0}img{width:100%;image-rendering:pixelated}figcaption,.muted{color:#afc0d0}#single{max-width:900px;margin:auto}table{border-collapse:collapse}td,th{padding:10px 20px;text-align:right;border-bottom:1px solid #40505f}td:first-child,th:first-child{text-align:left}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}.note{padding:15px;border:1px solid #52738d}</style>
<h1>Firefight — Covenant roster appraisal</h1>
<p>Fourteen CE loadouts in six new formations: Majors, Spec Ops, fuel-rod Grunts, Zealots, sword Elites and cloaked Elites. Existing enemy caps and the finite set structure remain in place.</p>
<p><a href="halo64-firefight-roster.z64">Playable candidate ROM</a> · <a href="pixel-checks.json">Camera and pixel record</a> · <a href="results.json">Full performance data</a></p>
<select id="page"></select><button id="prev">Previous</button><button id="next">Next</button>
<div><button data-mode="pair">Near / selected LOD</button><button data-mode="selected">Selected frame</button><button data-mode="diff">Difference ×4</button><button id="blink">Blink</button></div>
<h2 id="label"></h2><div class="pair" id="pair"><figure><figcaption>Near LOD reference</figcaption><img id="near"></figure><figure><figcaption>Selected LOD / state</figcaption><img id="selected"></figure></div><div id="single" hidden><img id="one"></div><pre id="state"></pre>
<p class="muted">46 native frames, each with four fixed cameras, at 320×240. Models are suspended for inspection. Middle/coarse meshes are deliberately shown close. These comparisons audit current LODs, not a before/after feature change. Cloak samples also change opacity: near revealed, middle partially cloaked, coarse fully cloaked. Melee pages show the source sword action before/after its strike key.</p>
<div class="note">Accepted body triangles, UVs, base animation frames and grips are unchanged. New missile/sword poses come from the original animation graphs. Gold/red Elite armor uses a brighter unlit palette to remain legible. Cloaking uses dithered transparency, rather than CE's refraction shader. Fuel-rod and sword guns use source geometry.</div>
<h2>Native performance</h2><div id="perf"></div>
<p class="muted">Ares v148, 8 MiB, NTSC, audio enabled, uncapped diagnostic ROMs. Each case contains 45 observations, discarding five warm-up samples. Table uses observations with at least one human alive, enemies alive and no arrival underway. Actual play is capped at 30 FPS. These are emulator measurements, not fresh cartridge measurements.</p>
<p>The original crowded control isolates the new runtime using the old enemy mix. The new-roster stress case changes that mix, so its result is not a matched optimization claim. The ordinary opening includes only early waves. Full 15-wave sets and every formation's concealed/Spirit arrival route pass host tests; later waves are not all covered by native timing samples.</p>
<h2>Source fidelity and limits</h2><p>Actor-specific vitality, shields, aim, fire cadence, grenades, evasions, weapon drops and source action selection feed the existing bounded AI. Sword damage waits for the original animation key and uses local reach; fuel rods use their own charge, ballistic projectile and timed death explosion. Camo uses source recharge and damage loss. Movement/navigation still use the demake's shared budgeted services.</p>
<h2>Packed audio previews</h2><p class="muted">These preview the exact packed PCM samples; they are not emulator audio recordings.</p>__AUDIO__
<p>Dialogue draws from 100 original Covenant voice permutations, plus four weapon-sound permutations, with two ROM-streamed channels shared across split-screen. This is a bounded event system, not the full original conversation scheduler. Existing simplified body meshes represent the ranks; special campaign helmet/body permutations are not added. Dropped fuel-rod guns settle at the corpse rather than simulating original rigid-body tumbling.</p>
<script>const D=__DATA__,$=x=>document.getElementById(x);let index=0,mode='pair',timer=null,blinkNear=false;D.labels.forEach((s,i)=>{let o=document.createElement('option');o.value=i;o.textContent=s;$('page').append(o)});const file=i=>String(i).padStart(2,'0')+'.png';function show(){let base=index<42?index-index%3:index;$('label').textContent=D.labels[index];$('page').value=index;$('state').textContent=D.states[index];$('near').src='photos/'+file(base);$('selected').src='photos/'+file(index);$('pair').hidden=mode!=='pair';$('single').hidden=mode==='pair';$('one').src=(mode==='diff'?'diff/':'photos/')+file(mode==='blink'&&blinkNear?base:index)}function stop(){clearInterval(timer);timer=null}document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>{stop();mode=b.dataset.mode;show()});$('page').onchange=e=>{index=+e.target.value;show()};$('prev').onclick=()=>{index=(index+45)%46;show()};$('next').onclick=()=>{index=(index+1)%46;show()};$('blink').onclick=()=>{if(timer){stop();return}mode='blink';show();timer=setInterval(()=>{blinkNear=!blinkNear;show()},650)};let t=document.createElement('table');t.innerHTML='<tr><th>Players</th><th>Original crowded</th><th>Same mix + runtime</th><th>New roster crowded</th><th>Ordinary opening</th></tr>';for(let n=1;n<=4;n++){let tr=document.createElement('tr');tr.innerHTML='<td>'+n+'</td>'+['baseline','candidate','roster','ordinary'].map(k=>'<td>'+D.perf[k+'-perf-'+n].living_players_and_landed_enemies.fps_mean.toFixed(2)+'</td>').join('');t.append(tr)}$('perf').append(t);show();</script>'''
    (output/'comparison.html').write_text(html.replace('__DATA__',data).replace('__AUDIO__',''.join(previews)));print(output/'comparison.html')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);main(p.parse_args().output)
