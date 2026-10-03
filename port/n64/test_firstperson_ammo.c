#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "firstperson_ammo_logic.h"

int main(void) {
    unsigned digits[2];
    for(int ammo=-2;ammo<=62;ammo++) {
        bg_ar_ammo_digits(ammo,digits);
        unsigned expected=ammo<0?0:ammo>60?60:(unsigned)ammo;
        assert(digits[0]*10+digits[1]==expected);
    }
    const int counts[4]={60,37,10,0};
    int16_t positions[2][4][8][3],uv[2][4][8][2];
    memset(positions,0x71,sizeof(positions));memset(uv,0x72,sizeof(uv));
    unsigned samples=0;
    for(unsigned clip=0;clip<4;clip++)for(unsigned frame=0;frame<bg_ar_ammo_clips[clip].frames;frame++)
        for(int fraction=0;fraction<=256;fraction+=32)for(unsigned slot=0;slot<2;slot++) {
            unsigned next=frame+1<bg_ar_ammo_clips[clip].frames?frame+1:frame;
            for(unsigned p=0;p<4;p++) {
                bg_ar_ammo_sample(positions[slot][p],uv[slot][p],clip,frame,next,fraction,counts[p]);
                for(unsigned i=0;i<8;i++) {
                    unsigned digit=i<4?(unsigned)counts[p]/10:(unsigned)counts[p]%10;
                    assert(uv[slot][p][i][0]==bg_ar_ammo_uv[i*2]+(int)digit*320);
                    assert(uv[slot][p][i][1]==bg_ar_ammo_uv[i*2+1]);
                    for(unsigned a=0;a<3;a++) {
                        const int16_t*q=bg_ar_ammo_clips[clip].positions;
                        int x=q[(frame*8+i)*3+a],y=q[(next*8+i)*3+a];
                        assert(positions[slot][p][i][a]==x+(y-x)*fraction/256);
                    }
                }
                samples++;
            }
        }
    assert(bg_needler_ammo_state(7,60,-1)==7);
    assert(bg_needler_ammo_state(7,60,43.f/30)==7);
    assert(bg_needler_ammo_state(7,60,49.f/30)==20);
    assert(bg_needler_ammo_state(12,3,2)==15);
    assert(bg_needler_ammo_state(0,0,2)==0);
    for(unsigned i=0;i<bg_needler_ammo.count;i++) {
        assert(bg_needler_ammo.vertices[i]<bg_needler_ammo.base_vertices);
        if(i)assert(bg_needler_ammo.vertices[i]>bg_needler_ammo.vertices[i-1]);
    }
    size_t bytes=((bg_needler_ammo.base_vertices+1u)/2u)*32u;
    unsigned char*buffer=malloc(bytes+32),*original=malloc(bytes+32);
    assert(buffer&&original);memset(original,0xA7,bytes+32);
    unsigned needle_samples=0;
    for(unsigned ammo=0;ammo<=20;ammo++)for(unsigned clip=0;clip<4;clip++)
        for(unsigned f=0;f<bg_needler_ammo.clip_frames[clip];f++)for(int fraction=0;fraction<=256;fraction+=128) {
            memcpy(buffer,original,bytes+32);
            unsigned next=f+1<bg_needler_ammo.clip_frames[clip]?f+1:f;
            bg_needler_ammo_sample(buffer+16,&bg_needler_ammo,clip,f,next,fraction,ammo);
            unsigned affected=0;
            for(unsigned v=0;v<bg_needler_ammo.base_vertices;v++) {
                size_t offset=16+(v/2)*32+(v%2)*8;
                if(affected<bg_needler_ammo.count&&bg_needler_ammo.vertices[affected]==v) {
                    unsigned track=bg_needler_ammo.indices[ammo*bg_needler_ammo.count+affected];
                    assert(track<bg_needler_ammo.tracks);
                    int16_t p[3];memcpy(p,buffer+offset,6);
                    for(unsigned a=0;a<3;a++) {
                        unsigned f0=f+bg_needler_ammo.clip_offsets[clip],f1=next+bg_needler_ammo.clip_offsets[clip];
                        int x=bg_needler_ammo.positions[(f0*bg_needler_ammo.tracks+track)*3+a];
                        int y=bg_needler_ammo.positions[(f1*bg_needler_ammo.tracks+track)*3+a];
                        assert(p[a]==bg_needler_ammo.origin[a]+x+(y-x)*fraction/256);
                    }
                    memcpy(buffer+offset,original+offset,6);affected++;
                }
            }
            assert(affected==bg_needler_ammo.count);
            assert(!memcmp(buffer,original,bytes+32)); /* includes normals/RGB/UV and canaries */
            needle_samples++;
        }
    free(buffer);free(original);
    printf("PASS: %u AR slot/player/pose samples; %u Needler ammo/pose samples; source intervals, exact XYZ decode and all non-position bytes/canaries preserved.\n",samples,needle_samples);
}
