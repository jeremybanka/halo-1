/* Offline orthographic depth/face-ID raster for measured demake audits. */
#include <math.h>
#include <stdint.h>
void bg_demake_raster(const double *tri,const double *facing,const double *colors,
    unsigned count,unsigned width,unsigned height,uint8_t *rgb,int32_t *ids,double *depth) {
    for(unsigned p=0;p<width*height;p++) {
        ids[p]=-1;depth[p]=-INFINITY;
        rgb[p*3]=150;rgb[p*3+1]=158;rgb[p*3+2]=168;
    }
    for(unsigned i=0;i<count;i++) {
        if(facing[i]<=0)continue;
        const double *a=tri+i*9,*b=a+3,*c=a+6;
        double den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1]);
        if(fabs(den)<1e-8)continue;
        int x0=fmax(0,floor(fmin(a[0],fmin(b[0],c[0])))),x1=fmin(width-1,ceil(fmax(a[0],fmax(b[0],c[0]))));
        int y0=fmax(0,floor(fmin(a[1],fmin(b[1],c[1])))),y1=fmin(height-1,ceil(fmax(a[1],fmax(b[1],c[1]))));
        for(int y=y0;y<=y1;y++)for(int x=x0;x<=x1;x++) {
            double u=((b[1]-c[1])*(x+.5-c[0])+(c[0]-b[0])*(y+.5-c[1]))/den;
            double v=((c[1]-a[1])*(x+.5-c[0])+(a[0]-c[0])*(y+.5-c[1]))/den,w=1-u-v;
            if(u< -1e-7||v< -1e-7||w< -1e-7)continue;
            unsigned p=y*width+x;double z=u*a[2]+v*b[2]+w*c[2];if(z<=depth[p])continue;
            depth[p]=z;ids[p]=(int32_t)i;
            if(colors)for(unsigned k=0;k<3;k++)rgb[p*3+k]=(uint8_t)fmin(255,fmax(0,nearbyint(u*colors[i*9+k]+v*colors[i*9+3+k]+w*colors[i*9+6+k])));
        }
    }
}
