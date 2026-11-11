"""Close local garment rims using their existing weighted contour vertices.

No positional weld crosses a skin-channel boundary. The ledger retains every
unclosed branch and all new return faces; the independent pose/depth audits are
still required. Large torso perimeters are left open deliberately.
"""
import argparse, copy, hashlib, json, sys
from collections import defaultdict
from pathlib import Path
import bpy, numpy as np
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
sys.path.insert(0, str(Path(__file__).resolve().parent))
from demake_gungnir import bake


def close(triangles, component):
    selected = [t for t in triangles if t['component'] == component]
    corners = []; lookup = {}; faces = []; edges = defaultdict(list)
    for t in selected:
        face = []
        for i, (p, ws) in enumerate(zip(t['p'], t['weights'])):
            key = tuple(round(x, 7) for x in p), tuple(sorted((b, round(w, 6)) for b, w in ws))
            if key not in lookup:
                lookup[key] = len(corners); corners.append((t, i))
            face.append(lookup[key])
        faces.append(face)
        for a, b in zip(face, face[1:] + face[:1]):
            edges[tuple(sorted((a, b)))].append((a, b))
    boundary = {es[0] for es in edges.values() if len(es) == 1}
    result = []; records = []
    while boundary:
        first = min(boundary); boundary.remove(first); loop = list(first)
        while loop[-1] != loop[0] and len(loop) <= len(corners):
            options = sorted(e for e in boundary if e[0] == loop[-1])
            if len(options) != 1: break
            edge = options[0]; boundary.remove(edge); loop.append(edge[1])
        closed = loop[-1] == loop[0]
        if closed: loop.pop()
        points = np.array([corners[i][0]['p'][corners[i][1]] for i in loop])
        span = np.ptp(points, axis=0)
        limit = .135 if component == 'garment-pelvis' else .065
        eligible = closed and len(loop) >= 3 and span.max() <= limit
        record = dict(component=component, vertices=len(loop), closed=closed,
                      span_halo_units=span.tolist(), added_triangles=0)
        if eligible:
            order = loop[::-1]; vectors = [Vector(corners[i][0]['p'][corners[i][1]]) for i in order]
            by_point = {tuple(p): i for p, i in zip(vectors, order)}
            for triangle in tessellate_polygon([vectors]):
                ids = [order[p] if isinstance(p, int) else by_point[tuple(p)] for p in triangle]
                donor = [corners[i] for i in ids]; tri = copy.deepcopy(donor[0][0])
                for field in ('p', 'weights', 'uv', 'source_faces'):
                    tri[field] = [copy.deepcopy(t[field][i]) for t, i in donor]
                if np.linalg.norm(np.cross(np.subtract(tri['p'][1],tri['p'][0]), np.subtract(tri['p'][2],tri['p'][0]))) < 1e-10: continue
                tri['construction'] = 'local return tessellated through the exact existing rim and native skin channels'
                tri['local_boundary_return'] = True
                result.append(tri); record['added_triangles'] += 1
        records.append(record)
    return result, records


def run(source, motion, candidate, output):
    source, motion, candidate, output = map(Path, (source,motion,candidate,output)); output.mkdir(parents=True,exist_ok=True)
    model = json.loads(source.read_text()); data = json.loads((candidate/'solid.json').read_text()); ledger=[]
    for lod, item in enumerate(data['lods']):
        triangles=item['triangles']; patches=[]
        for name in sorted({t['component'] for t in triangles}):
            if name.startswith('garment-') or name in ('torso','torso-back'):
                added, records=close(triangles,name); patches.extend(added); ledger.extend(dict(lod=lod,**r) for r in records)
        triangles.extend(patches)
        frames, clips=bake(model,triangles,motion); np.savez_compressed(output/f'poses-{lod}.npz',**frames);item['animations']=clips
    data['local_boundary_returns']=ledger;data['return_parent_sha256']=hashlib.sha256((candidate/'solid.json').read_bytes()).hexdigest();data['publication_approved']=False
    (output/'solid.json').write_text(json.dumps(data,separators=(',',':'))+'\n')
    (output/'boundary-returns.json').write_text(json.dumps(ledger,indent=2)+'\n')
    print('RETURNS', [sum(r['added_triangles'] for r in ledger if r['lod']==l) for l in range(2)],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('motion');p.add_argument('candidate');p.add_argument('output');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run(a.source,a.motion,a.candidate,a.output)
