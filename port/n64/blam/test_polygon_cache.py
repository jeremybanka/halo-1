"""Compare cached polygon metadata/projections and containment with original factories.

Every source surface, directed edge, vertex and near-edge probe is covered.
Only active points are compared: original unused tail bytes have no semantics.
"""

from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime_source import validation_output

ROOT = Path(__file__).resolve().parents[3]
C = r"""
#include <stdio.h>
int main(void){world_load();unsigned surfaces=0,probes=0;
 for(int si=0;si<bg_vehicle_bsp.surfaces.count;si++){
  collision_features_new(&vehicle_workspace->features);
  collision_features_from_surface(&bg_vehicle_bsp,si,NULL,0,.375f,NONE,&vehicle_workspace->features);
  assert(vehicle_workspace->features.count[_collision_feature_prism]==1);
  const struct collision_prism*old=&vehicle_workspace->features.prisms[0],*p=cached_polygon(&bg_vehicle_bsp,si);
  struct collision_prism adjusted=*p;adjusted.height=.375f;
  assert(!memcmp(old,&adjusted,offsetof(struct collision_prism,points)+old->point_count*sizeof(real_point2d)));
  const struct collision_surface*s=TAG_BLOCK_GET_ELEMENT(&bg_vehicle_bsp.surfaces,si,struct collision_surface);
  int edge=s->first_edge_index,j=0;
  do{
   const struct collision_edge*e=TAG_BLOCK_GET_ELEMENT(&bg_vehicle_bsp.edges,edge,struct collision_edge);bool reverse=e->surface_indices[1]==si;
   const struct collision_vertex*v0=TAG_BLOCK_GET_ELEMENT(&bg_vehicle_bsp.vertices,e->vertex_indices[reverse],struct collision_vertex);
   const struct collision_vertex*v1=TAG_BLOCK_GET_ELEMENT(&bg_vehicle_bsp.vertices,e->vertex_indices[!reverse],struct collision_vertex);
   real_point2d a,b;project_point3d(&v0->point,p->projection_axis,p->projection_sign,&a);project_point3d(&v1->point,p->projection_axis,p->projection_sign,&b);
   assert(!memcmp(&a,&p->points[j],sizeof(a)));assert(!memcmp(&b,&p->points[j+1<p->point_count?j+1:0],sizeof(b)));
   for(unsigned probe=0;probe<25;probe++){
    float weight=(probe%5)*.25f;real_point2d q={.n={a.x+weight*(b.x-a.x),a.y+weight*(b.y-a.y)}};
    if(probe>=5){unsigned axis=(probe/5)&1;q.n[axis]+=probe&1?.00001f:-.00001f;}
    bool expected=collision_surface_test_point(&bg_vehicle_bsp,0,NULL,si,p->projection_axis,p->projection_sign,&q);
    bool actual=cached_polygon_contains(p,&q);assert(expected==actual);probes++;
   }
   edge=e->edge_indices[reverse];j++;
  }while(edge!=s->first_edge_index);
  assert(j==p->point_count);surfaces++;
 }
 printf("PASS: %u original polygon factories and %u vertex/edge containment probes match cache\n",surfaces,probes);
}
"""


def main():
    out = validation_output("polygon-cache")
    out.mkdir(parents=True, exist_ok=True)
    solver = out / "solver"
    subprocess.run(
        [sys.executable, ROOT / "port/n64/blam/prepare_vehicle.py", "--output", solver], check=True
    )
    source = out / "polygons.c"
    source.write_text((ROOT / "port/n64/blam/vehicle_physics.c").read_text() + C)
    shared = (
        "game.c",
        "combat_geometry.c",
        "terrain.c",
        "movement.c",
        "blam/runtime.c",
        "blam/core.c",
    )
    generated = (
        "pickup_data.c",
        "combat_data.c",
        "movement_data.c",
        "interaction_defs.c",
        "vehicle_data.c",
        "terrain_data.c",
    )
    for label, math in (
        ("strict", ["-fno-fast-math"]),
        ("target", ["-ffast-math", "-ftrapping-math", "-fno-associative-math"]),
    ):
        binary = out / label
        subprocess.run(
            [
                "clang",
                "-std=c17",
                "-O2",
                "-g",
                "-fsanitize=address,undefined",
                "-ffp-contract=off",
                "-fno-strict-aliasing",
                "-fwrapv",
                "-Wno-multichar",
                "-Wno-unused-function",
                "-Wno-incompatible-pointer-types",
                "-Iport/n64",
                "-Iport/n64/blam",
                "-Ibuild/n64/blam-core",
                "-I" + str(solver),
                *math,
                str(source),
                *(str(ROOT / "port/n64" / s) for s in shared),
                *(str(ROOT / "build/n64/generated" / s) for s in generated),
                "-lm",
                "-o",
                str(binary),
            ],
            cwd=ROOT,
            check=True,
        )
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
