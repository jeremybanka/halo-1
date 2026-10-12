"""Compare exact outward rounding and fail-open bounds with the checkpoint."""

from pathlib import Path
import subprocess
from runtime_source import validation_output
from test_render_matrix import function

ROOT = Path(__file__).resolve().parents[2]
C = r"""
#include "render_bounds.h"
#include <assert.h>
#include <stdio.h>
static void reference(bg_cull_bounds*out,const bg_bounds*in){REFERENCE}
static uint32_t seed=0xce6464;
static uint32_t random_bits(void){seed=seed*1664525u+1013904223u;return seed;}
int main(void){
 unsigned valid=0;
 for(unsigned trial=0;trial<1000000;trial++){
  bg_bounds b;
  for(unsigned a=0;a<3;a++){
   if(trial&1){
    uint32_t lo=random_bits(),hi=random_bits();
    memcpy(&b.min[a],&lo,4);memcpy(&b.max[a],&hi,4);
   }else{
    b.min[a]=(int32_t)(random_bits()%131080)-65540.f;
    b.max[a]=b.min[a]+(random_bits()%4000)*.25f;
    b.min[a]+=(random_bits()%8)*.125f;
   }
  }
  bg_cull_bounds old={0},now={0};reference(&old,&b);bg_bounds_quantize(&now,&b);
  assert(old.valid==now.valid);
  assert(!memcmp(old.values,now.values,sizeof(old.values)));
  valid+=now.valid;
 }
 printf("PASS: 1000000 bounds match checkpoint rounding, including invalid/overflow (%u valid)\n",valid);
}
"""
out = validation_output("bounds-quantize")
out.mkdir(parents=True, exist_ok=True)
checkpoint = subprocess.check_output(
    ["git", "show", "ffc5e53d:port/n64/render_bounds.h"], cwd=ROOT, text=True
)
source = out / "bounds.c"
source.write_text(C.replace("REFERENCE", function(checkpoint, "bg_bounds_quantize")))
for label, math in (
    ("strict", ["-fno-fast-math"]),
    (
        "target",
        ["-ffast-math", "-ftrapping-math", "-fno-associative-math", "-fno-finite-math-only"],
    ),
):
    binary = out / label
    subprocess.run(
        [
            "clang",
            "-std=c17",
            "-O2",
            "-ffp-contract=off",
            "-fsanitize=address,undefined",
            "-Iport/n64",
            *math,
            str(source),
            "-lm",
            "-o",
            str(binary),
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run([str(binary)], check=True)
