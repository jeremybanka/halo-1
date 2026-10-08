#include "interaction_cache.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static uint8_t rom[131072];static unsigned reads;
static void load(void*out,uint32_t offset,uint32_t bytes){
    assert(offset+bytes<=sizeof(rom));memcpy(out,rom+offset,bytes);reads++;
}
int main(void){
    const unsigned stride=7520;
    bg_pose_cache c={.storage=malloc(bg_pose_cache_bytes(stride)),.stride=stride};assert(c.storage);
    for(unsigned i=0;i<sizeof(rom);i++)rom[i]=(i*37+(i>>8))&255;
    /* Four seats with near/far geometry and eight tiny marker tracks. Reuse
     * interpolation endpoints without re-reading their immutable ROM bytes. */
    for(unsigned frame=0;frame<30;frame++)for(unsigned i=0;i<8;i++){
        unsigned offset=i*8192,bytes=3008+i*16;
        assert(!memcmp(bg_pose_cache_fetch(&c,offset,bytes,load),rom+offset,bytes));
        assert(!memcmp(bg_pose_cache_fetch(&c,90000+i*128,64,load),rom+90000+i*128,64));
    }
    assert(reads==16);
    /* Changed endpoint lengths, clip changes and repeated evictions must
     * return the same bytes as an uncached read, including maximum pairs. */
    for(unsigned i=0;i<10000;i++){
        unsigned offset=(i*31%1400)*64,bytes=i%5?16*(1+i%400):stride;
        assert(!memcmp(bg_pose_cache_fetch(&c,offset,bytes,load),rom+offset,bytes));
    }
    free(c.storage);puts("PASS: cached ROM frame pairs byte-identical through reuse, length changes and 10000 evictions; 480 reads reduced to 16 for stable endpoints");
}
