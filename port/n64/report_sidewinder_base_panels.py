"""Appraisal for the isolated, authored west-base ceiling-detail pilot."""
import base64
import collections
import csv
import json
import math
import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from sidewinder_base_panels import OUT, PREVIOUS, ROOT, sha
from photo_sidewinder_structures import load_bank, render
from remap_sidewinder_visibility import sections


def detail_photos():
    before = load_bank(PREVIOUS / 'candidate-maps/sidewinder.map64')
    after = load_bank(OUT / 'candidate-maps/sidewinder.map64')
    plan = json.loads((OUT / 'design.json').read_text())
    directory = OUT / 'details'
    directory.mkdir(exist_ok=True)
    records = []
    for fixture in plan['fixtures']:
        x0, x1, z0, z1, y0, y1 = fixture['bounds']
        target = np.array([(x0+x1)/2, y0, (z0+z1)/2]) / 256
        # Both close views are authored inspections, not standing gameplay poses.
        for angle, offset in [('normal', [0, -1.2, 0]), ('grazing', [0, -.45, 1.25])]:
            eye = target + offset
            forward = target - eye
            forward /= np.linalg.norm(forward)
            right = np.cross(forward, [0, 0, 1])
            right /= np.linalg.norm(right)
            up = np.cross(right, forward)
            view = np.eye(4)
            view[:3, :3] = np.stack((right, up, -forward))
            view[:3, 3] = -view[:3, :3] @ (eye*32)
            near, far = .03*32, 300*32
            f = 1/math.tan(1.08/2)
            projection = np.zeros((4, 4))
            projection[0, 0] = f/(4/3)
            projection[1, 1] = f
            projection[2, 2] = -(far+near)/(far-near)
            projection[2, 3] = -2*far*near/(far-near)
            projection[3, 2] = -1
            matrix = (projection @ view).T
            a, b = render(before, matrix), render(after, matrix)
            difference = np.abs(a.astype(np.int16)-b.astype(np.int16))
            index = len(records)
            for name, image in [('before', a), ('after', b), ('difference', np.clip(difference*6, 0, 255).astype(np.uint8))]:
                Image.fromarray(image).save(directory / f'{index:02}-{name}.png')
            records.append(dict(index=index, label=fixture['name']+' — '+angle,
                                eye=eye.tolist(), target=target.tolist(), camera_kind='authored inspection, no player body',
                                fov=1.08, aspect=4/3, matrix_columns=matrix.tolist(),
                                rgb_changed_pixels=int(np.count_nonzero(difference.max(axis=2))),
                                rgb_mean_absolute_error=float(difference.mean())))
            print('detail', records[-1]['label'], records[-1]['rgb_changed_pixels'], flush=True)
    (OUT / 'details.json').write_text(json.dumps({'scope': 'Matched offline detail inspections. Visibility disabled. Normal and grazing angle for each replaced recess.', 'views': records}, indent=2)+'\n')
    contact = Image.new('RGB', (1280, 265*len(records)), (18, 24, 34))
    draw = ImageDraw.Draw(contact)
    for record in records:
        y = record['index']*265
        draw.text((8, y+5), record['label']+' — before', fill='white')
        draw.text((648, y+5), 'Flat panel', fill='white')
        for x, kind in [(0, 'before'), (640, 'after')]:
            contact.paste(Image.open(directory / f'{record["index"]:02}-{kind}.png'), (x, y+25))
    contact.save(OUT / 'detail-contact.png')


def preservation():
    """Check the expanded retained faces, including winding and UV continuity."""
    source = json.loads((OUT / 'source.json').read_text())
    candidate = json.loads((OUT / 'candidate.json').read_text())
    proof = json.loads((OUT / 'packing-report.json').read_text())
    removed = {tuple(r) for r in candidate['removed_source_refs']}
    old = sections((PREVIOUS / 'candidate-maps/sidewinder.map64').read_bytes())
    new = sections((OUT / 'candidate-maps/sidewinder.map64').read_bytes())
    assert old[7:] == new[7:]
    for section in range(3, 7):
        assert new[section].startswith(old[section])

    def key(material, triangle):
        # Canonicalize cyclic order only: retain winding. Whole-texture UV
        # translations are harmless; require the SAME translation at all corners.
        alternatives = []
        for at in range(3):
            tri = triangle[at:]+triangle[:at]
            u, v = tri[0][6]//1024*1024, tri[0][7]//1024*1024
            alternatives.append(tuple(tuple(vertex[:6]+[vertex[6]-u, vertex[7]-v]) for vertex in tri))
        return material, min(alternatives)

    expected = collections.Counter(key(r['material'], r['triangle']) for r in source['triangles'] if (r['batch'], r['face']) not in removed)
    actual = collections.Counter()
    panels = []
    for bi, c in enumerate(struct.iter_unpack('>IHH6hHH', new[1])):
        first, count, material, *rest = c
        at, n = rest[-2:]
        ids = struct.unpack_from('>'+str(n)+'H', new[2], at*2)
        vs = []
        for i in range(count):
            offset = (first+i)//2*32
            half = (first+i)%2
            vs.append([*struct.unpack_from('>3h', new[0], offset+half*8), *new[0][offset+16+half*4:offset+19+half*4], *struct.unpack_from('>2h', new[0], offset+24+half*4)])
        for ti in range(0, n, 3):
            triangle = [vs[i] for i in ids[ti:ti+3]]
            if material >= 29:
                panels.append(key(material, triangle))
            else:
                actual[key(material, triangle)] += 1
    assert actual == expected, ('Retained face attributes changed', sum((expected-actual).values()), sum((actual-expected).values()))
    assert collections.Counter(panels) == collections.Counter(key(r['material'], r['triangle']) for r in candidate['replacement_triangles'])
    canonical = ROOT / 'halo64-assets/generated/maps/sidewinder.map64'
    result = dict(retained_triangles_verified=sum(actual.values()), replaced_triangles=len(removed), replacement_triangles=len(panels),
                  exact_position_color_winding_and_uv_continuity=True,
                  collision_gameplay_sections_identical=True, original_texture_prefixes_identical=True,
                  baseline_sha256=sha((PREVIOUS / 'candidate-maps/sidewinder.map64').read_bytes()),
                  candidate_sha256=sha((OUT / 'candidate-maps/sidewinder.map64').read_bytes()),
                  canonical_sha256=sha(canonical.read_bytes()), adopted=False)
    assert result['canonical_sha256'] == '200a3e01cd0c29a4f3f6f2ab71a1737c81342d2d3950bf763e3e9417606f7948'
    (OUT / 'preservation.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result), flush=True)


def report():
    import report_sidewinder_structures as shared
    shared.OUT = OUT
    measurements = json.loads((OUT / 'measurements.json').read_text())
    visual = json.loads((OUT / 'visual-metrics.json').read_text())['views']
    photos = json.loads((OUT / 'player-photos.json').read_text())['photos']
    interior = json.loads((OUT / 'interiors.json').read_text())['views']
    details = json.loads((OUT / 'details.json').read_text())['views']
    preserved = json.loads((OUT / 'preservation.json').read_text())
    packing = json.loads((OUT / 'packing-report.json').read_text())
    all_camera_rows = []
    for workload in ['replay', 'photos']:
        cameras = list(csv.DictReader((OUT / workload / 'cameras.csv').open()))
        paired = collections.defaultdict(dict)
        for row in cameras:
            paired[row['tick'], row['camera']][row['candidate']] = row
        for (tick, camera), values in paired.items():
            a, b = values['0'], values['1']
            all_camera_rows.append(dict(workload=workload, tick=int(tick), camera=int(camera), before=int(a['vertices']), after=int(b['vertices']), material_before=int(a['material_changes']), material_after=int(b['material_changes']), alive=int(b['alive'])))
    (OUT / 'per-camera.json').write_text(json.dumps(all_camera_rows, indent=2)+'\n')
    rows = ''
    for kind, r in measurements.items():
        rows += f'<tr><td>{kind} ({r["samples"]} cameras)</td><td>{r["before_mean"]:,.1f}</td><td>{r["after_mean"]:,.1f}</td><td>{r["before_mean"]-r["after_mean"]:,.1f} ({100*(1-r["after_mean"]/r["before_mean"]):.2f}%)</td><td>{r["after_worst"]:,}</td><td>{r["below_1500"]}/{r["samples"]}</td></tr>'
    html = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sidewinder west base — authored detail pilot</title><style>body{background:#121822;color:#e7edf5;font:16px system-ui;max-width:1300px;margin:30px auto;padding:0 20px}p{max-width:1050px;line-height:1.6}a{color:#9ddcff}select,input{margin:12px;padding:8px;background:#293644;color:white;border:1px solid #52657b;max-width:95%}table{border-collapse:collapse;margin:20px 0}td,th{padding:10px 15px;border-bottom:1px solid #3d4a5b;text-align:right}td:first-child,th:first-child{text-align:left}.pair{display:grid;grid-template-columns:1fr 1fr;gap:12px}.pair img,#filter{width:100%;image-rendering:pixelated}#filter{max-width:900px}.viewer{border:1px solid #394b60;padding:15px;margin:25px 0}.notice{background:#283544;padding:14px;border-left:4px solid #a6d9f4}.scroll{overflow:auto}h1,h2{color:white}small{color:#c0cedc}@media(max-width:700px){.pair{grid-template-columns:1fr}}</style><h1>West base: six authored ceiling panels</h1><p class="notice"><b>Isolated appraisal candidate. Not adopted.</b> This is a narrow pilot after rejecting the broken aggressive decimation. It establishes a specific replacement that keeps the room shell intact. It does not achieve a substantial map-wide reduction.</p>'''
    html += '<p>Six recessed ceiling-light housings in the west base become flat panels at their exact original ceiling rims. Their frames, red light patterns and vertex shading are baked into three 32×32 RGBA5551 textures (6 KiB total). The four lower lights share a source-derived pattern with individual color modulation; the two upper lights have separate tiles. The removed depth is 0.078–0.082 world units. Roof profile, entrances, ramps, floors, wall planes, all other structures, terrain and scenery retain their source geometry.</p>'
    html += '<div class="scroll"><table><tr><th>Geometry</th><th>Before</th><th>After</th><th>Reduction</th></tr><tr><td>Six selected light housings</td><td>76 triangles</td><td>12</td><td>84.2%</td></tr><tr><td>Entire west base</td><td>1,281 triangles</td><td>1,217</td><td>5.0%</td></tr><tr><td>Whole map</td><td>14,883 triangles</td><td>14,819</td><td>0.43%</td></tr><tr><td>Whole-map stored paired vertex entries</td><td>21,962</td><td>21,834</td><td>128 (0.58%)</td></tr></table></div>'
    html += '<h2>Matched submission measurements</h2><p>Same 68 replay cameras and 24 photo fixtures, with identical full player states before and after. Host probes use the SDK camera, frustum and conservative visibility under ASan/UBSan. These are submitted vertex-load counts, <b>not new FPS measurements</b>. Stored map inventory and per-camera loads are separate measures.</p><div class="scroll"><table><tr><th>Workload</th><th>Before mean</th><th>After mean</th><th>Mean saved</th><th>After worst</th><th>Below 1,500</th></tr>'+rows+'</table></div>'
    deltas = [r['after']-r['before'] for r in all_camera_rows]
    material_delta = [r['material_after']-r['material_before'] for r in all_camera_rows]
    html += f'<p>Across all 92 cameras, load changes range from {min(deltas):+,} to {max(deltas):+,}; {sum(d>0 for d in deltas)} cameras increase. Material-change counts vary by {min(material_delta):+} to {max(material_delta):+}. The tiles add texture/material transitions when visible, and the new panel batches deliberately fail open for conservative visibility. Native timing would be needed to evaluate that tradeoff. The replay count includes inactive/dead camera samples; only 2 of the 63 live replay cameras are below 1,500. The 1,500-load target remains far away.</p>'
    html += '<h2>Close inspection of the actual edit</h2><p>Normal and grazing views of every selected fixture, sharing exact before/after cameras. These inspection cameras are authored for detail visibility, not player route poses. The source recess becomes visibly flat at grazing angles; texture resolution and flattened depth are the deliberate sacrifices. RGB difference is amplified ×6.</p>'
    html += shared.gallery('detail', details, 'details', 'index', lambda r: f'{r["index"]:02} {r["label"]}')
    west = [r for r in visual if r['structure'] == 'West base']
    data = [{**r, 'paths': {k: 'data:image/png;base64,'+base64.b64encode((OUT/p).read_bytes()).decode() for k,p in r['paths'].items()}} for r in west]
    html += '<h2>Base silhouette and appearance from eight angles</h2><p>Exact shared orthographic cameras; no independent fitting. These offline packed-map renders use the existing weapon-audit renderer with baked vertex colors. They supplement the perspective views below.</p><div class="viewer"><select id="angle"></select><div class="pair"><div>Before<img id="before"></div><div>Flat panels<img id="after"></div></div><p id="metrics"></p><select id="mode"><option value="difference">RGB difference ×6</option><option value="silhouette">Silhouette: gray overlap, cyan source only, orange candidate only</option></select><br><img id="filter"></div>'
    html += '<script>(()=>{const data='+json.dumps(data)+';const angle=document.getElementById("angle"),mode=document.getElementById("mode");data.forEach((r,i)=>angle.add(new Option(r.angle,i)));function update(){const r=data[angle.value];for(const k of ["before","after"])document.getElementById(k).src=r.paths[k];document.getElementById("filter").src=r.paths[mode.value];document.getElementById("metrics").textContent=`${r.silhouette_changed_pixels} silhouette pixels changed; ${r.changed_rgb_pixels} RGB pixels changed; silhouette IoU ${r.silhouette_iou.toFixed(6)}`;}angle.onchange=mode.onchange=update;update();})();</script>'
    other = [r for r in visual if r['structure'] != 'West base']
    html += f'<p>All {len(other)} views of the other eight structure regions are pixel-identical: {all(r["changed_rgb_pixels"]==0 and r["silhouette_changed_pixels"]==0 for r in other)}. West-base silhouette changes across eight views: {[r["silhouette_changed_pixels"] for r in west]}. Full 72-view metrics are saved.</p>'
    html += '<h2>Original 24-camera photo route</h2><p>Exact SDK float matrices and saved player poses, including crouch state and view angles. Offline perspective clipping, nearest packed textures, baked vertex lighting, material alpha/depth modes and perspective-correct interpolation. No HUD, fog, dynamic objects or native RSP/RDP rounding.</p>'
    html += shared.gallery('photo', photos, 'player-photos', 'photo', lambda r: f'{r["photo"]:02} {r["label"]}')
    html += f'<p>{sum(r["rgb_changed_pixels"]==0 for r in photos)}/24 route views are pixel-identical. Candidate visibility-on versus visibility-off control: {sum(r["pvs_control_changed_pixels"] for r in photos):,} differing pixels. These are sampled float-renderer checks, not a guarantee for every view.</p>'
    html += '<h2>Standing interior and roof views</h2><p>Four cardinal directions from the source-authored lower-room and roof stations in both bases, with a standing 0.62-unit eye height. Visibility disabled. These 16 diagnostic views do not enter the performance means.</p>'
    html += shared.gallery('interior', interior, 'interiors', 'index', lambda r: f'{r["index"]:02} {r["label"]}, yaw {r["yaw"]:.3f}')
    html += f'<h2>Preservation and reproducibility</h2><p>The validator expands the packed triangles and checks all {preserved["retained_triangles_verified"]:,} retained faces for exact position, color, winding and continuous UV coordinates (allowing only a whole-texture translation per triangle). The 12 new faces exactly match the Blender-authored output. Original texture data remains intact; three tiles are appended (32 materials total, within the existing engine capacity). Collision and gameplay sections 7–22 are byte-identical. {packing["unchanged_batches"]} original batches are copied byte-for-byte apart from offsets; 11 affected source batches are repacked locally. The canonical map is unchanged.</p>'
    html += '<p><a href="west-base-appraisal.blend">Blender appraisal scene</a> · <a href="design.json">Exact selected faces, rims and bake matrices</a> · <a href="candidate.json">Authored replacement faces</a> · <a href="preservation.json">Preservation validation</a> · <a href="packing-report.json">Packing report and bank hashes</a> · <a href="measurements.json">Measurement summary</a> · <a href="per-camera.json">All 92 paired load counts</a> · <a href="replay/cameras.csv">Replay CSV</a> · <a href="photos/cameras.csv">Photo-route CSV</a> · <a href="photos/poses.json">Complete route poses</a> · <a href="player-photos.json">Route matrices and pixel checks</a> · <a href="interiors.json">Interior cameras</a> · <a href="details.json">Detail cameras</a> · <a href="visual-metrics.json">72-angle metrics</a> · <a href="detail-contact.png">Detail contact sheet</a> · <a href="panel-29.png">Lower light tile</a> · <a href="panel-30.png">Upper front tile</a> · <a href="panel-31.png">Upper rear tile</a></p></html>'
    (OUT / 'comparison.html').write_text(html)
    print('Wrote', OUT / 'comparison.html')


if __name__ == '__main__':
    import sys
    if sys.argv[1:] == ['photos']:
        detail_photos()
    else:
        preservation()
        report()
