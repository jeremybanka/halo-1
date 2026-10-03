"""Bake broad source diffuse color regions into untextured N64 mesh corners.

The exported UV convention matches image rows (+V downward). Samples are
inset into each face, avoiding unrelated pixels across texture atlas seams.
This preserves diffuse color blocking; it does not reproduce Xbox reflections.
"""
import math
from PIL import Image
from pack_assets import normal, position


def load_images(paths):
    return [Image.open(path).convert('RGBA') if path else None for path in paths]


def sample(image, uv):
    u, v = uv
    return image.getpixel((int((u % 1) * image.width) % image.width,
                           int((v % 1) * image.height) % image.height))


def corner_samples(uvs, corner):
    for weight in (.65, .8, .95):
        yield [sum(uvs[i][axis] * (weight if i == corner else (1 - weight) / 2)
                   for i in range(3)) for axis in range(2)]


def bake_team_mask(tri, masks, channels):
    material = tri['material']
    image = masks[material] if material < len(masks) else None
    channel = channels[material] if material < len(channels) else None
    if image is None or channel is None:
        return [0, 0, 0]
    return [round(sum(sample(image, uv)[channel]
                      for uv in corner_samples(tri['uv'], corner)) / 3)
            for corner in range(3)]


def bake_triangle(tri, images, model, firstperson=False):
    direct = tri.get('sample_uv_direct', False)
    if not isinstance(direct,bool) or (direct and (len(tri['uv'])!=3 or
            any(len(c)!=2 or any(not math.isfinite(v) for v in c) for c in tri['uv']))):
        raise ValueError('Invalid source-derived diffuse UV samples')
    material = tri['material']
    image = images[material] if material < len(images) else None
    overrides = model.get('material_overrides', [])
    fallbacks = model.get('material_colors', [])
    override = overrides[material] if material < len(overrides) else None
    fallback = fallbacks[material] if material < len(fallbacks) else None
    n = normal([position(p, (0, 0, 0)) for p in tri['p']])
    ambient = .78 if firstperson else .68
    light = ambient + (1 - ambient) * max(0, sum(a * b for a, b in zip(n, [.25, .83, .49])))
    result = []
    for corner in range(3):
        if override is not None:
            rgb = override
        elif image is not None:
            samples = ([sample(image,tri['uv'][corner])] if direct else
                       [sample(image, uv) for uv in corner_samples(tri['uv'], corner)])
            rgb = [sum(s[c] for s in samples) / len(samples) for c in range(3)]
        else:
            rgb = fallback or (130, 133, 135)
        result.append([min(255, max(0, round(c * light))) for c in rgb[:3]])
    return result
