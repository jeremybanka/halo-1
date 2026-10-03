/* Integration tests against the locally generated, reduced Blood Gulch mesh. */
#include "game.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static void ticks(bg_input in[4], unsigned count) {
    for (unsigned i=0;i<count;i++) bg_tick(in,1.f/60);
}
static float distance(const float a[3], const float b[3]) {
    float x=a[0]-b[0],y=a[1]-b[1],z=a[2]-b[2];return sqrtf(x*x+y*y+z*z);
}
int main(void) {
    bg_input in[4]={0};
    bg_reset();ticks(in,120);
    for (unsigned i=0;i<2;i++) {
        bg_player *p=&bg_players[i];
        printf("P%u spawn %.3f %.3f %.3f yaw %.3f\n",i+1,p->pos[0],p->pos[1],p->pos[2],p->yaw);
        assert(p->health==100 && p->grounded);
        assert(fabsf(p->pos[1]-bg_floor(p->pos[0],p->pos[2],p->pos[1]+.1f)-.015f)<.002f);
        float eye[3]={p->pos[0],p->pos[1]+.62f,p->pos[2]};
        assert(fabsf(bg_raycast(eye,(float[]){0,-1,0},5)-.635f)<.005f);
    }
    assert(bg_floor(10000,10000,100)==-1000);
    bg_player p2=bg_players[1];float p1[3];memcpy(p1,bg_players[0].pos,12);
    in[0].forward=1;ticks(in,20);
    assert(distance(p1,bg_players[0].pos)>.25f);
    assert(distance(p2.pos,bg_players[1].pos)<.001f);
    memset(in,0,sizeof(in));bg_reset();float y=bg_players[0].pos[1];
    in[0].jump=true;ticks(in,1);in[0].jump=false;ticks(in,10);
    assert(bg_players[0].pos[1]>y+.1f);ticks(in,110);assert(bg_players[0].grounded);
    /* Close-range duel on the flat roof. World ray casts still gate hits. */
    bg_reset();bg_players[0].yaw=0;bg_players[0].pitch=0;
    memcpy(bg_players[1].pos,bg_players[0].pos,12);bg_players[1].pos[0]+=.8f;
    in[0].fire=true;ticks(in,25);
    assert(bg_players[1].health==0 && bg_players[0].score==1);
    assert(bg_players[0].ammo==28);
    in[0].fire=false;ticks(in,130);assert(bg_players[1].health==100);
    in[0].reload=true;ticks(in,1);in[0].reload=false;ticks(in,70);assert(bg_players[0].ammo==32);
    /* A target beneath the base roof must not take damage through it. */
    bg_reset();bg_players[0].yaw=0;bg_players[0].pitch=atan2f(-1.6f,.8f);
    memcpy(bg_players[1].pos,bg_players[0].pos,12);bg_players[1].pos[0]+=.8f;bg_players[1].pos[1]-=1.5f;
    in[0].fire=true;ticks(in,1);assert(bg_players[0].ammo==31 && bg_players[1].health==100);
    bg_reset();bg_set_players(1);
    memcpy(bg_players[1].pos,bg_players[0].pos,12);bg_players[1].pos[0]+=.8f;
    in[0].fire=true;ticks(in,25);assert(bg_players[1].health==100);
    puts("PASS: terrain/rays, independent movement, jumping, damage, occlusion, score, respawn, reload, inactive players");
    return 0;
}
