"""Compare five-ray hull packets with the checkpoint's complete single-ray kernel.

Static and articulated hulls, both orientation paths, zero/short rays and
independent clipping distances are tested under strict and integration math.
"""

from pathlib import Path
import subprocess
from runtime_source import validation_output
from test_render_matrix import function, compact

ROOT = Path(__file__).resolve().parents[2]
C = r"""
#include <stdio.h>
static uint32_t test_seed=0xceca5;
static float rnd(float lo,float hi){test_seed=test_seed*1664525u+1013904223u;return lo+(hi-lo)*(test_seed>>8)/16777215.f;}
static float reference(const bg_vehicle*v,const float origin[3],const float direction[3],float distance,unsigned*material){REFERENCE}
int main(void){unsigned rays=0,obstructed=0;
 for(unsigned trial=0;trial<16000;trial++){
  bg_vehicle v={0};v.kind=trial%4;v.active=trial%5!=0;v.hatch=rnd(0,1);v.hatch_closing=trial&1;
  v.pos[0]=rnd(-10,10);v.pos[1]=rnd(-2,5);v.pos[2]=rnd(-10,10);
  v.yaw=rnd(-3.14,3.14);v.pitch=rnd(-.8,.8);v.turret_yaw=rnd(-3.14,3.14);v.turret_pitch=rnd(-1,1);
  if(trial&1){float f[3]={1,0,0},u[3]={0,1,0};bg_vehicle_transform(&v,f,v.forward);bg_vehicle_transform(&v,u,v.up);
   for(unsigned a=0;a<3;a++){v.forward[a]-=v.pos[a];v.up[a]-=v.pos[a];}v.physics_valid=true;}
  float origin[3];for(unsigned a=0;a<3;a++)origin[a]=v.pos[a]+rnd(-5,5);
  float yaw=rnd(-3.14,3.14),pitch=rnd(-1.5,1.5),direction[5][3],reaches[5],old[5],now[5],length=rnd(.001,12);
  for(unsigned i=0;i<5;i++){
   direction[i][0]=cosf(yaw)*cosf(pitch)*length+(i==1?.1f:i==2?-.1f:0);
   direction[i][1]=sinf(pitch)*length+(i==3?.1f:i==4?-.1f:0);
   direction[i][2]=-sinf(yaw)*cosf(pitch)*length;
   reaches[i]=sqrtf(dot3(direction[i],direction[i]));
   for(unsigned a=0;a<3;a++)direction[i][a]/=fmaxf(.001f,reaches[i]);
   if((trial+i)%31==0)reaches[i]=0;
   old[i]=now[i]=rnd(0,12);
   if(reaches[i]>=.001f)old[i]=reference(&v,origin,direction[i],old[i],NULL);
  }
  bg_vehicle_camera_packet(&v,origin,(const float(*)[3])direction,reaches,now);
  for(unsigned i=0;i<5;i++){assert(!memcmp(old+i,now+i,sizeof(float)));rays++;obstructed+=now[i]<1;}
 }
 printf("PASS: %u hull packet lanes match checkpoint kernel exactly (%u near hits)\n",rays,obstructed);
}
"""


def main():
    out = validation_output("vehicle-camera-packet")
    out.mkdir(parents=True, exist_ok=True)
    checkpoint = subprocess.check_output(
        ["git", "show", "892fd19a:port/n64/combat_geometry.c"], cwd=ROOT, text=True
    )
    current = (ROOT / "port/n64/combat_geometry.c").read_text()
    for name in ("dot3", "cross3", "vehicle_sweep_radius", "bg_vehicle_collision_pose_impl"):
        assert compact(function(current, name)) == compact(function(checkpoint, name)), name
    source = out / "packet.c"
    source.write_text(
        current + C.replace("REFERENCE", function(checkpoint, "bg_vehicle_hit_ray_material_impl"))
    )
    shared = (
        "game.c",
        "terrain.c",
        "movement.c",
        "blam/runtime.c",
        "blam/core.c",
        "blam/vehicle_physics.c",
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
                "-Ibuild/n64/blam-core",
                "-Ibuild/n64/blam-vehicle",
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
