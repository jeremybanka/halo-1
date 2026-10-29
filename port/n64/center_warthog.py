"""Center the isolated upright windscreen fixture, preserving every face/UV.

Find it by connected component and its relationship to the glass, rather than
depending on triangle ordering. The micro mesh already omits this tiny part.
"""
from collections import defaultdict


def center_fixture(model):
    triangles = model['triangles']
    glass_material = next(i for i, m in enumerate(model['material_metadata'])
                          if m['path'].endswith('windshield'))
    glass = [p for t in triangles if t['material'] == glass_material for p in t['p']]
    bounds = [(min(p[a] for p in glass), max(p[a] for p in glass)) for a in range(3)]
    width = bounds[1][1] - bounds[1][0]
    axis = sum(bounds[1]) / 2
    key = lambda p: tuple(round(x, 6) for x in p)
    at = defaultdict(list)
    for i, t in enumerate(triangles):
        if t['material'] == glass_material:
            continue
        for p in t['p']:
            at[(t['material'], key(p))].append(i)
    unseen = {i for ids in at.values() for i in ids}
    candidates = []
    while unseen:
        first = unseen.pop()
        component, todo = {first}, [first]
        while todo:
            t = triangles[todo.pop()]
            for p in t['p']:
                for i in at[t['material'], key(p)]:
                    if i in unseen:
                        unseen.remove(i)
                        component.add(i)
                        todo.append(i)
        if len(component) != 2:
            continue
        points = [p for i in component for p in triangles[i]['p']]
        b = [(min(p[a] for p in points), max(p[a] for p in points)) for a in range(3)]
        if (b[0][0] > sum(bounds[0]) / 2 and b[0][1] > bounds[0][1]
                and b[2][0] < bounds[2][0] < b[2][1] < bounds[2][1]
                and b[1][1] - b[1][0] < width / 2
                and abs(sum(b[1]) / 2 - axis) < width / 4):
            candidates.append((sorted(component), axis - sum(b[1]) / 2))
    assert len(candidates) == 1, ('Expected one windscreen fixture', candidates)
    faces, delta = candidates[0]
    for i in faces:
        triangles[i]['p'] = [[x, y + delta, z] for x, y, z in triangles[i]['p']]
    return {'faces': faces, 'lateral_translation': delta, 'windshield_center': axis}
