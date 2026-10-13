"""Checked, isolated provenance hooks for the unchanged accepted map exporter."""

CHANGES = [('\n'
  'def uv_safe_triangles(triangles):\n'
  '    """Split only overly long texture edges; preserve the surface and UV tiling."""\n',
  '\n'
  'def uv_safe_triangles(triangles, source_ids=None):\n'
  '    """Split only overly long texture edges; preserve the surface and UV tiling."""\n'),
 ('    """Split only overly long texture edges; preserve the surface and UV tiling."""\n'
  '    pending=list(triangles);result=[]\n'
  '    while pending:\n',
  '    """Split only overly long texture edges; preserve the surface and UV tiling."""\n'
  '    if source_ids is not None:assert len(source_ids)==len(triangles)\n'
  '    pending=list(zip(triangles,source_ids if source_ids is not None else '
  '[-1]*len(triangles)));result=[];sources=[]\n'
  '    while pending:\n'),
 ('    while pending:\n'
  '        tri=pending.pop()\n'
  '        edges=[(max(abs(tri[a][k]-tri[b][k]) for k in (6,7)),a,b) for a,b in '
  '((0,1),(1,2),(2,0))]\n',
  '    while pending:\n'
  '        tri,source=pending.pop()\n'
  '        edges=[(max(abs(tri[a][k]-tri[b][k]) for k in (6,7)),a,b) for a,b in '
  '((0,1),(1,2),(2,0))]\n'),
 ('        length,a,b=max(edges)\n'
  '        if length<=32767:result.append(tri);continue\n'
  '        c=3-a-b;mid=tuple(round((tri[a][k]+tri[b][k])/2) for k in range(8))\n',
  '        length,a,b=max(edges)\n'
  '        if length<=32767:result.append(tri);sources.append(source);continue\n'
  '        c=3-a-b;mid=tuple(round((tri[a][k]+tri[b][k])/2) for k in range(8))\n'),
 ('        c=3-a-b;mid=tuple(round((tri[a][k]+tri[b][k])/2) for k in range(8))\n'
  '        pending.extend([[tri[a],mid,tri[c]],[mid,tri[b],tri[c]]])\n'
  '    return result[::-1]\n'
  '\n'
  'def arena(output, sky, name="wizard", bins=(8,8,4)):\n'
  '    legacy=name=="wizard"; map_id=map_ids()[name]\n',
  '        c=3-a-b;mid=tuple(round((tri[a][k]+tri[b][k])/2) for k in range(8))\n'
  '        pending.extend([([tri[a],mid,tri[c]],source),([mid,tri[b],tri[c]],source)])\n'
  '    return (result[::-1],sources[::-1]) if source_ids is not None else result[::-1]\n'
  '\n'
  'def arena(output, sky, name="wizard", bins=(8,8,4), provenance_out=None):\n'
  '    legacy=name=="wizard"; map_id=map_ids()[name]\n'),
 ('        '
  "groups=collections.defaultdict(list);raw_tris=list(struct.iter_unpack('<3H',bsp.surface.STEPTREE))\n"
  '        for light in bsp.lightmaps.STEPTREE:\n',
  '        '
  "groups=collections.defaultdict(list);raw_tris=list(struct.iter_unpack('<3H',bsp.surface.STEPTREE))\n"
  '        group_sources=collections.defaultdict(list)\n'
  '        for light in bsp.lightmaps.STEPTREE:\n'),
 ('                    else:colors.append((255,255,255))\n'
  '                for face in raw_tris[m.surfaces:m.surfaces+m.surface_count]:\n'
  '                    p=[positions[v] for v in face];center=[sum(v[a] for v in p)/3 for a in '
  'range(3)]\n',
  '                    else:colors.append((255,255,255))\n'
  '                for source_id,face in '
  'enumerate(raw_tris[m.surfaces:m.surfaces+m.surface_count],m.surfaces):\n'
  '                    p=[positions[v] for v in face];center=[sum(v[a] for v in p)/3 for a in '
  'range(3)]\n'),
 ('                    # submissions without changing source triangle geometry.\n'
  '                    groups[(mi,*(math.floor(center[a]/bins[a]) for a in '
  'range(3)))].append(tri)\n'
  '        if not legacy:\n',
  '                    # submissions without changing source triangle geometry.\n'
  '                    key=(mi,*(math.floor(center[a]/bins[a]) for a in range(3)))\n'
  '                    groups[key].append(tri)\n'
  '                    if provenance_out is not None:group_sources[key].append(source_id)\n'
  '        if not legacy:\n'),
 ('                '
  'tri=[(round(x*256),round(z*256),round(-y*256),255,255,255,round(u*period),round((1-v)*period)) '
  'for x,y,z,u,v in points]\n'
  '                groups[(mi,*(math.floor(center[a]/bins[a]) for a in range(3)))].append(tri)\n'
  '            '
  'scenery_report=scenery(h,new_materials,data,collision_materials,add_scenery,include_lights=name '
  'not in ACCEPTED_MAPS)\n',
  '                '
  'tri=[(round(x*256),round(z*256),round(-y*256),255,255,255,round(u*period),round((1-v)*period)) '
  'for x,y,z,u,v in points]\n'
  '                key=(mi,*(math.floor(center[a]/bins[a]) for a in range(3)))\n'
  '                groups[key].append(tri)\n'
  '                if provenance_out is not None:group_sources[key].append(-1)\n'
  '            '
  'scenery_report=scenery(h,new_materials,data,collision_materials,add_scenery,include_lights=name '
  'not in ACCEPTED_MAPS)\n'),
 ('        for key,tris in sorted(groups.items(),key=lambda kv:((overlays[kv[0][0]] if legacy else '
  'overlays[kv[0][0]]&1),*kv[0])):\n'
  '            if not legacy:tris=uv_safe_triangles(tris)\n'
  '            for batch in indexed_terrain(tris,uv_period=1024 if legacy else '
  'new_materials.sizes[key[0]]*32):\n'
  "                first=len(vertices);unique=batch['vertices'];vertices.extend(unique)\n",
  '        for key,tris in sorted(groups.items(),key=lambda kv:((overlays[kv[0][0]] if legacy else '
  'overlays[kv[0][0]]&1),*kv[0])):\n'
  '            sources=group_sources[key] if provenance_out is not None else None\n'
  '            if not legacy:\n'
  '                if sources is None:tris=uv_safe_triangles(tris)\n'
  '                else:tris,sources=uv_safe_triangles(tris,sources)\n'
  '            for batch in indexed_terrain(tris,uv_period=1024 if legacy else '
  'new_materials.sizes[key[0]]*32,source_ids=sources):\n'
  "                first=len(vertices);unique=batch['vertices'];vertices.extend(unique)\n"),
 ('                chunks.append((first,len(unique),key[0],*bounds,start,count))\n'
  '                if len(vertices)%2:vertices.append(vertices[-1])\n',
  '                chunks.append((first,len(unique),key[0],*bounds,start,count))\n'
  "                if provenance_out is not None:provenance_out.append(batch['source_ids'])\n"
  '                if len(vertices)%2:vertices.append(vertices[-1])\n')]

def instrument(source):
    for old,new in CHANGES:
        if source.count(old)!=1:
            raise ValueError('Accepted exporter changed; review provenance mapping: '+old)
        source=source.replace(old,new,1)
    # The accepted batcher preserves triangle order. Derive membership from
    # each emitted index count, without modifying its vertex/color/UV policy.
    source=source.replace('for batch in indexed_terrain(tris,uv_period=1024 if legacy else new_materials.sizes[key[0]]*32,source_ids=sources):',
                         'source_at=0\n            for batch in indexed_terrain(tris,uv_period=1024 if legacy else new_materials.sizes[key[0]]*32):')
    source=source.replace("if provenance_out is not None:provenance_out.append(batch['source_ids'])",
                         "if provenance_out is not None:provenance_out.append(sources[source_at:source_at+count//3]);source_at+=count//3")
    return source
