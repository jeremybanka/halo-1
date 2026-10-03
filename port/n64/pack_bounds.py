"""Conservative bounds of the exact quantized model and animation banks."""
import math
from pack_assets import position


def bounds(points):
    points=list(points)
    if not points:raise ValueError('Cannot bound empty geometry')
    return [[min(p[a] for p in points) for a in range(3)],
            [max(p[a] for p in points) for a in range(3)]]


def union(*items):
    return bounds(p for item in items for p in item)


def model_bounds(model,scale):
    points=[tuple(round(v*scale)/scale for v in position(p,(0,0,0)))
            for tri in model['triangles'] for p in tri['p']]
    # Runtime adds one render unit around transformed AABBs. A final 16.16
    # matrix coefficient truncation contributes <= (local L1 norm + 1)/65536.
    error=max((sum(abs(v*scale) for v in p)+1)/65536 for p in points)
    if error>=.5:raise ValueError('Model exceeds conservative fixed-matrix margin')
    return bounds(points),max(math.sqrt(sum(v*v for v in p)) for p in points)


def animation_bounds(*clips,scale=128):
    # Linear interpolation, including integer rounding, cannot leave the
    # coordinate intervals of the quantized endpoints. Both LODs are included.
    return bounds(tuple(round(v*scale)/scale for v in position(p,(0,0,0)))
                  for clip in clips for frame in clip['frames'] for p in frame)


def initializer(value):
    # Float extrema must round outward when converted to target float32.
    # One micro-unit also covers the emitted seven-place decimal conversion.
    return '{'+','.join('{'+','.join(f'{v+(-1e-6 if side==0 else 1e-6):.7f}f'
                                     for v in point)+'}' for side,point in enumerate(value))+'}'
