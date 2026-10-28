#!/usr/bin/env python3
"""Bake source objective locations and mode eligibility into private sidecars.

The existing map/geometry banks are never rewritten. Sidecars bind to the
map ID and exact serialized starts, including accepted clearance corrections.
"""
import argparse
import collections
import contextlib
import hashlib
import json
from pathlib import Path
import struct

from asset_ids import map_ids
from extract_extended import tag_values

ROOT = Path(__file__).resolve().parents[2]
ENGINES = ('slayer', 'ctf', 'oddball', 'king', 'race')
FLAG_TYPES = {'ctf_flag': 0, 'oddball_ball_spawn': 1, 'hill_flag': 2,
              'race_track': 3, 'race_vehicle': 4}
WEAPONS = ('assault rifle', 'pistol', 'plasma pistol', 'plasma rifle',
           'needler', 'shotgun', 'sniper rifle', 'rocket launcher', 'flamethrower')
KINDS = {'weapons\\' + n + '\\' + n: i for i, n in enumerate(WEAPONS)}
KINDS.update({r'powerups\health pack': 9, r'weapons\frag grenade\frag grenade': 10,
              r'weapons\plasma grenade\plasma grenade': 11, r'powerups\over shield': 12,
              r'powerups\active camouflage': 13})


def mode_mask(row):
    mask = 0
    for i in range(4):
        kind = row['type_' + str(i)]
        if kind == 'none': continue
        if kind == 'all_games': mask |= 31
        elif kind == 'all_games_except_ctf': mask |= 29
        elif kind == 'all_games_except_ctf_and_race': mask |= 13
        else:
            kind = {'king_of_the_hill': 'king'}.get(kind, kind)
            assert kind in ENGINES, kind
            mask |= 1 << ENGINES.index(kind)
    return mask


def fingerprint(data):
    value = 2166136261
    for byte in data: value = ((value ^ byte) * 16777619) & 0xffffffff
    return value


def hull(points):
    """Same convex region as find_hill, with deterministic point ordering."""
    unique = sorted(set(tuple(p) for p in points), key=lambda p: (p[0], p[2], p[1]))
    if len(unique) == 1:
        x, y, z = unique[0]
        unique = [(x-1,y,z-1),(x-1,y,z+1),(x+1,y,z-1),(x+1,y,z+1)]
    def cross(a,b,c): return (b[0]-a[0])*(c[2]-a[2])-(b[2]-a[2])*(c[0]-a[0])
    lower, upper = [], []
    for p in unique:
        while len(lower)>1 and cross(lower[-2],lower[-1],p)<=0: lower.pop()
        lower.append(p)
    for p in reversed(unique):
        while len(upper)>1 and cross(upper[-2],upper[-1],p)<=0: upper.pop()
        upper.append(p)
    result = lower[:-1]+upper[:-1]
    assert 3 <= len(result) <= 12, 'Degenerate source hill'
    return result


def extract(source_root, output, clearance):
    from reclaimer.meta.wrappers.halo1_map import Halo1Map
    output.mkdir(parents=True, exist_ok=True)
    positions={(r['id'],r['start']):r['position'] for r in json.loads(clearance.read_text())}
    report = {'schema': 2, 'maps': {}, 'source': 'Owned Xbox scenario metadata; geometry banks unchanged.'}
    for name, map_id in map_ids().items():
        cache = source_root/'build/n64-map-survey'/f'{name}-decompressed.map'
        if name == 'bloodgulch': cache = source_root/'build/n64/assets/bloodgulch-decompressed.map'
        bank = ROOT/'halo64-assets/generated/maps'/f'{name}.map64'
        raw = bank.read_bytes()
        start_offset, start_count, stride = struct.unpack_from('>3I', raw, 16+14*12)
        origin_offset = struct.unpack_from('>I', raw, 16+21*12)[0]
        ox, oy, oz, _ = struct.unpack_from('>4f', raw, origin_offset)
        def position(p): return (p['x']-ox, p['z']-oz, -(p['y']-oy))
        with (output/f'{name}-modes-extraction.log').open('w') as log, contextlib.redirect_stdout(log):
            h = Halo1Map(); h.load_map(cache); entries = h.tag_index.tag_index
            sc = tag_values(h.scnr_meta)
            def tag(path, kind):
                return tag_values(h.get_meta(next(i for i,e in enumerate(entries)
                                                 if e.path==path and e.class_1.enum_name==kind)))
            def collection(path): return tag(path, 'item_collection')
            assert len(sc['player_starting_locations']) == start_count and stride == 20
            masks = [mode_mask(s) for s in sc['player_starting_locations']]
            flags, hills = [], collections.defaultdict(list)
            for flag in sc['netgame_flags']:
                if flag['type'] not in FLAG_TYPES: continue
                kind, group = FLAG_TYPES[flag['type']], flag['team_index']
                p = position(flag['position'])
                if kind == 2:
                    hills[group].append(p)
                else:
                    assert group >= 0
                    flags.append((*p, flag['facing'], kind, group))
            for group, points in hills.items():
                for p in hull(points[:12]): flags.append((*p, 0, 2, group))
            globals_meta = h.get_meta(next(i for i,e in enumerate(entries) if e.class_1.enum_name=='globals'))
            unit_path = globals_meta.multiplayer_informations.STEPTREE[0].unit.filepath
            default = [KINDS[w['weapon']] for w in tag(unit_path,'biped')['unit_attrs']['weapons'] if w['weapon']]
            starts = []
            for engine in range(5):
                start = next((r for r in sc['starting_equipments'] if mode_mask(r)&(1<<engine)), None)
                weapons, grenades = default[:], [4,0]
                if start is not None:
                    weapons = []
                    for slot in range(1,7):
                        path = start['item_collection_'+str(slot)]
                        if path: weapons.append(KINDS[collection(path)['item_permutations'][0]['item']])
                    grenades = [0,0] if start['flags']['no_grenades'] else [4,0]
                    if start['flags']['plasma_grenades']: grenades = [0,sum(grenades)]
                starts.append((*(weapons+[-1,-1])[:2], *grenades))
            items = []
            for item in sc['netgame_equipments']:
                mask = mode_mask(item)
                if not mask: continue
                col = collection(item['item_collection']); perms = col['item_permutations']
                assert 0 < len(perms) <= 3
                kinds = [KINDS[p['item']] for p in perms]; weights = [round(p['weight']) for p in perms]
                assert 0 < sum(weights) <= 255 and all(w>0 for w in weights)
                items.append((*position(item['position']), -item['facing'],
                              item['spawn_time'] or col['spawn_time'] or 30,
                              *(kinds+[-1])[:2], weights[0], sum(weights),
                              kinds[2] if len(kinds)==3 else 0,
                              weights[1] if len(kinds)==3 else 0, mask))
        assert len(flags)<=512 and len(items)<=128 and start_count<=128
        for engine in range(5):
            assert sum(bool(m&(1<<engine)) for m in masks)>=4, (name,engine,'starts')
            assert sum(bool(i[-1]&(1<<engine)) for i in items)<=56, (name,engine,'items')
        assert {f[-1] for f in flags if f[-2]==0} == {0,1}, (name,'CTF bases')
        assert any(f[-2]==1 for f in flags) and hills and any(f[-2]==3 for f in flags)
        payload = b''.join(struct.pack('>4i',*r) for r in starts)
        payload += b''.join(struct.pack('>I',m) for m in masks)
        for index,mask in enumerate(masks):
            original=struct.unpack_from('>3f',raw,start_offset+index*stride)
            assert not mask or (map_id,index) in positions, (name,index,'missing clearance')
            payload += struct.pack('>3f',*positions.get((map_id,index),original))
        payload += b''.join(struct.pack('>4f2H',*r) for r in flags)
        payload += b''.join(struct.pack('>4fH2b4BI',*r) for r in items)
        signature = fingerprint(raw[start_offset:start_offset+start_count*stride])
        data = struct.pack('>8I',0x484d4d44,2,map_id,32+len(payload),start_count,len(flags),len(items),signature)+payload
        path = output/f'{name}.modes64'; path.write_bytes(data)
        report['maps'][name] = dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),
            source_sha256=hashlib.sha256(cache.read_bytes()).hexdigest(),
            starts=[sum(bool(m&(1<<e)) for m in masks) for e in range(5)],
            items=[sum(bool(i[-1]&(1<<e)) for i in items) for e in range(5)],
            objectives=dict(collections.Counter(f[-2] for f in flags)),hills=len(hills),
            spawn_fingerprint=signature, starting_equipment=starts)
        print(name, report['maps'][name]['starts'], len(flags),'objective markers',len(data),'bytes')
    report['inputs']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
        (Path(__file__).resolve(),ROOT/'port/n64/map_catalog.def',clearance.resolve())}
    (output/'modes-report.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,default=ROOT)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'halo64-assets/generated/maps')
    parser.add_argument('--clearance',type=Path,default=ROOT/'halo64-assets/generated/maps/mode-spawn-clearance.json')
    args = parser.parse_args()
    extract(args.source_root,args.output_dir,args.clearance)
