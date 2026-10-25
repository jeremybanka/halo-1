"""Appraise reduced terrain plus conservative visibility against matched controls."""
import csv
import json
from pathlib import Path
import statistics
import report_sidewinder_photos as viewer

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/n64-sidewinder-combined'
TERRAIN=ROOT/'build/n64-sidewinder-aggressive'

def rows(path):return list(csv.DictReader(path.open()))

def distribution(records,key='vertices'):
    values=[int(r[key]) for r in records];mean=statistics.mean(values)
    return dict(samples=len(values),mean=mean,median=statistics.median(values),min=min(values),max=max(values),
                below_1500=sum(v<1500 for v in values),mean_target_multiple=mean/1500,
                mean_remaining_reduction_percent=100*(1-1500/mean))

def census():
    raw=rows(OUT/'cameras/cameras.csv')
    pair=[[r for r in raw if r['map']=='1' and r['candidate']==str(i)] for i in (0,1)]
    prior=rows(TERRAIN/'four-cameras.csv')
    fields=['vertices','triangles','chunks','material_changes','float_clip_crossing_estimate','float_clip_rejected_estimate']
    pose=['map','tick','camera','eye_x','eye_y','eye_z','alive','zoom']
    assert len(pair[0])==len(pair[1])==len(prior)==68
    assert (OUT/'after-census/poses.json').read_bytes()==(TERRAIN/'after-census/poses.json').read_bytes()
    for a,b,p in zip(*pair,prior):
        assert all(a[k]==b[k]==p[k] for k in pose)
        assert all(a[k]==p['after_'+k] for k in fields)
    summary={phase:{k:statistics.mean(int(r[k]) for r in records) for k in fields}
             for phase,records in zip(['before','after'],pair)}
    summary.update(camera_samples=68,scope='Reduced terrain without/with conservative PVS. Static world only; clipping is an estimate.')
    (OUT/'four-camera-results.json').write_text(json.dumps(summary,indent=2)+'\n')
    with (OUT/'four-cameras.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=pose+[ph+'_'+k for k in fields for ph in ['before','after']]);w.writeheader()
        for a,b in zip(*pair):w.writerow({**{k:a[k] for k in pose},**{ph+'_'+k:r[k] for k in fields for ph,r in zip(['before','after'],[a,b])}})
    original=rows(ROOT/'build/n64-visibility-rollout/sidewinder/cameras/cameras.csv')
    photo0=rows(ROOT/'build/n64-sidewinder-photography/before-census/cameras.csv')
    photo1=rows(OUT/'after-census/cameras.csv')
    progress={'four':{'original':distribution([r for r in original if r['map']=='1' and r['candidate']=='0']),
                      'visibility_only':distribution([r for r in original if r['map']=='1' and r['candidate']=='1']),
                      'terrain_only':distribution(pair[0]),'combined':distribution(pair[1]),
                      'combined_alive_only':distribution([r for r in pair[1] if r['alive']=='1'])},
              'photos':{'original':distribution([r for r in photo0 if r['candidate']=='0']),
                        'terrain_only':distribution([r for r in photo1 if r['candidate']=='0']),
                        'combined':distribution([r for r in photo1 if r['candidate']=='1'])},
              'native_checkpoints':{str(tick):[[int(r[k]) for k in ['camera','vertices','triangles','chunks','material_changes']]
                        for r in pair[1] if r['tick']==str(tick)] for tick in [180,1148]}}
    (OUT/'target-progress.json').write_text(json.dumps(progress,indent=2)+'\n')
    return progress

def main():
    p=census();vis=json.loads((OUT/'data/visibility.json').read_text());target='<h2>Target: fewer than 1,500 vertex loads per camera</h2>'
    target+='<table><thead><tr><th>Workload</th><th>Version</th><th>Mean</th><th>Median</th><th>Range</th><th>Under target</th></tr></thead><tbody>'
    for route,label in [('four','Four-camera replay'),('photos','Single-player photos')]:
        for version,s in p[route].items():
            target+=f"<tr><td>{label}</td><td>{version.replace('_',' ')}</td><td>{s['mean']:,.1f}</td><td>{s['median']:,.0f}</td><td>{s['min']:,}–{s['max']:,}</td><td>{s['below_1500']}/{s['samples']}</td></tr>"
    target+='</tbody></table>'
    target+=f"<p>The combined replay mean is {p['four']['combined']['mean_target_multiple']:.2f} times the target, requiring another {p['four']['combined']['mean_remaining_reduction_percent']:.1f}% reduction to reach 1,500 on average. That would still not guarantee every view meets the target. One below-target replay view is a dead-player camera; only two of 63 alive-player samples qualify. <a href='target-progress.json'>Complete target census</a> · <a href='four-cameras.csv'>All matched cameras</a>.</p>"
    target+=f"<p>The reduced terrain bank is byte-identical to the earlier aggressive candidate. Visibility transfers through verified geometry identity: all 383 protected batches and {len(vis['exact_terrain_chunks'])} terrain batches retain original cluster masks; {len(vis['modified_fail_open_chunks'])} modified/unassigned terrain batches remain visible. Existing nonopaque and ten native pixel guards carry over. Four additional batches are retained after a three-sample counterexample in photos 14 and 15. <a href='data/visibility.json'>Hash-bound visibility data</a> · <a href='initial-visibility/pixel-comparisons.json'>Initial counterexample</a> · <a href='pvs-contract.log'>Camera-sphere tests</a>.</p>"
    target+="<p>The viewer compares <b>terrain only</b> with <b>terrain + visibility</b>. It isolates the visual effect of visibility. <a href='../n64-sidewinder-aggressive/comparison.html'>Original vs reduced-terrain appraisal</a> shows the simplification cost.</p>"
    if (OUT/'timing-summary.json').exists():
        timing=json.loads((OUT/'timing-summary.json').read_text())
        target+='<h2>Fresh-pose timing across experiments</h2><table><thead><tr><th>Route</th><th>Original reference</th><th>Terrain only</th><th>Combined</th><th>Over original</th><th>Added visibility</th></tr></thead><tbody>'
        for route,label in [('one','Single-player photo walk'),('four','Four-player replay')]:
            t=timing[route]
            target+=f"<tr><td>{label}</td><td>{t['original_fps']:.2f} FPS</td><td>{t['terrain_fps']:.2f} FPS</td><td>{t['combined_fps']:.2f} FPS</td><td>+{t['gain_over_original_percent']:.2f}%</td><td>+{t['incremental_gain_percent']:.2f}%</td></tr>"
        target+='</tbody></table><p>Original-map numbers are prior repeated controls. Terrain-only and combined numbers were freshly measured baseline/candidate/baseline/candidate in this run, and each repeat is exact. Single-player P95 stays 50.1 ms, but its maximum increases 83.5→100.2 ms. Four-player P95 stays 133.7 ms and maximum stays 200.5 ms. <a href="timing-summary.json">Exact rate calculations and reference scope</a>.</p>'
    viewer.OUT=OUT;html=viewer.HTML
    a=html.index('</style><h1>');b=html.index('<div id="perf">',a)
    html=html[:a]+"</style><h1>Sidewinder: terrain + conservative visibility</h1><p>Matched camera, photo and quiet timing checks on the same reduced terrain. An appraisal experiment; accepted assets remain unchanged.</p>"+html[b:]
    html=html.replace('<div id="perf"></div>','<div id="perf"></div>'+target)
    html=html.replace('alt="Original terrain"','alt="Reduced terrain without visibility"').replace('alt="Simplified terrain"','alt="Reduced terrain with visibility"')
    html=html.replace('Original PNG','Terrain-only PNG').replace('Candidate PNG','Combined PNG').replace('Original fixture ROM','Terrain-only fixture ROM').replace('Candidate fixture ROM','Combined fixture ROM')
    html=html.replace('data-mode="before">Before','data-mode="before">Terrain only').replace('data-mode="after">After','data-mode="after">Terrain + visibility')
    viewer.HTML=html;viewer.main()

if __name__=='__main__':main()
