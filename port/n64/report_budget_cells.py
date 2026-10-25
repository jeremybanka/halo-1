"""Matched before/after photos, replay views and native appraisal evidence."""
import csv,json,math,struct
import numpy as np
from PIL import Image,ImageDraw
from sidewinder_budget_cells import BASE,OUT,ROOT,sections
from photo_sidewinder_structures import load_bank,render
from report_sidewinder_budget import selected as old_selected
from report_world_lod import subset

def cell_row(data,eye,scoped=False):
    if scoped and data['cells'].get('unscoped_only'):return cell_row({'cells':data['cells']['fallback']},eye)
    c=data['cells'];at=(np.array(eye)-c['origin'])/c['step'];dims=c['dimensions']
    if not np.isfinite(at).all() or any(at[a]<0 or at[a]>=dims[a] for a in range(3)):
        return cell_row({'cells':c['fallback']},eye) if 'fallback' in c else None
    x,y,z=map(int,at);i=(y*dims[2]+z)*dims[0]+x
    return c['visible'][i*c['words']:(i+1)*c['words']]

def selected(bank,data,levels,eye,cells=True,scoped=False):
    view=old_selected(bank,data,levels,eye)
    rep=data['representation'];active=all(rep['bounds'][a]<eye[a]<rep['bounds'][a+3] for a in range(3)) and all(p[0]*eye[0]+p[1]*eye[2]>p[2] for p in rep['footprint_planes'])
    row=cell_row(data,eye,scoped) if cells and not active else None
    if row is not None:view=subset(view,np.array([bool(row[int(b)//32]>>(int(b)%32)&1) for b in view[2]]))
    return view

def native_faces(bank,eye):
    # The earlier float photo helper drew both sides of opaque faces. Match
    # the actual world bank's CULL_FRONT winding for both baseline/candidate.
    p=bank[0][:,:,:3];n=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]);front=np.sum(n*(np.array(eye)*32-p[:,0]),axis=1)<=1e-5
    two=np.array([bool(bank[4][m]&4) for m in bank[1]])
    return subset(bank,front|two)

def extras():
    import ctypes,subprocess
    code='#include "render_world_lod.h"\nint choose(unsigned g,float c[4][4],float p[4][4],float w,float h,float n,float e[3]){return bg_world_lod_far(&bg_world_lod.groups[g],c,p,w,h,n,e);}\n'
    (OUT/'selector.c').write_text(code)
    libs=[]
    for root in (BASE,OUT):
        destination=OUT/('selector-old.dylib' if root==BASE else 'selector-new.dylib')
        subprocess.run(['clang','-shared','-fPIC','-O2','-ffp-contract=off','-fno-fast-math','-I'+str(ROOT/'port/n64'),str(OUT/'selector.c'),str(root/'visibility-data.c'),'-lm','-o',str(destination)],check=True)
        lib=ctypes.CDLL(str(destination));fp=ctypes.POINTER(ctypes.c_float);lib.choose.argtypes=[ctypes.c_uint,fp,fp,ctypes.c_float,ctypes.c_float,ctypes.c_float,fp];lib.choose.restype=ctypes.c_int;libs.append(lib)
    old=json.loads((BASE/'visibility.json').read_text());new=json.loads((OUT/'visibility.json').read_text());banks=[load_bank(root/'candidate-maps/sidewinder.map64') for root in (BASE,OUT)]
    directory=OUT/'extra-images';directory.mkdir(exist_ok=True);records=[]
    stations=[('West far apron',[-43.8438759,.792942643,-40.4629784]),('West base entrance',[-38.7644768,-3.11913776,29.3298626]),('Central passage',[-4.54840994,.862279117,11.1106997]),('East far apron',[40.3628654,.819689155,-39.6673965])]
    requests=[]
    for label,eye in stations:
        for yaw in (0,math.pi/2,math.pi,math.pi*1.5):
            for zoom in (0,2,10):requests.append((label,eye,yaw,0,zoom))
    # Both sides of an actual cell edge, at the same saved photo station.
    for x in (-40.0001,-39.9999):
        for yaw in (0,math.pi/2,math.pi,math.pi*1.5):requests.append(('Cell edge diagnostic',[x,.792942643,-40.1519165],yaw,-.15,0))
    for index,(label,eye,yaw,pitch,zoom) in enumerate(requests):
        width,height=320,240;near=32 if zoom else 4;far=12400 if zoom else 6200;fov=2*math.atan(math.tan(1.08/2)/(zoom or 1));f=1/math.tan(fov/2)
        forward=np.array([math.cos(yaw)*math.cos(pitch),math.sin(pitch),-math.sin(yaw)*math.cos(pitch)]);right=np.cross(forward,[0,1,0]);right/=np.linalg.norm(right);up=np.cross(right,forward);view=np.eye(4);view[:3,:3]=np.stack((right,up,-forward));view[:3,3]=-view[:3,:3]@(np.array(eye)*32)
        projection=np.zeros((4,4));projection[0,0]=f/(width/height);projection[1,1]=f;projection[2,2]=-(far+near)/(far-near);projection[2,3]=-2*far*near/(far-near);projection[3,2]=-1
        ca=np.ascontiguousarray(view.T,dtype=np.float32);pa=np.ascontiguousarray(projection.T,dtype=np.float32);ea=np.ascontiguousarray(np.array(eye)*32,dtype=np.float32);levels=[]
        for lib,meta in zip(libs,(old,new)):levels.append(np.array([lib.choose(g,ca.ctypes.data_as(fp),pa.ctypes.data_as(fp),width,height,near,ea.ctypes.data_as(fp)) for g in range(len(meta['lod_groups']))]))
        matrix=(projection@view).T;aa=native_faces(old_selected(banks[0],old,levels[0],eye),eye);bb=native_faces(selected(banks[1],new,levels[1],eye,scoped=bool(zoom)),eye);control=native_faces(selected(banks[1],new,levels[1],eye,cells=False),eye)
        a=render(aa,matrix,width=width,height=height);b=render(bb,matrix,width=width,height=height);c=render(control,matrix,width=width,height=height);diff=np.abs(a.astype(np.int16)-b.astype(np.int16));prefix=f'{index:02}'
        for name,im in [('before',a),('after',b),('difference',np.clip(diff*6,0,255).astype(np.uint8))]:Image.fromarray(im).save(directory/f'{prefix}-{name}.png')
        records.append(dict(label=f'{label} / yaw {yaw:.2f} / zoom {zoom or 1}x',eye=eye,yaw=yaw,pitch=pitch,zoom=zoom,fov=fov,near=near,far=far,matrix_columns=matrix.tolist(),prefix='extra-images/'+prefix,changed_pixels=int(np.count_nonzero(diff.max(2))),mean_rgb_error=float(diff.mean()),cell_control_changed_pixels=int(np.count_nonzero(np.any(b!=c,axis=2)))))
        print(index,records[-1]['label'],'RGB',records[-1]['mean_rgb_error'],'cell',records[-1]['cell_control_changed_pixels'],flush=True)
    (OUT/'extra-images.json').write_text(json.dumps(records,indent=2)+'\n')

def photos(dataset='photos'):
    before=load_bank(BASE/'candidate-maps/sidewinder.map64');after=load_bank(OUT/'candidate-maps/sidewinder.map64')
    old=json.loads((BASE/'visibility.json').read_text());new=json.loads((OUT/'visibility.json').read_text())
    cameras={(r['tick'],r['camera']):r for r in csv.DictReader((OUT/dataset/'cameras.csv').open()) if r['candidate']=='1'}
    oldcams={(r['tick'],r['camera']):r for r in csv.DictReader((BASE/dataset/'cameras.csv').open()) if r['candidate']=='1'}
    traces={tuple(row[:2]):row for row in csv.reader((BASE/dataset/'lod-trace.csv').open())}
    poses=json.loads((OUT/'photos/poses.json').read_text());directory=OUT/(dataset+'-images');directory.mkdir(exist_ok=True);records=[];contacts=[]
    for row in csv.reader((OUT/dataset/'lod-trace.csv').open()):
        key=tuple(row[:2]);pose=cameras[key];oldrow=traces[key];eye=[float(pose[k]) for k in ('eye_x','eye_y','eye_z')];matrix=np.array(list(map(float,row[2:18]))).reshape(4,4);levels=np.array(list(map(int,row[18:])));oldlevels=np.array(list(map(int,oldrow[18:])));mask=int(pose['pvs_mask'])
        w,h=(640,240) if dataset=='photos' else (160,120)
        aa=native_faces(old_selected(before,old,oldlevels,eye),eye);bb=native_faces(selected(after,new,levels,eye,scoped=bool(int(pose['alive']) and int(pose['zoom']))),eye);unculled=native_faces(selected(after,new,levels,eye,cells=False),eye)
        a=render(aa,matrix,old['chunk_masks'],mask,width=w,height=h);b=render(bb,matrix,new['chunk_masks'],mask,width=w,height=h);control=render(unculled,matrix,new['chunk_masks'],mask,width=w,height=h);pvs_control=render(bb,matrix,width=w,height=h)
        diff=np.abs(a.astype(np.int16)-b.astype(np.int16));cdiff=np.abs(control.astype(np.int16)-b.astype(np.int16));pdiff=np.abs(pvs_control.astype(np.int16)-b.astype(np.int16));prefix='-'.join(key)
        for name,im in [('before',a),('after',b),('difference',np.clip(diff*6,0,255).astype(np.uint8)),('culling-control',np.clip(cdiff*6,0,255).astype(np.uint8))]:Image.fromarray(im).save(directory/f'{prefix}-{name}.png')
        rec=dict(tick=int(key[0]),camera=int(key[1]),eye=eye,matrix_columns=matrix.tolist(),levels=levels.tolist(),before_levels=oldlevels.tolist(),before_loads=int(oldcams[key]['vertices']),after_loads=int(pose['vertices']),before_chunks=int(oldcams[key]['chunks']),after_chunks=int(pose['chunks']),changed_pixels=int(np.count_nonzero(diff.max(2))),mean_rgb_error=float(diff.mean()),cell_control_changed_pixels=int(np.count_nonzero(cdiff.max(2))),pvs_control_changed_pixels=int(np.count_nonzero(pdiff.max(2))),prefix=f'{dataset}-images/{prefix}')
        if dataset=='photos':rec.update(label=poses[int(key[0])]['label'],pose=poses[int(key[0])])
        else:rec['label']=f'Tick {key[0]} / camera {key[1]}'
        records.append(rec)
        if dataset=='photos' or int(oldcams[key]['vertices'])>=12000:
            im=Image.new('RGB',(1280,265),(18,24,34));im.paste(Image.fromarray(a).resize((640,240),Image.Resampling.NEAREST),(0,25));im.paste(Image.fromarray(b).resize((640,240),Image.Resampling.NEAREST),(640,25));ImageDraw.Draw(im).text((4,4),rec['label']+f'  {rec["before_loads"]} -> {rec["after_loads"]} loads; RGB {rec["mean_rgb_error"]:.3f}',fill='white');contacts.append(im)
        print(dataset,key,rec['before_loads'],'->',rec['after_loads'],'RGB',round(rec['mean_rgb_error'],4),'culling',rec['cell_control_changed_pixels'],'PVS',rec['pvs_control_changed_pixels'],flush=True)
    sheet=Image.new('RGB',(1280,265*len(contacts)),(18,24,34))
    for i,im in enumerate(contacts):sheet.paste(im,(0,265*i))
    if contacts:sheet.save(OUT/(dataset+'-contact.png'))
    (OUT/(dataset+'-images.json')).write_text(json.dumps(records,indent=2)+'\n')

def report():
    m=json.loads((OUT/'measurements.json').read_text());data=[]
    for kind,filename in [('Photo route','photos-images.json'),('Replay cameras','replay-images.json'),('Extra cameras','extra-images.json')]:
        if not (OUT/filename).exists():continue
        for r in json.loads((OUT/filename).read_text()):data.append(dict(kind=kind,label=r['label'],before=r['prefix']+'-before.png',after=r['prefix']+'-after.png',difference=r['prefix']+'-difference.png',meta=r))
    native=json.loads((OUT/'native-images.json').read_text()) if (OUT/'native-images.json').exists() else []
    for r in native:data.append(dict(kind='Native Ares',label=r['label'],before=r['prefix']+'-before.png',after=r['prefix']+'-after.png',difference=r['prefix']+'-difference.png',meta=r))
    timing=json.loads((OUT/'timing.json').read_text()) if (OUT/'timing.json').exists() else {}
    profiles=json.loads((OUT/'profiling.json').read_text()) if (OUT/'profiling.json').exists() else {}
    profile_table=''
    if profiles:
        runs=profiles['runs'];a=runs['cpu-baseline']['groups']['ALL']['mean_phase_us'];b=runs['cpu-candidate']['groups']['ALL']['mean_phase_us']
        profile_table='<h3>Ordinary CPU attribution</h3><p>Inclusive milliseconds per rendered frame. Simulation can execute multiple fixed ticks in a slow frame. These rows overlap and must not be summed.</p><table><tr><th>Phase</th><th>Before ms</th><th>After ms</th></tr>'+''.join(f'<tr><td>{label}</td><td>{a[key]/1000:.3f}</td><td>{b[key]/1000:.3f}</td></tr>' for key,label in [('sim','Simulation'),('camera','Camera preparation'),('animation','Animation'),('world','World submission'),('objects','Dynamic object submission'),('wait','Measured wait'),('queue_stall','Queue stalls (overlap other phases)')])+'</table>'
        profile_table+='<h3>Serialized geometry controls</h3><p>Remaining fence/drain waits after CPU submission, not total processor execution time. Longer submission gives graphics more time to run before the fence. Empty scissor removes 3D pixel coverage while retaining geometry commands.</p><table><tr><th>Run</th><th>World CPU ms</th><th>RSP fence ms</th><th>Residual RDP ms</th><th>DP busy while polling</th></tr>'
        for key,label in [('pipeline-baseline','Baseline'),('pipeline-candidate','Candidate'),('pipeline-empty','Candidate / empty scissor')]:
            r=runs[key]['groups']['ALL'];p=r['mean_phase_us'];profile_table+=f'<tr><td>{label}</td><td>{p["world"]/1000:.3f}</td><td>{p["geometry_rsp_wait"]/1000:.3f}</td><td>{p["geometry_rdp_wait"]/1000:.3f}</td><td>{r["dp_busy_poll_percent"]:.1f}%</td></tr>'
        profile_table+='</table><p><b>The saving is real, but finer batching is expensive.</b> Average submitted batches rise from 177 to 261 per sampled replay camera. CPU world submission rises from 14.6 to 23.7 ms per instrumented frame while quiet four-player throughput improves. The empty-scissor control leaves the remaining graphics wait essentially unchanged, so pixel coverage is not the main remaining graphics cost. Future budgeting needs to reduce command/batch overhead alongside vertex loads.</p>'
    counts=json.loads((OUT/'camera-budgets.json').read_text())
    costly=sorted(counts['replay']['cameras'],key=lambda r:r['before'],reverse=True)[:12]
    costly_table='<table><tr><th>Replay camera</th><th>Before loads</th><th>After loads</th><th>Over 1,500</th><th>Batches before → after</th></tr>'+''.join(f'<tr><td>{r["tick"]} / P{r["camera"]}</td><td>{r["before"]:,}</td><td>{r["after"]:,}</td><td>{r["gap_to_1500"]:,}</td><td>{r["before_batches"]} → {r["after_batches"]}</td></tr>' for r in costly)+'</table>'
    checks=''
    if (OUT/'rdp-validation.json').exists():checks='<h2>Native validation</h2><p>Twelve native camera counter sets match their SDK fixtures. The RDP validator reports 0 errors and 0 warnings with 8 KiB queues in four authored hotspot views. A repeated frozen baseline is pixel-identical. Native cell-culling-disabled controls at ticks 600 and 1950 change zero pixels across all eight camera images, with LOD and batching held constant. Native route photos retain identical full-precision pose logs and debug overlays; their image differences are available in the viewer.</p><p><a href="native-census-checks.json">Native counter checks</a> · <a href="native-images.json">Native image metrics</a> · <a href="native-cell-controls.json">Native culling-only controls</a> · <a href="rdp-validation.png">RDP validator capture</a> · <a href="scenery-support-checks.json">Scenery support and sphere checks</a></p>'
    table=''.join(f'<tr><td>{name}</td><td>{r["before_mean"]:,.0f}</td><td>{r["after_mean"]:,.0f}</td><td>{r["after_worst"]:,}</td><td>{r["below_1500"]}/{r["samples"]}</td></tr>' for name,r in m.items())
    timing_table=''.join(f'<tr><td>{name}</td><td>{r["baseline_fps"]:.3f}</td><td>{r["candidate_fps"]:.3f}</td><td>{r["gain_percent"]:+.2f}%</td><td>{r["baseline_p95_ms"]:.3f} → {r["candidate_p95_ms"]:.3f}</td></tr>' for name,r in timing.items())
    old=(BASE/'comparison.html').read_text();css=old[old.index('<style>'):old.index('</style>')+8];js=old[old.index(';const $=id=>'):old.index('</script>')]
    page='<!doctype html><meta charset="utf-8"><title>Sidewinder — broader camera budgets</title>'+css+'''<h1>Sidewinder — broader camera budgets</h1><div class="hero"><div><strong>6,983 → 5,279</strong>sampled mean loads / replay camera</div><div><strong>12.58 → 14.03 FPS</strong>quiet native four-player replay</div><div><strong>29.08 → 29.93 FPS</strong>quiet native single-player route</div></div><p>A private appraisal candidate extending the previous east-room prototype. The original collision, movement and texture sections remain exact. Other expensive views move toward 1,500 static-world loads; this is not a claim that the map now meets that budget. Additional startup RAM is about 622 KiB; the native four-player run starts with 2,182,960 bytes free. This is not a peak-memory watermark.</p>
    <h2>What changed</h2><ul><li>Opaque faces are batched by spatial region and facing direction. Precomputed 8 × 2 × 8 world-unit camera cells skip batches only when every face is back-facing throughout the cell, or a certified opaque shadow covers the entire batch. Uncertain/outside positions fail open. The original enclosed east-room selection remains.</li><li>Thirty scenery components were authored and 28 accepted for screen-size LOD treatment. Tiny details disappear only below a 0.75-pixel projected diameter; other accepted proxies use directional support pins and switch below 12 pixels, with a two-unit near exclusion. The complete original near geometry remains available.</li><li>Existing structure/terrain distance proxies are selected with twice the previous projected-error allowance (6 and 3 pixels), retaining their original geometry bounds and near exclusions. Tree selection is unchanged.</li></ul>
    <h2>Matched static-world loads</h2><table><tr><th>Workload</th><th>Before mean</th><th>After mean</th><th>After maximum</th><th>Below 1,500</th></tr>'''+table+'''</table><p>Counts include paired padding and repeated batch vertices. Dynamic objects are additional. The baseline is the previous complete east-room budget candidate. Four of 63 live replay camera samples are below 1,500; three additional below-target samples are dead views.</p><h3>Previously expensive cameras</h3>'''+costly_table+'''
    <h2>Native Ares performance</h2><p>Fresh quiet NTSC runs: 8 MiB Expansion Pak, release LTO, three surfaces, 32 KiB queues, one-second warmup and 75-second fresh-pose sampling. CPU profiling and deliberately serialized RSP/RDP experiments are separate; their phase times overlap and must not be summed into production frame time.</p><table><tr><th>Workload</th><th>Before FPS</th><th>After FPS</th><th>Gain</th><th>P95 frame ms</th></tr>'''+timing_table+'''</table>
    '''+profile_table+'''<details><summary>Complete fresh CPU / RSP / RDP records</summary><pre>'''+json.dumps(profiles,indent=2)+'''</pre></details>
    <h2>Matched images and difference filters</h2><p>All 24 full photo poses and 68 replay camera states are retained. Offline rendering now applies the actual opaque-face winding on both sides of each comparison; the older helper rendered opaque faces from both sides. Offline float/nearest renders omit native fog, RDP rounding, HUD and dynamics. Native images provide separate checks. Diff RGB is amplified six times. Exact poses, loads, LOD levels and culling-control pixel results are attached to every image.</p>
    <div class="viewer"><select id="kind"></select><button id="prev">Previous</button><select id="choice"></select><button id="next">Next</button><p id="description"></p><div class="pair"><div>Previous budget candidate<img id="before"></div><div>Broader budget candidate<img id="after"></div></div><p><select id="mode"><option value="difference">RGB difference ×6</option><option value="blend">Before / after blend</option><option value="wipe">Before / after wipe</option></select><input id="amount" type="range" min="0" max="100" value="50"></p><canvas id="filter"></canvas><details><summary>Camera and measurements</summary><pre id="metadata"></pre></details></div>
    '''+checks+'''<p><a href="REPRODUCE.txt">Reproduction and limits</a> · <a href="measurements.json">Measurements</a> · <a href="camera-budgets.json">Per-camera budgets</a> · <a href="profiling.json">Profiling</a> · <a href="timing.json">Native timing</a> · <a href="validation.json">Validation</a> · <a href="photos-images.json">Photos and poses</a> · <a href="replay-images.json">Replay camera comparisons</a> · <a href="scenery-appraisal.blend">Blender scenery study</a></p><script>const records='''+json.dumps(data)+js+'</script>'
    (OUT/'comparison.html').write_text(page)

if __name__=='__main__':
    import sys
    if sys.argv[1] in ('photos','replay'):photos(sys.argv[1])
    elif sys.argv[1]=='extras':extras()
    else:report()
