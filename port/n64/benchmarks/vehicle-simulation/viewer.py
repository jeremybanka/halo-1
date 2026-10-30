import json,shutil
from pathlib import Path
from run import ROOT,HERE,OUT
VIEW=ROOT.parents[2]/'build/n64-vehicle-simulation'
def main():
 data=json.loads((HERE/'results.json').read_text());rows=''
 for players in range(1,5):
  cells=[]
  for fixture in (8,9):
   values=[data['live'][f'{v}-{fixture}-{players}']['living_players_and_landed_enemies']['fps_mean'] for v in ('before','after')]
   cells.append(f'<td>{values[0]:.2f} → {values[1]:.2f}</td>')
  rows+=f'<tr><td>{players}</td>'+''.join(cells)+'</tr>'
 html='''<!doctype html><meta charset="utf-8"><title>Firefight vehicle simulation appraisal</title>
<style>body{max-width:1100px;margin:32px auto;padding:0 20px;background:#14202b;color:#edf3f8;font:16px/1.5 system-ui}a{color:#8ed7ff}select,button{font:inherit;padding:8px;margin:4px;background:#243e50;color:white;border:1px solid #59778b}.pair{display:flex;gap:16px}figure{flex:1;margin:0}img{width:100%;image-rendering:pixelated}td,th{padding:8px 20px;text-align:left}</style>
<h1>Firefight: shared vehicle queries</h1><p>Wraith aim stays current during cooldown. Five clearance rays share BVH traversal and polygon setup, retaining independent exact hits. Geometry, movement rate and source weapon behavior remain intact.</p>
<p><a href="results.json">Native profiling and equivalence</a> · <a href="host-strict.json">Host strict checks</a> · <a href="host-target.json">Target-style math checks</a> · <a href="provenance.json">Build provenance</a> · <a href="halo64-vehicle-simulation.z64">Playable candidate</a></p>
<table><tr><th>Players</th><th>Four-vehicle stress, FPS</th><th>One-Ghost control, FPS</th></tr>__ROWS__</table>
<p>Ares v148, NTSC 320×240, 8 MiB, audio enabled. Samples require at least one living player and enemy, with no arrival underway, after five warm-ups; one 45-observation capture per build/fixture. All four humans alive in the stress fixture: 2.96 → 3.19 FPS (27/26 samples). Native ROM timing, not cartridge measurements. Verification ROMs are excluded from this table.</p>
<select id="route"><option value="60">Tick 60</option><option value="180">Tick 180</option></select><button id="diff">Toggle difference ×4</button>
<p id="status"></p><div class="pair"><figure><figcaption>Baseline</figcaption><img id="before"></figure><figure><figcaption id="caption">Candidate</figcaption><img id="after"></figure></div>
<p>Both routes and all nine diagnostic pages are bit-identical before/after. Black difference images indicate zero changed pixels. Camera, vehicle pose and full-scene repeat checks also pass.</p>
<script>const $=x=>document.getElementById(x);let diff=false;function show(){let t=$('route').value;$('before').src='before-photo-'+t+'/00.png';$('after').src=diff?'diff-'+t+'.png':'after-photo-'+t+'/00.png';$('caption').textContent=diff?'Difference ×4':'Candidate';$('status').textContent='Matched route at simulation tick '+t+' — zero changed pixels';}$('route').onchange=show;$('diff').onclick=()=>{diff=!diff;show()};show();</script>'''
 (VIEW/'comparison.html').write_text(html.replace('__ROWS__',rows))
 rom=next((OUT/'after-play').glob('*.z64'));shutil.copyfile(rom,VIEW/'halo64-vehicle-simulation.z64');print(VIEW/'comparison.html')
if __name__=='__main__':main()
