"""Aggressive whole-structure proxies with multi-angle outline protection.

Rejected visual experiment, retained for evidence. Whole-structure collapse
distorted the architectural forms and texture mapping. Original assets remain
intact; the load savings do not establish an acceptable simplification.
"""
import collections
import json
import math
from pathlib import Path
import re
import struct
import sys
import numpy as np
from sidewinder_structures import ROOT,PREVIOUS,sha

OUT=ROOT/'build/n64-sidewinder-structures-aggressive'


def prepare():
    import sidewinder_structures as base
    import report_sidewinder_structures as view
    base.OUT=OUT;base.prepare()
    source=json.loads((OUT/'source.json').read_text());groups=collections.defaultdict(list)
    for r in source['triangles']:
        if r['editable']:groups[view.region(r)].append(r)
    regions=[]
    for name,rows in groups.items():
        points=sorted({tuple(v[:3]) for r in rows for v in r['triangle']});p=np.array(points,dtype=float)/256
        edges=collections.Counter()
        for r in rows:
            xyz=[tuple(v[:3]) for v in r['triangle']]
            for a,b in ((0,1),(1,2),(2,0)):edges[tuple(sorted((xyz[a],xyz[b])))]+=1
        pins={v for e,n in edges.items() if n!=2 for v in e};boundary_count=len(pins)
        horizontal_faces=[];floor_edges=collections.Counter();ramp_pins=set()
        for r in rows:
            xyz=np.array([v[:3] for v in r['triangle']],dtype=float);normal=np.cross(xyz[1]-xyz[0],xyz[2]-xyz[0]);length_squared=normal@normal
            # Preserve every potentially walkable floor/ramp and roof/ceiling
            # face. Source winding varies, so use the squared vertical normal.
            if length_squared and normal[1]**2>=.38*length_squared:
                horizontal_faces.append([r['batch'],r['face']])
                if normal[1]**2>=.9999*length_squared:
                    vertices=[tuple(v[:3]) for v in r['triangle']]
                    for a,b in ((0,1),(1,2),(2,0)):floor_edges[tuple(sorted((vertices[a],vertices[b])))]+=1
                elif math.sqrt(length_squared)/2/256**2>=.5:ramp_pins.update(tuple(v[:3]) for v in r['triangle'])
        # Protect the large floor/roof profile corners and substantial ramps,
        # not their coplanar tessellation or every tiny bevel along the rim.
        neighbors=collections.defaultdict(set)
        for (a,b),n in floor_edges.items():
            if n==1:neighbors[a].add(b);neighbors[b].add(a)
        for point,adjacent in neighbors.items():
            if len(adjacent)!=2:continue
            a,b=[np.array(v,dtype=float)/256 for v in adjacent];q=np.array(point,dtype=float)/256;ab=b-a
            t=np.clip((q-a)@ab/max(ab@ab,1e-20),0,1);deviation=np.linalg.norm(q-a-t*ab)
            if deviation>.08 and min(np.linalg.norm(q-a),np.linalg.norm(q-b))>.2:pins.add(point)
        pins.update(ramp_pins)
        # Hold the coarse outer envelope, rather than every tiny edge in every
        # silhouette (which would freeze almost all of the original detail).
        # The full eight-angle images are compared after reduction.
        for elevation in (-1.5,-1.0,-.5,0,.5,1.,1.5):
            for azimuth in np.linspace(0,math.tau,24,endpoint=False):
                direction=np.array([math.cos(elevation)*math.cos(azimuth),math.sin(elevation),math.cos(elevation)*math.sin(azimuth)])
                pins.add(points[int(np.argmax(p@direction))])
        regions.append({'name':name,'rows':rows,'pins':sorted(pins),'boundary_vertices':boundary_count,'source_vertices':len(points),'protected_horizontal_faces':horizontal_faces})
        print(name,len(rows),'triangles;',len(pins),'/',len(points),'profile/boundary vertices protected',flush=True)
    (OUT/'regions.json').write_text(json.dumps({'source_sha256':sha((OUT/'source.json').read_bytes()),'regions':regions},separators=(',',':'))+'\n')


def prototype(ratio=.25):
    import bpy,bmesh
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    source=json.loads((OUT/'source.json').read_text());data=json.loads((OUT/'regions.json').read_text());assert data['source_sha256']==sha((OUT/'source.json').read_bytes())
    scene=bpy.data.scenes.new('Sidewinder - aggressive architecture appraisal');bpy.context.window.scene=scene;scene.view_settings.view_transform='Standard'
    original_collection=bpy.data.collections.new('Original whole structures');reduced_collection=bpy.data.collections.new('Aggressive whole structures');scene.collection.children.link(original_collection);scene.collection.children.link(reduced_collection)
    materials=[];texture_dir=ROOT/'build/n64-visibility-rollout/sidewinder/data/sidewinder-textures'
    for mi in range(17):
        material=bpy.data.materials.new('Aggressive source '+str(mi));material.use_nodes=True;nodes=material.node_tree.nodes;nodes.clear()
        output=nodes.new('ShaderNodeOutputMaterial');emission=nodes.new('ShaderNodeEmission');texture=nodes.new('ShaderNodeTexImage');texture.image=bpy.data.images.load(str(texture_dir/f'packed-{mi}.png'),check_existing=True);texture.interpolation='Closest'
        color=nodes.new('ShaderNodeVertexColor');color.layer_name='Source lightmap';mix=nodes.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=1
        links=material.node_tree.links;links.new(texture.outputs['Color'],mix.inputs[1]);links.new(color.outputs['Color'],mix.inputs[2]);links.new(mix.outputs[0],emission.inputs['Color']);links.new(emission.outputs[0],output.inputs['Surface']);materials.append(material)
    triangles=[];reports=[]
    for region in data['regions']:
        rows=region['rows'];positions=[];lookup={};faces=[]
        for r in rows:
            face=[]
            for v in r['triangle']:
                p=tuple(v[:3])
                if p not in lookup:lookup[p]=len(positions);positions.append((p[0]/256,-p[2]/256,p[1]/256))
                face.append(lookup[p])
            faces.append(face)
        mesh=bpy.data.meshes.new(region['name']+' source');mesh.from_pydata(positions,[],faces)
        for m in materials:mesh.materials.append(m)
        uv=mesh.uv_layers.new(name='Source diffuse');color=mesh.color_attributes.new(name='Source lightmap',type='FLOAT_COLOR',domain='CORNER')
        for poly,r in zip(mesh.polygons,rows):
            poly.material_index=r['material']
            for li,v in zip(poly.loop_indices,r['triangle']):uv.data[li].uv=(v[6]/1024,1-v[7]/1024);color.data[li].color=tuple(c/255 for c in v[3:6])+(1,)
        mesh.update();obj=bpy.data.objects.new(region['name']+' original',mesh);original_collection.objects.link(obj)
        pin_ids={lookup[tuple(p)] for p in region['pins']};free=[i for i in range(len(positions)) if i not in pin_ids]
        group=obj.vertex_groups.new(name='Remove detail; hold profiles and openings')
        if free:group.add(free,1,'REPLACE')
        modifier=obj.modifiers.new('Aggressive architectural proxy','DECIMATE');modifier.decimate_type='COLLAPSE';modifier.ratio=ratio;modifier.vertex_group=group.name;modifier.vertex_group_factor=1000;modifier.use_collapse_triangulate=True
        if not free:modifier.ratio=1.
        bpy.context.view_layer.update();graph=bpy.context.evaluated_depsgraph_get();graph.update();evaluated=obj.evaluated_get(graph);result=evaluated.to_mesh();result.calc_loop_triangles()
        ps=[Vector(tuple(round(x*256)/256 for x in v.co)) for v in result.vertices];fs=[list(t.vertices) for t in result.loop_triangles]
        retained={tuple(round(x*256) for x in (v[0],v[2],-v[1])) for v in ps};missing=len({tuple(p) for p in region['pins']}-retained)
        reference=BVHTree.FromPolygons([Vector(p) for p in positions],faces,all_triangles=True);target=BVHTree.FromPolygons(ps,fs,all_triangles=True)
        def samples(points,faces):
            for f in faces:
                a,b,c=[points[i] for i in f]
                yield a;yield b;yield c;yield (a+b)/2;yield (b+c)/2;yield (c+a)/2;yield (a+b+c)/3
        deviation=max([reference.find_nearest(p)[3] for p in samples(ps,fs)]+[target.find_nearest(p)[3] for p in samples([Vector(p) for p in positions],faces)])
        newuv=result.uv_layers.active;newcolor=result.color_attributes['Source lightmap']
        for t in result.loop_triangles:
            tri=[]
            for vi,li in zip(t.vertices,t.loops):
                x,y,z=ps[vi];u,v=newuv.data[li].uv;rgb=newcolor.data[li].color[:3]
                tri.append([round(x*256),round(z*256),round(-y*256),*[min(255,max(0,round(c*255))) for c in rgb],round(u*1024),round((1-v)*1024)])
            triangles.append({'region':region['name'],'material':t.material_index,'triangle':tri})
        clone=result.copy();clone.name=region['name']+' aggressive mesh';reduced=bpy.data.objects.new(region['name']+' reduced',clone);reduced_collection.objects.link(reduced)
        report={'name':region['name'],'source_triangles':len(rows),'candidate_triangles':len(fs),'source_vertices':len(positions),'candidate_vertices':len(ps),'profile_and_boundary_pins':len(pin_ids),'missing_pins':missing,'requested_ratio':ratio,'symmetric_sampled_surface_deviation':deviation}
        reports.append(report);evaluated.to_mesh_clear();obj.modifiers.remove(modifier)
    original_collection.hide_render=True;original_collection.hide_viewport=True
    output={'source_sha256':sha((OUT/'source.json').read_bytes()),'regions_sha256':sha((OUT/'regions.json').read_bytes()),'bank_sha256':source['bank_sha256'],'method':'Whole-structure weighted collapse; coarse floor/roof corners, substantial ramps, directional support points and real mesh boundaries protected. Eight-angle silhouettes measured afterward. UVs and baked-light interpolation may change. No per-material or PVS-partition seam locks.','report':reports,'triangles':triangles}
    (OUT/'candidate.json').write_text(json.dumps(output,separators=(',',':'))+'\n')
    for obj in scene.objects:obj.select_set(not obj.hide_get())
    for area in bpy.context.screen.areas:
        if area.type=='VIEW_3D':
            region=next(r for r in area.regions if r.type=='WINDOW')
            with bpy.context.temp_override(area=area,region=region):bpy.ops.view3d.view_all(center=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'structure-appraisal.blend'));print(json.dumps(reports))


def pack():
    from remap_sidewinder_visibility import sections,batches
    from pack_maps import bank,packed,uv_safe_triangles
    from pack_terrain import indexed_terrain
    source=json.loads((OUT/'source.json').read_text());candidate=json.loads((OUT/'candidate.json').read_text())
    assert candidate['source_sha256']==sha((OUT/'source.json').read_bytes()) and candidate['regions_sha256']==sha((OUT/'regions.json').read_bytes())
    original=(PREVIOUS/'candidate-maps/sidewinder.map64').read_bytes();assert sha(original)==source['bank_sha256']==candidate['bank_sha256']
    ss=sections(original);visibility=json.loads((PREVIOUS/'data/visibility.json').read_text());all_mask=(1<<visibility['clusters'])-1
    editable={r['batch'] for r in source['triangles'] if r['editable']};original_masks=collections.defaultdict(int)
    for r in source['triangles']:
        if r['editable']:original_masks[r['material'],tuple(sorted(tuple(v[:3]) for v in r['triangle']))]|=r['mask']
    groups=collections.defaultdict(list);exact=changed=0
    for r in candidate['triangles']:
        key=r['material'],tuple(sorted(tuple(v[:3]) for v in r['triangle']));mask=original_masks[key]
        if mask:exact+=1
        else:mask=all_mask;changed+=1
        center=[sum(v[a] for v in r['triangle'])/3/256 for a in range(3)]
        # New faces fail open; exact original triangles retain their mask.
        # Material/spatial/membership keys are carried through batching.
        group=(r['material'],*(math.floor(v/16) for v in center))
        groups[group].append((r['triangle'],mask))
    vertex=bytearray();indices=bytearray();chunks=[];proof=[];masks=[];done=set();old_chunks=list(struct.iter_unpack('>IHH6hHH',ss[1]))
    def add_batch(vertices,ix,material,mask):
        first=len(vertex)//16;start=len(indices)//2;padded=vertices+([vertices[-1]] if len(vertices)%2 else []);pairs=[]
        rgba=lambda v:(v[3]<<24)|(v[4]<<16)|(v[5]<<8)|255
        for a,b in zip(padded[::2],padded[1::2]):pairs.append((*a[:3],0,*b[:3],0,rgba(a),rgba(b),*a[6:],*b[6:]))
        vertex.extend(packed('3hH3hHII4h',pairs));indices.extend(packed('H',[(i,) for i in ix]))
        while len(indices)%8:indices.extend(b'\0\0')
        bounds=[math.floor(min(v[a] for v in vertices)/8) for a in range(3)]+[math.ceil(max(v[a] for v in vertices)/8) for a in range(3)]
        chunks.append((first,len(vertices),material,*bounds,start,len(ix)));proof.append({'unchanged':False,'material':material,'mask':mask});masks.append(mask)
    for old,c in enumerate(old_chunks):
        first,count,material,*rest=c;at,n=rest[-2:]
        if old in editable:
            if material in done:continue
            done.add(material)
            for key,records in sorted(groups.items()):
                if key[0]!=material:continue
                tris=[];face_masks=[]
                for tri,mask in records:
                    expanded=uv_safe_triangles([tri]);tris.extend(expanded);face_masks.extend([mask]*len(expanded))
                at=0
                for b in indexed_terrain(tris,uv_period=1024):
                    count=len(b['indices'])//3;mask=0
                    for m in face_masks[at:at+count]:mask|=m
                    add_batch(b['vertices'],b['indices'],material,mask);at+=count
                assert at==len(tris)
        else:
            bv=len(vertex)//16;bi=len(indices)//2;vertex.extend(ss[0][first//2*32:(first+((count+1)&~1))//2*32]);indices.extend(ss[2][at*2:(at+((n+3)&~3))*2]);chunks.append((bv,count,material,*rest[:6],bi,n));proof.append({'old_batch':old,'unchanged':True});masks.append(visibility['chunk_masks'][old])
    assert len(chunks)<=512 and len(indices)//2<65536
    destination=OUT/'candidate-maps';destination.mkdir(exist_ok=True)
    for p in (PREVIOUS/'candidate-maps').iterdir():
        if p.name!='sidewinder.map64' and not (destination/p.name).exists():(destination/p.name).symlink_to(p.resolve())
    ss[0]=bytes(vertex);ss[1]=packed('IHH6hHH',chunks);ss[2]=bytes(indices);result=bank(destination/'sidewinder.map64',1,ss);payload=(destination/'sidewinder.map64').read_bytes()
    assert sections(payload)[3:]==sections(original)[3:]
    old=list(batches(original));new=list(batches(payload))
    for i,e in enumerate(proof):
        if e['unchanged']:assert old[e['old_batch']][1]==new[i][1]
    result.update(baseline_sha256=sha(original),candidate_sha256=sha(payload),candidate_json_sha256=sha((OUT/'candidate.json').read_bytes()),vertices=len(vertex)//16,chunks=len(chunks),triangles=sum(c[-1]//3 for c in chunks),batches=proof,chunk_masks=masks,unchanged_batches=sum(e['unchanged'] for e in proof),new_exact_geometry_faces=exact,new_fail_open_faces=changed,all_nonrender_sections_identical=True)
    (OUT/'packing-report.json').write_text(json.dumps(result,indent=2)+'\n')
    c=(PREVIOUS/'cameras/visibility-data.c').read_text();c,n=re.subn(r'static const uint64_t chunks\[\]=\{[^}]+\};','static const uint64_t chunks[]={'+','.join('UINT64_C('+str(m)+')' for m in masks)+'};',c);assert n==1
    c,n=re.subn(r'(bg_world_pvs=\{nodes,planes,leaves,rows,chunks,\d+,\d+,\d+,35,)478,',lambda m:m[1]+str(len(chunks))+',',c);assert n==1
    (OUT/'visibility-data.c').write_text(c);print(json.dumps({k:result[k] for k in ['vertices','chunks','triangles','unchanged_batches','new_exact_geometry_faces','new_fail_open_faces']}))


def report():
    import base64
    import csv
    import html
    import statistics
    import report_sidewinder_structures as viewer
    viewer.OUT=OUT
    candidate=json.loads((OUT/'candidate.json').read_text());packing=json.loads((OUT/'packing-report.json').read_text());measurements=json.loads((OUT/'measurements.json').read_text())
    visuals=json.loads((OUT/'visual-metrics.json').read_text())['views'];photos=json.loads((OUT/'player-photos.json').read_text())['photos'];interiors=json.loads((OUT/'interiors.json').read_text())['views']
    extreme=ROOT/'build/n64-sidewinder-structures-extreme';extreme_measurements=json.loads((extreme/'measurements.json').read_text());extreme_visuals=json.loads((extreme/'visual-metrics.json').read_text())['views']
    before_categories=ROOT/'build/n64-sidewinder-cost-breakdown';breakdown={};matched=[]
    for route in ['replay','photos']:
        a=[r for r in csv.DictReader((before_categories/route/'categories.csv').open()) if r['candidate']=='1']
        b=[r for r in csv.DictReader((OUT/route/'cameras.csv').open()) if r['candidate']=='1']
        assert len(a)==len(b)
        new_arch=[]
        for old,new in zip(a,b):
            assert all(old[k]==new[k] for k in ('map','tick','camera','eye_x','eye_y','eye_z','alive','zoom','pvs_mask'))
            arch=int(new['vertices'])-int(old['terrain'])-int(old['scenery']);assert arch>=0;new_arch.append(arch)
            matched.append({'route':route,'tick':old['tick'],'camera':old['camera'],'alive':old['alive'],'terrain':int(old['terrain']),'scenery':int(old['scenery']),'before_structures':int(old['structures']),'after_structures':arch,'before_total':int(old['vertices']),'after_total':int(new['vertices'])})
        breakdown[route]={'terrain_mean':statistics.mean(int(r['terrain']) for r in a),'scenery_mean':statistics.mean(int(r['scenery']) for r in a),'architecture_before':statistics.mean(int(r['structures']) for r in a),'architecture_after':statistics.mean(new_arch)}
    with (OUT/'matched-costs.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(matched[0]));w.writeheader();w.writerows(matched)
    source_arch=5617;new_arch=sum(r['candidate_triangles'] for r in candidate['report'])+296
    rejection_path=OUT/'rejection.json'
    rejection=json.loads(rejection_path.read_text()) if rejection_path.exists() else None
    summary={'architecture_triangles_before':source_arch,'architecture_triangles_after':new_arch,'triangle_reduction_percent':100*(1-new_arch/source_arch),'measurements':measurements,'breakdown':breakdown,'worst_silhouette_iou':min(r['silhouette_iou'] for r in visuals),'offline_pvs_control_changed_pixels':sum(r['pvs_control_changed_pixels'] for r in photos),'source_bank_sha256':packing['baseline_sha256'],'candidate_bank_sha256':packing['candidate_sha256'],'status':'rejected' if rejection else 'unadopted','rejection':rejection,'scope':'Rejected visual experiment; never adopted. SDK host submission counts and offline image checks; no new native FPS/RSP/RDP validation.' if rejection else 'Unadopted aggressive architecture prototype. SDK host submission counts and offline image checks; no new native FPS/RSP/RDP validation.'}
    (OUT/'appraisal.json').write_text(json.dumps(summary,indent=2)+'\n')
    embed=lambda path:'data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()
    data=[]
    for name,directory,records in [('Aggressive candidate',OUT,visuals),('Extreme trial — rejected for shape loss',extreme,extreme_visuals)]:
        for r in records:data.append({**r,'variant':name,'paths':{k:embed(directory/p) for k,p in r['paths'].items()}})
    style='body{background:#121822;color:#e7edf5;font:16px system-ui;max-width:1300px;margin:30px auto;padding:0 20px}p{max-width:1050px;line-height:1.6}a{color:#9ddcff}select,input{margin:10px;padding:8px;background:#293644;color:white;border:1px solid #52657b}table{border-collapse:collapse;margin:20px 0;width:100%}td,th{padding:10px;border-bottom:1px solid #3d4a5b;text-align:right}td:first-child,th:first-child{text-align:left}.pair{display:grid;grid-template-columns:1fr 1fr;gap:12px}.pair img,#filter{width:100%;image-rendering:pixelated}#filter{max-width:900px}.viewer{border:1px solid #394b60;padding:15px;margin:25px 0}h1,h2{color:white}small{color:#bac8da}.note{border-left:4px solid #e7b260;padding:6px 16px;background:#202730}'
    page=['<!doctype html><meta charset="utf-8"><title>Sidewinder: aggressive structure reduction</title><style>'+style+'</style><h1>Sidewinder: aggressive structure reduction</h1>']
    if rejection:
        page.append('<div class="note" style="border-color:#ff7777"><h2>Rejected — visually unacceptable</h2><p>Whole-structure collapse warped the architectural forms and texture mapping. The count reductions below are retained as experiment data, not an acceptable result. Neither trial was adopted. Original structures remain the baseline.</p></div>')
    page.append(f'<p><b>Architecture: 5,617 → {new_arch:,} triangles ({summary["triangle_reduction_percent"]:.1f}% fewer).</b> The two main bases lose roughly half their editable triangles. This pass simplifies whole structures across material and old visibility-partition boundaries. Small bevels, recesses and their texture/lighting interpolation can change. It is substantially coarser than the previous 102-triangle cleanup.</p>')
    page.append('<table><tr><th>Matched workload</th><th>Before loads/camera</th><th>Aggressive</th><th>Reduction</th><th>Extreme rejected trial</th></tr>')
    for route,label in [('replay','68 four-player replay cameras'),('photos','24 single-player photo cameras')]:
        m=measurements[route];page.append(f'<tr><td>{label}</td><td>{m["before_mean"]:,.1f}</td><td>{m["after_mean"]:,.1f}</td><td>{100*(1-m["after_mean"]/m["before_mean"]):.1f}%</td><td>{extreme_measurements[route]["after_mean"]:,.1f}</td></tr>')
    page.append('</table>')
    b=breakdown['replay'];page.append(f'<p>Replay architecture submissions fall from {b["architecture_before"]:,.0f} to {b["architecture_after"]:,.0f} loads/camera ({100*(1-b["architecture_after"]/b["architecture_before"]):.1f}% fewer). Terrain remains {b["terrain_mean"]:,.0f} and scenery {b["scenery_mean"]:,.0f}. Worst total replay view: 19,952 → {measurements["replay"]["after_worst"]:,}. Still {measurements["replay"]["below_1500"]}/68 replay views and 0/24 photo views are below 1,500. These are measured host submission counts, <b>not FPS estimates</b>.</p>')
    page.append('<div class="note"><p><b>Visible tradeoffs for appraisal:</b> this candidate has more angular bevels, simpler wall and ceiling transitions, shifted shallow recesses, and changed UV/baked-light gradients. Close-wall views can differ substantially. The worst measured exterior silhouette overlap is '+f'{100*summary["worst_silhouette_iou"]:.2f}%. Original collision is byte-identical and the full walking/photo player states match, but the reduced render surfaces are approximate. No adoption or claim of invisible changes is implied.</p></div>')
    page.append('<h2>Same angles, same framing</h2><p>72 offline views cover nine structure regions from eight directions. Before/after share camera and scale. The rejected extreme trial is included to show the larger 68% triangle cut and the accompanying roof/corridor distortion. These float packed-map diagnostics do not emulate native RSP/RDP rounding, fog, HUD or dynamics.</p><div class="viewer"><label>Candidate <select id="variant"></select></label><label>Structure <select id="structure"></select></label><label>Angle <select id="angle"></select></label><div class="pair"><div>Before<img id="before"></div><div>Reduced<img id="after"></div></div><p id="metrics"></p><label>Filter <select id="mode"><option value="silhouette">Silhouette: gray overlap, cyan removed, orange added</option><option value="difference">RGB difference ×6</option></select></label><br><img id="filter"></div>')
    page.append('<h2>Per-structure geometry</h2><table><tr><th>Editable structure region</th><th>Before triangles</th><th>After</th><th>Reduction</th><th>Protected vertices retained</th></tr>')
    for r in candidate['report']:page.append(f'<tr><td>{html.escape(r["name"])}</td><td>{r["source_triangles"]:,}</td><td>{r["candidate_triangles"]:,}</td><td>{100*(1-r["candidate_triangles"]/r["source_triangles"]):.1f}%</td><td>{r["profile_and_boundary_pins"]-r["missing_pins"]}/{r["profile_and_boundary_pins"]}</td></tr>')
    page.append('</table><p>296 additional architecture triangles remain unchanged: lights, ladders and the architecture faces of mixed scenery batches. Blender holds coarse floor/roof corners, substantial ramp vertices, outer support points and real mesh boundaries. It permits the removal of finer edges inside that framework. All protected vertices survive; this is not a guarantee that every intervening surface remains identical. See <a href="candidate.json">per-region sampled surface deviations</a>.</p>')
    page.append('<h2>Original photo route</h2><p>All 24 exact SDK photo-camera matrices and full player states match. These offline views include packed textures, material alpha/depth modes, baked vertex color and perspective-correct interpolation. Every candidate visibility-on versus visibility-off control is pixel-identical; geometry/appearance changes versus the original are shown separately.</p>')
    page.append(viewer.gallery('photo',photos,'player-photos','photo',lambda p:f'{p["photo"]:02} {p["label"]}'))
    page.append('<h2>Lower rooms and roofs</h2><p>Sixteen additional authored views from lower-room and roof spawn positions in both bases, with the same standing eye height, position, yaw and projection before/after. These are separate from the performance census. Inspect the simpler wall and ceiling transitions here.</p>')
    page.append(viewer.gallery('interior',interiors,'interiors','index',lambda p:f'{p["index"]:02} {p["label"]}, yaw {p["yaw"]:.3f}'))
    page.append(f'<h2>Preservation and visibility</h2><p>All 20 non-render sections remain byte-identical: original collision, textures, placements and gameplay data. All {packing["unchanged_batches"]} protected terrain/scenery/other batches retain their complete packed attributes, indices and bounds. Exact source triangles retain source masks; {packing["new_fail_open_faces"]} changed architecture faces fail open. Batch masks are conservative unions carried through UV splitting and packing. This includes the cost of extra visibility, rather than assuming original cluster ownership for changed shapes.</p>')
    page.append('<p>The host probes pass AddressSanitizer/UndefinedBehaviorSanitizer and match all camera/player states. No new native FPS or native pixel checks have been run. The source assets and the previous conservative prototype remain unchanged; both new candidates are private, unadopted build artifacts.</p><p><a href="matched-costs.csv">Every matched camera and category cost</a> · <a href="appraisal.json">Summary</a> · <a href="visual-metrics.json">All exterior cameras and metrics</a> · <a href="player-photos.json">Photo states and pixel checks</a> · <a href="interiors.json">Interior camera coordinates</a> · <a href="packing-report.json">Packing proof</a> · <a href="structure-appraisal.blend">Blender scene</a> · <a href="../n64-sidewinder-structures/comparison.html">Previous cautious pass</a></p>')
    page.append('<script>const views='+json.dumps(data)+';const variant=document.querySelector("#variant"),structure=document.querySelector("#structure"),angle=document.querySelector("#angle"),mode=document.querySelector("#mode");for(const n of [...new Set(views.map(v=>v.variant))])variant.add(new Option(n,n));for(const n of [...new Set(views.map(v=>v.structure))])structure.add(new Option(n,n));for(const n of [...new Set(views.map(v=>v.angle))])angle.add(new Option(n,n));function update(){const v=views.find(v=>v.variant===variant.value&&v.structure===structure.value&&v.angle===angle.value);for(const k of ["before","after"])document.getElementById(k).src=v.paths[k];document.querySelector("#filter").src=v.paths[mode.value];document.querySelector("#metrics").textContent=`${v.before_triangles} → ${v.after_triangles} triangles in this region; silhouette overlap ${(100*v.silhouette_iou).toFixed(2)}%; ${v.silhouette_changed_pixels} silhouette pixels changed; ${v.changed_rgb_pixels} RGB pixels changed.`;}variant.onchange=structure.onchange=angle.onchange=mode.onchange=update;update();</script>')
    (OUT/'comparison.html').write_text('\n'.join(page)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':
    if sys.argv[1:] and sys.argv[1]=='pack':pack()
    elif sys.argv[1:] and sys.argv[1]=='report':report()
    else:prepare()
