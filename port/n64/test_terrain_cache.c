/* Broad-phase conservatism oracle: compare cached IDs against every exact
 * capsule/triangle distance, including motion inside the cached AABB. */
#include "terrain.c"
#include <assert.h>
#include <stdio.h>
static uint32_t seed=1234567;
static float rand01(void){seed=seed*1664525u+1013904223u;return (seed>>8)*(1.f/16777216);}
int main(void){
    bg_player p={0};unsigned contacts=0;
    for(unsigned run=0;run<160;run++){
        unsigned face=(unsigned)(rand01()*bg_collision_count);const bg_triangle*t=&bg_collision[face];
        for(unsigned k=0;k<3;k++)p.pos[k]=(t->p[0][k]+t->p[1][k]+t->p[2][k])/3;
        p.pos[1]-=.25f;float base[3];memcpy(base,p.pos,12);bg_terrain_reset();
        for(unsigned frame=0;frame<4;frame++){
            if(frame)for(unsigned k=0;k<3;k++)p.pos[k]=base[k]+(rand01()-.5f)*.48f;
            p.crouch_amount=rand01();const terrain_candidates*c=nearby(&p);
            for(unsigned j=0;j<bg_collision_count;j++){
                float a[3],b[3];float r=bg_movement.radius+.0155f;
                if(bg_capsule_triangle(p.pos,bg_body_height(&p),bg_movement.radius,&bg_collision[j],a,b)>r*r)continue;
                contacts++;bool found=c->count==UINT16_MAX;
                for(unsigned n=0;!found&&n<c->count;n++)found=c->ids[n]==j;
                assert(found);
            }
        }
    }
    printf("PASS: 640 cached capsule positions vs every source triangle, %u contacts, none omitted\n",contacts);
}
