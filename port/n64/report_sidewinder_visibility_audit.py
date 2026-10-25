"""Appraisal report for unchanged-geometry tunnel / west-base visibility."""
import csv,hashlib,json,re
from pathlib import Path
import numpy as np
from PIL import Image
from audit_sidewinder_visibility import OUT,BASE,ROOT
from collect_budget_cells import PHASES

def save(name,data):
    (OUT/name).write_text(json.dumps(data,indent=2)+'\n')

def quiet(label):
    s=(OUT/(label+'.log')).read_text();line=next(x for x in s.splitlines() if 'BENCH vi_fresh group=ALL ' in x)
    r={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',line)}
    return dict(**r,label=label,fps=r['frames']*1e6/r['elapsed_us'],free_bytes=int(re.search(r'RAM=8388608 free=(\d+)',s)[1]))

def profile(label):
    s=(OUT/(label+'.log')).read_text();m=re.search(r'BENCH attribution group=0 frames=(\d+) elapsed_us=(\d+) phases=([\d,]+)',s)
    values=list(map(int,m[3].split(',')));assert len(values)==len(PHASES)
    return dict(label=label,frames=int(m[1]),elapsed_us=int(m[2]),phases=dict(zip(PHASES,values)))

def report():
    records=[];budgets={}
    for kind,name in [('Photo route','photos'),('Replay cameras','replay'),('Angles and zoom','extra'),('Room boundaries','edge')]:
        rows=json.loads((OUT/(name+'-images.json')).read_text())
        assert all(r['changed_pixels']==0 and r['cell_control_changed_pixels']==0 for r in rows)
        for r in rows:
            records.append(dict(kind=kind,label=r['label'],before=r['prefix']+'-before.png',after=r['prefix']+'-after.png',difference=r['prefix']+'-difference.png',meta=r))
        if name in ('photos','replay'):
            budgets[name]=dict(cameras=rows,before_mean=float(np.mean([r['before_loads'] for r in rows])),after_mean=float(np.mean([r['after_loads'] for r in rows])),
                before_max=max(r['before_loads'] for r in rows),after_max=max(r['after_loads'] for r in rows),before_batches=float(np.mean([r['before_chunks'] for r in rows])),after_batches=float(np.mean([r['after_chunks'] for r in rows])))
    save('camera-budgets.json',budgets)
    native=[]
    for label in ('image180','image1500','image1950','photo0','photo20'):
        paths=[OUT/f'native-{label}-{side}.png' for side in ('before','after')]
        if label.startswith('photo'):paths=[OUT/f'native-{side}-{label}.png' for side in ('before','after')]
        a,b=[np.array(Image.open(p).convert('RGB')) for p in paths];assert a.shape==b.shape==(240,640,3)
        d=np.abs(a.astype(np.int16)-b.astype(np.int16));n=int(np.count_nonzero(d.max(2)));assert n==0,(label,n)
        diff=f'native-{label}-difference.png';Image.fromarray(np.clip(d*6,0,255).astype(np.uint8)).save(OUT/diff)
        r=dict(label=label,changed_pixels=n,before=paths[0].name,after=paths[1].name,difference=diff)
        if label.startswith('photo'):
            poses=[re.findall(r'PHOTO \d+ tick=.*',(OUT/f'{side}-{label}.log').read_text()) for side in ('before','after')];assert poses[0] and poses[0]==poses[1];r['matched_full_pose']=poses[0]
        native.append(r);records.insert(0,dict(kind='Native Ares',label=label,before=r['before'],after=r['after'],difference=diff,meta=r))
    save('native-images.json',native)
    timings=[quiet(k) for k in ('before-four','after-four','before-four-repeat','after-four-repeat','before-one','after-one')]
    mean=lambda prefix:sum(r['frames'] for r in timings if r['label'].startswith(prefix))*1e6/sum(r['elapsed_us'] for r in timings if r['label'].startswith(prefix))
    timing=dict(before_four=mean('before-four'),after_four=mean('after-four'),before_one=mean('before-one'),after_one=mean('after-one'),runs=timings)
    timing['four_gain_percent']=(timing['after_four']/timing['before_four']-1)*100;save('timing.json',timing)
    profiles={k:profile(k) for k in ('before-cpu','after-cpu','after-pipeline')};save('profiling.json',profiles)
    audit=json.loads((OUT/'audit.json').read_text());packing=json.loads((OUT/'table-packing.json').read_text());cert=json.loads((OUT/'certificate-validation.json').read_text())
    comparison=(BASE.parent/'comparison.html').read_text();css=comparison[comparison.index('<style>'):comparison.index('</style>')+8];js=comparison[comparison.index(';const $=id=>'):comparison.index('</script>')]
    geometry=[]
    for label,gi in [('Central tunnels','0'),('West base','1')]:
        rows=[r['groups'][gi] for r in audit['cameras']];geometry.append(dict(label=label,loads=float(np.mean([r['loads'] for r in rows])),zero_pixel_loads=float(np.mean([r['zero_pixel_batch_loads'] for r in rows])),depth_hidden=float(np.mean([r['zero_pixel_reasons']['depth_hidden'] for r in rows]))))
    table='<table><tr><th>Structure</th><th>Average submitted loads</th><th>Loads in zero-pixel batches</th><th>Of those, depth-hidden</th></tr>'+''.join(f'<tr><td>{r["label"]}</td><td>{r["loads"]:.0f}</td><td>{r["zero_pixel_loads"]:.0f}</td><td>{r["depth_hidden"]:.0f}</td></tr>' for r in geometry)+'</table>'
    costly='<table><tr><th>Tick / camera</th><th>Before</th><th>After</th><th>Saved</th></tr>'+''.join(f'<tr><td>{r["tick"]} / P{r["camera"]}</td><td>{r["before_loads"]:,}</td><td>{r["after_loads"]:,}</td><td>{r["before_loads"]-r["after_loads"]}</td></tr>' for r in sorted(budgets['replay']['cameras'],key=lambda r:r['before_loads']-r['after_loads'],reverse=True)[:12])+'</table>'
    cpu='<table><tr><th>Inclusive phase, ms/render</th><th>Before</th><th>After</th></tr>'+''.join(f'<tr><td>{key}</td><td>{profiles["before-cpu"]["phases"][key]/1000:.3f}</td><td>{profiles["after-cpu"]["phases"][key]/1000:.3f}</td></tr>' for key in ('world','camera','animation','objects','sim','wait'))+'</table>'
    quiet_table='<table><tr><th>Quiet run</th><th>FPS</th><th>P95 frame ms</th><th>Startup free KiB</th></tr>'+''.join(f'<tr><td>{r["label"]}</td><td>{r["fps"]:.3f}</td><td>{r["p95_us"]/1000:.3f}</td><td>{r["free_bytes"]/1024:.1f}</td></tr>' for r in timings)+'</table>'
    gpu=profiles['after-pipeline']['phases']
    cards=''.join(f'<div><p>Tick {tick} / P{cam}: normal, submitted target wireframe, visible target pixels</p><div class="audit"><img src="audit-images/{tick}-{cam}-normal.png"><img src="audit-images/{tick}-{cam}-submitted.png"><img src="audit-images/{tick}-{cam}-visible.png"></div></div>' for tick,cam in ((180,3),(600,2),(1500,2),(1950,0)))
    c=budgets['replay'];memory=packing['index_bytes']+packing['row_bytes']
    page='<!doctype html><meta charset="utf-8"><title>Sidewinder — visibility audit</title>'+css+'''<style>.audit{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.audit img{width:100%;image-rendering:pixelated}</style>'''+f'''
<h1>Sidewinder — intact architecture visibility audit</h1>
<div class="hero"><div><strong>{timing['before_four']:.2f} → {timing['after_four']:.2f} FPS</strong>four-player, {timing['four_gain_percent']:+.2f}%</div><div><strong>{c['before_mean']:,.0f} → {c['after_mean']:,.0f}</strong>static loads / matched replay camera</div><div><strong>0 changed pixels</strong>all matched native and offline comparisons</div></div>
<p>Private prototype for appraisal. The entire map bank is byte-identical to the previous throughput candidate: triangles, batch order, vertex attributes, LOD meshes, textures, collision and gameplay data are unchanged. Canonical assets are untouched. The changes are visibility tables and their lookup.</p>
<p><b>Recommendation: retain this as research.</b> The repeatable {timing['four_gain_percent']:.2f}% four-player gain is too small to justify the additional {memory/1024:.0f} KiB as a default setting.</p>
<h2>What the audit found</h2>{table}<p>Counts cover 68 matched replay cameras. “Zero pixels” is a diagnostic at 160 × 120, not a license to remove geometry: clipping, back-facing surfaces, occlusion and subpixel triangles all contribute. Some batches combine visible and hidden faces. Orange is the central tunnels; cyan is the west base. The wireframe intentionally shows submitted surfaces without depth hiding.</p>{cards}
<h2>Conservative prototype</h2><p>Reconstructed {cert['source_polygons']} inset convex opaque polygons from the actual near meshes. A local 2 × 1 × 2 world-unit grid covers the two structures. A target batch is skipped only when every triangle is back-facing for the complete cell or lies behind certified opaque walls for every eye position in it. A blocking wall must be guaranteed to use its original near mesh and remain eligible under all cluster-row unions that could admit the target. Doors and holes remain open.</p><p>The fine table applies to unscoped views; scoped and outside-grid cameras use the unchanged previous table. Shared visibility rows are deduplicated. Additional table storage: {memory/1024:.1f} KiB. The first, coarser prototype saved only 44 average replay loads and is retained under <code>coarse/</code>. Neither experiment changes geometry or regrouping.</p>
<h2>Actual camera savings</h2><p>Mean replay batches: {c['before_batches']:.1f} → {c['after_batches']:.1f}. Worst replay loads: {c['before_max']:,} → {c['after_max']:,}. Photo-route average: {budgets['photos']['before_mean']:,.1f} → {budgets['photos']['after_mean']:,.1f}. Of the 55.47 loads saved per replay camera, 54.06 come from finer all-eye back-face rejection and only 1.41 depend on wall occlusion. Most views remain above 1,500 loads; dynamic objects add work.</p>{costly}
<h2>Native performance</h2><p>Two fresh quiet 75-second runs per four-player variant, plus matched single-player runs. NTSC, 8 MiB, release LTO, three display surfaces, private 32 KiB queues and the same private unlit microcode. No concurrent builds or offline renders during sampling. These are native ROM measurements in Ares, not physical-console results. Single-player: {timing['before_one']:.2f} → {timing['after_one']:.2f} FPS.</p>{quiet_table}{cpu}<p>The CPU baseline is a fresh run of the saved pre-audit throughput ROM; quiet FPS uses the freshly rebuilt before/after pair. Inclusive profiling intervals overlap and must not be summed. Simulation ticks per rendered frame change with throughput. Candidate serialized diagnostic: world submission {gpu['world']/1000:.2f} ms, remaining RSP fence {gpu['geometry_rsp_wait']/1000:.2f} ms, residual RDP drain {gpu['geometry_rdp_wait']/1000:.3f} ms. The separate serialized graphics fence measures remaining work, not total RSP utilization.</p>
<h2>Matched photos and pixel checks</h2><p>Five native pairs (three four-camera replay views and two route photos); all 24 full route states and 68 replay cameras; 104 additional angle, scope and boundary views. Native photos retain identical full-precision pose logs. Offline float renders omit native fog, HUD, dynamics and RDP rounding. Every image pair is identical; the difference ×6 filter is therefore black.</p>
<div class="viewer"><select id="kind"></select><button id="prev">Previous</button><select id="choice"></select><button id="next">Next</button><p id="description"></p><div class="pair"><div>Previous throughput candidate<img id="before"></div><div>Visibility prototype<img id="after"></div></div><p><select id="mode"><option value="difference">RGB difference ×6</option><option value="blend">Before / after blend</option><option value="wipe">Before / after wipe</option></select><input id="amount" type="range" min="0" max="100" value="50"></p><canvas id="filter"></canvas><details><summary>Camera and measurements</summary><pre id="metadata"></pre></details></div>
<h2>Appraisal</h2><p>This pass preserves the architecture, but recovers little of the measured submission waste. Existing batches and conservative all-direction/whole-cell guarantees limit rejection. The roughly one-megabyte fine table should be judged against the measured FPS change, not the much larger sampled zero-pixel count. A further experiment could split selected mixed batches along existing room or surface boundaries while retaining every triangle; that has not been implemented here and could increase CPU submission overhead.</p>
<p><a href="REPRODUCE.txt">Reproduction and limits</a> · <a href="timing.json">Native timings</a> · <a href="profiling.json">Profiles</a> · <a href="camera-budgets.json">Every matched camera</a> · <a href="audit.json">Visibility audit</a> · <a href="certificate-validation.json">Certificate checks</a> · <a href="native-images.json">Native pixel checks</a> · <a href="validation.json">Preservation and validation</a></p>'''
    (OUT/'comparison.html').write_text(page+'<script>const records='+json.dumps(records)+js+'</script>');save('viewer-records.json',records)
    for r in records:
        for k in ('before','after','difference'):assert (OUT/r[k]).is_file(),r[k]
    print(json.dumps(timing,indent=2))

if __name__=='__main__':report()
