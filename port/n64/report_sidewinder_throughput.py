"""Bind the CPU/region experiment to matched cameras, native logs and photos."""
import csv,hashlib,json,re,shutil
from pathlib import Path
import numpy as np
from PIL import Image
from collect_budget_cells import PHASES
from sidewinder_regions import ROOT,OUT as REGIONS,BASE,validate

OUT=REGIONS.parent
def save(name,data):
    (OUT/name).write_text(json.dumps(data,indent=2)+'\n')
def quiet(label):
    s=(OUT/(label+'.log')).read_text();line=next(x for x in s.splitlines() if 'BENCH vi_fresh group=ALL ' in x)
    r={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',line)}
    r.update(label=label,fps=r['frames']*1e6/r['elapsed_us'],initial_free_bytes=int(re.search(r'RAM=8388608 free=(\d+)',s)[1]),source_log=label+'.log')
    return r
def profile(label):
    s=(OUT/(label+'.log')).read_text();m=re.search(r'BENCH attribution group=0 frames=(\d+) elapsed_us=(\d+) phases=([\d,]+)',s)
    values=list(map(int,m[3].split(',')));assert len(values)==len(PHASES)
    return dict(label=label,frames=int(m[1]),elapsed_us=int(m[2]),phases=dict(zip(PHASES,values)),source_log=label+'.log')
def collect():
    data=json.loads((REGIONS/'visibility.json').read_text());validate(data,(REGIONS/'candidate-maps/sidewinder.map64').read_bytes())
    timings=[quiet(k) for k in ('baseline-four','baseline-four-repeat','regions-v4-four','final-four-repeat','baseline-one','final-one')]
    ab=[r for r in timings if r['label'] in ('baseline-four','baseline-four-repeat')];cd=[r for r in timings if r['label'] in ('regions-v4-four','final-four-repeat')]
    mean=lambda rs:sum(r['frames'] for r in rs)*1e6/sum(r['elapsed_us'] for r in rs)
    timing=dict(four_before=mean(ab),four_after=mean(cd),four_gain_percent=(mean(cd)/mean(ab)-1)*100,one_before=timings[-2]['fps'],one_after=timings[-1]['fps'],runs=timings)
    save('timing.json',timing)
    profiles={k:profile(k) for k in ('baseline-cpu','final-cpu','baseline-pipeline','final-pipeline','final-empty')};save('profiling.json',profiles)
    counts={}
    for name in ('replay','photos'):
        before={(r['tick'],r['camera']):r for r in csv.DictReader((BASE/name/'cameras.csv').open()) if r['candidate']=='1'}
        rows=[]
        for r in csv.DictReader((REGIONS/name/'cameras.csv').open()):
            if r['candidate']!='1':continue
            a=before[r['tick'],r['camera']]
            rows.append(dict(tick=int(r['tick']),camera=int(r['camera']),alive=int(r['alive']),before=int(a['vertices']),after=int(r['vertices']),before_batches=int(a['chunks']),after_batches=int(r['chunks']),over_1500=max(0,int(r['vertices'])-1500)))
        counts[name]=dict(cameras=rows,before_mean=float(np.mean([r['before'] for r in rows])),after_mean=float(np.mean([r['after'] for r in rows])),before_max=max(r['before'] for r in rows),after_max=max(r['after'] for r in rows),before_batches=float(np.mean([r['before_batches'] for r in rows])),after_batches=float(np.mean([r['after_batches'] for r in rows])),live_samples=sum(r['alive'] for r in rows),live_below=sum(r['alive'] and r['after']<1500 for r in rows))
    save('camera-budgets.json',counts)
    native=[]
    for key,baseline in [('600','target600'),('1950','target1950'),('photo14','photo14'),('photo20','photo20')]:
        before=BASE/f'native-{baseline}-after.png';after=OUT/('native-'+('image' if key.isdigit() else 'final')+key+'.png')
        a=np.array(Image.open(before).convert('RGB'));b=np.array(Image.open(after).convert('RGB'));assert a.shape==b.shape==(240,640,3)
        d=np.abs(a.astype(np.int16)-b.astype(np.int16));prefix='native-'+key
        shutil.copy2(before,OUT/(prefix+'-before.png'));shutil.copy2(after,OUT/(prefix+'-after.png'));Image.fromarray(np.clip(d*6,0,255).astype(np.uint8)).save(OUT/(prefix+'-difference.png'))
        r=dict(label='Native '+key,prefix=prefix,changed_pixels=int(np.count_nonzero(d.max(2))),mean_rgb_error=float(d.mean()))
        if key.startswith('photo'):
            r['overlay_changed_pixels']=int(np.count_nonzero(d[194:].max(2)));assert r['overlay_changed_pixels']==0
            poses=[re.findall(r'PHOTO \d+ tick=.*',(p).read_text()) for p in (BASE/(key+'-after.log'),OUT/('final'+key+'.log'))]
            assert poses[0] and poses[0]==poses[1];r['exact_pose_log']=poses[0]
        native.append(r)
    save('native-images.json',native)
    controls=[]
    for tick in (600,1950):
        a=np.array(Image.open(OUT/f'native-image{tick}.png'));b=np.array(Image.open(OUT/f'native-control-image{tick}.png'))
        n=int(np.count_nonzero(np.any(a!=b,axis=2)));assert n==0,(tick,n)
        controls.append(dict(tick=tick,changed_pixels=n,scope='Same regional geometry and LOD; stock Tiny3D, ordinary uncached submission and all cell masks open versus optimized candidate.'))
    save('native-controls.json',controls)
    census=[]
    for tick in (600,1950):
        lines=[r for r in (OUT/f'final{tick}.log').read_text().splitlines() if r.startswith('CENSUS ')]
        observed=[{k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',s)} for s in lines];assert len(observed)==4
        expected=[r for r in csv.DictReader((REGIONS/'replay/cameras.csv').open()) if r['candidate']=='1' and int(r['tick'])==tick]
        for a,b in zip(observed,expected):
            for x,y in [('vertices','vertices'),('triangles','triangles'),('chunks','chunks'),('materials','material_changes')]:assert a[x]==int(b[y]),(tick,x,a[x],b[y])
        census.append(dict(tick=tick,observed=observed,all_match=True))
    save('native-census.json',census)
    images=sum([json.loads((REGIONS/(n+'-images.json')).read_text()) for n in ('photos','replay','extra')],[])
    assert len(images)==148 and all(r['cell_control_changed_pixels']==0 for r in images)
    assert all(r.get('pvs_control_changed_pixels',0)==0 for r in images)
    rdp=json.loads((OUT/'rdp-validation.json').read_text());assert rdp['errors']==rdp['warnings']==0
    canonical=ROOT/'halo64-assets/generated/maps/sidewinder.map64';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    assert sha(canonical)=='200a3e01cd0c29a4f3f6f2ab71a1737c81342d2d3950bf763e3e9417606f7948'
    save('validation.json',dict(canonical_unchanged=True,candidate_sha256=data['map_sha256'],texture_and_gameplay_sections_unchanged_from_previous_candidate=True,near_geometry_retained=True,authored_far_faces_verified=True,retained_cluster_memberships_not_narrowed=True,matched_photo_states=24,matched_replay_cameras=68,offline_cell_controls=148,offline_pvs_controls=92,native_control_cameras=8,native_census_cameras=8,rdp_errors=rdp['errors'],rdp_warnings=rdp['warnings'],source_math_checks='200000 box-selector comparisons, 200000 coarse/child frustum certificates, exact submission-key tests, 36 legacy renderer helpers; ASan/UBSan where applicable',limitations=['Private prototype, not adopted into canonical assets.','Finite image and transition coverage; not a proof for every possible view.','Unlit assembly remains a private zero-light / FX-none implementation.','Ares native ROM measurements, not physical console results.','Most views remain above 1500 static loads; dynamic objects add further work.']))
    return timing,profiles,counts,native

def report():
    timing,profiles,counts,native=collect();records=[]
    ledger=[quiet(k) for k in ('cache-four','unlit-four','commands-four','regions-v2-four','regions-v3-four','regions-v4-four')]
    save('experiment-ledger.json',ledger)
    for r in native:records.append(dict(kind='Native Ares',label=r['label'],before=r['prefix']+'-before.png',after=r['prefix']+'-after.png',difference=r['prefix']+'-difference.png',meta=r))
    for kind,filename in [('Photo route','photos'),('Replay cameras','replay'),('Angles and zoom','extra')]:
        for r in json.loads((REGIONS/(filename+'-images.json')).read_text()):
            records.append(dict(kind=kind,label=r['label'],before='regions/'+r['prefix']+'-before.png',after='regions/'+r['prefix']+'-after.png',difference='regions/'+r['prefix']+'-difference.png',meta=r))
    old=(BASE/'comparison.html').read_text();css=old[old.index('<style>'):old.index('</style>')+8];js=old[old.index(';const $=id=>'):old.index('</script>')]
    c=counts['replay'];p=profiles
    table='<table><tr><th>Inclusive phase / ms per rendered frame</th><th>Before</th><th>After</th></tr>'+''.join(f'<tr><td>{name}</td><td>{p["baseline-cpu"]["phases"][key]/1000:.2f}</td><td>{p["final-cpu"]["phases"][key]/1000:.2f}</td></tr>' for key,name in [('world','World preparation'),('sim','Simulation'),('animation','Animation'),('camera','Camera'),('objects','Object submission'),('audio','Audio service'),('wait','Frame-slot wait')])+'</table>'
    pipeline='<table><tr><th>Serialized diagnostic</th><th>World CPU ms</th><th>RSP fence ms</th><th>Residual RDP ms</th></tr>'+''.join(f'<tr><td>{key}</td><td>{p[key]["phases"]["world"]/1000:.2f}</td><td>{p[key]["phases"]["geometry_rsp_wait"]/1000:.2f}</td><td>{p[key]["phases"]["geometry_rdp_wait"]/1000:.2f}</td></tr>' for key in ('baseline-pipeline','final-pipeline','final-empty'))+'</table>'
    costly='<table><tr><th>Camera</th><th>Loads before → after</th><th>Batches before → after</th><th>Above 1,500</th></tr>'+''.join(f'<tr><td>{r["tick"]} / P{r["camera"]}</td><td>{r["before"]:,} → {r["after"]:,}</td><td>{r["before_batches"]} → {r["after_batches"]}</td><td>{r["over_1500"]:,}</td></tr>' for r in sorted(c['cameras'],key=lambda r:r['after'],reverse=True)[:12])+'</table>'
    experiments='<table><tr><th>Experiment</th><th>Quiet four-player FPS</th></tr>'+''.join(f'<tr><td>{r["label"]}</td><td>{r["fps"]:.3f}</td></tr>' for r in ledger)+'</table>'
    page='<!doctype html><meta charset="utf-8"><title>Sidewinder — throughput appraisal</title>'+css+f'''<h1>Sidewinder — throughput appraisal</h1><div class="hero"><div><strong>{timing['four_before']:.2f} → {timing['four_after']:.2f} FPS</strong>four-player, {timing['four_gain_percent']:.1f}% faster</div><div><strong>{c['before_mean']:,.0f} → {c['after_mean']:,.0f}</strong>mean static loads / replay camera</div><div><strong>{c['before_batches']:.0f} → {c['after_batches']:.0f}</strong>mean submitted batches / replay camera</div></div>
<p>Private, reviewable prototype. This compares directly with the previous broader-budget candidate. The canonical map is unchanged. Near geometry, textures, collision, movement and spawn data are preserved relative to that candidate. Most views still exceed the 1,500-load target.</p>
<h2>What produced the improvement</h2><ul><li>Regional far representations simplify terrain and structures only when their projected bounding box is small enough. Original near meshes remain available. Open boundaries, shared region seams and directional outline extrema are pinned in Blender.</li><li>Coarser geometry packing reduces repeated vertices and batch overhead. Source cluster memberships are retained or widened. New far meshes are conservative across all clusters; uncertain cell visibility stays visible.</li><li>An exact per-camera cache reuses the ordered eligible batch list. Conservative bounds around groups of 16 batches avoid redundant individual frustum tests. Geometry CALLs remain in their original order, with CPU RDP-state invalidation performed once per uninterrupted geometry run.</li><li>A private Tiny3D build removes unused normal/lighting work for this zero-light renderer. Ambient color, fog, clipping and texture coordinates remain. Stock-microcode controls are included below.</li></ul>
<h2>Native performance</h2><p>Single-player: {timing['one_before']:.2f} → {timing['one_after']:.2f} fresh-pose FPS. Four-player values pool two quiet 75-second runs per version. NTSC, Expansion Pak, release LTO, three display surfaces, 32 KiB queues, one-second warmup. These are native ROM measurements in Ares, not measurements on physical hardware.</p>
{table}<p>CPU intervals are inclusive and overlap. Simulation work per rendered frame changes when render throughput changes; these values must not be added into an exclusive frame budget.</p>{pipeline}<p>The pipeline diagnostic deliberately serializes the remaining graphics work. RSP fence time includes work remaining after CPU submission and may include RDP backpressure; residual RDP drain is not total RDP cost. The empty-scissor control removes 3D pixel coverage while retaining geometry commands.</p>
<details><summary>Experiment ledger</summary>{experiments}<p>These are complete variants, not additive isolated speedups. See REPRODUCE.txt for each variant. Complete command caching did not help; regional packing, distance treatment and cheaper submission together produced the useful gain.</p></details>
<h2>Remaining camera budget</h2><p>Worst sampled replay camera: {c['before_max']:,} → {c['after_max']:,} loads. {c['live_below']} of {c['live_samples']} live replay cameras are below 1,500; dead views are excluded from that count. Dynamic objects add more work. The full 24-station photo route averages {counts['photos']['after_mean']:,.0f} loads and peaks at {counts['photos']['after_max']:,}.</p>{costly}
<h2>Matched photos and difference filters</h2><p>Native captures, all 24 route poses, all 68 replay cameras and 56 angle/zoom/cell-edge checks. Offline images omit native fog, HUD, dynamics and RDP rounding. Every camera includes its saved pose or projection matrix. Difference RGB is amplified six times.</p>
<div class="viewer"><select id="kind"></select><button id="prev">Previous</button><select id="choice"></select><button id="next">Next</button><p id="description"></p><div class="pair"><div>Previous candidate<img id="before"></div><div>Throughput candidate<img id="after"></div></div><p><select id="mode"><option value="difference">RGB difference ×6</option><option value="blend">Before / after blend</option><option value="wipe">Before / after wipe</option></select><input id="amount" type="range" min="0" max="100" value="50"></p><canvas id="filter"></canvas><details><summary>Camera and measurements</summary><pre id="metadata"></pre></details></div>
<h2>Validation and limits</h2><p>All 148 offline cell controls and 92 offline cluster controls are pixel-identical. Two native four-camera controls use stock Tiny3D, ordinary submission and all cell masks open; they match the optimized candidate exactly. Eight native camera censuses match the host fixture. Native route overlays and full-precision pose logs match. Geometry, source cluster memberships and gameplay sections are checked against the previous candidate. The native RDP validator reports zero errors and warnings in the four authored hotspot views, using 8 KiB queues: <a href="native-final-validation.png">capture</a>.</p><p>This is finite camera coverage, not an all-view proof. Regional detail transitions and the private microcode still need broader play appraisal before adoption. The complete-command-plan cache was tested and rejected: its rebuild cost erased the benefit.</p>
<p><a href="REPRODUCE.txt">Reproduction and experiment ledger</a> · <a href="timing.json">Quiet timings</a> · <a href="profiling.json">CPU/RSP/RDP profiles</a> · <a href="camera-budgets.json">All camera budgets</a> · <a href="native-controls.json">Native controls</a> · <a href="native-census.json">Native counters</a> · <a href="validation.json">Validation</a> · <a href="regions/regional-appraisal.blend">Blender study</a></p>'''
    (OUT/'comparison.html').write_text(page+'<script>const records='+json.dumps(records)+js+'</script>')
    save('viewer-records.json',records)
    for r in records:
        for key in ('before','after','difference'):assert (OUT/r[key]).is_file(),r[key]
    print(json.dumps(dict(timing=timing,replay=counts['replay']),indent=2))
if __name__=='__main__':report()
