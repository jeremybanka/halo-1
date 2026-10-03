#include "render_micro_lod.h"
#include <assert.h>
#include <stdio.h>
static float from_bits(uint32_t raw){volatile uint32_t value=raw;uint32_t v=value;float f;memcpy(&f,&v,sizeof(f));return f;}
static uint32_t seed=0xce064;
static float random_unit(void){seed=seed*1664525u+1013904223u;return (seed>>8)*(1.f/16777216.f);}
int main(void){
    float camera[4][4]={{1,0,0,0},{0,1,0,0},{0,0,1,0},{0,0,0,1}};
    const float projection[4][4]={{1.25f,0,0,0},{0,1.6666667f,0,0},{0,0,1,0},{0,0,0,1}};
    unsigned eligible[3]={0};double maximum_fixed_span_error=0;
    for(unsigned test=0;test<40000;test++){
        float angle=((int)(test%17)-8)*.1f;
        camera[0][0]=cosf(angle);camera[2][0]=sinf(angle);camera[0][2]=-sinf(angle);camera[2][2]=cosf(angle);
        bg_cull_bounds b={.valid=true};
        float depth=10+random_unit()*5000;
        for(unsigned a=0;a<3;a++){
            float center=a==2?-depth:(random_unit()-.5f)*depth*3.f;
            int radius=1+(int)(random_unit()*30);
            b.min[a]=(int16_t)floorf(center-radius);b.max[a]=(int16_t)ceilf(center+radius);
        }
        bg_micro_sphere s;bg_micro_sphere_from_bounds(&s,&b);assert(s.valid);
        for(unsigned corner=0;corner<8;corner++){
            float d2=0;for(unsigned a=0;a<3;a++){float v=(corner&(1u<<a))?b.max[a]:b.min[a];float d=v-s.center[a];d2+=d*d;}
            assert(d2<=s.radius*s.radius);
        }
        for(unsigned p=0;p<3;p++){
            float pixels=4+2*p;
            bool pass=bg_micro_lod_below(&s,camera,projection,160,120,1.4f,pixels,true,false,4);
            if(!pass)continue;eligible[p]++;
            /* Independent double-precision full rectangle of all box corners. */
            double minx=1e30,maxx=-1e30,miny=1e30,maxy=-1e30;
            double fxmin=1e30,fxmax=-1e30,fymin=1e30,fymax=-1e30;
            for(unsigned corner=0;corner<8;corner++){
                double v[3];for(unsigned a=0;a<3;a++)v[a]=(corner&(1u<<a))?b.max[a]:b.min[a];
                double cv[3]={0};for(unsigned a=0;a<3;a++){cv[a]=camera[3][a];for(unsigned b=0;b<3;b++)cv[a]+=v[b]*camera[b][a];}
                double dx=cv[0]/-cv[2]*160*projection[0][0]*.5;
                double dy=cv[1]/-cv[2]*120*projection[1][1]*.5;
                assert(-cv[2]>1.401);
                double fixedcv[3];for(unsigned a=0;a<3;a++){fixedcv[a]=trunc((double)camera[3][a]*65536)/65536;for(unsigned k=0;k<3;k++)fixedcv[a]+=v[k]*trunc((double)camera[k][a]*65536)/65536;}
                double fdx=fixedcv[0]/-fixedcv[2]*80*trunc((double)projection[0][0]*65536)/65536;
                double fdy=fixedcv[1]/-fixedcv[2]*60*trunc((double)projection[1][1]*65536)/65536;
                fxmin=fmin(fxmin,fdx);fxmax=fmax(fxmax,fdx);fymin=fmin(fymin,fdy);fymax=fmax(fymax,fdy);
                minx=fmin(minx,dx);maxx=fmax(maxx,dx);miny=fmin(miny,dy);maxy=fmax(maxy,dy);
            }
            double span=fmax(maxx-minx,maxy-miny),fixedspan=fmax(fxmax-fxmin,fymax-fymin);
            assert(span+.5<pixels+1e-4);assert(fixedspan<pixels);
            maximum_fixed_span_error=fmax(maximum_fixed_span_error,fabs(fixedspan-span));
            assert(!bg_micro_lod_below(&s,camera,projection,160,120,1.4f,pixels,false,false,4));
            assert(!bg_micro_lod_below(&s,camera,projection,160,120,1.4f,pixels,true,true,4));
            assert(!bg_micro_lod_below(&s,camera,projection,320,240,1.4f,pixels,true,false,1));
            assert(!bg_micro_lod_below(&s,camera,projection,320,120,1.4f,pixels,true,false,2));
        }
    }
    for(unsigned p=0;p<3;p++)assert(eligible[p]>1000);
    camera[0][0]=camera[2][2]=1;camera[2][0]=camera[0][2]=0;
    bg_micro_sphere s={{0,0,-1000},1,true,NULL};
    assert(bg_micro_lod_below(&s,camera,projection,160,120,1.4f,4,true,false,4));
    s.center[2]=-2.4f;assert(!bg_micro_lod_below(&s,camera,projection,160,120,1.4f,8,true,false,4));
    s.center[2]=-2.399f;assert(!bg_micro_lod_below(&s,camera,projection,160,120,1.4f,8,true,false,4));
    s.center[2]=-1000;s.valid=false;assert(!bg_micro_lod_below(&s,camera,projection,160,120,1.4f,8,true,false,4));
    s.valid=true;s.radius=from_bits(0x7fc00000u);assert(!bg_micro_lod_below(&s,camera,projection,160,120,1.4f,8,true,false,4));
    s.radius=1;s.center[0]=from_bits(0x7f800000u);assert(!bg_micro_lod_below(&s,camera,projection,160,120,1.4f,8,true,false,4));
    s.center[0]=0;float bad[4][4];memcpy(bad,projection,sizeof(bad));bad[0][0]=from_bits(0x7fc00000u);
    assert(!bg_micro_lod_below(&s,camera,bad,160,120,1.4f,8,true,false,4));
    memcpy(bad,camera,sizeof(bad));bad[3][0]=1e30f;
    assert(!bg_micro_lod_below(&s,bad,projection,160,120,1.4f,8,true,false,4));
    memcpy(bad,camera,sizeof(bad));bad[0][0]=from_bits(0x7f800000u);
    assert(!bg_micro_lod_below(&s,bad,projection,160,120,1.4f,8,true,false,4));
    bg_cull_bounds invalid={.min={3,0,0},.max={2,1,1},.valid=true};bg_micro_sphere_from_bounds(&s,&invalid);assert(!s.valid);
    printf("Max camera/projection 16.16-only span difference: %.9g pixels (not a full RSP raster equivalence claim)\n",maximum_fixed_span_error);
    printf("PASS: 40,000 hybrid outward boxes with.5pxmargin;4/6/8px eligibility %u/%u/%u; zoom/near-plane/invalid/one-two-view guards\n",eligible[0],eligible[1],eligible[2]);
}
