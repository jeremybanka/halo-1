"""Audit vehicle query work on the native replay and six showcases.

Writes instrumented adapter copies, query traces and aggregate counts to an
ignored output directory. Never modifies engine source or asset banks. These
are work counts, not N64 timing; use Ares quiet VI runs for acceptance.
"""

from pathlib import Path
import sys, subprocess, struct, collections, json, hashlib, argparse

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--output-dir", type=Path, default=ROOT / "build/n64-strategy-research/query-audit"
)
parser.add_argument(
    "--vehicle-body-candidates", action=argparse.BooleanOptionalAction, default=True
)
parser.add_argument(
    "--expected-state-sha", help="Optional checkpoint SHA256 for the complete state trace"
)
audit_options = parser.parse_args()
OUT = audit_options.output_dir.resolve()
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "port/n64"))
sys.path.insert(0, str(ROOT / "port/n64/blam"))
from prepare_vehicle import function
from test_runtime_equivalence import TRACE

solver = OUT / "solver"
subprocess.run(
    [sys.executable, str(ROOT / "port/n64/blam/prepare_vehicle.py"), "--output", str(solver)],
    check=True,
)
api = """#include <stdio.h>
#include <stdint.h>
extern FILE *research_trace;
extern uint32_t research_scenario,research_tick;
"""
(OUT / "research_api.h").write_text(api)
impl = api + """
uint32_t bg_counters[BG_COUNTER_COUNT];
FILE *research_trace;
uint32_t research_scenario,research_tick;
static uint32_t research_vehicle,research_stage,research_pass,research_force_count;
static void research_force_begin(const struct physics_instance*instance);
static struct {uint32_t h[9];float values[8];} research_record;
_Static_assert(sizeof(research_record)==68,"Native query trace schema");
static uint16_t research_ids[8192];
static void research_begin(unsigned type,unsigned flags,const float*p,const float*d,float radius,float height,float width){
 memset(&research_record,0,sizeof(research_record));
 research_record.h[0]=research_scenario;research_record.h[1]=research_tick;
 research_record.h[2]=research_vehicle;research_record.h[3]=research_stage;
 research_record.h[4]=research_pass;research_record.h[5]=type;research_record.h[6]=flags;
 memcpy(research_record.values,p,12);
 if(d)memcpy(research_record.values+3,d,12);
 else{research_record.values[3]=radius;research_record.values[4]=height;research_record.values[5]=width;}
}
static void research_id(unsigned id){unsigned n=research_record.h[7]++;assert(n<8192);research_ids[n]=id;}
static void research_finish(unsigned hit){research_record.h[8]=hit;
 assert(fwrite(&research_record,sizeof(research_record),1,research_trace)==1);
 assert(fwrite(research_ids,2,research_record.h[7],research_trace)==research_record.h[7]);
}
"""
(OUT / "research_impl.h").write_text(impl)
s = (solver / "vehicle_original.c").read_text()
wrappers = []
for name, stage, args in [
    (
        "physics_compute_new",
        1,
        "instance, powered_mass_points, mass_points, total_force, total_torque",
    ),
    (
        "physics_update_new",
        2,
        "instance, powered_mass_points, mass_points, total_force, total_torque",
    ),
]:
    body = function(s, name)
    signature = body.split("{", 1)[0]
    s = s.replace(body, body.replace(name + "(", name + "_research(", 1), 1)
    wrappers.append(
        signature
        + "{unsigned old_stage=research_stage,old_vehicle=research_vehicle,old_pass=research_pass;research_stage="
        + str(stage)
        + ";research_vehicle=instance->object_index;research_pass=0;"
        + ("research_force_begin(instance);" if stage == 1 else "")
        + name
        + "_research("
        + args
        + ");research_stage=old_stage;research_vehicle=old_vehicle;research_pass=old_pass;}"
    )
s = s.replace(
    "while (passes_remaining-- > 0)\n\t\t{",
    "while (passes_remaining-- > 0)\n\t\t{\n research_pass=4-passes_remaining;",
    1,
)
(solver / "vehicle_original.c").write_text(s + "\n" + "\n".join(wrappers))
s = (ROOT / "port/n64/blam/vehicle_physics.c").read_text()
s = s.replace(
    '#include "vehicle_profile.h"', '#include "vehicle_profile.h"\n#include "research_impl.h"'
)
name = "collision_get_features_in_sphere"
body = function(s, name)
body = body.replace(
    " BG_VP_BEGIN;", " BG_VP_BEGIN;\n research_begin(0,flags,p->n,NULL,radius,height,width);", 1
)
body = body.replace(
    "query_begin(&query_state,lo,hi);int si;",
    "query_begin(&query_state,lo,hi);research_record.values[6]=query_state.cached?query_state.cached->count:-1;research_record.values[7]=research_force_count;int si;",
    1,
)
body = body.replace(
    "while((si=query_next(&query_state))>=0){",
    "while((si=query_next(&query_state))>=0){research_id(si);",
    1,
)
body = body.replace(
    " BG_VP_END(BG_VP_FEATURE_BUILD);",
    " research_finish(out->count[0]+out->count[1]+out->count[2]);\n BG_VP_END(BG_VP_FEATURE_BUILD);",
)
s = s.replace(function(s, name), body, 1)
name = "collision_test_vector"
body = function(s, name)
body = body.replace(" BG_VP_BEGIN;", " BG_VP_BEGIN;\n research_begin(1,flags,p->n,d->n,0,0,0);", 1)
body = body.replace(
    "query_begin(&query_state,lo,hi);int si;",
    "query_begin(&query_state,lo,hi);research_record.values[6]=query_state.cached?query_state.cached->count:-1;research_record.values[7]=research_force_count;int si;",
    1,
)
body = body.replace(
    "while((si=query_next(&query_state))>=0){",
    "while((si=query_next(&query_state))>=0){research_id(si);",
    1,
)
body = body.replace(
    " BG_VP_END(BG_VP_SWEEP);", " research_finish(out->surface_index>=0);\n BG_VP_END(BG_VP_SWEEP);"
)
s = s.replace(function(s, name), body, 1)
name = "suspension_update"
body = function(s, name)
body = body.replace(
    " BG_VP_BEGIN;", " BG_VP_BEGIN;\n research_stage=3;research_vehicle=i;research_pass=0;", 1
)
body = body.replace(
    " BG_VP_END(BG_VP_SUSPENSION);", " research_stage=0;\n BG_VP_END(BG_VP_SUSPENSION);"
)
s = s.replace(function(s, name), body, 1)
s += """
static void research_force_begin(const struct physics_instance*instance){
 float lo[3],hi[3];
 for(int i=0;i<instance->physics->mass_points.count;i++){
  const struct mass_point_definition*m=TAG_BLOCK_GET_ELEMENT(&instance->physics->mass_points,i,struct mass_point_definition);
  real_point3d p;matrix4x3_transform_point(&instance->world_matrix,&m->position,&p);
  for(int a=0;a<3;a++){float l=p.n[a]-m->radius,h=p.n[a]+m->radius;if(!i){lo[a]=l;hi[a]=h;}else{lo[a]=MIN(lo[a],l);hi[a]=MAX(hi[a],h);}}
 }
 struct surface_query q;query_begin_raw(&q,lo,hi);research_force_count=0;while(query_next_raw(&q)>=0)research_force_count++;
}
"""
(OUT / "vehicle_physics.c").write_text(s)
driver = TRACE.replace('#include "game.h"', '#include "game.h"\n#include "research_api.h"').replace(
    "assert(argc==2);",
    'assert(argc==3);research_trace=fopen(argv[2],"wb");assert(research_trace);setvbuf(research_trace,NULL,_IOFBF,1024*1024);',
)
driver = driver.replace(
    "bg_clear_events();bg_tick",
    "research_scenario=scenario;research_tick=tick;bg_clear_events();bg_tick",
)
driver = driver.replace(
    "assert(fclose(out)==0);", "assert(fclose(out)==0);assert(fclose(research_trace)==0);"
)
(OUT / "driver.c").write_text(driver)
sources = [
    "game.c",
    "combat_geometry.c",
    "terrain.c",
    "movement.c",
    "blam/runtime.c",
    "blam/core.c",
    "replay.c",
    "showcase.c",
]
generated = [
    "pickup_data.c",
    "combat_data.c",
    "movement_data.c",
    "interaction_defs.c",
    "vehicle_data.c",
    "terrain_data.c",
]
subprocess.run(
    [
        "clang",
        "-std=c17",
        "-O2",
        "-fno-fast-math",
        "-ffp-contract=off",
        "-fno-strict-aliasing",
        "-fwrapv",
        "-DBG_TELEMETRY",
        *(["-DBG_BODY_CANDIDATES"] if audit_options.vehicle_body_candidates else []),
        "-Wno-multichar",
        "-Wno-unused-function",
        "-Wno-incompatible-pointer-types",
        "-Iport/n64",
        "-Iport/n64/blam",
        "-I" + str(OUT),
        "-Ibuild/n64/blam-core",
        "-I" + str(solver),
        str(OUT / "driver.c"),
        str(OUT / "vehicle_physics.c"),
        *[str(ROOT / "port/n64" / n) for n in sources],
        *[str(ROOT / "build/n64/generated" / n) for n in generated],
        "-lm",
        "-o",
        str(OUT / "audit"),
    ],
    cwd=ROOT,
    check=True,
)
subprocess.run([str(OUT / "audit"), str(OUT / "state.bin"), str(OUT / "queries.bin")], check=True)
sha = hashlib.sha256((OUT / "state.bin").read_bytes()).hexdigest()
if audit_options.expected_state_sha:
    assert sha == audit_options.expected_state_sha, sha
records = []
with (OUT / "queries.bin").open("rb") as f:
    while data := f.read(68):
        x = struct.unpack("=9I8f", data)
        ids = struct.unpack("=" + str(x[7]) + "H", f.read(x[7] * 2))
        records.append((x[:9], x[9:], ids))
summary = {
    "state_sha256": sha,
    "queries": len(records),
    "body_candidates": audit_options.vehicle_body_candidates,
    "scope": "native work counts, not FPS",
    "groups": [],
}
for scenario in range(7):
    for stage in (1, 2, 3):
        rr = [r for r in records if r[0][0] == scenario and r[0][3] == stage]
        groups = collections.defaultdict(list)
        for h, v, ids in rr:
            groups[(h[1], h[2], h[4])].append((h, v, ids))
        repeated_inputs = 0
        repeated_lists = 0
        candidate_total = 0
        union_total = 0
        for rows in groups.values():
            repeated_inputs += len(rows) - len({(h[5], h[6], v[:6]) for h, v, i in rows})
            repeated_lists += len(rows) - len({i for h, v, i in rows})
            candidate_total += sum(len(i) for h, v, i in rows)
            union_total += len({id for h, v, i in rows for id in i})
        passes = collections.Counter(r[0][4] for r in rr)
        summary["groups"].append(
            dict(
                scenario=scenario,
                stage=stage,
                queries=len(rr),
                empty=sum(not r[2] for r in rr),
                hits=sum(bool(r[0][8]) for r in rr),
                passes=dict(passes),
                repeated_inputs=repeated_inputs,
                repeated_candidate_lists=repeated_lists,
                candidate_visits=candidate_total,
                per_group_union=union_total,
                groups=len(groups),
                cached_scans=sum(max(0, r[1][6]) for r in rr),
                envelope_scans=sum(r[1][7] for r in rr),
                envelope_overflow=sum(r[1][7] > 64 for r in rr),
            )
        )
(OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
