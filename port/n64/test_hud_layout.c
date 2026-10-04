#include "hud_layout.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

/* Independent transcription of the relevant original compute_window_bounds
 * and render_camera_build_frustum_bounds operations. The shipping helper
 * does not call this reference. This port supports 1, 2, 3 or 4 views. */
static void source_reference(unsigned views,unsigned player,float *x,float *y,
    float *projection_x,float *projection_y)
{
    int columns=1,rows=1;
    while((unsigned)(columns*rows)<views){
        if(columns<rows)columns++;
        else{columns=1;rows++;}
    }
    int row=(int)player/columns,column=(int)player-row*columns;
    int inset=views>1?4:0,w=544/columns,h=408/rows;
    int window[4]={48+w*column,36+h*row,48+w*(column+1),36+h*(row+1)};
    int viewport[4];memcpy(viewport,window,sizeof(viewport));
    window[0]+=column*inset;window[2]-=(column==0)*inset;
    window[1]+=row*inset;window[3]-=(row==0)*inset;
    if(!column)viewport[0]=0;if(column+1==columns)viewport[2]=640;
    if(!row)viewport[1]=0;if(row+1==rows)viewport[3]=480;
    float vw=viewport[2]-viewport[0],vh=viewport[3]-viewport[1];
    *x=((window[0]+window[2])/2.f-viewport[0])/vw;
    *y=((window[1]+window[3])/2.f-viewport[1])/vh;
    float inverse_height=1.f/(window[3]-window[1]),aspect=vh/vw;
    float l=(2*viewport[0]-window[0]-window[2])*inverse_height*aspect;
    float r=(2*viewport[2]-window[0]-window[2])*inverse_height*aspect;
    float top=-(2*viewport[1]-window[1]-window[3])*inverse_height;
    float bottom=-(2*viewport[3]-window[1]-window[3])*inverse_height;
    *projection_x=(l+r)/(r-l);
    *projection_y=(bottom+top)/(top-bottom);
}

int main(void)
{
    const unsigned layouts[]={1,2,3,4};
    const float expected[4][4][2]={{{160,120}},{{159,68},{159,172}},
        {{91,68},{229,68},{91,172}},
        {{91,68},{229,68},{91,172},{229,172}}};
    unsigned projected=0;
    for(unsigned l=0;l<4;l++)for(unsigned p=0;p<layouts[l];p++){
        unsigned views=layouts[l],columns=views>=3?2:1;
        float width=views>=3?160:320,height=views==1?240:120;
        float x=(p%columns)*width,y=(p/columns)*height,cx,cy,rx,ry,px,py;
        source_reference(views,p,&rx,&ry,&px,&py);
        bg_hud_aim_point(views,p,x,y,width,height,&cx,&cy);
        assert(fabsf(cx-expected[l][p][0])<.0001f);
        assert(fabsf(cy-expected[l][p][1])<.0001f);
        assert(fabsf((cx-x)/width-rx)<.000001f);
        assert(fabsf((cy-y)/height-ry)<.000001f);
        for(unsigned zoom=1;zoom<=10;zoom++){
            float matrix[4][4]={{0}},before[4][4];
            matrix[0][0]=1.7f*zoom;matrix[1][1]=2.1f*zoom;
            matrix[2][2]=-1.001f;matrix[2][3]=-1;matrix[3][2]=-2.8f;
            memcpy(before,matrix,sizeof(matrix));bg_hud_aim_projection(matrix,views,p);
            assert(fabsf(matrix[2][0]-px)<.000001f);
            assert(fabsf(matrix[2][1]-py)<.000001f);
            for(unsigned a=0;a<4;a++)for(unsigned b=0;b<4;b++)
                if(a!=2||b>1)assert(matrix[a][b]==before[a][b]);
            /* Every point on the unchanged forward shot ray projects to the
             * reticle, independently of depth and zoom. Include fixed16.16
             * projection quantization used by Tiny3D. */
            for(unsigned distance=2;distance<6200;distance+=31){
                float z=-(float)distance,w=-z;
                float sx=x+(matrix[2][0]*z/w+1)*width*.5f;
                float sy=y+(1-matrix[2][1]*z/w)*height*.5f;
                assert(fabsf(sx-cx)<.0001f&&fabsf(sy-cy)<.0001f);
                float qx=truncf(matrix[2][0]*65536.f)/65536.f;
                float qy=truncf(matrix[2][1]*65536.f)/65536.f;
                assert(fabsf(x+(1-qx)*width*.5f-cx)<.0025f);
                assert(fabsf(y+(1+qy)*height*.5f-cy)<.0025f);projected++;
            }
        }
        /* Viewport-local scaling also works at original resolution and at
         * a translated viewport origin, not only a fixed 640→320 shortcut. */
        float ax,ay;bg_hud_aim_point(views,p,17,23,width*2,height*2,&ax,&ay);
        assert(fabsf(ax-(17+2*(cx-x)))<.0001f);
        assert(fabsf(ay-(23+2*(cy-y)))<.0001f);
    }
    printf("PASS: original safe-window centers, ten viewports, 10 zoom scales, %u forward rays and fixed projection rounding\n",projected);
}
