#include "flag_cloth.h"
#include <assert.h>
#include <stdio.h>
static const bg_cloth_physics physics={.375f,.3f,-3.20161004f,7.57934191f};
static void check(const bg_cloth_state *s,const float corners[3][3]) {
    assert(!memcmp(s->points[0].p,corners[0],12));
    assert(!memcmp(s->points[BG_CLOTH_ROWS-1].p,corners[1],12));
    for(unsigned i=0;i<BG_CLOTH_VERTICES;i++) {
        float d[3];for(unsigned a=0;a<3;a++) {
            assert(isfinite(s->points[i].p[a])&&isfinite(s->points[i].v[a]));
            d[a]=s->points[i].p[a]-corners[0][a];
        }
        assert(bg_cloth_dot(d,d)<1.5f*1.5f);
    }
}
int main(void) {
    float corners[3][3]={{0,1,0},{0,.65f,0},{-.375f,1,0}},wind[BG_CLOTH_VERTICES][3]={{0}};
    bg_cloth_state still={0},moving={0};bg_cloth_reset(&still,corners);bg_cloth_reset(&moving,corners);
    for(unsigned t=0;t<900;t++)bg_cloth_step(&still,&physics,corners,wind,1.f/30);
    check(&still,corners);assert(still.points[BG_CLOTH_VERTICES-1].p[1]<.65f);
    bg_cloth_wind_state ws={0};const bg_cloth_weather weather={.speed={.6f,1},.variation={.87f,.35f},.magnitude=2,.root=-2};
    float motion=0;
    for(unsigned t=0;t<18000;t++) {
        bg_cloth_wind_step(&ws,&weather);
        for(unsigned i=0;i<BG_CLOTH_VERTICES;i++)for(unsigned a=0;a<3;a++)wind[i][a]=ws.wind[a];
        float angle=t*.013f,shift=.8f*sinf(t*.03f);
        corners[0][0]=corners[1][0]=shift;corners[2][0]=shift-.375f*cosf(angle);corners[2][2]=-.375f*sinf(angle);
        float before=moving.points[BG_CLOTH_VERTICES-1].p[2];
        bg_cloth_step(&moving,&physics,corners,wind,1.f/30);check(&moving,corners);
        motion+=fabsf(moving.points[BG_CLOTH_VERTICES-1].p[2]-before);
    }
    assert(motion>1);assert(still.points[0].p[0]==0); /* States do not share mutable storage. */
    for(unsigned c=0;c<3;c++)corners[c][0]+=20;
    bg_cloth_step(&moving,&physics,corners,wind,1.f/30);check(&moving,corners);
    for(unsigned i=0;i<BG_CLOTH_VERTICES;i++)for(unsigned a=0;a<3;a++)assert(moving.points[i].v[a]==0);
    const bg_cloth_weather_node nodes[]={{{1,0,0,2},-1,-2}};
    const bg_cloth_weather selective={.nodes=nodes,.root=0,.count=1};
    assert(!bg_cloth_has_wind(&selective,(float[]){1,0,0}));
    assert(bg_cloth_has_wind(&selective,(float[]){3,0,0}));
    float noise[3][64][3];
    for(unsigned a=0;a<3;a++)for(unsigned i=0;i<64;i++)for(unsigned c=0;c<3;c++)noise[a][i][c]=(float)((i+c+a)%64)/64;
    const bg_cloth_weather gusts={.local_weight=.5f,.local_rate=1.5f};
    const float scale[3]={.1f,.2f,.07f};
    for(unsigned i=0;i<4096;i++){
        float source[3]={-128.f+i/16.f,3.0625f-i/32.f,i/64.f},out[3],expected[3];
        memcpy(expected,ws.wind,12);bg_cloth_wind_at(out,&gusts,&ws,noise,source);
        for(unsigned a=0;a<3;a++){
            unsigned at=(unsigned)lrintf(fabsf((scale[a]*ws.tick*gusts.local_rate+source[a])*8))&63;
            for(unsigned c=0;c<3;c++)expected[c]+=noise[a][at][c]*gusts.local_weight*ws.speed/3;
        }
        for(unsigned c=0;c<3;c++)assert(fabsf(expected[c]-out[c])<1e-6f);
    }
    puts("PASS: 10-minute moving/turning cloth stress, exact pole anchors, sag, independent flags, teleport reset and weather selection");
}
