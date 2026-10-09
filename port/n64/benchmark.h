#ifndef BG_BENCHMARK_H
#define BG_BENCHMARK_H
#include <stdint.h>
#include <stdlib.h>

/* NTSC can present at most 4500 frames in the 75-second sample window.
 * Store the phase in the high bit so the complete sample bank uses 20 KiB. */
#define BG_BENCHMARK_CAPACITY 5120
#define BG_BENCHMARK_PHASES 17
#define BG_BENCHMARK_CATEGORIES 6
typedef struct {
    uint64_t elapsed,triangles,vertices,phase_us[BG_BENCHMARK_PHASES];
    uint64_t category_triangles[BG_BENCHMARK_CATEGORIES];
    unsigned frames,slow_frames,minimum,maximum,p95,max_triangles,max_vertices;
} bg_benchmark_result;
typedef struct {
    uint32_t samples[BG_BENCHMARK_CAPACITY];
    unsigned count,overflow;
    /* 0: combined, 1: combat, 2: vehicles. */
    bg_benchmark_result result[3];
} bg_benchmark;

static inline void bg_benchmark_add(bg_benchmark*b,uint32_t elapsed,unsigned vehicle,
        unsigned triangles,unsigned vertices,const unsigned phase_us[BG_BENCHMARK_PHASES],
        const unsigned categories[BG_BENCHMARK_CATEGORIES]) {
    vehicle=!!vehicle;
    if(b->count<BG_BENCHMARK_CAPACITY)b->samples[b->count++]=elapsed|(vehicle<<31);
    else b->overflow++;
    for(unsigned i=0;i<2;i++) {
        bg_benchmark_result*r=&b->result[i?1+vehicle:0];
        if(!r->frames||elapsed<r->minimum)r->minimum=elapsed;
        if(elapsed>r->maximum)r->maximum=elapsed;
        r->frames++;r->elapsed+=elapsed;r->slow_frames+=elapsed>33333;
        r->triangles+=triangles;if(triangles>r->max_triangles)r->max_triangles=triangles;
        r->vertices+=vertices;if(vertices>r->max_vertices)r->max_vertices=vertices;
        for(unsigned p=0;p<BG_BENCHMARK_PHASES;p++)r->phase_us[p]+=phase_us[p];
        for(unsigned p=0;p<BG_BENCHMARK_CATEGORIES;p++)r->category_triangles[p]+=categories[p];
    }
}
static int bg_benchmark_compare(const void*a,const void*b) {
    uint32_t x=*(const uint32_t*)a&0x7fffffff,y=*(const uint32_t*)b&0x7fffffff;
    return (x>y)-(x<y);
}
static inline void bg_benchmark_finish(bg_benchmark*b) {
    qsort(b->samples,b->count,sizeof(b->samples[0]),bg_benchmark_compare);
    unsigned seen[3]={0};
    for(unsigned n=0;n<b->count;n++)for(unsigned i=0;i<2;i++) {
        unsigned index=i?1+(b->samples[n]>>31):0;
        if(++seen[index]==(b->result[index].frames*95+99)/100)
            b->result[index].p95=b->samples[n]&0x7fffffff;
    }
}
#endif
