#include "benchmark.h"
#include <assert.h>
#include <stdio.h>
static bg_benchmark sample;
int main(void) {
    unsigned phases[BG_BENCHMARK_PHASES]={1,2,3,4,5,6,7,8,9,10,0,0,13};
    for(unsigned i=100;i;i--){unsigned categories[6]={i,0,0,0,0,0};bg_benchmark_add(&sample,i*1000,i>60,i,i*2,phases,categories);}
    bg_benchmark_finish(&sample);
    assert(sample.result[0].frames==100&&sample.result[0].elapsed==5050000);
    assert(sample.result[0].minimum==1000&&sample.result[0].maximum==100000);
    assert(sample.result[0].p95==95000&&sample.result[0].slow_frames==67);
    assert(sample.result[1].frames==60&&sample.result[1].p95==57000);
    assert(sample.result[2].frames==40&&sample.result[2].p95==98000);
    assert(sample.result[0].triangles==5050&&sample.result[2].max_triangles==100);
    assert(sample.result[0].vertices==10100&&sample.result[1].max_vertices==120&&sample.result[2].max_vertices==200);
    assert(sample.result[0].category_triangles[0]==5050&&sample.result[0].category_triangles[1]==0);
    assert(sample.result[0].phase_us[9]==1000&&sample.result[1].phase_us[3]==240);
    assert(sample.result[0].phase_us[12]==1300&&sample.result[2].phase_us[12]==520);
    puts("Benchmark quantiles, phase grouping, frame budget and sums pass");
    return 0;
}
