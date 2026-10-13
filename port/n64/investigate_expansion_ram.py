"""Measure immutable collision reuse and RAM costs without changing production.

The generated host adapter records actual prism/edge requests from the current
four-player replays. Cache simulations are operation counts, never N64 timing.
Source assets and the maintained adapter are read-only inputs.
"""
import argparse
import array
import collections
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "port/n64"))
from asset_ids import map_ids
from test_runtime_equivalence import TRACE
from feature_cache_candidate import candidate_source


def run(out, prototype_cache_slots=None):
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    solver = out / "solver"
    for script in ("prepare_vehicle.py", "export_vehicle.py"):
        command = [sys.executable, str(ROOT / "port/n64/blam" / script),
                   "--output", str(solver)]
        if script == "export_vehicle.py":
            command += ["--rom-files", str(solver)]
        subprocess.run(command, cwd=ROOT, check=True)
    original_adapter = (ROOT / "port/n64/blam/vehicle_physics.c").read_text()
    adapter = original_adapter
    if prototype_cache_slots:
        adapter = candidate_source(adapter, prototype_cache_slots)
    adapter = adapter.replace('#include "vehicle_profile.h"',
                              '#include "vehicle_profile.h"\n#include "ram_trace.h"', 1)
    for signature, kind, identifier in (
        ('static const struct collision_prism*cached_polygon(const struct collision_bsp*b,int si){', 0, 'si'),
        ('static void cached_edge_feature(const struct collision_bsp*b,int edge,float height,float width,struct collision_feature_list*out){', 1, 'edge'),
    ):
        assert adapter.count(signature) == 1
        if kind == 0:
            adapter = adapter.replace(signature, signature +
                                      f'\n ram_record({kind},{identifier});', 1)
        else:
            edge_capacity = prototype_cache_slots or 64
            marker = f' unsigned slot=((uint32_t)edge*2654435761u)&{edge_capacity-1}u;'
            assert adapter.count(marker) == 1
            adapter = adapter.replace(marker, ' ram_record(1,edge);\n' + marker, 1)
    (out / "ram_trace.h").write_text(r'''
#include <stdio.h>
#include "terrain_trace.h"
ram_terrain_metrics ram_terrain;
static FILE *ram_requests;
static unsigned ram_scenario;
uint32_t bg_counters[BG_COUNTER_COUNT];
static void ram_record(unsigned kind,unsigned id){
 if(!ram_requests)return;
 uint32_t row[4]={bg_map_id(),ram_scenario,kind,id};
 assert(fwrite(row,sizeof(row),1,ram_requests)==1);
}
''')
    (out / 'terrain_trace.h').write_text('''
#ifndef RAM_TERRAIN_TRACE_H
#define RAM_TERRAIN_TRACE_H
#include <stdint.h>
typedef struct {uint64_t near_calls,capsule_calls,fallback_queries,move_calls,substeps,recovery_calls;unsigned max_steps;} ram_terrain_metrics;
extern ram_terrain_metrics ram_terrain;
#endif
''')
    terrain_original = (ROOT / 'port/n64/terrain.c').read_text()
    terrain = terrain_original
    for marker, addition in (
        ('static bool near_triangle(const bg_triangle*t,const float*p,float h,float r){', 'ram_terrain.near_calls++;'),
        ('float bg_capsule_triangle(const float base[3],float height,float radius,const bg_triangle*t,float pa[3],float pb[3]){', 'ram_terrain.capsule_calls++;'),
        ('static bool recover_support(bg_player*p,unsigned previous,float normal[3]){', 'ram_terrain.recovery_calls++;'),
        ('if(steps>64)steps=64;', 'ram_terrain.move_calls++;ram_terrain.substeps+=steps;if(steps>ram_terrain.max_steps)ram_terrain.max_steps=steps;'),
    ):
        assert terrain.count(marker) == 1, marker
        terrain = terrain.replace(marker, marker + addition, 1)
    marker = 'unsigned count=c->count==UINT16_MAX?bg_collision_count:c->count;'
    assert terrain.count(marker) == 3
    terrain = terrain.replace(marker, marker + 'if(c->count==UINT16_MAX)ram_terrain.fallback_queries++;')
    (out / 'terrain.c').write_text('#include "terrain_trace.h"\n' + terrain)
    # Include the adapter to inspect its actual structs and factory outputs.
    driver = TRACE[TRACE.index('static void state('):TRACE.index('int main(')]
    driver += r'''
static void census(FILE *report,unsigned id){
 world_load();
 unsigned points=0,produced=0,checked=0;
 for(int si=0;si<bg_vehicle_bsp.surfaces.count;si++){
  struct collision_feature_list *list=&vehicle_workspace->features;
  collision_features_new(list);
  collision_features_from_surface(&bg_vehicle_bsp,si,NULL,0,.375f,NONE,list);
  assert(list->count[_collision_feature_prism]==1);
  struct collision_prism p=*cached_polygon(&bg_vehicle_bsp,si);p.height=.375f;
  const struct collision_prism *original=&list->prisms[0];
  assert(!memcmp(original,&p,offsetof(struct collision_prism,points)+p.point_count*sizeof(real_point2d)));
  points+=p.point_count;checked++;
 }
 for(int edge=0;edge<bg_vehicle_bsp.edges.count;edge++){
  struct collision_feature_list *list=&vehicle_workspace->features;
  collision_features_new(list);
  collision_features_from_edge(&bg_vehicle_bsp,edge,NULL,0,.375f,NONE,list);
  unsigned count=list->count[_collision_feature_cylinder];assert(count<=1);
  struct collision_cylinder expected;
  if(count)expected=list->cylinders[0];
  collision_features_new(list);cached_edge_feature(&bg_vehicle_bsp,edge,0,.375f,list);
  assert((unsigned)list->count[_collision_feature_cylinder]==count);
  if(count)assert(!memcmp(&expected,&list->cylinders[0],sizeof(expected)));
  produced+=count;checked++;
 }
 fprintf(report,"%u %d %d %u %u %zu %zu %zu %zu %u\n",id,
  bg_vehicle_bsp.surfaces.count,bg_vehicle_bsp.edges.count,points,produced,
  sizeof(struct collision_prism),offsetof(struct collision_prism,points),
  sizeof(struct collision_cylinder),sizeof(vehicle_workspace->prisms[0]),checked);
 memset(vehicle_workspace->prisms,0,sizeof(vehicle_workspace->prisms));
 memset(vehicle_workspace->cylinders,0,sizeof(vehicle_workspace->cylinders));
}
int main(int argc,char **argv){
 assert(argc==5);FILE *states=fopen(argv[1],"wb"),*report=fopen(argv[3],"w");
 FILE *actual=fopen(argv[4],"w");assert(actual);
 assert(states&&report);
 const unsigned maps[]={9,0,1,2,3,4,5,6,7,8,10,11,12};
 for(unsigned mi=0;mi<sizeof(maps)/sizeof(*maps);mi++){
  unsigned map=maps[mi];assert(bg_map_load(map));census(report,map);
  ram_requests=fopen(argv[2],mi?"ab":"wb");assert(ram_requests);
  setvbuf(ram_requests,NULL,_IOFBF,1024*1024);
  for(unsigned scenario=0;scenario<(map==9?7u:1u);scenario++){
   ram_scenario=scenario;
   memset(bg_counters,0,sizeof(bg_counters));
   memset(&ram_terrain,0,sizeof(ram_terrain));
   bg_set_players(4);bg_set_score_limit(1000);bg_reset();
   if(scenario)bg_showcase_begin(scenario-1);
   float seconds=0;unsigned ticks=map==9?(scenario?1800:4500):2250;
   for(unsigned tick=0;tick<ticks;tick++){
    bg_input input[4]={{0}};
    if(scenario)bg_showcase_input(input,seconds);else bg_replay_input(input,seconds);
    bg_clear_events();bg_tick(input,BLAM_TICK_SECONDS);seconds+=BLAM_TICK_SECONDS;
    if(scenario)bg_showcase_observe();
    state(states);
   }
   fprintf(actual,"%u %u %u %u %u %u %u %u %u %u %u %llu %llu %llu %llu %llu %llu %u\n",map,scenario,
    bg_counters[BG_COUNT_PRISM_HIT],bg_counters[BG_COUNT_PRISM_MISS],
    bg_counters[BG_COUNT_EDGE_HIT],bg_counters[BG_COUNT_EDGE_MISS],
    bg_counters[BG_COUNT_TERRAIN_HIT],bg_counters[BG_COUNT_TERRAIN_MISS],
    bg_counters[BG_COUNT_TERRAIN_OVERFLOW],bg_counters[BG_COUNT_FLOOR_HIT],bg_counters[BG_COUNT_FLOOR_MISS],
    (unsigned long long)ram_terrain.near_calls,(unsigned long long)ram_terrain.capsule_calls,
    (unsigned long long)ram_terrain.fallback_queries,(unsigned long long)ram_terrain.move_calls,
    (unsigned long long)ram_terrain.substeps,(unsigned long long)ram_terrain.recovery_calls,ram_terrain.max_steps);
  }
  assert(fclose(ram_requests)==0);ram_requests=NULL;bg_map_unload();
 }
 assert(fclose(states)==0&&fclose(report)==0&&fclose(actual)==0);
 puts("PASS: original prism/edge factories match on all 13 maps; replays complete");
}
'''
    (out / "driver.c").write_text(adapter + '\n#include "replay.h"\n#include "showcase.h"\n#include "blam/runtime.h"\n' + driver)
    flags = ['-std=c17', '-O2', '-g', '-fsanitize=address,undefined',
             '-fno-fast-math', '-ffp-contract=off', '-fno-strict-aliasing', '-fwrapv',
             '-Wno-multichar', '-Wno-unused-function', '-Wno-incompatible-pointer-types',
             '-DBG_STREAM_MAPS', '-DBG_BODY_CANDIDATES', '-DBG_TELEMETRY', '-Iport/n64', '-Iport/n64/blam',
             '-Ibuild/n64/blam-core', '-I' + str(solver), '-I' + str(out)]
    sources = ['port/n64/map.c', 'halo64-assets/generated/maps/common_data.c',
               'port/n64/game.c', 'port/n64/combat_geometry.c', str(out / 'terrain.c'),
               'port/n64/movement.c', 'port/n64/blam/runtime.c', 'port/n64/blam/core.c',
               'port/n64/replay.c', 'port/n64/showcase.c',
               'build/n64/generated/combat_data.c', 'build/n64/generated/movement_data.c',
               'build/n64/generated/interaction_defs.c', str(solver / 'vehicle_data.c')]
    compiler = ['clang', *flags]
    tail = [*sources, '-lm']
    subprocess.run([*compiler, str(out / 'driver.c'), *tail,
                    '-o', str(out / 'probe')], cwd=ROOT, check=True)
    subprocess.run([str(out / 'probe'), str(out / 'all-map-state.bin'),
                    str(out / 'requests.bin'), str(out / 'census.txt'),
                    str(out / 'actual-counts.txt')], cwd=ROOT,
                   env={**os.environ, 'BG_MAP_DIRECTORY': str(ROOT / 'halo64-assets/generated/maps')},
                   check=True)
    # A matched, independent adapter build avoids comparing sanitizer codegen
    # with an old nonsanitized trace. Instrumentation must not change state.
    baseline_adapter = original_adapter.replace('#include "vehicle_profile.h"',
                              '#include "vehicle_profile.h"\n#include "ram_trace.h"', 1)
    suffix = '\n#include "replay.h"\n#include "showcase.h"\n#include "blam/runtime.h"\n'
    (out / 'baseline.c').write_text(baseline_adapter + suffix + driver)
    subprocess.run([*compiler, str(out / 'baseline.c'), *tail,
                    '-o', str(out / 'baseline')], cwd=ROOT, check=True)
    subprocess.run([str(out / 'baseline'), str(out / 'baseline-state.bin'),
                    str(out / 'baseline-requests.bin'), str(out / 'baseline-census.txt'),
                    str(out / 'baseline-counts.txt')], cwd=ROOT,
                   env={**os.environ, 'BG_MAP_DIRECTORY': str(ROOT / 'halo64-assets/generated/maps')},
                   check=True)
    names = {value: key for key, value in map_ids().items()}
    census = {}
    for line in (out / 'census.txt').read_text().splitlines():
        map_id, surfaces, edges, points, cylinders, prism_bytes, header_bytes, cylinder_bytes, slot_bytes, checked = map(int, line.split())
        census[names[map_id]] = dict(surfaces=surfaces, edges=edges, points=points,
            producing_edges=cylinders, prism_bytes=prism_bytes, prism_header_bytes=header_bytes,
            cylinder_bytes=cylinder_bytes, checked_factories=checked,
            dense_prisms_bytes=surfaces * prism_bytes,
            compact_prisms_bytes=surfaces * (header_bytes + 4) + points * 8,
            dense_edges_bytes=edges * (cylinder_bytes + 1),
            compact_edges_bytes=edges * 4 + cylinders * cylinder_bytes,
            prism_cache_slot_bytes=slot_bytes)
    requests = array.array('I')
    with (out / 'requests.bin').open('rb') as stream:
        requests.frombytes(stream.read())
    assert requests.itemsize == 4 and len(requests) % 4 == 0
    caches, counts, unique = {}, collections.Counter(), collections.defaultdict(set)
    for at in range(0, len(requests), 4):
        map_id, scenario, kind, identifier = requests[at:at+4]
        group = (map_id, scenario, kind)
        counts[group, 'calls'] += 1
        unique[group].add(identifier)
        for capacity in (32, 64, 128, 256, 512, 1024):
            # Same direct-map policy as production, generalized to powers of 2.
            key = (map_id, kind, capacity)
            cache = caches.get(key)
            if cache is None:
                cache = caches[key] = [-1] * capacity
            slot = (identifier if kind == 0 else identifier * 2654435761) & (capacity - 1)
            if cache[slot] != identifier:
                counts[group, capacity] += 1
                cache[slot] = identifier
    groups = []
    baseline_counts = {}
    for line in (out / 'baseline-counts.txt').read_text().splitlines():
        map_id, scenario, ph, pm, eh, em, *_ = map(int, line.split())
        baseline_counts[map_id, scenario, 0] = ph + pm
        baseline_counts[map_id, scenario, 1] = eh + em
    pressure = []
    for line in (out / 'actual-counts.txt').read_text().splitlines():
        map_id, scenario, prism_hits, prism_misses, edge_hits, edge_misses, th, tm, to, fh, fm, near, capsule, fallback, moves, substeps, recovery, max_steps = map(int, line.split())
        pressure.append(dict(map=names[map_id], scenario=scenario,
                             terrain_hits=th, terrain_misses=tm, terrain_overflows=to,
                             floor_hits=fh, floor_misses=fm, near_triangle_calls=near,
                             capsule_calls=capsule, full_scan_queries=fallback,
                             move_calls=moves, substeps=substeps,recovery_calls=recovery,max_substeps=max_steps))
        for kind, capacity, hits, misses in ((0, prototype_cache_slots or 32, prism_hits, prism_misses),
                                            (1, prototype_cache_slots or 64, edge_hits, edge_misses)):
            group = (map_id, scenario, kind)
            assert counts[group, 'calls'] == hits + misses, (group, 'call count')
            assert counts[group, capacity] == misses, (group, 'cache simulation')
            assert counts[group, 'calls'] == baseline_counts[group], (group, 'baseline requests')
    for group in sorted(unique):
        map_id, scenario, kind = group
        groups.append(dict(map=names[map_id], scenario=scenario,
            kind='prism' if kind == 0 else 'edge', calls=counts[group, 'calls'],
            unique_ids=len(unique[group]), misses={str(n): counts[group, n]
                for n in (32, 64, 128, 256, 512, 1024)}))
    sha = hashlib.sha256((out / 'all-map-state.bin').read_bytes()).hexdigest()
    expected = hashlib.sha256((out / 'baseline-state.bin').read_bytes()).hexdigest()
    assert sha == expected, (sha, expected)
    result = dict(source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        scope='Host operation counts and payload sizes, not N64 performance; rendering/camera-only calls excluded.',
        prototype_cache_slots=prototype_cache_slots,
        adapter_sha256=hashlib.sha256(adapter.encode()).hexdigest(),
        baseline_adapter_sha256=hashlib.sha256(original_adapter.encode()).hexdigest(),
        terrain_source_sha256=hashlib.sha256(terrain_original.encode()).hexdigest(),
        all_map_state_sha256=sha, all_map_state_bytes=(out / 'all-map-state.bin').stat().st_size,
        factory_checks=sum(m['checked_factories'] for m in census.values()),
        maps=census, requests=len(requests)//4, groups=groups, query_pressure=pressure)
    (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('source_commit', 'prototype_cache_slots', 'all_map_state_sha256', 'factory_checks', 'requests')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'build/n64-expansion-research/collision')
    parser.add_argument('--prototype-cache-slots', type=int, choices=(128,512),
                        help='Change only the isolated host copy; compare every map state byte with the original adapter')
    options = parser.parse_args()
    run(options.output_dir, options.prototype_cache_slots)
