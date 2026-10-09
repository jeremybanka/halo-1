"""Losslessly share identical quantized motion tracks across triangle corners."""
from pack_assets import position


def compact_clip(clip, scale):
    frames = [[tuple(round(v * scale) for v in position(p, (0, 0, 0)))
               for p in frame] for frame in clip['frames']]
    if not frames or any(len(f) != len(frames[0]) for f in frames):
        raise ValueError('Inconsistent animation vertex count')
    tracks, indices, lookup = [], [], {}
    for vertex in range(len(frames[0])):
        track = tuple(f[vertex] for f in frames)
        if track not in lookup:
            lookup[track] = len(tracks)
            tracks.append(track)
        indices.append(lookup[track])
    values = [v for f in range(len(frames)) for track in tracks for v in track[f]]
    if not all(-32768 <= v <= 32767 for v in values):
        raise ValueError('Animation vertex overflow')
    if len(tracks) > 65535:
        raise ValueError('Animation track index overflow')
    origin = [min(values[axis::3]) for axis in range(3)]
    offsets = [v - origin[i % 3] for i, v in enumerate(values)]
    if max(offsets) > 255:
        raise ValueError('Animation coordinate span exceeds lossless byte encoding')
    # Check the complete reconstruction, including seam duplicates and every
    # pose. Sharing is exact at the runtime's existing fixed-point precision.
    for f, frame in enumerate(frames):
        for vertex, expected in enumerate(frame):
            start = (f * len(tracks) + indices[vertex]) * 3
            if tuple(offsets[start + c] + origin[c] for c in range(3)) != expected:
                raise AssertionError('Animation track reconstruction differs')
    return {'values': offsets, 'origin': origin, 'indices': indices, 'tracks': len(tracks),
            'vertices': len(indices), 'frames': len(frames),
            'bytes': len(values) + 2 * len(indices),
            'uncompressed_bytes': len(frames) * len(indices) * 6}


def emit_clip(lines, name, clip, scale):
    packed = compact_clip(clip, scale)
    lines.append(f'static const uint8_t {name}[]={{' + ','.join(map(str, packed['values'])) + '};')
    lines.append(f'static const uint16_t {name}_indices[]={{' + ','.join(map(str, packed['indices'])) + '};')
    return packed


def clip_initializer(name, clip, packed):
    return ('{' + f'{name},{name}_indices,{packed["frames"]},{packed["vertices"]},'
            f'{packed["tracks"]},{clip["duration"]:.6f}f,' + '{' + ','.join(map(str,packed['origin'])) + '}},')
