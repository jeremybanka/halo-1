"""Matched snow-pine asset and world-photo appraisal."""
import base64
import collections
import csv
import json
import math
from pathlib import Path
import re

import numpy as np
from PIL import Image, ImageDraw

from sidewinder_trees import ROOT, OUT, PREVIOUS
from photo_sidewinder_structures import load_bank, render


def asset_bank(model, textures, flags):
    triangles, materials = [], []
    for face, mi in zip(model['faces'], model['materials']):
        triangle = []
        for vi in reversed(face):
            x, y, z, u, v = model['vertices'][vi]
            triangle.append([x*32, z*32, -y*32, 255, 255, 255, u, 1-v])
        triangles.append(triangle)
        materials.append(mi+18)
    return np.array(triangles), np.array(materials), np.zeros(len(triangles), dtype=int), textures, flags


def assets():
    source = json.loads((OUT / 'source-models.json').read_text())
    authored = json.loads((OUT / 'authored-models.json').read_text())
    world = load_bank(PREVIOUS / 'candidate-maps/sidewinder.map64')
    directory = OUT / 'assets'
    directory.mkdir(exist_ok=True)
    records = []
    contacts = []
    for species, entry in enumerate(source):
        model = entry['lods'][0]
        variants = {'source': model, **authored[species]['variants']}
        points = np.array(model['vertices'])[:, :3][:, [0, 2, 1]]*32
        points[:, 2] *= -1
        center = (points.min(0)+points.max(0))/2
        span = (points[:, 1].max()-points[:, 1].min())*1.10
        for ai in range(10):
            angle = ai*math.pi/4 if ai < 8 else math.pi/4+(ai-8)*math.pi
            direction = np.array([math.sin(angle), .05 if ai < 8 else .65, math.cos(angle)])
            direction /= np.linalg.norm(direction)
            forward = -direction
            right = np.cross(forward, [0, 1, 0]); right /= np.linalg.norm(right)
            up = np.cross(right, forward)
            view = np.eye(4)
            view[:3, :3] = np.stack([right, up, -forward])
            view[:3, 3] = -view[:3, :3] @ (center+direction*100*32)
            projection = np.eye(4)
            projection[0, 0] = 2/(span*2/3)
            projection[1, 1] = 2/span
            projection[2, 2] = -2/(300*32)
            projection[2, 3] = -1
            matrix = (projection @ view).T
            images = {}
            for name, data in variants.items():
                image = render(asset_bank(data, world[3], world[4]), matrix, width=400, height=600)
                images[name] = image
                Image.fromarray(image).save(directory / f'{species}-{ai:02}-{name}.png')
            before = images['source']
            for name in ('medium', 'lean'):
                after = images[name]
                difference = np.abs(before.astype(np.int16)-after.astype(np.int16))
                Image.fromarray(np.clip(difference*6, 0, 255).astype(np.uint8)).save(directory / f'{species}-{ai:02}-{name}-difference.png')
                a = np.any(before != (18, 24, 34), axis=2)
                b = np.any(after != (18, 24, 34), axis=2)
                overlay = np.full_like(before, (18, 24, 34))
                overlay[a & b] = (175, 190, 203)
                overlay[a & ~b] = (40, 211, 246)
                overlay[b & ~a] = (255, 136, 58)
                Image.fromarray(overlay).save(directory / f'{species}-{ai:02}-{name}-silhouette.png')
                records.append(dict(species=species, tree='Large' if species == 0 else 'Small', angle=ai, yaw=angle,
                                    elevation=float(direction[1]), variant=name, before_triangles=len(model['faces']), after_triangles=len(variants[name]['faces']),
                                    rgb_changed_pixels=int(np.count_nonzero(difference.max(axis=2))),
                                    silhouette_iou=float(np.count_nonzero(a & b)/max(1, np.count_nonzero(a | b))),
                                    source_coverage_pixels=int(a.sum()), candidate_coverage_pixels=int(b.sum()),
                                    matrix_columns=matrix.tolist()))
            if ai in (0, 1, 2, 4):
                contact = Image.new('RGB', (1200, 625), (18, 24, 34))
                draw = ImageDraw.Draw(contact)
                for x, name in enumerate(('source', 'medium', 'lean')):
                    draw.text((x*400+8, 5), ('Large' if species == 0 else 'Small')+f' / angle {ai} / '+name, fill='white')
                    contact.paste(Image.fromarray(images[name]), (x*400, 25))
                contacts.append(contact)
            print('asset', species, ai, flush=True)
    contact = Image.new('RGB', (1200, len(contacts)*625), (18, 24, 34))
    for i, row in enumerate(contacts):
        contact.paste(row, (0, i*625))
    contact.save(OUT / 'asset-contact.png')
    (OUT / 'asset-metrics.json').write_text(json.dumps({'scope': 'Offline asset inspection; same source-centered orthographic matrix and original packed textures/material alpha for each comparison. No independent framing. Ten views of each of two trees.', 'views': records}, indent=2)+'\n')


def world_photos(variant):
    import photo_sidewinder_structures as shared
    shared.OUT = OUT / variant
    shared.main()


def data_image(path):
    return 'data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()


def timings():
    records = []
    summaries = {}
    for workload in ('one', 'four'):
        for label in ('baseline', 'candidate'):
            path = OUT / (workload+'-'+('baseline-repeat' if workload == 'four' and label == 'baseline' else label)+'.log')
            text = path.read_text()
            groups = {}
            for line in text.splitlines():
                if 'BENCH vi_fresh group=' in line:
                    group = re.search(r'group=(\w+)', line)[1]
                    values = {k: int(v) for k, v in re.findall(r'(\w+)=(\d+)', line)}
                    if group in groups:
                        assert groups[group] == values, 'Result panel repeated with changed measurements'
                    groups[group] = values
            assert set(groups) == {'ALL', 'EARLY', 'LATE'}
            all_values = groups['ALL']
            records.append(dict(workload=workload, label=label, groups=groups, fps=all_values['frames']*1e6/all_values['elapsed_us'],
                                source_log=path.name, screenshot=f'{workload}-{label}-native.png'))
        before, after = records[-2:]
        a, b = before['groups']['ALL'], after['groups']['ALL']
        summary = dict(before_fps=before['fps'], after_fps=after['fps'], gain_percent=100*(after['fps']/before['fps']-1),
                       before_p95_ms=round(a['p95_us']/1000, 3), after_p95_ms=round(b['p95_us']/1000, 3),
                       before_max_ms=round(a['max_us']/1000, 3), after_max_ms=round(b['max_us']/1000, 3))
        if workload == 'four':
            text = (OUT / 'four-candidate-repeat.log').read_text()
            line = next(line for line in text.splitlines() if 'BENCH vi_fresh group=ALL' in line)
            values = {k: int(v) for k, v in re.findall(r'(\w+)=(\d+)', line)}
            summary['candidate_repeat_exact'] = values == b
            assert summary['candidate_repeat_exact']
            summary['baseline_repeat_scope'] = 'First fresh baseline screenshot: 773 frames / 75050 ms; repeated baseline log: 773 frames / 75050760 us.'
        summary['scope'] = '75-second NTSC fresh-pose sample after 1-second warmup; 8 MiB, LTO, three surfaces, 32 KiB queues; quiet Ares. Single-player has one fresh baseline/candidate pair; four-player has repeated baseline/candidate controls. No physical-console claim.'
        summaries[workload] = summary
    (OUT / 'timing.json').write_text(json.dumps(records, indent=2)+'\n')
    (OUT / 'timing-summary.json').write_text(json.dumps(summaries, indent=2)+'\n')
    print(json.dumps(summaries, indent=2))


def report():
    from remap_sidewinder_visibility import sections, sha
    import report_sidewinder_structures as shared
    assets = json.loads((OUT / 'asset-metrics.json').read_text())['views']
    source = json.loads((OUT / 'source-models.json').read_text())
    packing = {v: json.loads((OUT / v / 'packing-report.json').read_text()) for v in ('medium', 'lean')}
    measurements = {v: json.loads((OUT / v / 'measurements.json').read_text()) for v in ('medium', 'lean')}
    original = (PREVIOUS / 'candidate-maps/sidewinder.map64').read_bytes()
    source_sections = sections(original)
    proof = {}
    for variant in ('medium', 'lean'):
        payload = (OUT / variant / 'candidate-maps/sidewinder.map64').read_bytes()
        from sidewinder_tree_visibility import validate
        validate(json.loads((OUT / variant / 'visibility.json').read_text()), payload)
        assert sections(payload)[3:] == source_sections[3:]
        photos = json.loads((OUT / variant / 'player-photos.json').read_text())['photos']
        proof[variant] = dict(map_sha256=sha(payload), original_nonrender_sections_identical=True,
                              matching_player_bytes=json.loads((OUT / variant / 'photos/poses.json').read_text()) == json.loads((PREVIOUS / 'after-census/poses.json').read_text()),
                              pvs_control_changed_pixels=sum(r['pvs_control_changed_pixels'] for r in photos),
                              unchanged_non_tree_batches=packing[variant]['unchanged_batches'], original_material_pass_order_verified=True)
    assert sha((ROOT / 'halo64-assets/generated/maps/sidewinder.map64').read_bytes()) == '200a3e01cd0c29a4f3f6f2ab71a1737c81342d2d3950bf763e3e9417606f7948'
    (OUT / 'validation.json').write_text(json.dumps(proof, indent=2)+'\n')
    html = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sidewinder — snow pine simplification</title><style>body{background:#121822;color:#e7edf5;font:16px system-ui;max-width:1300px;margin:30px auto;padding:0 20px}p{max-width:1050px;line-height:1.6}a{color:#9ddcff}select,input,button{margin:8px;padding:8px;background:#293644;color:white;border:1px solid #52657b;max-width:95%}table{border-collapse:collapse;margin:20px 0}td,th{padding:10px 15px;border-bottom:1px solid #3d4a5b;text-align:right}td:first-child,th:first-child{text-align:left}.pair{display:grid;grid-template-columns:1fr 1fr;gap:12px}.pair img{width:100%;image-rendering:pixelated}.viewer{border:1px solid #394b60;padding:15px;margin:25px 0}.notice{background:#283544;padding:14px;border-left:4px solid #a6d9f4}.scroll{overflow:auto}h1,h2{color:white}small{color:#c0cedc}#assetFilter{max-width:400px;width:100%}#assetBefore,#assetAfter{max-height:650px;object-fit:contain}.world .pair img{aspect-ratio:4/3} @media(max-width:700px){.pair{grid-template-columns:1fr}}</style><h1>Sidewinder: simpler snow pines</h1><p class="notice"><b>Appraisal candidates; unadopted.</b> Only the nine trees change. This pass retains the original trunks, original branch-tier corner positions, original snowy foliage and bark textures, original placements and collision. It adds no materials or textures.</p>'''
    html += '<p>The source names the two assets <code>tree_pine_snow</code> and <code>tree_pine_snowsmall</code>. There is no source identification as Douglas fir. Existing exported detail variants provide no useful lower-cost mesh. The proposals retain the source tree appearance rather than substituting a generic conifer.</p><p><b>Medium:</b> every foliage component remains; subdivided branch cards become two triangles using their original four UV corner positions. <b>Lean:</b> the same branch tiers remain, while the separate small two-triangle twig cards are omitted. This intentionally reduces foliage density and fine protrusions. Both are fixed-detail prototypes; distance-dependent switching is not implemented.</p>'
    html += '<div class="scroll"><table><tr><th>Tree mesh</th><th>Count</th><th>Source triangles</th><th>Medium</th><th>Lean</th></tr><tr><td>Large snow pine</td><td>3</td><td>541</td><td>378 (−30.1%)</td><td>228 (−57.9%)</td></tr><tr><td>Small snow pine</td><td>6</td><td>249</td><td>214 (−14.1%)</td><td>124 (−50.2%)</td></tr></table></div><h2>Matched vertex loads</h2><p>The original 68 four-player replay cameras and 24 single-player photo fixtures. Full player states and camera poses match. Counts use the original SDK camera, frustum and conservative PVS under ASan/UBSan; static world only, with dynamic objects additional.</p><div class="scroll"><table><tr><th>Workload</th><th>Variant</th><th>Before mean</th><th>After mean</th><th>Saved</th><th>After worst</th><th>Below 1,500</th></tr>'
    for workload in ('replay', 'photos'):
        for variant in ('medium', 'lean'):
            r = measurements[variant][workload]
            html += f'<tr><td>{workload}</td><td>{variant}</td><td>{r["before_mean"]:,.1f}</td><td>{r["after_mean"]:,.1f}</td><td>{r["before_mean"]-r["after_mean"]:,.1f} ({100*(1-r["after_mean"]/r["before_mean"]):.1f}%)</td><td>{r["after_worst"]:,}</td><td>{r["below_1500"]}/{r["samples"]}</td></tr>'
    html += '</table></div><p>The replay includes five dead-camera samples. Budget attainment remains poor: trees alone cannot bring the whole scene to 1,500. Repacking is restricted to trees and uses separate spatial batches per tree; measured changes include that batching change as well as mesh simplification.</p>'
    control = json.loads((OUT / 'control/measurements.json').read_text())
    html += f'<p>A no-geometry-change tree-batching control gives means of {control["replay"]["after_mean"]:,.1f} replay loads and {control["photos"]["after_mean"]:,.1f} route loads. Relative to that control, the lean meshes save another {control["replay"]["after_mean"]-measurements["lean"]["replay"]["after_mean"]:,.1f} and {control["photos"]["after_mean"]-measurements["lean"]["photos"]["after_mean"]:,.1f} loads, respectively. Expanded control tree faces match every original position, color, winding and continuous UV coordinate. <a href="control-preservation.json">Control preservation</a> · <a href="control/measurements.json">Control counts</a>.</p>'
    tree_costs = json.loads((OUT / 'tree-costs.json').read_text())['lean']
    html += f'<p>Tree-only work: replay {tree_costs["replay"]["tree_before"]:,.1f} → {tree_costs["replay"]["tree_after"]:,.1f} loads (−{tree_costs["replay"]["tree_reduction_percent"]:.1f}%); photo route {tree_costs["photos"]["tree_before"]:,.1f} → {tree_costs["photos"]["tree_after"]:,.1f} (−{tree_costs["photos"]["tree_reduction_percent"]:.1f}%). This attribution uses the prior exact per-material census and subtracts the unchanged non-tree submissions.</p>'
    if (OUT / 'timing-summary.json').exists():
        timing = json.loads((OUT / 'timing-summary.json').read_text())
        html += '<h2>Fresh Ares timing</h2><div class="scroll"><table><tr><th>Workload</th><th>Before FPS</th><th>Lean FPS</th><th>Change</th><th>P95 before → after</th></tr>'
        for label, t in timing.items():
            html += f'<tr><td>{label}</td><td>{t["before_fps"]:.2f}</td><td>{t["after_fps"]:.2f}</td><td>{t["gain_percent"]:+.1f}%</td><td>{t["before_p95_ms"]} → {t["after_p95_ms"]} ms</td></tr>'
        html += '</table></div><p>75-second NTSC samples after one-second warmup, Expansion Pak enabled, LTO, three surfaces and 32 KiB queues. Quiet native fresh-pose counters; no concurrent builds or image rendering. Separate single-player walking and four-player replay workloads. Four-player baseline and candidate repeat; the single-player result is one fresh pair. <a href="timing.json">Exact timing records</a> · <a href="timing-summary.json">Summary and scope</a>. Ares results are not physical-console validation.</p>'
        html += '<p><a href="one-baseline-native.png">Single-player baseline screen</a> · <a href="one-candidate-native.png">Single-player candidate screen</a> · <a href="four-baseline-native.png">Four-player baseline screen</a> · <a href="four-candidate-native.png">Four-player candidate screen</a> · <a href="four-candidate-repeat-native.png">Repeated candidate screen</a></p>'
    else:
        html += '<p><b>No new native FPS measurements yet.</b> Submission-count gains are not automatically equivalent to frame-rate gains.</p>'
    html += '<h2>Tree shape from ten matched angles</h2><p>Two sizes, eight horizontal directions plus two elevated views. Each comparison shares the exact original-centered camera and original packed textures/material alpha modes. RGB difference is amplified ×6. Silhouette uses occupied pixels: gray overlap, cyan source only, orange candidate only. Alpha foliage intentionally changes coverage, so IoU is diagnostic rather than an acceptance score.</p><div class="viewer"><select id="assetTree"></select><select id="assetAngle"></select><select id="assetVariant"><option value="lean">Lean</option><option value="medium">Medium</option></select><div class="pair"><div>Original<img id="assetBefore"></div><div>Candidate<img id="assetAfter"></div></div><p id="assetMetrics"></p><select id="assetMode"><option value="difference">RGB difference ×6</option><option value="silhouette">Silhouette coverage</option></select><br><img id="assetFilter"></div>'
    data = []
    for record in assets:
        prefix = f'{record["species"]}-{record["angle"]:02}'
        variant = record['variant']
        paths = dict(before=f'{prefix}-source.png', after=f'{prefix}-{variant}.png', difference=f'{prefix}-{variant}-difference.png', silhouette=f'{prefix}-{variant}-silhouette.png')
        data.append({**record, 'paths': {k: data_image(OUT / 'assets' / p) for k, p in paths.items()}})
    html += '<script>(()=>{const data='+json.dumps(data)+';const $=id=>document.getElementById(id);for(const x of [0,1])$("assetTree").add(new Option(x?"Small snow pine":"Large snow pine",x));for(let x=0;x<10;x++)$("assetAngle").add(new Option(x<8?`${x*45}° horizontal`:`Elevated ${x-7}`,x));function update(){const r=data.find(r=>r.species==$("assetTree").value&&r.angle==$("assetAngle").value&&r.variant==$("assetVariant").value);$("assetBefore").src=r.paths.before;$("assetAfter").src=r.paths.after;$("assetFilter").src=r.paths[$("assetMode").value];$("assetMetrics").textContent=`${r.before_triangles} → ${r.after_triangles} triangles; occupied-pixel IoU ${r.silhouette_iou.toFixed(4)}; coverage ${r.source_coverage_pixels} → ${r.candidate_coverage_pixels} pixels.`;}for(const id of ["assetTree","assetAngle","assetVariant","assetMode"])$(id).onchange=update;update();})();</script>'
    html += '<h2>Same 24-camera player photo route</h2><p>Exact SDK matrices, standing/crouched states, view angles and full player bytes are saved with the fixtures. These are offline perspective packed-map renders; no native fog, HUD, dynamic objects or RSP/RDP rounding. Displayed at 4:3. Both candidates also receive a visibility-on versus visibility-off pixel control.</p>'
    for variant in ('lean', 'medium'):
        shared.OUT = OUT / variant
        photos = json.loads((shared.OUT / 'player-photos.json').read_text())['photos']
        html += '<h3>'+variant.title()+'</h3><div class="world">'+shared.gallery(variant+'Photo', photos, 'player-photos', 'photo', lambda r:f'{r["photo"]:02} {r["label"]}')+'</div>'
        html += f'<p>Visibility control: {sum(r["pvs_control_changed_pixels"] for r in photos)} differing pixels across all 24 views.</p>'
    html += '<h2>Preservation and review files</h2><p>All 381 non-tree batches retain exact vertex/index bytes, bounds, materials and relative order. All 20 non-render sections—including collision, placements and textures—are byte-identical. New tree batches retain the existing alpha-tested, depth-writing material modes and conservatively fail open for PVS. Original material/pass placement is validated; depth-writing trees precede transparent scenery. The corrected candidate has zero RDP errors and warnings in the sampled native four-camera source-start inspection with 8 KiB validation queues. <a href="rdp-validation-native.png">Native validation screen</a> · <a href="rdp-validation.log">Validation log</a>. No changes are adopted into the canonical map.</p><p><a href="tree-appraisal.blend">Blender scene</a> · <a href="asset-contact.png">Three-version contact sheet</a> · <a href="asset-metrics.json">Asset cameras and pixel metrics</a> · <a href="source-models.json">Source meshes and placements</a> · <a href="authored-models.json">Blender-exported candidates</a> · <a href="validation.json">Validation summary</a> · <a href="lean/measurements.json">Lean measurements</a> · <a href="medium/measurements.json">Medium measurements</a> · <a href="lean/photos/poses.json">Exact photo poses</a> · <a href="lean/replay/cameras.csv">Lean replay counts</a> · <a href="lean/photos/cameras.csv">Lean route counts</a> · <a href="lean/packing-report.json">Lean packing proof</a></p></html>'
    (OUT / 'comparison.html').write_text(html)
    print('Wrote', OUT / 'comparison.html')


if __name__ == '__main__':
    import sys
    if sys.argv[1:] == ['assets']:
        assets()
    elif sys.argv[1:] and sys.argv[1] == 'photos':
        world_photos(sys.argv[2])
    elif sys.argv[1:] == ['timings']:
        timings()
    else:
        report()
