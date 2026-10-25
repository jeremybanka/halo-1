"""Appraise cluster-aware simplification, including independent visibility photos."""
import base64
import csv
import json
from pathlib import Path
import statistics
import report_sidewinder_photos as viewer
from report_sidewinder_combined import distribution

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/n64-sidewinder-cluster-terrain'
PREVIOUS=ROOT/'build/n64-sidewinder-combined'

def rows(path):return list(csv.DictReader(path.open()))

def census():
    old=[r for r in rows(PREVIOUS/'cameras/cameras.csv') if r['map']=='1' and r['candidate']=='1']
    raw=rows(OUT/'cameras/cameras.csv');new=[[r for r in raw if r['map']=='1' and r['candidate']==str(i)] for i in (0,1)]
    fields=['vertices','triangles','chunks','material_changes','float_clip_crossing_estimate','float_clip_rejected_estimate']
    pose=['map','tick','camera','eye_x','eye_y','eye_z','alive','zoom']
    assert len(old)==len(new[0])==len(new[1])==68
    for a,b in zip(old,new[1]):assert all(a[k]==b[k] for k in pose)
    assert (OUT/'after-census/poses.json').read_bytes()==(PREVIOUS/'after-census/poses.json').read_bytes()
    summary={ph:{k:statistics.mean(int(r[k]) for r in rs) for k in fields} for ph,rs in [('before',old),('after',new[1])]}
    summary.update(camera_samples=68,scope='Previous aggressive terrain + PVS versus cluster-aware terrain + PVS. Exact camera states; static world only.')
    (OUT/'four-camera-results.json').write_text(json.dumps(summary,indent=2)+'\n')
    with (OUT/'four-cameras.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=pose+[ph+'_'+k for k in fields for ph in ['before','after']]);w.writeheader()
        for a,b in zip(old,new[1]):w.writerow({**{k:a[k] for k in pose},**{ph+'_'+k:r[k] for k in fields for ph,r in zip(['before','after'],[a,b])}})
    historic=json.loads((PREVIOUS/'target-progress.json').read_text())
    photos=rows(OUT/'after-census/cameras.csv')
    progress={'four':{'original':historic['four']['original'],'previous_combined':historic['four']['combined'],
                      'cluster_terrain_unculled':distribution(new[0]),'cluster_terrain_pvs':distribution(new[1]),
                      'cluster_terrain_alive_only':distribution([r for r in new[1] if r['alive']=='1'])},
              'photos':{'original':historic['photos']['original'],'previous_combined':historic['photos']['combined'],
                        'cluster_terrain_unculled':distribution([r for r in photos if r['candidate']=='0']),
                        'cluster_terrain_pvs':distribution([r for r in photos if r['candidate']=='1'])},
              'native_checkpoints':{str(t):[[int(r[k]) for k in ['camera','vertices','triangles','chunks','material_changes']] for r in new[1] if r['tick']==str(t)] for t in [180,1148]}}
    old_raw=[r for r in rows(PREVIOUS/'cameras/cameras.csv') if r['map']=='1' and r['candidate']=='0']
    a=statistics.mean(int(r['vertices']) for r in old_raw);b=progress['four']['previous_combined']['mean']
    c=progress['four']['cluster_terrain_unculled']['mean'];d=progress['four']['cluster_terrain_pvs']['mean']
    progress['replay_decomposition']={'previous_unculled':a,'previous_pvs':b,'new_unculled':c,'new_pvs':d,'additional_unculled_loads':c-a,'additional_pvs_savings':(c-d)-(a-b),'net_load_increase':d-b}
    (OUT/'target-progress.json').write_text(json.dumps(progress,indent=2)+'\n');return progress

def main():
    p=census();packing=json.loads((OUT/'packing-report.json').read_text());target='<h2>Target: fewer than 1,500 static-world vertex loads per camera</h2><table><thead><tr><th>Workload</th><th>Version</th><th>Mean</th><th>Median</th><th>Range</th><th>Under target</th></tr></thead><tbody>'
    for route,label in [('four','Four-player replay'),('photos','Single-player photos')]:
        for version,s in p[route].items():target+=f"<tr><td>{label}</td><td>{version.replace('_',' ')}</td><td>{s['mean']:,.1f}</td><td>{s['median']:,.0f}</td><td>{s['min']:,}–{s['max']:,}</td><td>{s['below_1500']}/{s['samples']}</td></tr>"
    t=p['four']['cluster_terrain_pvs'];d=p['replay_decomposition']
    target+=f"</tbody></table><p>The new replay mean is {t['mean_target_multiple']:.2f}× the target; another {t['mean_remaining_reduction_percent']:.1f}% reduction would reach 1,500 on average, without guaranteeing every camera meets it. Dynamic geometry is additional. <a href='target-progress.json'>Target census and decomposition</a> · <a href='four-cameras.csv'>Every matched camera</a>.</p>"
    target+=f"<p>Compared with the previous combined prototype, cluster-local geometry/batching adds {d['additional_unculled_loads']:.1f} mean replay loads before PVS. Better membership coverage saves an additional {d['additional_pvs_savings']:.1f} loads; the net change is {d['net_load_increase']:+.1f}. Source terrain has 4,218 triangles: previous reduction retained 3,306; this candidate retains {sum(r['candidate_triangles'] for r in packing['blender_report']):,}. No changed terrain is unassigned: all {packing['terrain_membership_batches']} terrain batches carry source memberships, with {packing['mixed_membership_batches']} conservative unions of multiple partition masks.</p>"
    target+="<p>Reduction is restricted to 21 material/membership partitions. Cluster seams and all 298 source cliff faces at walkable slopes are pinned; original collision and all 383 nonterrain batches are preserved. Native pixel guards from the previous prototype carry over. This final candidate also strengthens rock walking-surface protection from the previous 239 flatter faces to all 298 faces at walkable slopes; the comparison includes that added constraint. <a href='data/cluster-source.json'>Original face memberships</a> · <a href='data/batch-memberships.json'>Memberships through batching</a> · <a href='data/visibility.json'>Hash-bound PVS</a> · <a href='pvs-contract.log'>Camera-sphere tests</a>.</p>"
    if (OUT/'timing-summary.json').exists():
        timing=json.loads((OUT/'timing-summary.json').read_text());target+='<h2>Timing versus previous combined prototype</h2><table><thead><tr><th>Route</th><th>Previous</th><th>Cluster-aware</th><th>Change</th></tr></thead><tbody>'
        for route,label in [('one','Single-player'),('four','Four-player')]:
            t=timing[route];target+=f"<tr><td>{label}</td><td>{t['baseline_fps']:.2f} FPS</td><td>{t['candidate_fps']:.2f} FPS</td><td>{t['gain_percent']:+.2f}%</td></tr>"
        target+='</tbody></table><p>Freshly repeated previous/candidate/previous/candidate controls; exact rates from native pose counts and sample durations. <a href="timing-summary.json">Timing scope and calculations</a>.</p>'
    target+='<p><a href="../n64-sidewinder-combined/comparison.html">Previous combined appraisal</a> · <a href="visibility-pixel-comparisons.json">Independent PVS pixel check</a> · <a href="four-pixel-comparisons.json">Four-camera image checks</a></p>'
    viewer.OUT=OUT;html=viewer.HTML;a=html.index('</style><h1>');b=html.index('<div id="perf">',a)
    html=html[:a]+"</style><h1>Sidewinder: cluster-aware terrain appraisal</h1><p>Cluster-local simplification preserves original walking collision and structures, carrying face membership through UV splitting and batching. A separate candidate, stopped for appraisal; accepted assets remain unchanged.</p>"+html[b:]
    html=html.replace('<div id="perf"></div>','<div id="perf"></div>'+target)
    html=html.replace('<h2>Matched photos</h2>','<h2>Matched photos</h2><label>Compare against <select id="comparison"><option value="before">Previous combined prototype</option><option value="uncull">Same new geometry, visibility off</option></select></label>')
    html=html.replace('Original PNG','Baseline PNG').replace('Original fixture ROM','Baseline fixture ROM').replace('Candidate PNG','Cluster-aware PNG')
    html=html.replace('data-mode="before">Before','data-mode="before">Baseline').replace('data-mode="after">After','data-mode="after">Cluster-aware')
    html=html.replace("const paths=['photos/before/'+id+'-native.png'", "const paths=['photos/'+(DATA.beforePhase||'before')+'/'+id+'-native.png'")
    html=html.replace("'photo-roms/before/'+id+'.z64'", "'photo-roms/'+(DATA.beforePhase||'before')+'/'+id+'.z64'")
    controls=['data:image/png;base64,'+base64.b64encode((OUT/f'photos/uncull/{i:02}-native.png').read_bytes()).decode() for i in range(24)]
    setup="DATA.priorImages=DATA.images.before;DATA.controlImages="+json.dumps(controls)+";DATA.beforePhase='before';$('comparison').onchange=e=>{DATA.beforePhase=e.target.value;DATA.images.before=DATA.beforePhase==='uncull'?DATA.controlImages:DATA.priorImages;select(index);};"
    html=html.replace('const poses=DATA.poses;','const poses=DATA.poses;'+setup)
    html=html.replace("+a.fps+' → '+b.fps+","+(a.poses*1000/a.sample_ms).toFixed(2)+' → '+(b.poses*1000/b.sample_ms).toFixed(2)+")
    html=html.replace("+x.fps+' FPS;","+(x.poses*1000/x.sample_ms).toFixed(2)+' FPS;")
    html=html.replace('Freshly repeated previous/candidate/previous/candidate controls; exact rates', 'Both final repeats match exactly. Overall P95 and maximum intervals are unchanged. Early four-player P95 worsens 133.7→167.1 ms. Freshly repeated previous/candidate/previous/candidate controls; exact rates')
    viewer.HTML=html;viewer.main()
    # This candidate can increase counts; avoid describing a negative saving as a fall.
    path=OUT/'comparison.html';text=path.read_text().replace('vertex loads fall from','vertex loads change from').replace('world triangles fall from','world triangles change from')
    path.write_text(text);(OUT/'report-script.js').write_text(text.split('<script>')[1].split('</script>')[0])

if __name__=='__main__':main()
