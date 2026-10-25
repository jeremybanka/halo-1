"""Matched appraisal of intact room/wall section regrouping."""
import csv, hashlib, json, re
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from sidewinder_sections import OUT, BASE, ROOT, save
from collect_budget_cells import PHASES

def quiet(label):
    text=(OUT/(label+'.log')).read_text()
    line=next(s for s in text.splitlines() if 'BENCH vi_fresh group=ALL ' in s)
    fields={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',line)}
    return dict(**fields,label=label,fps=fields['frames']*1e6/fields['elapsed_us'],
                free_bytes=int(re.search(r'RAM=8388608 free=(\d+)',text)[1]))

def profile(label):
    text=(OUT/(label+'.log')).read_text();m=re.search(r'BENCH attribution group=0 frames=(\d+) elapsed_us=(\d+) phases=([\d,]+)',text)
    values=list(map(int,m[3].split(',')));assert len(values)==len(PHASES)
    return dict(label=label,frames=int(m[1]),elapsed_us=int(m[2]),phases=dict(zip(PHASES,values)))

def report():
    records=[];budgets={};offline=0
    for kind,name in [('Photo route','photos'),('Replay cameras','replay'),('Angles and zoom','extra'),('Room boundaries','edge')]:
        rows=json.loads((OUT/(name+'-images.json')).read_text());offline+=len(rows)
        for r in rows:records.append(dict(kind=kind,label=r['label'],before=r['prefix']+'-before.png',after=r['prefix']+'-after.png',difference=r['prefix']+'-difference.png',meta=r))
        if name in ('photos','replay'):
            budgets[name]=dict(cameras=rows,before_mean=float(np.mean([r['before_loads'] for r in rows])),after_mean=float(np.mean([r['after_loads'] for r in rows])),before_max=max(r['before_loads'] for r in rows),after_max=max(r['after_loads'] for r in rows),before_batches=float(np.mean([r['before_chunks'] for r in rows])),after_batches=float(np.mean([r['after_chunks'] for r in rows])),below_1500=sum(r['after_loads']<1500 for r in rows))
    save(OUT/'camera-budgets.json',budgets)
    native=[];contact=[]
    for label in ('image180','image1500','image1950','photo0','photo20'):
        paths=[OUT/f'native-{label}-{side}.png' for side in ('before','after')]
        if label.startswith('photo'):paths=[OUT/f'native-{side}-{label}.png' for side in ('before','after')]
        a,b=[np.array(Image.open(p).convert('RGB')) for p in paths];assert a.shape==b.shape==(240,640,3)
        d=np.abs(a.astype(np.int16)-b.astype(np.int16));n=int(np.count_nonzero(d.max(2)))
        diff=f'native-{label}-difference.png';Image.fromarray(np.clip(d*6,0,255).astype(np.uint8)).save(OUT/diff)
        r=dict(label=label,changed_pixels=n,before=paths[0].name,after=paths[1].name,difference=diff)
        if label.startswith('photo'):
            poses=[re.findall(r'PHOTO \d+ tick=.*',(OUT/f'{side}-{label}.log').read_text()) for side in ('before','after')]
            assert poses[0] and poses[0]==poses[1];r['matched_full_pose']=poses[0]
        native.append(r);records.insert(0,dict(kind='Native Ares',label=label,before=r['before'],after=r['after'],difference=diff,meta=r))
        card=Image.new('RGB',(960,385),(18,24,34));ImageDraw.Draw(card).text((8,5),label+' — baseline / room sections',fill='white')
        for i,im in enumerate((a,b)):card.paste(Image.fromarray(im).resize((480,360),Image.Resampling.NEAREST),(i*480,25))
        contact.append(card)
    sheet=Image.new('RGB',(960,len(contact)*385))
    for i,im in enumerate(contact):sheet.paste(im,(0,i*385))
    sheet.save(OUT/'native-contact.png');save(OUT/'native-images.json',native)
    controls=[]
    for tick in (180,1500,1950):
        a_path=f'native-image{tick}-after.png';b_path=f'native-control{tick}.png'
        a,b=[np.array(Image.open(OUT/p).convert('RGB')) for p in (a_path,b_path)]
        d=np.abs(a.astype(np.int16)-b.astype(np.int16));n=int(np.count_nonzero(d.max(2)));assert n==0
        diff=f'native-control{tick}-difference.png';Image.fromarray(np.clip(d*6,0,255).astype(np.uint8)).save(OUT/diff)
        r=dict(tick=tick,changed_pixels=n,before=a_path,after=b_path,difference=diff,scope='Same candidate batching; target backface bits open and bounds expanded')
        controls.append(r);records.append(dict(kind='Native rejection controls',label=f'Tick {tick}: candidate / rejection disabled',before=a_path,after=b_path,difference=diff,meta=r))
    save(OUT/'native-rejection-controls.json',controls)
    timings=[quiet(k) for k in ('before-four','after-four','before-four-repeat','after-four-repeat','before-one','after-one')]
    mean=lambda prefix:sum(r['frames'] for r in timings if r['label'].startswith(prefix))*1e6/sum(r['elapsed_us'] for r in timings if r['label'].startswith(prefix))
    timing=dict(before_four=mean('before-four'),after_four=mean('after-four'),before_one=mean('before-one'),after_one=mean('after-one'),runs=timings)
    timing['four_gain_percent']=(timing['after_four']/timing['before_four']-1)*100;save(OUT/'timing.json',timing)
    profiles={k:profile(k) for k in ('before-cpu','after-cpu','before-pipeline','after-pipeline')};save(OUT/'profiling.json',profiles)
    packing=json.loads((OUT/'packing-report.json').read_text());costs=json.loads((OUT/'section-costs.json').read_text())['replay']['summary'];trials=json.loads((OUT/'packing-trials.json').read_text())
    table='<table><tr><th>Geometry</th><th>Mean loads before → after</th><th>Mean batches before → after</th></tr>'+''.join(f'<tr><td>{g.replace("_"," ")}</td><td>{costs["before"][g]["loads"]:.1f} → {costs["after"][g]["loads"]:.1f}</td><td>{costs["before"][g]["batches"]:.1f} → {costs["after"][g]["batches"]:.1f}</td></tr>' for g in costs['before'])+'</table>'
    trial_table='<table><tr><th>Offline partition trial</th><th>Mean loads</th><th>Mean batches</th><th>Worst loads</th></tr>'+''.join(f'<tr><td>{name}</td><td>{r["mean_loads"]:.1f}</td><td>{r["mean_batches"]:.1f}</td><td>{r["max_loads"]}</td></tr>' for name,r in trials.items())+'</table>'
    costly='<table><tr><th>Tick / camera</th><th>Before</th><th>After</th><th>Saved</th></tr>'+''.join(f'<tr><td>{r["tick"]} / P{r["camera"]}</td><td>{r["before_loads"]:,}</td><td>{r["after_loads"]:,}</td><td>{r["before_loads"]-r["after_loads"]}</td></tr>' for r in sorted(budgets['replay']['cameras'],key=lambda r:r['before_loads'],reverse=True)[:12])+'</table>'
    cpu='<table><tr><th>Inclusive CPU ms/render</th><th>Before</th><th>After</th></tr>'+''.join(f'<tr><td>{k}</td><td>{profiles["before-cpu"]["phases"][k]/1000:.3f}</td><td>{profiles["after-cpu"]["phases"][k]/1000:.3f}</td></tr>' for k in ('world','camera','animation','objects','sim','wait'))+'</table>'
    gpu='<table><tr><th>Serialized diagnostic, ms</th><th>Before</th><th>After</th></tr>'+''.join(f'<tr><td>{k}</td><td>{profiles["before-pipeline"]["phases"][k]/1000:.3f}</td><td>{profiles["after-pipeline"]["phases"][k]/1000:.3f}</td></tr>' for k in ('world','geometry_rsp_wait','geometry_rdp_wait'))+'</table>'
    quiet_table='<table><tr><th>Quiet run</th><th>FPS</th><th>P95 frame ms</th><th>Startup free KiB</th></tr>'+''.join(f'<tr><td>{r["label"]}</td><td>{r["fps"]:.3f}</td><td>{r["p95_us"]/1000:.3f}</td><td>{r["free_bytes"]/1024:.1f}</td></tr>' for r in timings)+'</table>'
    previous=(BASE.parent/'comparison.html').read_text();css=previous[previous.index('<style>'):previous.index('</style>')+8];js=previous[previous.index(';const $=id=>'):previous.index('</script>')]
    c=budgets['replay'];different=sum(r['meta']['changed_pixels'] for r in records)
    page='<!doctype html><meta charset="utf-8"><title>Sidewinder — intact room sections</title>'+css+f'''
<h1>Sidewinder — intact rooms and wall sections</h1>
<div class="hero"><div><strong>{timing['before_four']:.2f} → {timing['after_four']:.2f} FPS</strong>four-player, {timing['four_gain_percent']:+.2f}%</div><div><strong>{c['before_mean']:,.0f} → {c['after_mean']:,.0f}</strong>static loads per replay camera</div><div><strong>{different:,} changed pixels</strong>all matched native and offline comparisons</div></div>
<p>Private prototype, stopped for appraisal. The baseline is the earlier throughput candidate. The rejected fine visibility-table experiment is not used. All 17,222 triangles retain their exact positions, corner colors, UVs, winding, materials and LOD assignment. Collision, textures, walking paths, gameplay sections and LOD thresholds are unchanged. Canonical map assets remain untouched.</p>
<h2>What changed</h2><p>The original near central tunnels and west base are regrouped by their adjacent source BSP room and wall-facing direction. Room labels only decide which triangles share a batch; they do not authorize hiding geometry. Each batch keeps the union of its source visibility masks. The existing conservative frustum test and all-eye backface table can now reject smaller bounds. No new wall occlusion or camera-sampled visibility list is added.</p>
<p>The two structures change from {packing['source_target_chunks']} to {packing['target_chunks']} near batches; all {json.loads((OUT/'geometry-validation.json').read_text())['unchanged_batches']} other batches, including distant representations, retain their exact vertex/index bytes and bounds. Additional bank storage: {packing['additional_bank_bytes']/1024:.1f} KiB; backface table change: {packing['additional_cell_bytes']/1024:+.1f} KiB.</p>
<h2>Where the work went</h2>{table}<p>These are averages over the same 68 replay cameras, including dead views. Total submitted batches: {c['before_batches']:.1f} → {c['after_batches']:.1f}. Worst camera: {c['before_max']:,} → {c['after_max']:,} loads. Views below 1,500 static loads improve from 7/68 to {c['below_1500']}/68; among the 63 live views, 4 → 9 meet the target. Dynamic objects are additional. Photo-route average: {budgets['photos']['before_mean']:,.1f} → {budgets['photos']['after_mean']:,.1f}. Splitting bounds can reduce rejection waste while losing vertex reuse: tick 1950/P0 saves 1,016 loads, while tick 1050/P2 rises from 4,276 to 4,356.</p>{costly}
<details><summary>Why this partition was selected</summary><p>Five offline layouts were measured. Rooms plus facing direction provide the best balance of geometry saving and batch overhead. The 16-, 8- and 4-unit grids also partition distant meshes and create many tiny sections. These exploratory alternatives were not native-benchmarked.</p>{trial_table}</details>
<h2>Native performance</h2><p>Fresh before/after Ares runs: two quiet 75-second four-player measurements per variant and matched single-player runs. NTSC, 8 MiB Expansion Pak, release LTO, three surfaces, 32 KiB queues, the same private unlit microcode and existing coarse/bulk submission path. No concurrent builds or offline renders during timing. Single-player: {timing['before_one']:.2f} → {timing['after_one']:.2f} FPS. These are emulator measurements, not physical-console measurements.</p>{quiet_table}{cpu}{gpu}
<p>CPU profiling and deliberately serialized graphics diagnostics are separate from quiet timing. CPU intervals overlap and must not be added. Simulation ticks per render change with throughput. The RSP fence measures work remaining after CPU submission; it is not total RSP execution time. Residual RDP drain is likewise not total RDP time.</p>
<h2>Appraisal</h2><p>The result is a modest {timing['four_gain_percent']:.2f}% four-player improvement. Finer room/wall bounds recover geometry work, while additional batches increase measured CPU world submission from {profiles['before-cpu']['phases']['world']/1000:.2f} to {profiles['after-cpu']['phases']['world']/1000:.2f} ms per instrumented render. The current worst view remains far above 1,500 loads and four-player throughput remains far below 30 FPS. This prototype is retained for appraisal, not adopted.</p>
<h2>Matched photos and pixel checks</h2><p>{offline} offline pairs: the full 24-photo route, 68 replay cameras and 104 angle, zoom and boundary checks. Five native pairs cover 14 camera images: replay ticks 180, 1500 and 1950 plus route photos 0 and 20. Full photo pose logs, camera matrices and LOD choices are retained. Offline renders omit native fog, HUD, dynamics and RDP rounding. Native scanouts are shown at their intended 4:3 aspect ratio.</p>
<p>All offline pairs, both native route photos and native tick 1950 match exactly. Native ticks 180 and 1500 differ at 3 and 21 pixels respectively. A repeated baseline is exact. Rejection-disabled controls retain the candidate's triangle order and batching, open every target backface bit and expand target bounds to signed16 limits; all 12 resulting camera images match the candidate exactly. This isolates the small native differences to rebatching rather than the new bounds/backface rejection. They remain visible in the difference filters and are not claimed as zero-difference results.</p>
<p>Eight native camera counter sets match the host fixtures. The RDP validator reports <b>0 errors and 0 warnings</b> in four authored hotspot views using 8 KiB queues (<a href="native-rdp-validation.png">capture</a>).</p>
<div class="viewer"><select id="kind"></select><button id="prev">Previous</button><select id="choice"></select><button id="next">Next</button><p id="description"></p><div class="pair"><div>Earlier throughput candidate<img id="before"></div><div>Regrouped rooms and walls<img id="after"></div></div><p><select id="mode"><option value="difference">RGB difference ×6</option><option value="blend">Before / after blend</option><option value="wipe">Before / after wipe</option></select><input id="amount" type="range" min="0" max="100" value="50"></p><canvas id="filter"></canvas><details><summary>Camera and measurements</summary><pre id="metadata"></pre></details></div>
<p><a href="REPRODUCE.txt">Reproduction and limits</a> · <a href="timing.json">Native timings</a> · <a href="profiling.json">Profiles</a> · <a href="camera-budgets.json">Every camera</a> · <a href="section-costs.json">Structure costs</a> · <a href="native-images.json">Native pixel checks</a> · <a href="validation.json">Preservation and validation</a></p>'''
    (OUT/'comparison.html').write_text(page+'<script>const records='+json.dumps(records)+js+'</script>');save(OUT/'viewer-records.json',records)
    for r in records:
        for key in ('before','after','difference'):assert (OUT/r[key]).is_file()
    print(json.dumps(timing,indent=2))

if __name__=='__main__':report()
