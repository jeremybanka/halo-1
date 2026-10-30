"""Verify native inputs, decode the four actual menu frames and package a local review."""
import hashlib,json,re,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent;OUT=ROOT/'build/firefight-fights';VIEW=ROOT.parents[2]/'build/n64-firefight-fights'
sys.path.insert(0,str(HERE.parent/'firefight-limited'));from decode_photo import decode
VIEW.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
log=OUT/'menu-4-native.log';text=log.read_text(errors='replace')
assert 'FIREFIGHT_QA PASS players=4' in text
assert 'SESSION_START firefight=1 map=9 players=4 npcs=0 fight=1' in text
assert 'SESSION_START firefight=0 map=9 players=4' in text
assert not re.search(r'assertion failed|assertf|exception|rdpq.*(?:warning|error)',text,re.I)
frames={}
for block in re.findall(r'FF_PHOTO_BEGIN.*?FF_PHOTO_END',text,re.S):
 n=int(re.search(r'tick=(\d+)',block).group(1));assert n not in frames
 path=OUT/'photos'/f'{n}.log';path.parent.mkdir(exist_ok=True);path.write_text(block)
 decode(path,VIEW/f'{n}.png');frames[n]=sha(VIEW/f'{n}.png')
assert set(frames)=={0,1,2,3}
manifest_data={}
for name in ('menu-4','play'):
 path=next((OUT/name).glob('*.build.json'));m=json.loads(path.read_text())
 for group in ('sources','headers','included_data','generated_adapters'):
  for file,expected in m[group].items():assert sha(ROOT/file)==expected,(group,file)
 rom=Path(m['rom']['path']);assert sha(rom)==m['rom']['sha256']
 manifest_data[name]={'manifest_sha256':sha(path),'rom':m['rom'],'options':m['options'],'sources':m['sources'],'headers':m['headers'],'included_data':m['included_data']}
 if name=='play':shutil.copyfile(rom,VIEW/'halo64-firefight-fights.z64');assert sha(VIEW/'halo64-firefight-fights.z64')==m['rom']['sha256']
host=json.loads((HERE/'host.json').read_text())
for file,expected in host['source_sha256'].items():assert sha(ROOT/file)==expected,file
result={'native':'Ares v148, NTSC 320x240, 8 MiB, real shell input; lifecycle QA, not performance','menu_4_pass':True,'photos_sha256':frames,'raw_log_sha256':sha(log),'builds':manifest_data,'host':host}
(HERE/'native.json').write_text(json.dumps(result,indent=2)+'\n')
(HERE/'menu-4-native.log').write_text('\n'.join(line for line in text.splitlines() if not line.startswith('FF_PIX '))+'\n')
shutil.copyfile(HERE/'native.json',VIEW/'native.json')
shutil.copyfile(ROOT/'port/n64/FIREFIGHT_FIGHTS.md',VIEW/'rules.md')
(VIEW/'comparison.html').write_text('''<!doctype html><meta charset="utf-8"><title>Firefight — Onslaught &amp; Gauntlet</title>
<style>body{max-width:1100px;margin:32px auto;padding:0 20px;background:#14202b;color:#edf3f8;font:17px/1.5 system-ui}a{color:#8ed7ff}.pair{display:flex;gap:24px}figure{flex:1;margin:0}img{width:100%;image-rendering:pixelated}td,th{text-align:left;padding:8px 22px}</style>
<h1>Choose your fight</h1><p>Firefight → Players → Blood Gulch → Fight → Countdown.</p>
<p><a href="halo64-firefight-fights.z64">Playable ROM</a> · <a href="rules.md">Rules and validation</a> · <a href="native.json">Native evidence and input hashes</a></p>
<div class="pair"><figure><h2>Onslaught</h2><p>The original encounter. More players bring larger waves.</p><img src="0.png" alt="Native Onslaught selection"></figure><figure><h2>Gauntlet</h2><p>The same wave sizes for every party. More players face stronger Covenant ranks and armaments.</p><img src="2.png" alt="Native Gauntlet selection"></figure></div>
<table><tr><th>Players</th><th>Onslaught enemies / cap</th><th>Gauntlet enemies / cap</th></tr><tr><td>1</td><td>276 / 6</td><td>276 / 6</td></tr><tr><td>2</td><td>337 / 8</td><td>276 / 8</td></tr><tr><td>3</td><td>395 / 10</td><td>276 / 8</td></tr><tr><td>4</td><td>456 / 12</td><td>276 / 8</td></tr></table>
<p>Counts cover 15 waves, excluding the bonus. Gauntlet preserves the species mix: Grunts, Elites, Jackals and Hunters. Two players bring Majors; three add more Spec Ops; four add Zealot leaders and more fuel rods, at most one per squad. Sword and cloaked roles remain intact.</p>
<div class="pair"><figure><img src="1.png" alt="Native Onslaught countdown"></figure><figure><img src="3.png" alt="Native Gauntlet countdown"></figure></div>
<p>Both keep three rounds, the vehicle sequence, shared lives, recovery, source-derived combat and the Grunt bonus. All 1–4-player host lifecycle checks pass. Native four-player selection, Gauntlet launch/restart, quit and multiplayer return pass. These screenshots are actual N64 framebuffer readbacks. Balance still needs human play; this pass makes no new FPS claim.</p>''')
html=(VIEW/'comparison.html').read_text()
for file in re.findall(r'(?:href|src)="([^"]+)"',html):assert (VIEW/file).is_file(),file
print('Verified native menu, 4 framebuffers, both build input sets, playable ROM and all viewer links:',VIEW)
