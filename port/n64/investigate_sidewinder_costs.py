"""Attribute matched cluster-terrain submissions to source BSP and scenery.

Reuses the completed study's generated camera drivers, visibility data and
vehicle solver. Source IDs distinguish scenery even when its shader is shared
with architecture. Counts are vertex loads, including batch duplicates/padding.
"""
import collections
import csv
import hashlib
import html
import json
import os
from pathlib import Path
import statistics
import struct
import subprocess

from remap_sidewinder_visibility import batches, sections

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / 'build/n64-sidewinder-cluster-terrain'
OUT = ROOT / 'build/n64-sidewinder-cost-breakdown'
SDK = ROOT.parent / 'n64-3d-splitscreen/.build/tiny3d/src'


def attribution():
    bank = (STUDY/'candidate-maps/sidewinder.map64').read_bytes()
    original = (ROOT/'halo64-assets/generated/maps/sidewinder.map64').read_bytes()
    proof = json.loads((STUDY/'data/batch-memberships.json').read_text())
    source = json.loads((ROOT/'build/n64-visibility-rollout/sidewinder/data/visibility.json').read_text())
    assert hashlib.sha256(bank).hexdigest() == proof['candidate_map_sha256']
    assert hashlib.sha256(original).hexdigest() == proof['baseline_map_sha256'] == source['map_sha256']
    old, new = list(batches(original)), list(batches(bank))
    ss = sections(bank)
    result = []
    for b, (material, identity, triangles) in enumerate(new):
        count = identity[0]; loads = (count+1)&~1
        c = struct.unpack_from('>IHH6hHH', ss[1], b*24)
        indices = struct.unpack_from('>'+str(c[-1])+'H', ss[2], c[-2]*2)
        membership = proof['batches'][b]
        if material in (7, 8):
            assert 'old_chunk' not in membership
            portions = {'terrain': loads}
            tri_counts = {'terrain': len(triangles)}
        else:
            old_id = membership['old_chunk']
            assert old[old_id][1] == identity
            ids = source['chunk_source_ids'][old_id]
            assert len(ids) == len(triangles)
            vertices = collections.defaultdict(set)
            tri_counts = collections.Counter()
            for t, source_id in enumerate(ids):
                category = 'scenery' if source_id < 0 else ('terrain' if material == 9 else 'structures')
                vertices[category].update(indices[t*3:t*3+3])
                tri_counts[category] += 1
            # The four mixed batches have disjoint indices and no padding.
            assert sum(map(len, vertices.values())) == count
            if len(vertices) == 1:
                portions = {next(iter(vertices)): loads}
            else:
                assert count == loads
                portions = {k: len(v) for k, v in vertices.items()}
        assert sum(portions.values()) == loads
        result.append({'material': material, 'loads': portions, 'triangles': dict(tri_counts)})
    return result


def measure(name, directory, attributed):
    output = OUT/name; output.mkdir(parents=True, exist_ok=True)
    driver = (directory/'camera.c').read_text()
    # Instrument inside the original post-frustum/post-PVS submission loop.
    anchor = '   c[candidate].chunks++;'
    assert driver.count(anchor) == 1
    driver = driver.replace(anchor, '   if(bg_map_id()==1)fprintf(stderr,"%u,%u,%u,%u,%u,%u\\n",tick,p,candidate,b,k->material,(k->count+1)&~1u);\n'+anchor)
    if name == 'replay':
        import re
        driver, n = re.subn(r'const unsigned maps\[\]=\{[^}]+\};', 'const unsigned maps[]={1};', driver)
        assert n == 1
    (output/'camera.c').write_text(driver)
    solver = STUDY/'cameras/solver'
    sources = ['map.c','game.c','combat_geometry.c','terrain.c','movement.c','blam/runtime.c','blam/core.c','blam/vehicle_physics.c','replay.c','render_pvs.c']
    generated = ['combat_data.c','movement_data.c','interaction_defs.c','camera_data.c']
    flags = ['-std=c17','-O2','-g','-fsanitize=address,undefined','-ffp-contract=off','-fno-fast-math','-fno-strict-aliasing','-fwrapv','-Wno-multichar','-Wno-unused-function','-Wno-incompatible-pointer-types','-DBG_STREAM_MAPS','-DBG_BODY_CANDIDATES', '-I'+str(directory),'-I'+str(SDK),'-Iport/n64','-Ibuild/n64/blam-core','-I'+str(solver)]
    flags.append('-I'+str(STUDY/'cameras'))  # Shared libdragon host shim.
    cmd = ['clang', *flags, str(output/'camera.c'), str(directory/'visibility-data.c'), str(SDK/'t3d/t3dmath.c'), *(str(ROOT/'port/n64'/s) for s in sources), *(str(ROOT/'build/n64/generated'/s) for s in generated), str(ROOT/'halo64-assets/generated/maps/common_data.c'), str(solver/'vehicle_data.c'), '-lm','-o',str(output/'probe')]
    subprocess.run(cmd, cwd=ROOT, check=True)
    with (output/'submitted-batches.csv').open('w') as trace, (output/'poses.json').open('w') as poses:
        trace.write('tick,camera,candidate,batch,material,vertices\n'); trace.flush()
        subprocess.run([str(output/'probe'), str(output/'cameras.csv')], cwd=ROOT, check=True, stderr=trace, stdout=poses, env={**os.environ,'BG_MAP_DIRECTORY':str(STUDY/'candidate-maps')})
    actual = list(csv.DictReader((output/'cameras.csv').open()))
    expected = [r for r in csv.DictReader((directory/'cameras.csv').open()) if r['map']=='1']
    assert actual == expected, 'Camera poses or aggregate submissions changed'
    grouped = collections.defaultdict(collections.Counter)
    materials = collections.defaultdict(collections.Counter)
    for row in csv.DictReader((output/'submitted-batches.csv').open()):
        key = tuple(int(row[k]) for k in ('tick','camera','candidate'))
        a = attributed[int(row['batch'])]
        assert a['material'] == int(row['material']) and sum(a['loads'].values()) == int(row['vertices'])
        grouped[key].update(a['loads'])
        for category, loads in a['loads'].items(): materials[key][category, a['material']] += loads
    table = []
    for row in actual:
        key = tuple(int(row[k]) for k in ('tick','camera','candidate'))
        costs = {c:grouped[key][c] for c in ('terrain','structures','scenery')}
        assert sum(costs.values()) == int(row['vertices'])
        table.append({**row, **costs})
    with (output/'categories.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
    with (output/'materials.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['tick','camera','candidate','category','material','vertices'])
        for key, costs in materials.items():
            for (category, material), loads in sorted(costs.items()): w.writerow([*key,category,material,loads])
    selected = [r for r in table if r['candidate']=='1']
    summaries = {}
    for label, rows in [('all',selected), ('alive',[r for r in selected if r['alive']=='1'])]:
        summaries[label] = {'samples':len(rows), 'means':{c:statistics.mean(int(r[c]) for r in rows) for c in ('vertices','terrain','structures','scenery')}, 'worst':max(rows,key=lambda r:int(r['vertices'])), 'below_target':sum(int(r['vertices'])<1500 for r in rows)}
    mat_sum = collections.Counter()
    for key, costs in materials.items():
        if key[2]==1: mat_sum.update(costs)
    summaries['material_means'] = [{'category':c,'material':m,'vertices':n/len(selected)} for (c,m),n in mat_sum.most_common()]
    return summaries


def report(result):
    categories = ('terrain','structures','scenery')
    colors = ('#62b6cb','#f5bc67','#b69cfa')
    names = json.loads((ROOT/'halo64-assets/generated/maps/maps-report.json').read_text())['maps']['sidewinder']['materials']
    parts = ['<!doctype html><meta charset="utf-8"><title>Sidewinder submission costs</title><style>body{background:#11151c;color:#e8edf5;font:16px system-ui;max-width:1150px;margin:40px auto;padding:0 20px}h1,h2{color:white}p{line-height:1.6;max-width:950px}table{border-collapse:collapse;width:100%;margin:20px 0}th,td{text-align:right;padding:8px;border-bottom:1px solid #394350}th:first-child,td:first-child{text-align:left}a{color:#8cd6ff}.bar{display:flex;height:28px;margin:8px 0 18px;max-width:100%}.bar span{min-width:1px}small{color:#b6c1d1}details{margin:25px 0}code{color:#c4ddff}</style><h1>Sidewinder: where the vertex loads go</h1>']
    parts.append('<p>Current cluster-aware terrain candidate, conservative visibility enabled. Repeated the exact 68 four-camera replay views and 24 single-player photo views. Every camera pose and aggregate count matches the previous census exactly. These are static-world vertex loads, including vertices repeated for batches and paired padding; dynamic players, vehicles and weapons are excluded. No new FPS or image claims are made.</p>')
    parts.append('<p><b>The remaining cost is mostly architecture and scenery.</b> Removing all terrain would still leave 7,002 loads per replay view on average. The 1,500 target requires an 83.6% average reduction across the remaining submitted world.</p>')
    parts.append('<p>Terrain = source cliffs, snow and ice. Structures = all other source BSP architecture. Scenery = appended source models, identified by source triangle IDs, including scenery sharing a metal shader with architecture. The four mixed batches have disjoint vertex indices and no padding, allowing an exact split. Pure-batch padding belongs to that batch’s category.</p>')
    for dataset,label in [('replay','Four-camera replay'),('photos','Single-player photo route')]:
        summary=result[dataset]['all'];means=summary['means'];n=summary['samples']
        parts.append(f'<h2>{label}</h2><p>{n} matched views; average {means["vertices"]:,.1f} loads; {summary["below_target"]}/{n} below 1,500.</p><div class="bar">')
        for c,color in zip(categories,colors):parts.append(f'<span title="{c}: {means[c]:,.1f}" style="background:{color};width:{100*means[c]/means["vertices"]:.5f}%"></span>')
        parts.append('</div><table><tr><th>Category</th><th>Mean loads</th><th>Share</th></tr>')
        for c,color in zip(categories,colors):parts.append(f'<tr><td style="color:{color}">{c.title()}</td><td>{means[c]:,.1f}</td><td>{100*means[c]/means["vertices"]:.1f}%</td></tr>')
        parts.append('</table><details><summary>Material breakdown</summary><table><tr><th>Source material</th><th>Category</th><th>Mean loads</th></tr>')
        for row in result[dataset]['material_means']:
            material=names[row['material']].replace('\\',' / ')
            parts.append(f'<tr><td>{html.escape(material)}</td><td>{row["category"]}</td><td>{row["vertices"]:,.1f}</td></tr>')
        parts.append('</table></details>')
        rows=[r for r in csv.DictReader((OUT/dataset/'categories.csv').open()) if r['candidate']=='1']
        parts.append('<details><summary>Every matched camera, ordered by cost</summary><table><tr><th>Tick / photo</th><th>Camera (0–3)</th><th>Alive</th><th>Terrain</th><th>Structures</th><th>Scenery</th><th>Total</th></tr>')
        for row in sorted(rows,key=lambda r:int(r['vertices']),reverse=True):
            parts.append('<tr>'+''.join(f'<td>{row[k]}</td>' for k in ('tick','camera','alive','terrain','structures','scenery','vertices'))+'</tr>')
        parts.append(f'</table></details><p><a href="{dataset}/categories.csv">Full camera/category CSV</a> · <a href="{dataset}/materials.csv">Per-camera material CSV</a></p>')
    parts.append('<h2>What reaching 1,500 entails</h2><p>The first architecture target is <code>metal flat generic</code>: 2,605 loads/view in the replay, 64% of architecture. Investigate simpler render meshes for these surfaces while retaining silhouettes, openings and collision. A shader name alone does not establish that all its surfaces are flat or safely collapsible.</p><p>Tree needles cost 1,708 loads/view in the replay and 2,576 on the photo route. Needles plus bark are the largest scenery target. Simplified near trees and much cheaper distant tree meshes are stronger candidates than spending the next pass on small fixtures. Rocks cost 315 replay loads/view and 567 photo loads/view; cliffs and snow still cost 2,017 replay loads/view combined.</p><p>For scale, a hypothetical 80% terrain reduction plus 85% cuts to both architecture and scenery gives a replay mean of 1,478 loads. It still leaves the worst replay view at 3,200 and the photo-route mean at 1,692. These are arithmetic scenarios, not demonstrated mesh quality or measured performance. Distance-dependent detail and visibility must constrain the expensive views; an average budget alone cannot ensure 1,500 for every camera.</p><p>Current worst replay view (tick 600, camera 2): terrain 4,150; structures 9,040; scenery 6,762; total 19,952. Reaching 1,500 there requires 92.5% fewer loads. The replay’s 68-view mean includes five dead-camera samples; the 63 alive views average 9,565, with the same category ranking.</p>')
    parts.append(f'<p><small>Map SHA-256: {result["bank_sha256"]}<br>Source commit: {result["source_commit"]}. Host probes use AddressSanitizer/UndefinedBehaviorSanitizer and the original SDK camera/frustum math. Aggregate counts have the preceding study’s native corroboration; category attribution is host instrumentation.</small></p><p><a href="results.json">Machine-readable summary</a> · <a href="../n64-sidewinder-cluster-terrain/comparison.html">Previous photos, differences and performance</a></p>')
    (OUT/'comparison.html').write_text('\n'.join(parts)+'\n')


if __name__ == '__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    a = attribution()
    (OUT/'batch-attribution.json').write_text(json.dumps(a,indent=2)+'\n')
    result = {'scope':'Exact static-world paired vertex loads, with repeated batch vertices and padding. Dynamic objects excluded. Same camera/PVS code; every aggregate row and pose must equal the completed study. Terrain=cliffs/snow/ice; structures=other source BSP; scenery=appended source models, identified by source IDs.', 'bank_sha256':hashlib.sha256((STUDY/'candidate-maps/sidewinder.map64').read_bytes()).hexdigest(), 'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()}
    for name, directory in [('replay',STUDY/'cameras'),('photos',STUDY/'after-census')]:
        result[name] = measure(name,directory,a)
    (OUT/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    report(result)
    print(json.dumps(result,indent=2))
