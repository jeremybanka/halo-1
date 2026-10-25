"""Matched world LOD photos, native-size asset views, and appraisal viewer."""
import collections,csv,json,math,re
import numpy as np
from PIL import Image,ImageDraw
from sidewinder_world_lod import ROOT,OUT,BASE
from photo_sidewinder_structures import load_bank,render

def subset(bank,keep):return (bank[0][keep],bank[1][keep],bank[2][keep],bank[3],bank[4])

def photos():
    before=load_bank(BASE/'candidate-maps/sidewinder.map64');bank=load_bank(OUT/'candidate-maps/sidewinder.map64');data=json.loads((OUT/'visibility.json').read_text());codes=np.array(data['lod_chunks']);owner_codes=codes[bank[2]];group=np.maximum(0,(owner_codes-1)//2);level=(owner_codes-1)%2
    near=subset(bank,(owner_codes==0)|(level==0));cameras={int(r['tick']):r for r in csv.DictReader((OUT/'photos/cameras.csv').open()) if r['candidate']=='1'};poses=json.loads((OUT/'photos/poses.json').read_text());oldm=json.loads((BASE/'visibility.json').read_text())['chunk_masks'];out=OUT/'photos/images';out.mkdir(exist_ok=True);results=[];contacts=[]
    for row in csv.reader((OUT/'photos/lod-trace.csv').open()):
        index=int(row[0]);matrix=np.array(list(map(float,row[2:18]))).reshape(4,4);levels=np.array(list(map(int,row[18:])));view=subset(bank,(owner_codes==0)|(levels[group]==level));mask=int(cameras[index]['pvs_mask'])
        a=render(before,matrix,oldm,mask);b=render(view,matrix,data['chunk_masks'],mask);unculled=render(view,matrix);n=render(near,matrix,data['chunk_masks'],mask)
        diff=np.abs(a.astype(np.int16)-b.astype(np.int16));control=np.abs(a.astype(np.int16)-n.astype(np.int16));pvs=np.abs(unculled.astype(np.int16)-b.astype(np.int16))
        for name,im in [('before',a),('after',b),('difference',np.clip(diff*6,0,255).astype(np.uint8)),('near-control',n),('pvs-control',unculled)]:Image.fromarray(im).save(out/f'{index:02}-{name}.png')
        result=dict(photo=index,label=poses[index]['label'],pose=poses[index],matrix_columns=matrix.tolist(),selected_levels=levels.tolist(),far_groups=dict(collections.Counter(g['category'] for g,l in zip(data['lod_groups'],levels) if l)),changed_pixels=int(np.count_nonzero(diff.max(2))),mean_rgb_error=float(diff.mean()),near_control_changed_pixels=int(np.count_nonzero(control.max(2))),pvs_control_changed_pixels=int(np.count_nonzero(pvs.max(2))))
        results.append(result);im=Image.new('RGB',(1280,265),(18,24,34));im.paste(Image.fromarray(a),(0,25));im.paste(Image.fromarray(b),(640,25));draw=ImageDraw.Draw(im);draw.text((8,5),f'{index:02} {result["label"]} / accepted fixed lean',fill='white');draw.text((648,5),'screen-size world LOD',fill='white');contacts.append(im)
        print(index,result['changed_pixels'],'LOD pixels;',result['near_control_changed_pixels'],'near-control;',result['pvs_control_changed_pixels'],'PVS',flush=True)
    im=Image.new('RGB',(1280,len(contacts)*265),(18,24,34))
    for i,r in enumerate(contacts):im.paste(r,(0,i*265))
    im.save(OUT/'photo-contact.png');(OUT/'photos.json').write_text(json.dumps(results,indent=2)+'\n')

def assets():
    bank=load_bank(OUT/'candidate-maps/sidewinder.map64');data=json.loads((OUT/'visibility.json').read_text());codes=np.array(data['lod_chunks'])[bank[2]];directory=OUT/'assets';directory.mkdir(exist_ok=True);results=[];contact=[]
    # Test both bases, large and small pines, a cliff and a snow patch at their
    # relevant small image sizes. Repeated tree placements share source shape.
    picks=[]
    for category in ('structures','trees','terrain'):
        candidates=[(i,g) for i,g in enumerate(data['lod_groups']) if g['category']==category]
        if category=='structures':candidates=[(i,g) for i,g in candidates if g['key'][1] in ('West base','East base')]
        elif category=='trees':candidates=[candidates[0],next((i,g) for i,g in candidates if 'snowsmall' in str(g['key']))]
        else:candidates=[next((i,g) for i,g in candidates if g['key'][1]==m) for m in (7,8)]
        picks.extend(candidates)
    for si,(gi,g) in enumerate(picks):
        near=subset(bank,codes==1+gi*2);far=subset(bank,codes==2+gi*2);center=np.array(g['center'])*32;allp=near[0][:,:,:3].reshape(-1,3);span=max(np.ptp(allp,axis=0))*1.2
        for ai in range(8):
            yaw=ai*math.pi/4;direction=np.array([math.sin(yaw),.18,math.cos(yaw)]);direction/=np.linalg.norm(direction);forward=-direction;right=np.cross(forward,[0,1,0]);right/=np.linalg.norm(right);up=np.cross(right,forward)
            view=np.eye(4);view[:3,:3]=np.stack((right,up,-forward));view[:3,3]=-view[:3,:3]@(center+direction*300*32)
            proj=np.eye(4);proj[0,0]=proj[1,1]=2/span;proj[2,2]=-2/(700*32);proj[2,3]=-1;matrix=(proj@view).T
            # Small views expose the actual distant read; large views expose
            # the sacrifices. These are authored orthographic asset checks,
            # not an assertion that the runtime switches at exactly 64 pixels.
            for pixels in (64,256):
                a=render(near,matrix,width=pixels,height=pixels);b=render(far,matrix,width=pixels,height=pixels);diff=np.abs(a.astype(np.int16)-b.astype(np.int16));ma=np.any(a!=(18,24,34),axis=2);mb=np.any(b!=(18,24,34),axis=2);outline=np.full_like(a,(18,24,34));outline[ma&mb]=(175,190,203);outline[ma&~mb]=(40,211,246);outline[mb&~ma]=(255,136,58)
                prefix=f'{si}-{ai}-{pixels}'
                for name,im in [('before',a),('after',b),('difference',np.clip(diff*6,0,255).astype(np.uint8)),('silhouette',outline)]:Image.fromarray(im).save(directory/f'{prefix}-{name}.png')
                results.append(dict(group=gi,label=str(g['key']),angle=ai,pixels=pixels,prefix=prefix,changed_pixels=int(np.count_nonzero(diff.max(2))),silhouette_iou=float((ma&mb).sum()/max(1,(ma|mb).sum())),silhouette_changed_pixels=int(np.count_nonzero(ma^mb)),matrix_columns=matrix.tolist()))
                if ai in (0,1) and pixels==64:
                    im=Image.new('RGB',(600,320),(18,24,34));im.paste(Image.fromarray(a).resize((256,256),Image.Resampling.NEAREST),(0,40));im.paste(Image.fromarray(b).resize((256,256),Image.Resampling.NEAREST),(300,40));ImageDraw.Draw(im).text((5,5),str(g['key'])[:75]+f' / angle {ai}',fill='white');contact.append(im)
        print('asset',g['key'],flush=True)
    im=Image.new('RGB',(1200,math.ceil(len(contact)/2)*320),(18,24,34))
    for i,r in enumerate(contact):im.paste(r,((i%2)*600,(i//2)*320))
    im.save(OUT/'asset-contact.png');(OUT/'assets.json').write_text(json.dumps(results,indent=2)+'\n')


def transitions():
    """Same-C selector and paired photographs immediately beyond each switch."""
    import ctypes,subprocess
    code='#include "render_world_lod.h"\nint choose(unsigned g,float c[4][4],float p[4][4],float w,float h,float n,float e[3]){return bg_world_lod_far(&bg_world_lod.groups[g],c,p,w,h,n,e);}\n'
    (OUT/'selector.c').write_text(code);subprocess.run(['clang','-shared','-fPIC','-O2','-ffp-contract=off','-I'+str(ROOT/'port/n64'),str(OUT/'selector.c'),str(OUT/'visibility-data.c'),'-lm','-o',str(OUT/'selector.dylib')],check=True)
    lib=ctypes.CDLL(str(OUT/'selector.dylib'));fp=ctypes.POINTER(ctypes.c_float);lib.choose.argtypes=[ctypes.c_uint,fp,fp,ctypes.c_float,ctypes.c_float,ctypes.c_float,fp];lib.choose.restype=ctypes.c_int
    data=json.loads((OUT/'visibility.json').read_text());bank=load_bank(OUT/'candidate-maps/sidewinder.map64');codes=np.array(data['lod_chunks'])[bank[2]];directory=OUT/'transitions';directory.mkdir(exist_ok=True);results=[]
    chosen=[int(r['group']) for r in json.loads((OUT/'assets.json').read_text()) if r['angle']==0 and r['pixels']==64]
    for si,gi in enumerate(chosen):
        g=data['lod_groups'][gi];center=np.array(g['center'])*32;nearbank=subset(bank,codes==1+gi*2);farbank=subset(bank,codes==2+gi*2)
        for ai in range(4):
            yaw=ai*math.pi/2+.3;direction=np.array([math.sin(yaw),.08,math.cos(yaw)]);direction/=np.linalg.norm(direction);right=np.cross(-direction,[0,1,0]);right/=np.linalg.norm(right);up=np.cross(right,-direction)
            for views,width,height in ((1,320,240),(4,160,120)):
                proj=np.zeros((4,4));f=1/math.tan(1.08/2);proj[0,0]=f/(width/height);proj[1,1]=f;near,far=4,6200;proj[2,2]=-(far+near)/(far-near);proj[2,3]=-2*far*near/(far-near);proj[3,2]=-1;pa=np.ascontiguousarray(proj.T,dtype=np.float32)
                def camera(distance):
                    eye=center+direction*distance*32;view=np.eye(4);view[:3,:3]=np.stack((right,up,direction));view[:3,3]=-view[:3,:3]@eye;ca=np.ascontiguousarray(view.T,dtype=np.float32);ea=np.ascontiguousarray(eye,dtype=np.float32)
                    selected=lib.choose(gi,ca.ctypes.data_as(fp),pa.ctypes.data_as(fp),width,height,near,ea.ctypes.data_as(fp));return selected,(proj@view).T,eye
                lo,hi=0.,1000.
                assert camera(lo)[0]==0 and camera(hi)[0]==1
                for _ in range(40):
                    mid=(lo+hi)/2
                    if camera(mid)[0]:hi=mid
                    else:lo=mid
                assert camera(hi*.99)[0]==0 and camera(hi*1.01)[0]==1
                selected,matrix,eye=camera(hi*1.01);a=render(nearbank,matrix,width=width,height=height);b=render(farbank,matrix,width=width,height=height);diff=np.abs(a.astype(np.int16)-b.astype(np.int16));prefix=f'{si}-{ai}-{views}'
                for name,im in [('before',a),('after',b),('difference',np.clip(diff*6,0,255).astype(np.uint8))]:Image.fromarray(im).save(directory/f'{prefix}-{name}.png')
                results.append(dict(group=gi,label=str(g['key']),angle=ai,views=views,prefix=prefix,threshold_world_distance=hi,eye=(eye/32).tolist(),matrix_columns=matrix.tolist(),changed_pixels=int(np.count_nonzero(diff.max(2))),mean_rgb_error=float(diff.mean()),near_at_99_percent=True,far_at_101_percent=True))
        print('switch',g['key'],flush=True)
    (OUT/'transitions.json').write_text(json.dumps(results,indent=2)+'\n')

def report():
    import html
    m=json.loads((OUT/'measurements.json').read_text());proof=json.loads((OUT/'packing-report.json').read_text());photos=json.loads((OUT/'photos.json').read_text());assets=json.loads((OUT/'assets.json').read_text());switches=json.loads((OUT/'transitions.json').read_text());timing=json.loads((OUT/'timing.json').read_text()) if (OUT/'timing.json').exists() else {}
    table=''.join(f'<tr><td>{name}</td><td>{r["samples"]}</td><td>{r["before_mean"]:,.0f}</td><td>{r["control_near_mean"]:,.0f}</td><td>{r["after_mean"]:,.0f}</td><td>{100*(1-r["after_mean"]/r["before_mean"]):.1f}%</td><td>{r["after_worst"]:,}</td><td>{r["below_1500"]}/{r["samples"]}</td></tr>' for name,r in m.items())
    native=''.join(f'<tr><td>{name}</td><td>{r["baseline_fps"]:.3f}</td><td>{r["candidate_fps"]:.3f}</td><td>{r["gain_percent"]:+.1f}%</td><td>{r["baseline_p95_ms"]:.2f} → {r["candidate_p95_ms"]:.2f} ms</td></tr>' for name,r in timing.items())
    allphotos=[]
    for r in photos:allphotos.append(dict(label=f'{r["photo"]:02} {r["label"]}',prefix=f'photos/images/{r["photo"]:02}',description=f'{r["changed_pixels"]} changed RGB pixels / 153,600; mean error {r["mean_rgb_error"]:.4f} / 255. Far groups: {r["far_groups"]}.',meta=r,kind='route'))
    if (OUT/'native-photos.json').exists():
        n=json.loads((OUT/'native-photos.json').read_text())
        allphotos.append(dict(label='Native Ares / photo 14 EAST BEND',prefix='native/images/14',description=f'Native RDP render: {n["changed_pixels"]} changed pixels; debug overlay has zero changed pixels. Difference ×6 includes native filtering, fog and rounding.',meta={**n,'saved_host_pose':photos[14]['pose']},kind='native'))
    for r in assets:allphotos.append(dict(label=f'Asset {r["label"]} / angle {r["angle"]} / {r["pixels"]}px',prefix='assets/'+r['prefix'],description=f'Authored orthographic inspection. Silhouette IoU {r["silhouette_iou"]:.4f}; {r["silhouette_changed_pixels"]} silhouette pixels changed. 256px views deliberately magnify sacrifices; runtime uses a conservative screen-size/error limit.',meta=r,kind='asset'))
    for r in switches:allphotos.append(dict(label=f'Switch {r["label"]} / angle {r["angle"]} / {r["views"]} views',prefix='transitions/'+r['prefix'],description=f'Identical camera, original versus far proxy, 1% beyond switch. Shared C selector stays near at 99% and switches far at 101% of {r["threshold_world_distance"]:.2f} world units. {r["changed_pixels"]} changed RGB pixels at native viewport resolution.',meta=r,kind='switch'))
    page='''<!doctype html><html><meta charset="utf-8"><title>Sidewinder — screen-size world LOD</title><style>
    body{font:16px system-ui;color:#e8eef5;background:#121822;max-width:1320px;margin:32px auto;padding:0 22px;line-height:1.55}h1,h2{line-height:1.2}a{color:#9ddcff}p{max-width:1050px}table{border-collapse:collapse;font-variant-numeric:tabular-nums}th,td{padding:9px 12px;border-bottom:1px solid #394655;text-align:right}th:first-child,td:first-child{text-align:left}.cards{display:grid;grid-template-columns:1fr 1fr;gap:16px}.cards img{width:100%;image-rendering:pixelated;object-fit:contain;background:#101720}select,button{color:white;background:#293747;padding:10px;border:1px solid #5c7089;margin:5px}select{max-width:90%}pre{white-space:pre-wrap;max-height:300px;overflow:auto;font-size:12px}.viewer{border:1px solid #3b4b60;padding:18px;margin:24px 0}#filter{max-width:960px;width:100%;image-rendering:pixelated}.note{color:#b6c8db}.photos{aspect-ratio:4/3;object-fit:fill!important}summary{cursor:pointer}input{vertical-align:middle}code{color:#d5e8fc}</style>
    <h1>Make distance do the sacrificing</h1><p>Private Sidewinder prototype: retain the appraised fixed-lean bank nearby; independently select distant geometry per camera using projected size or a conservative projected surface-error bound. Both banks retain the previous cluster-aware terrain reductions and conservative visibility. This is a first implementation of shared world LOD, ready for appraisal; the accepted map bank has not been replaced.</p>
    <h2>What changes with distance</h2><ul><li><b>Trees:</b> nearby large/small pines retain 228/124 triangles. Distant trees use two crossed, alpha-tested cards: four triangles and eight vertex entries, with two orthogonal 16×32 views baked from each accepted tree size. The two 32×32 atlases add 4 KiB. A sparse branch-card trial looked bare and was rejected.</li><li><b>Structures:</b> nine regions get separate Blender-authored proxies. Boundaries and material seams stay pinned; the projected symmetric surface-distance bound must fit a 3-pixel budget. Any camera within 8 world units of a region's box uses the original rooms, doors, ramps and roofs. This first proxy still collapses the whole region: it does <b>not yet provide purpose-built exterior shells or separate portal/interior LOD</b>.</li><li><b>Terrain:</b> 16-unit spatial patches of snow and cliff can use a cheaper interior triangulation. Shared patch boundary vertices stay fixed. Close patches stay original within 8 world units; distant error must fit 1.5 pixels. Heavily pinned patches with little reduction receive no alternate mesh.</li><li><b>Camera selection:</b> actual projection and native viewport dimensions account for scope magnification and split-screen. Trees switch only below a conservative 48-pixel projected-diameter bound. Inside/near-plane/invalid cases retain nearby detail. This appraisal uses deterministic, stateless switches; hysteresis and movement-pop assessment remain production work.</li></ul>
    <h2>Same cameras, actual submitted vertex loads</h2><p>68 replay cameras and 24 photo-route views use SDK matrices, frustum/PVS checks and the same C selector as the N64. ASan/UBSan passes. All replay eyes, view/zoom/alive states and photo-route player bytes match. Paired padding and vertices repeated across batches count as loads. Dynamic bodies, weapons and vehicles are additional.</p>
    <table><tr><th>Workload</th><th>Views</th><th>Fixed lean</th><th>Repacked / near only</th><th>World LOD</th><th>Net reduction</th><th>Worst</th><th>&lt;1,500</th></tr>'''+table+'''</table><p>The near-only control separates repacking/culling changes from LOD savings. Every control photo has exactly zero changed pixels against the accepted fixed-lean input. New far chunks fail open for PVS; near chunks inherit a union of source memberships. All 24 selected-LOD renders also have zero changed pixels against their own PVS-disabled control.</p>
    <h2>Native Ares performance</h2><p>Fresh baseline/candidate runs: NTSC, 8 MiB Expansion Pak, release LTO, three surfaces, 32 KiB RSP queues, 1-second warmup and 75-second fresh-pose sample. Single player uses the existing walking-photo benchmark; four players use the existing replay. Builds and asset hashes are saved. These are emulator measurements, not physical-console measurements.</p><table><tr><th>Workload</th><th>Fixed lean FPS</th><th>LOD FPS</th><th>Change</th><th>P95 frame time</th></tr>'''+native+'''</table>
    <h2>Photo, asset and switch inspection</h2><p>Route images are offline packed-map renders at the exact saved cameras. They implement float clipping, depth and nearest textures/alpha; they do not emulate RDP rounding, bilinear filtering, fog, HUD or dynamics. The RGB difference filter is amplified 6×. Switch views use the native-size viewport; source and far proxy always share the same camera. Native captures below provide a separate renderer check.</p>
    <div class="viewer"><div><select id="kind"><option value="route">24 matched route photos</option><option value="native">Native Ares photo pair</option><option value="asset">Multi-angle assets at 64 / 256 pixels</option><option value="switch">48 views just beyond LOD switches</option></select><button id="previous">Previous</button><button id="next">Next</button></div><select id="choice"></select><p id="description"></p><div class="cards"><div><b>Fixed lean / nearby representation</b><img id="before"></div><div><b>World LOD / distant representation</b><img id="after"></div></div><p>Filter <select id="mode"><option value="difference">RGB difference ×6</option><option value="blend">Before/after blend</option><option value="silhouette">Silhouette change (assets)</option><option value="near-control">Repacked near-only control (route)</option><option value="pvs-control">PVS-disabled LOD control (route)</option></select> <input id="mix" type="range" min="0" max="100" value="50"></p><canvas id="filter"></canvas><details><summary>Exact pose, camera and selection metadata</summary><pre id="metadata"></pre></details></div>
    <h2>Native renderer checks</h2><div class="cards"><div><b>Fixed lean — photo 14</b><img class="photos" src="native-photo14-baseline.png"></div><div><b>World LOD — photo 14</b><img class="photos" src="native-photo14-candidate.png"></div></div><p class="note">Native photo 14 includes the same debug pose overlay in both builds. Native four-camera census and RDP validation captures/logs are linked in the evidence below. The 24 offline pairs supply the full repeatable route; native photo 14 supplies a targeted hardware-renderer check at the route's largest offline difference.</p>
    <h2>What this establishes—and what remains</h2><p>The same accepted geometry can remain convincing nearby while a different distant representation avoids work. It does not solve Sidewinder's 1,500-load goal: most close structures, the long central tunnel region, unchanged scenery and expensive visible terrain remain. Whole-region geometric error limits deliberately retain detail when removing interior geometry would produce a large surface error, even if it might be invisible from a particular exterior camera. Larger gains need authored exterior shells, portal-aware interior retention, and better terrain LOD partitions, with the same image/transition checks. The current bases are geometric proxies, not that final shell system.</p>
    <p>Memory cost: '''+f'{proof["extra_bank_bytes"]:,} additional bank bytes ({proof["extra_bank_bytes"]/1024:.1f} KiB), including the atlases; the LOD tables and recorded draw lists are additional. The fresh native four-player pair uses 229,408 additional bytes of RAM at startup (224 KiB), leaving 2,905,144 bytes free at that point. This is an initial heap comparison, not a peak memory guarantee. The renderer permits 1,024 chunks only for this opt-in experiment; this bank uses {proof["chunk_count"]}.'+''' Collision, movement, spawns, source textures and gameplay sections remain exact. Original textures are retained byte for byte; the two new tree materials are appended.</p>
    <p><a href="measurements.json">Matched counts</a> · <a href="replay/cameras.csv">Every replay camera</a> · <a href="photos/cameras.csv">Every photo camera</a> · <a href="photos.json">Exact photo poses and pixel checks</a> · <a href="transitions.json">Switch cameras</a> · <a href="packing-report.json">Packing and memory</a> · <a href="timing.json">Native timing</a> · <a href="native-census.png">Native four-camera census</a> · <a href="native-photo-census.png">Native single-camera census</a> · <a href="native-census-checks.json">Counter cross-checks</a> · <a href="native-photos.json">Native pixel checks</a> · <a href="rdp-validation.png">RDP validation</a> · <a href="validation.json">Validation and hashes</a> · <a href="world-lod-appraisal.blend">Blender appraisal</a></p>
    <script>const records='''+json.dumps(allphotos)+''';let list=[],index=0;const $=id=>document.getElementById(id);function loadKind(){list=records.filter(r=>r.kind===$('kind').value);$('choice').innerHTML=list.map((r,i)=>`<option value="${i}">${r.label}</option>`).join('');index=0;update()}function update(){let r=list[index];$('choice').value=index;$('description').textContent=r.description;$('metadata').textContent=JSON.stringify(r.meta,null,2);$('before').src=r.prefix+'-before.png';$('after').src=r.prefix+'-after.png';['before','after'].forEach(id=>$(id).className=(r.kind==='route'||r.kind==='native')?'photos':'');draw()}function draw(){let r=list[index],canvas=$('filter'),ctx=canvas.getContext('2d'),im=new Image();canvas.className=(r.kind==='route'||r.kind==='native')?'photos':'';if($('mode').value==='blend'){let a=new Image(),b=new Image();a.onload=()=>{b.onload=()=>{canvas.width=a.width;canvas.height=a.height;ctx.globalAlpha=1;ctx.drawImage(a,0,0);ctx.globalAlpha=$('mix').value/100;ctx.drawImage(b,0,0);ctx.globalAlpha=1};b.src=r.prefix+'-after.png'};a.src=r.prefix+'-before.png';return}let mode=$('mode').value;if(mode==='silhouette'&&r.kind!=='asset')mode='difference';if((mode==='near-control'||mode==='pvs-control')&&r.kind!=='route')mode='difference';im.onload=()=>{canvas.width=im.width;canvas.height=im.height;ctx.drawImage(im,0,0)};im.src=r.prefix+'-'+mode+'.png'}$('kind').onchange=loadKind;$('choice').onchange=()=>{index=+$('choice').value;update()};$('previous').onclick=()=>{index=(index+list.length-1)%list.length;update()};$('next').onclick=()=>{index=(index+1)%list.length;update()};$('mode').onchange=draw;$('mix').oninput=draw;loadKind();</script></html>'''
    (OUT/'comparison.html').write_text(page)

def timings():
    summaries={};records=[]
    for workload in ('one','four'):
        pair=[]
        for label in ('baseline','candidate'):
            path=OUT/f'{workload}-{label}.log';text=path.read_text();groups={}
            for line in text.splitlines():
                if 'BENCH vi_fresh group=' not in line:continue
                group=re.search(r'group=(\w+)',line)[1];values={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',line)}
                if group in groups:assert groups[group]==values
                groups[group]=values
            assert set(groups)=={'ALL','EARLY','LATE'}
            all=groups['ALL'];record=dict(workload=workload,label=label,groups=groups,fps=all['frames']*1e6/all['elapsed_us'],source_log=path.name,initial_free_bytes=int(re.search(r'RAM=8388608 free=(\d+)',text)[1]));records.append(record);pair.append(record)
        a,b=pair;summaries[workload]=dict(baseline_fps=a['fps'],candidate_fps=b['fps'],gain_percent=100*(b['fps']/a['fps']-1),baseline_p95_ms=a['groups']['ALL']['p95_us']/1000,candidate_p95_ms=b['groups']['ALL']['p95_us']/1000,baseline_max_ms=a['groups']['ALL']['max_us']/1000,candidate_max_ms=b['groups']['ALL']['max_us']/1000,initial_additional_ram_bytes=a['initial_free_bytes']-b['initial_free_bytes'],scope='One fresh matched baseline/candidate pair per workload; baseline ALL counters reproduce previous appraised fixed-lean run. NTSC Ares, 8 MiB, release LTO, three surfaces, 32 KiB queues, 1 s warmup, 75 s sample. No physical-console claim.')
    (OUT/'timing-records.json').write_text(json.dumps(records,indent=2)+'\n');(OUT/'timing.json').write_text(json.dumps(summaries,indent=2)+'\n');print(json.dumps(summaries,indent=2))

def native_difference():
    a=np.asarray(Image.open(OUT/'native-photo14-baseline.png').convert('RGB'));b=np.asarray(Image.open(OUT/'native-photo14-candidate.png').convert('RGB'));assert a.shape==b.shape==(240,640,3);diff=np.abs(a.astype(np.int16)-b.astype(np.int16));Image.fromarray(np.clip(diff*6,0,255).astype(np.uint8)).save(OUT/'native-photo14-difference.png')
    # The exact frozen pose is retained in the host fixture JSON; native's
    # on-screen debug overlay independently confirms rounded pose parameters.
    result=dict(photo=14,shape=list(a.shape),changed_pixels=int(np.count_nonzero(diff.max(2))),mean_rgb_error=float(diff.mean()),debug_overlay_changed_pixels=int(np.count_nonzero(diff[194:].max(2))),scope='Native screenshots from the same frozen production photo fixture with unchanged HUD/debug overlay; bilinear filtering, fog and RDP rounding active. This is separate from the offline full-route pixel study.')
    import shutil
    directory=OUT/'native/images';directory.mkdir(parents=True,exist_ok=True)
    for source,dest in [('baseline','before'),('candidate','after'),('difference','difference')]:shutil.copy2(OUT/('native-photo14-'+source+'.png'),directory/('14-'+dest+'.png'))
    (OUT/'native-photos.json').write_text(json.dumps(result,indent=2)+'\n');print(result)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',nargs='?',default='report',choices=('photos','assets','transitions','timings','native-difference','report','all'))
    args=parser.parse_args()
    if args.action=='all':photos();assets();transitions();timings();native_difference();report()
    else:{'photos':photos,'assets':assets,'transitions':transitions,'timings':timings,'native-difference':native_difference,'report':report}[args.action]()
