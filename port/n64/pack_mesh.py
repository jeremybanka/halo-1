"""Bounded color welding and Tiny3D indexed batches.

Static models may reorder independent triangles for vertex reuse; overlapping
coplanar faces retain their original precedence. Animated/default callers keep
the complete original order.

Only coincident positions, identical materials and team masks and (for animated
meshes) identical full motion trajectories may share a vertex. The first
corner's RGB is retained, and every joining corner must remain inside that
model's audited per-channel bound. Terrain uses its separate, stricter packer.
"""
import math
from collections import defaultdict
from pack_animation import compact_clip

MODEL_COLOR_TOLERANCE = 48

# Reviewed against the highest source and approved models in all eight audit
# directions, including native-size views. Unknown models fail closed until
# their color regions have been reviewed. The optional PC assets retain24.
MODEL_COLOR_TOLERANCES = {
    'world': {
        'ar': 48, 'pistol': 48, 'plasma_pistol': 48, 'plasma_rifle': 48,
        'needler': 48, 'shotgun': 48, 'sniper': 48, 'rocket': 48,
        'warthog': 48, 'ghost': 24, 'scorpion': 48, 'banshee': 48,
        'warthog_lod': 48, 'ghost_lod': 24, 'scorpion_lod': 48, 'banshee_lod': 48,
        'spartan': 48, 'spartan_lod': 48,
        'frag': 48, 'plasma_grenade': 48, 'healthpack': 48,
        'overshield': 48, 'camouflage': 48,
        'ar_pickup_lod': 48, 'pistol_pickup_lod': 48,
        'plasma_pistol_pickup_lod': 48, 'plasma_rifle_pickup_lod': 48,
        'needler_pickup_lod': 48, 'shotgun_pickup_lod': 48,
        'sniper_pickup_lod': 48, 'rocket_pickup_lod': 48,
        'frag_pickup_lod': 48, 'plasma_grenade_pickup_lod': 48,
        'healthpack_pickup_lod': 48, 'overshield_pickup_lod': 48,
        'camouflage_pickup_lod': 48,
        'flamethrower': 24, 'flamethrower_pickup_lod': 24,
    },
    'firstperson': {
        'ar': 48, 'pistol': 48, 'plasma_pistol': 48, 'plasma_rifle': 48,
        'needler': 48, 'shotgun': 48, 'sniper': 48, 'rocket': 32,
        'flamethrower': 24,
    },
}


def model_color_tolerance(bank, name):
    """Ghost texture markings and the FP rocket's copper housing need less weld."""
    return MODEL_COLOR_TOLERANCES[bank][name]


def trajectory_keys(clips, scale):
    """Exact identities for every quantized pose across all supplied clips."""
    packed = [compact_clip(clip, scale) for clip in clips.values()]
    count = packed[0]['vertices']
    assert all(clip['vertices'] == count for clip in packed)
    return [tuple(clip['indices'][i] for clip in packed) for i in range(count)]


def remap_clip(clip, sources):
    return {**clip, 'frames': [[frame[source] for source in sources]
                              for frame in clip['frames']]}


def indexed_mesh(positions, colors, team_mask, motion_keys=None, segments=None,
                 color_tolerance=MODEL_COLOR_TOLERANCE, reorder_static=False,
                 material_keys=None):
    """Pack exact geometry and return original triangle IDs in draw order.

    ``colors`` in the result stays indexed by original source corner;
    ``triangle_order`` describes the emitted index stream and preview order.
    ``sources`` maps packed vertices back to immutable source corners.
    """
    assert len(positions) == len(colors) == len(team_mask)
    assert len(positions) % 3 == 0 and 0 <= color_tolerance <= MODEL_COLOR_TOLERANCE
    if material_keys is None:
        material_keys = [0] * len(positions)
    assert len(material_keys) == len(positions)
    if motion_keys is not None:
        assert len(motion_keys) == len(positions)
    if segments is None:
        segments = [(0, len(positions))]
    assert [i for first, count in segments for i in range(first, first + count)] == list(range(len(positions)))
    if reorder_static:
        assert motion_keys is None, 'Animated meshes must retain their original order'
        return _indexed_static(positions, colors, team_mask, segments,
                               color_tolerance, material_keys)
    output = {'vertices': [], 'sources': [], 'indices': [], 'batches': [],
              'segments': [], 'colors': [None] * len(colors),
              'triangle_order': list(range(len(positions) // 3))}
    for segment_first, segment_count in segments:
        batch_start = len(output['batches'])
        local_vertices, local_sources, local_indices, groups = [], [], [], {}

        def flush():
            if not local_indices:
                return
            first = len(output['vertices'])
            index_first = len(output['indices'])
            # Each T3DVertPacked holds two vertices. Padding also participates
            # in motion scatter, using an existing exact trajectory.
            if len(local_vertices) % 2:
                local_vertices.append(local_vertices[-1])
                local_sources.append(local_sources[-1])
            assert len(local_vertices) <= 60 and len(local_indices) <= 120
            output['vertices'].extend(local_vertices)
            output['sources'].extend(local_sources)
            output['indices'].extend(local_indices)
            output['batches'].append((first, len(local_vertices), index_first, len(local_indices)))
            while len(output['indices']) % 4:
                output['indices'].append(0)

        for triangle in range(segment_first, segment_first + segment_count, 3):
            while True:
                trial_vertices = list(local_vertices)
                trial_sources = list(local_sources)
                trial_groups = {key: list(value) for key, value in groups.items()}
                triangle_indices = []
                for source in range(triangle, triangle + 3):
                    key = (tuple(positions[source]), team_mask[source], material_keys[source],
                           motion_keys[source] if motion_keys is not None else None)
                    candidates = trial_groups.get(key, [])
                    rgb = colors[source]
                    matches = [index for index in candidates
                               if max(abs(a-b) for a,b in zip(rgb,trial_vertices[index][1])) <= color_tolerance]
                    if matches:
                        index = min(matches, key=lambda i: sum((a-b)**2 for a,b in zip(rgb,trial_vertices[i][1])))
                    else:
                        index = len(trial_vertices)
                        trial_vertices.append((positions[source], rgb, team_mask[source]))
                        trial_sources.append(source)
                        trial_groups.setdefault(key, []).append(index)
                    triangle_indices.append(index)
                if ((len(trial_vertices) + 1) & ~1) <= 60 and len(local_indices) + 3 <= 120:
                    local_vertices, local_sources, groups = trial_vertices, trial_sources, trial_groups
                    local_indices.extend(triangle_indices)
                    for source, index in zip(range(triangle, triangle + 3), triangle_indices):
                        output['colors'][source] = local_vertices[index][1]
                    break
                assert local_indices, 'A triangle must fit an empty batch'
                flush()
                local_vertices, local_sources, local_indices, groups = [], [], [], {}
        flush()
        output['segments'].append((batch_start, len(output['batches']) - batch_start))
    _verify_mesh(output, positions, colors, team_mask, motion_keys, color_tolerance, material_keys)
    return output


def _verify_mesh(output, positions, colors, team_mask, motion_keys, color_tolerance, material_keys):
    assert sorted(output['triangle_order']) == list(range(len(positions) // 3))
    # Verify exact geometry, mask and animation source identity through the
    # actual emitted triangle index stream, including batch boundaries.
    corner = 0
    for first, count, index_first, index_count in output['batches']:
        assert first % 2 == 0 and index_first % 4 == 0
        for index in output['indices'][index_first:index_first + index_count]:
            assert 0 <= index < count
            vertex = first + index
            source = output['sources'][vertex]
            original = output['triangle_order'][corner // 3] * 3 + corner % 3
            assert positions[original] == output['vertices'][vertex][0]
            assert team_mask[original] == output['vertices'][vertex][2]
            assert material_keys[original] == material_keys[source]
            assert max(abs(a-b) for a,b in zip(colors[original],output['vertices'][vertex][1])) <= color_tolerance
            if motion_keys is not None:
                assert motion_keys[original] == motion_keys[source]
            corner += 1
    assert corner == len(positions)



def emit_batches(lines, name, packed):
    lines.append(f'static int16_t {name}_indices[] __attribute__((aligned(8)))={{' +
                 ','.join(map(str, packed['indices'])) + '};')
    lines.append(f'static const bg_mesh_batch {name}_batches[]={{')
    lines.extend('{' + ','.join(map(str, batch)) + '},' for batch in packed['batches'])
    lines.append('};')


def _canonicalize(pos,rgb,mask,first,count,tolerance,materials):
    vertices=[];groups=defaultdict(list);ids=[];sources=[]
    for i in range(first,first+count):
        key=(tuple(pos[i]),mask[i],materials[i]);matches=[j for j in groups[key] if max(abs(a-b) for a,b in zip(rgb[i],vertices[j][1]))<=tolerance]
        if matches:j=min(matches,key=lambda j:sum((a-b)**2 for a,b in zip(rgb[i],vertices[j][1])))
        else:
            j=len(vertices);vertices.append((pos[i],rgb[i],mask[i]));sources.append(i);groups[key].append(j)
        ids.append(j)
    return vertices,sources,[tuple(ids[i:i+3]) for i in range(0,len(ids),3)]

def _coplanar_predecessors(vertices,tris):
    """Keep source draw order wherever quantized coplanar interiors overlap."""
    planes=defaultdict(list);predecessors=[set() for _ in tris]
    def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
    def overlap(a,b):
        for poly in (a,b):
            for i in range(3):
                p,q=poly[i],poly[(i+1)%3];axis=(q[1]-p[1],p[0]-q[0])
                if not any(axis):continue
                aa=[x*axis[0]+y*axis[1] for x,y in a];bb=[x*axis[0]+y*axis[1] for x,y in b]
                if max(aa)<=min(bb) or max(bb)<=min(aa):return False
        return True
    for i,t in enumerate(tris):
        pts=[vertices[v][0] for v in t];a,b,c=pts
        n=cross([b[j]-a[j] for j in range(3)],[c[j]-a[j] for j in range(3)])
        if not any(n):continue
        plane=(*n,-sum(n[j]*a[j] for j in range(3)));g=math.gcd(*plane);plane=tuple(v//g for v in plane)
        if next(v for v in plane if v) < 0:plane=tuple(-v for v in plane)
        axis=max(range(3),key=lambda j:abs(n[j]));flat=[tuple(p[j] for j in range(3) if j!=axis) for p in pts]
        for previous,other in planes[plane]:
            if overlap(flat,other):predecessors[i].add(previous)
        planes[plane].append((i,flat))
    return predecessors

def _order_triangles(tris,mode,vertices):
    if mode=='global_order':return list(range(len(tris)))
    predecessors=_coplanar_predecessors(vertices,tris)
    mode=mode.removesuffix('_safe')
    remaining=set(range(len(tris)));sets=[set(t) for t in tris];adj=defaultdict(set)
    for i,t in enumerate(sets):
        for v in t:adj[v].add(i)
    live={v:len(ts) for v,ts in adj.items()};order=[];batch=set();batch_tris=0;frontier=set()
    while remaining:
        candidates=(frontier&remaining) if batch else set()
        def score(i):
            new=len(sets[i]-batch)
            # Exhaust low-valence adjacency before jumping to another surface.
            return (new,sum(live[v] for v in sets[i]),i)
        fits=[i for i in candidates if not(predecessors[i]&remaining) and ((len(batch|sets[i])+1)&~1)<=60]
        if not fits:
            fits=[i for i in remaining if not(predecessors[i]&remaining) and ((len(batch|sets[i])+1)&~1)<=60]
        if batch_tris>=40 or not fits:
            batch=set();batch_tris=0;frontier=set();continue
        if not batch and mode=='greedy_source':i=min(fits)
        elif not batch and mode=='greedy_high':i=min(fits,key=lambda i:(-sum(live[v] for v in sets[i]),i))
        else:i=min(fits,key=score)
        remaining.remove(i);order.append(i);batch|=sets[i];batch_tris+=1
        for v in sets[i]:live[v]-=1;frontier|=adj[v]
    return order

def _pack_canonical(segments,mode):
    output={'vertices':[],'sources':[],'indices':[],'batches':[],'segments':[],'order':[],'colors':[]}
    for base,(vertices,sources,tris) in segments:
        order=_order_triangles(tris,mode,vertices);at=len(output['batches']);local={};local_ids=[];indices=[];tri_order=[]
        def flush():
            if not indices:return
            start=len(output['vertices']);ii=len(output['indices']);vv=[vertices[i] for i in local_ids];ss=[sources[i] for i in local_ids]
            if len(vv)%2:vv.append(vv[-1]);ss.append(ss[-1])
            assert len(vv)<=60 and len(indices)<=120
            output['vertices'].extend(vv);output['sources'].extend(ss);output['indices'].extend(indices)
            output['batches'].append((start,len(vv),ii,len(indices)))
            while len(output['indices'])%4:output['indices'].append(0)
            output['order'].extend([base+i for i in tri_order])
            output['colors'].extend([vertices[v][1] for i in tri_order for v in tris[i]])
        for i in order:
            add=set(tris[i])-set(local)
            if ((len(local)+len(add)+1)&~1)>60 or len(indices)+3>120:
                flush();local={};local_ids=[];indices=[];tri_order=[]
            for v in tris[i]:
                if v not in local:local[v]=len(local);local_ids.append(v)
                indices.append(local[v])
            tri_order.append(i)
        flush();output['segments'].append((at,len(output['batches'])-at))
    return output


def _indexed_static(positions, colors, team_mask, segments, color_tolerance, material_keys):
    # Canonical representatives always come from immutable source colors.
    # This prevents tolerance from chaining through already modified batches.
    canonical = [(first // 3, _canonicalize(positions, colors, team_mask,
                                          first, count, color_tolerance, material_keys))
                 for first, count in segments]
    # Stable source-, low-valence- and high-valence seeds have complementary
    # behavior on disconnected colored surfaces. Keep the least expensive
    # valid result, including a non-reordered fallback.
    candidates = [_pack_canonical(canonical, mode) for mode in
                  ('global_order', 'greedy_source_safe',
                   'greedy_low_safe', 'greedy_high_safe')]
    cost = lambda mesh: (len(mesh['vertices']), len(mesh['batches']))
    baseline = indexed_mesh(positions, colors, team_mask, segments=segments,
                            color_tolerance=color_tolerance, material_keys=material_keys)
    candidates = [mesh for mesh in candidates
                  if len(mesh['batches']) <= len(baseline['batches'])]
    if not candidates:
        return baseline
    result = min(candidates, key=cost)
    if cost(baseline) <= cost(result):
        return baseline
    original_colors = [None] * len(colors)
    for corner, rgb in enumerate(result['colors']):
        original = result['order'][corner // 3] * 3 + corner % 3
        original_colors[original] = rgb
    result['colors'] = original_colors
    result['triangle_order'] = result.pop('order')
    _verify_mesh(result, positions, colors, team_mask, None, color_tolerance, material_keys)
    offset = 0
    for first, count in segments:
        actual = result['triangle_order'][offset:offset + count // 3]
        assert sorted(actual) == list(range(first // 3, (first + count) // 3))
        offset += count // 3
    return result
