"""Ordered Tiny3D terrain batches with bounded colors and exact texture wrap."""

TEXTURE_SIZE = 32
UV_FRACTION = 32
UV_PERIOD = TEXTURE_SIZE * UV_FRACTION


def _uv_offset(vertices, period=UV_PERIOD):
    # Integer texture periods preserve repeat sampling and interpolation.
    return tuple((min(v[a] for v in vertices) + max(v[a] for v in vertices))
                 // (2 * period) * period for a in (6, 7))


def _uv_fits(vertices, period=UV_PERIOD):
    offset = _uv_offset(vertices, period)
    return all(-32768 <= v[a] - offset[a - 6] <= 32767
               for v in vertices for a in (6, 7))


def indexed_terrain(triangles, color_delta=8, uv_period=UV_PERIOD):
    """Pack one material/spatial cell, preserving its triangle/corner order.

    Input vertices are immutable integer (x,y,z,r,g,b,s,t) tuples. UVs have
    already been rounded in global coordinates at 32 units per texel. Output
    UVs subtract ONE whole-texture offset per batch; interpolated coordinates
    therefore differ by a constant integer repeat, even with perspective.
    """
    assert 0 <= color_delta <= 8
    assert uv_period in (1024, 2048)
    chunks = []
    vertices, lookup, indices, originals = [], {}, [], []

    def flush():
        if not indices:
            return
        offset = _uv_offset(vertices, uv_period)
        packed = [v[:6] + (v[6] - offset[0], v[7] - offset[1]) for v in vertices]
        assert ((len(packed) + 1) & ~1) <= 60 and len(indices) <= 120
        assert len(indices) % 3 == 0
        assert _uv_fits(vertices, uv_period)
        # Check every expanded corner against the original, not a previous
        # merge. Representatives are never averaged or modified.
        for original, index in zip(originals, indices):
            v = packed[index]
            assert v[:3] == original[:3]
            assert max(abs(v[a] - original[a]) for a in (3, 4, 5)) <= color_delta
            assert (original[6] - v[6], original[7] - v[7]) == offset
        chunks.append({'vertices': packed, 'indices': indices.copy()})

    for triangle in triangles:
        assert len(triangle) == 3
        triangle = [tuple(v) for v in triangle]
        assert all(len(v) == 8 and all(isinstance(x, int) for x in v) for v in triangle)
        # Tiny3D's triangle setup subtracts texture attributes in signed16.
        # Individual stored coordinates fitting signed16 is insufficient.
        if any(max(v[a] for v in triangle) - min(v[a] for v in triangle) > 32767 for a in (6, 7)):
            raise ValueError('A terrain triangle exceeds signed16 UV edge differences')
        while True:
            trial = vertices.copy()
            trial_lookup = {key: value.copy() for key, value in lookup.items()}
            local = []
            for v in triangle:
                key = v[:3] + v[6:]
                matches = [i for i in trial_lookup.get(key, ())
                           if max(abs(v[a] - trial[i][a]) for a in (3, 4, 5)) <= color_delta]
                if matches:
                    index = matches[0]
                else:
                    index = len(trial)
                    trial.append(v)
                    trial_lookup.setdefault(key, []).append(index)
                local.append(index)
            fits = ((len(trial) + 1) & ~1) <= 60 and len(indices) + 3 <= 120 and _uv_fits(trial, uv_period)
            if indices and not fits:
                flush()
                vertices, lookup, indices, originals = [], {}, [], []
                continue
            if not fits:
                raise ValueError('A terrain triangle cannot fit signed16 UVs after an integer texture offset')
            vertices, lookup = trial, trial_lookup
            indices.extend(local)
            originals.extend(triangle)
            break
    flush()
    return chunks
