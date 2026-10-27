#include <assert.h>
#define BG_WORLD_CHUNK_CAPACITY 4096
#include "render_world_submit.h"
int main(void) {
    bg_world_submit_cache c={0};
    uint32_t row[2]={0};
    bg_world_submit_key k={.cell=row,.pvs=0x1234,.map=1,.groups=128,.chunks=1850,.lod=true};
    for(unsigned i=0;i<128;i++)k.levels[i]=i&1;
    assert(!bg_world_submit_same(&c,&k));c.valid=true;c.key=k;
    assert(bg_world_submit_same(&c,&k));
    for(unsigned i=0;i<128;i++) {k.levels[i]^=1;assert(!bg_world_submit_same(&c,&k));k.levels[i]^=1;}
    k.cell=0;assert(!bg_world_submit_same(&c,&k));k=c.key;
    k.pvs^=1;assert(!bg_world_submit_same(&c,&k));k=c.key;
    k.map++;assert(!bg_world_submit_same(&c,&k));k=c.key;
    k.groups--;assert(!bg_world_submit_same(&c,&k));k=c.key;
    k.chunks--;assert(!bg_world_submit_same(&c,&k));k=c.key;
    k.room=true;assert(!bg_world_submit_same(&c,&k));k=c.key;
    k.lod=false;assert(!bg_world_submit_same(&c,&k));
    c.key=k;memset(k.levels,0xff,sizeof(k.levels));assert(bg_world_submit_same(&c,&k));
    c.valid=false;assert(!bg_world_submit_same(&c,&k));
}
