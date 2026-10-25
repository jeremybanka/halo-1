"""Matched multi-angle architecture images, using the saved weapon audit renderer.

These are offline packed-map diagnostics, not native screenshots or timing.
Every before/after pair shares exact orthographic camera, scale and framing.
"""
import base64
import collections
import importlib.util
import inspect
import json
from pathlib import Path
import struct
import sys
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from sidewinder_structures import ROOT,PREVIOUS,OUT,sha
from remap_sidewinder_visibility import sections

AUDIT=ROOT/'build/n64-wizard-audit/accepted-baseline-source/port/n64/audit_models.py'
spec=importlib.util.spec_from_file_location('structure_weapon_renderer',AUDIT);audit=importlib.util.module_from_spec(spec);sys.modules[spec.name]=audit;spec.loader.exec_module(audit)
# Reuse the weapon renderer's camera/rasterizer, with the map's already baked
# vertex lighting replacing the weapon source's neutral directional light.
render_source=inspect.getsource(audit.render).replace('colors*=base+(1-base)*max(0,n@lightdir)','colors*=weights@mesh.rgb[ti]/255')
assert render_source!=inspect.getsource(audit.render)
exec(render_source,audit.__dict__);audit.BG=np.array((18,24,34),dtype=np.uint8)
ANGLES=[('front',(0,.02,-1)),('back',(0,.02,1)),('left',(-1,.02,0)),('right',(1,.02,0)),('front quarter',(1,.35,-1)),('back quarter',(-1,.35,1)),('top',(.001,1,.001)),('low quarter',(-1,.1,-1))]
TEXTURES=[str(ROOT/f'build/n64-visibility-rollout/sidewinder/data/sidewinder-textures/packed-{i}.png') for i in range(17)]


def packed_architecture():
    source=json.loads((OUT/'source.json').read_text());proof=json.loads((OUT/'packing-report.json').read_text())
    old_faces={(r['batch'],r['face']):r for r in source['triangles']}
    result=[];ss=sections((OUT/'candidate-maps/sidewinder.map64').read_bytes())
    for b,c in enumerate(struct.iter_unpack('>IHH6hHH',ss[1])):
        first,count,material,*rest=c;at,n=rest[-2:];entry=proof['batches'][b]
        ids=struct.unpack_from('>'+str(n)+'H',ss[2],at*2);vs=[]
        for i in range(count):
            o=(first+i)//2*32;h=(first+i)%2
            vs.append([*struct.unpack_from('>3h',ss[0],o+h*8),*ss[0][o+16+h*4:o+19+h*4],*struct.unpack_from('>2h',ss[0],o+24+h*4)])
        for t in range(0,n,3):
            category=old_faces[entry['old_batch'],t//3]['category'] if entry['unchanged'] else 'structures'
            if category=='structures':result.append({'material':material,'triangle':[vs[i] for i in ids[t:t+3]]})
    before=[r for r in source['triangles'] if r['category']=='structures']
    return before,result


def mesh(rows,clay=False):
    p=np.array([[v[:3] for v in r['triangle']] for r in rows],dtype=float)/256
    rgb=np.full(p.shape,190.) if clay else np.array([[v[3:6] for v in r['triangle']] for r in rows],dtype=float)
    uv=np.array([[v[6:8] for v in r['triangle']] for r in rows],dtype=float)/1024
    return audit.Mesh(p,rgb,uv,np.array([r['material'] for r in rows]),TEXTURES,source=not clay)


def region(r):
    x,y,z=np.mean([v[:3] for v in r['triangle']],axis=0)/256
    if z>15 and x<-24:return 'West base'
    if z>15 and x>23:return 'East base'
    if z>10:return 'Central tunnels'
    if abs(x)<15:return 'Central bridge'
    if z<-35:return 'West far outpost' if x<0 else 'East far outpost'
    if x<-44:return 'West near outpost'
    if x>44:return 'East near outpost'
    return 'West recessed structure'


def main():
    directory=OUT/'images';directory.mkdir(exist_ok=True)
    before,after=packed_architecture();pairs=collections.defaultdict(lambda:[[],[]])
    for i,rows in enumerate((before,after)):
        for r in rows:pairs[region(r)][i].append(r)
    records=[];contact=[]
    for ri,(name,(old,new)) in enumerate(pairs.items()):
        if not old or not new:continue
        a,b=mesh(old),mesh(new)
        for ai,(angle,direction) in enumerate(ANGLES):
            bounds=audit.matching_bounds([a,b],direction)
            images=[];masks=[]
            for m in (a,b):
                im,mask=audit.render(m,bounds,direction,width=640,height=420,cull='none');images.append(im);masks.append(mask)
            arr=[np.asarray(im,dtype=np.int16) for im in images];difference=np.abs(arr[0]-arr[1]);overlap=masks[0]&masks[1];union=masks[0]|masks[1]
            overlay=np.full((420,640,3),(18,24,34),dtype=np.uint8);overlay[overlap]=[175,190,203];overlay[masks[0]&~masks[1]]=[40,211,246];overlay[masks[1]&~masks[0]]=[255,136,58]
            diff=Image.fromarray(np.clip(difference*6,0,255).astype(np.uint8));overlay=Image.fromarray(overlay)
            prefix=f'{ri:02}-{ai:02}';paths={}
            for key,im in [('before',images[0]),('after',images[1]),('difference',diff),('silhouette',overlay)]:
                path=directory/f'{prefix}-{key}.png';im.save(path);paths[key]=str(path.relative_to(OUT))
            record={'structure':name,'angle':angle,'direction':direction,'center':bounds[0].tolist(),'span':bounds[1].tolist(),'before_triangles':len(old),'after_triangles':len(new),'silhouette_iou':float(overlap.sum()/max(1,union.sum())),'silhouette_changed_pixels':int(np.count_nonzero(masks[0]^masks[1])),'changed_rgb_pixels':int(np.count_nonzero(difference.max(axis=2))),'mean_absolute_rgb_error':float(difference[union].mean()) if union.any() else 0,'paths':paths}
            records.append(record)
            if ai==4:
                row=Image.new('RGB',(1280,455),(18,24,34));row.paste(images[0],(0,35));row.paste(images[1],(640,35));draw=ImageDraw.Draw(row);draw.text((10,10),name+' — before',fill='white');draw.text((650,10),name+' — reduced',fill='white');contact.append(row)
        print(name, len(old),'->',len(new),flush=True)
    sheet=Image.new('RGB',(1280,455*len(contact)),(18,24,34))
    for i,im in enumerate(contact):sheet.paste(im,(0,455*i))
    sheet.save(OUT/'contact-sheet.png')
    metadata={'scope':__doc__,'renderer_path':str(AUDIT),'renderer_sha256':sha(AUDIT.read_bytes()),'before_bank_sha256':sha((PREVIOUS/'candidate-maps/sidewinder.map64').read_bytes()),'after_bank_sha256':sha((OUT/'candidate-maps/sidewinder.map64').read_bytes()),'views':records}
    (OUT/'visual-metrics.json').write_text(json.dumps(metadata,indent=2)+'\n')
    report(records)


def report(records):
    measurements=json.loads((OUT/'measurements.json').read_text());candidate=json.loads((OUT/'candidate.json').read_text());packing=json.loads((OUT/'packing-report.json').read_text())
    rows=''.join(f'<tr><td>{kind}</td><td>{r["before_mean"]:,.1f}</td><td>{r["after_mean"]:,.1f}</td><td>{r["after_mean"]-r["before_mean"]:+.1f}</td></tr>' for kind,r in measurements.items())
    data=[]
    for r in records:
        paths={k:'data:image/png;base64,'+base64.b64encode((OUT/p).read_bytes()).decode() for k,p in r['paths'].items()};data.append({**r,'paths':paths})
    accepted=[r for r in candidate['report'] if r['accepted']]
    worst=min(r['silhouette_iou'] for r in records)
    html='''<!doctype html><meta charset="utf-8"><title>Sidewinder structures: careful simplification</title><style>body{background:#121822;color:#e7edf5;font:16px system-ui;max-width:1300px;margin:30px auto;padding:0 20px}p{max-width:1000px;line-height:1.6}a{color:#9ddcff}select,input{margin:12px;padding:8px;background:#293644;color:white;border:1px solid #52657b}table{border-collapse:collapse;margin:20px 0}td,th{padding:10px 18px;border-bottom:1px solid #3d4a5b;text-align:right}td:first-child,th:first-child{text-align:left}.pair{display:grid;grid-template-columns:1fr 1fr;gap:12px}.pair img,#filter{width:100%;image-rendering:pixelated}#filter{max-width:900px}small{color:#b6c7d8}.viewer{border:1px solid #394b60;padding:15px;margin:25px 0}h1,h2{color:white}</style><h1>Sidewinder structures: first careful reduction</h1>'''
    html+=f'<p>The prototype removes 102 of 5,617 architecture triangles (1.8%) across {len(accepted)} connected surface components. Openings and membership/material seams receive a sampled symmetric boundary check; original collision, terrain, scenery, textures and placements are retained. {packing["unchanged_batches"]} of the previous 478 render batches remain byte-identical apart from offsets. The edited 50 source batches are repacked locally.</p>'
    html+='<p><b>This is a small geometry cleanup, with almost no load benefit.</b> More aggressive edge-collapse trials were rejected for surface/UV/lighting changes. The strict planar trial removed 51 triangles; the final limited-angle surface trial removes 102. Most larger components failed the appearance checks and retain their original triangles. The candidate is private and unadopted.</p><table><tr><th>Matched workload</th><th>Before loads/view</th><th>After loads/view</th><th>Change</th></tr>'+rows+'</table>'
    html+=f'<p>All 68 replay poses and all 24 complete photo-route player states match. Counts use the original SDK camera, frustum and PVS classifier under ASan/UBSan. These are host submission counts, <b>not new FPS measurements</b>. The images below are offline packed-map renders, <b>not Ares screenshots</b>. Every pair shares camera, scale and framing; no independent fitting. {len(records)} matched views cover nine structure regions from eight directions. Worst sampled silhouette IoU: {worst:.6f}.</p>'
    html+='<div class="viewer"><label>Structure <select id="structure"></select></label><label>Angle <select id="angle"></select></label><div class="pair"><div>Before<img id="before"></div><div>Reduced<img id="after"></div></div><p id="metrics"></p><label>Filter <select id="mode"><option value="silhouette">Silhouette: gray overlap, cyan source only, orange reduced only</option><option value="difference">RGB difference ×6</option></select></label><br><img id="filter"></div>'
    html+='<h2>What is protected, and what the checks mean</h2><p>Reduction runs separately within source material and conservative membership partitions, then within connected surfaces. The final Blender operation is limited dissolve at 0.08 radians followed by triangulation and source-grid quantization. Components are rejected if sampled surface deviation exceeds 0.05 world units, boundary deviation exceeds 0.004, UV deviation exceeds half a texture texel, or a sampled color channel changes more than 48/255. Accepted components’ actual maxima are recorded in candidate.json. These samples and 72 silhouette views are evidence for appraisal, not a proof for every possible viewpoint.</p>'
    html+='<p>The tiny count change does not justify a fresh FPS benchmark: the replay saves about eleven loads per view, while the photo route slightly increases. This pass establishes the comparison workflow and identifies safe cleanup; it does not solve the 1,500-load budget. Substantial architecture savings would require a designed proxy of the dense base/tunnel interiors, with decisions about which trim, recesses and lighting detail to replace.</p><p><a href="contact-sheet.png">Before/after contact sheet</a> · <a href="visual-metrics.json">All cameras and visual metrics</a> · <a href="measurements.json">Load measurements</a> · <a href="replay/cameras.csv">Replay camera CSV</a> · <a href="photos/cameras.csv">Photo-route camera CSV</a> · <a href="packing-report.json">Packing and preservation proof</a> · <a href="structure-appraisal.blend">Blender scene</a></p>'
    if (OUT/'player-photos.json').exists():
        photos=json.loads((OUT/'player-photos.json').read_text())['photos']
        controls=sum(p['pvs_control_changed_pixels'] for p in photos)
        identical=sum(p['rgb_changed_pixels']==0 for p in photos);changes=[p['rgb_changed_pixels'] for p in photos if p['rgb_changed_pixels']]
        html+=f'<h2>Matched player-camera views</h2><p>The original 24 photo fixtures, using their exact SDK float projection matrices and complete player states. Offline perspective clipping, nearest packed textures, baked vertex lighting, material alpha/depth modes and perspective-correct interpolation; no fog, HUD or dynamics. {identical} views have identical RGB output; the other views change {changes} pixels respectively. Candidate PVS versus candidate visibility-off controls differ at {controls} pixels across all 24 views. These float software checks supplement the exterior appraisal; they do not replace native RSP/RDP validation.</p>'
        html+=gallery('photo',photos,'player-photos','photo',lambda p:f'{p["photo"]:02} {p["label"]}')
    if (OUT/'interiors.json').exists():
        interior=json.loads((OUT/'interiors.json').read_text())['views']
        html+='<h2>Interior and roof inspection</h2><p>Sixteen additional views: four horizontal directions from source-authored lower-room and roof spawn positions in both bases, with a standing 0.62-unit eye height. Identical before/after cameras; visibility disabled. These authored diagnostic views are separate from the replay performance means. Position, yaw, pitch, eye height, projection and matrix are saved in <a href="interiors.json">interiors.json</a>.</p>'
        html+=gallery('interior',interior,'interiors','index',lambda p:f'{p["index"]:02} {p["label"]}, yaw {p["yaw"]:.3f}')
    html+='<script>const views='+json.dumps(data)+';const structure=document.querySelector("#structure"),angle=document.querySelector("#angle"),mode=document.querySelector("#mode");for(const n of [...new Set(views.map(v=>v.structure))])structure.add(new Option(n,n));for(const n of [...new Set(views.map(v=>v.angle))])angle.add(new Option(n,n));function update(){const v=views.find(v=>v.structure===structure.value&&v.angle===angle.value);for(const k of ["before","after"])document.getElementById(k).src=v.paths[k];document.querySelector("#filter").src=v.paths[mode.value];document.querySelector("#metrics").textContent=`${v.before_triangles} → ${v.after_triangles} triangles in this region; silhouette IoU ${v.silhouette_iou.toFixed(6)}; ${v.silhouette_changed_pixels} silhouette pixels changed; ${v.changed_rgb_pixels} RGB pixels changed. Camera [${v.direction}]`;};structure.onchange=angle.onchange=mode.onchange=update;update();</script>'
    (OUT/'comparison.html').write_text(html)


def gallery(name,records,directory,index,label):
    items=[]
    for r in records:
        paths={k:'data:image/png;base64,'+base64.b64encode((OUT/directory/f'{r[index]:02}-{k}.png').read_bytes()).decode() for k in ['before','after','difference']}
        items.append(dict(label=label(r),paths=paths,changed=r['rgb_changed_pixels']))
    return f'<div class="viewer"><select id="{name}Select"></select><div class="pair"><div>Before<img id="{name}Before"></div><div>Reduced<img id="{name}After"></div></div><p id="{name}Metrics"></p><p>RGB difference ×6</p><img id="{name}Difference" style="width:100%"></div><script>(()=>{{const data='+json.dumps(items)+f';const select=document.getElementById("{name}Select");data.forEach((r,i)=>select.add(new Option(r.label,i)));function update(){{const r=data[select.value];for(const k of ["Before","After","Difference"])document.getElementById("{name}"+k).src=r.paths[k.toLowerCase()];document.getElementById("{name}Metrics").textContent=r.changed+" RGB pixels changed";}}select.onchange=update;update();}})();</script>'

if __name__=='__main__':main()
