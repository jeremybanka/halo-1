"""Deterministic source-vertex support hulls for optional tiny far models.

These are approximations at a separately audited screen-size gate. A convex
hull must never be described as preserving holes or concave surfaces.
"""
import itertools
import numpy as np


def hull(points):
    """Triangulate supporting planes, with inward winding for CULL_FRONT."""
    points = np.asarray(points, dtype=float)
    if len(points) < 4 or np.linalg.matrix_rank(points-points[0], tol=1e-12) < 3:
        raise ValueError('Support hull requires non-coplanar source geometry')
    equations = {}
    for i, j, k in itertools.combinations(range(len(points)), 3):
        normal = np.cross(points[j] - points[i], points[k] - points[i])
        length = np.linalg.norm(normal)
        if length < 1e-12:
            continue
        normal /= length
        distance = normal @ points[i]
        offsets = points @ normal - distance
        if offsets.max() <= 1e-9:
            pass
        elif offsets.min() >= -1e-9:
            normal = -normal
            distance = -distance
            offsets = -offsets
        else:
            continue
        key = tuple(np.round(np.r_[normal, distance], 9))
        equations[key] = normal, distance, np.flatnonzero(abs(offsets) < 1e-8)
    faces, planes = [], []
    for normal, distance, ids in equations.values():
        face_points = points[ids]
        center = face_points.mean(0)
        right = face_points[0] - center
        right /= np.linalg.norm(right)
        up = np.cross(normal, right)
        angles = np.arctan2((face_points-center) @ up, (face_points-center) @ right)
        order = ids[np.argsort(angles)]
        for i in range(1, len(order)-1):
            faces.append([int(order[0]), int(order[i+1]), int(order[i])])
        planes.append(np.r_[normal, distance])
    if not planes:
        raise ValueError('No valid supporting planes')
    return faces, np.array(planes)


def support_hull(model, target):
    """Retain axis extrema, then greedily add missing source support points."""
    points = np.asarray(model['positions'])
    rgb = np.asarray(model['colors'], dtype=float)
    vertices, reverse = np.unique(points, axis=0, return_inverse=True)
    colors = np.array([rgb[reverse == i].mean(0) for i in range(len(vertices))])
    centroids = points.reshape(-1, 3, 3).mean(1)
    chosen = []
    for axis in range(3):
        # This integer-set ordering is part of the reviewed recipe. Preserve it
        # when reproducing a candidate; changing ties requires a new audit.
        chosen += list({int(vertices[:, axis].argmin()), int(vertices[:, axis].argmax())})
    chosen = list(dict.fromkeys(chosen))
    maximum = max(len(chosen), (target+4)//2)
    while len(chosen) < maximum:
        _, planes = hull(vertices[chosen])
        offsets = vertices @ planes[:, :3].T - planes[:, 3]
        errors = offsets.max(1)
        errors[chosen] = -1
        index = int(errors.argmax())
        if errors[index] < 1e-9:
            break
        chosen.append(index)
    faces, _ = hull(vertices[chosen])
    result = {'positions': [], 'colors': [], 'materials': []}
    for face in faces:
        ids = np.array(chosen)[face]
        result['positions'].extend(vertices[ids].tolist())
        result['colors'].extend(np.round(colors[ids]).astype(int).tolist())
        nearest = int(np.linalg.norm(centroids-vertices[ids].mean(0), axis=1).argmin())
        result['materials'].append(int(model['materials'][nearest]))
    result['triangle_count'] = len(faces)
    return result


def restore_materials(reduced, original, materials):
    """Replace selected material faces with exact original geometry and RGB."""
    keep = set(materials)
    result = {'positions': [], 'colors': [], 'materials': []}
    for model, restoring in ((reduced, False), (original, True)):
        for i, material in enumerate(model['materials']):
            if (material in keep) == restoring:
                result['positions'].extend(model['positions'][3*i:3*i+3])
                result['colors'].extend(model['colors'][3*i:3*i+3])
                result['materials'].append(material)
    result['triangle_count'] = len(result['materials'])
    return result
