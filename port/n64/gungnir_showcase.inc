/* Scripted controller inputs for recording; all movement, targeting, shots,
 * shields, deaths and navigation use the unmodified production simulation. */
#include "showcase.h"
#include "rifle_fixture.h"
#include "gungnir.h"
#include "autopilot_nav.h"
#include <math.h>
#include <string.h>
static unsigned demo_mode,demo_frame,demo_aim_frames,demo_auto_frames,demo_auto_shots;
static unsigned demo_damage_events;
static bool demo_toggle_sent,demo_command_sent,demo_off_sent;
static bg_showcase_stats demo_stats;
static float demo_now,demo_previous[3],demo_start[3],demo_yaw,demo_pitch;
static float demo_clamp(float x,float lo,float hi){return x<lo?lo:x>hi?hi:x;}
static float demo_angle(float x){x=fmodf(x+3.14159265f,6.2831853f);return (x<0?x+6.2831853f:x)-3.14159265f;}
static void demo_place(unsigned p,float x,float z){
    bg_player *q=&bg_players[p];q->pos[0]=x;q->pos[1]=bg_floor(x,z,100)+.015f;q->pos[2]=z;
    q->yaw=q->pitch=q->vy=0;q->grounded=true;memset(q->velocity,0,sizeof(q->velocity));memcpy(q->last_pos,q->pos,12);
}
static void demo_face(unsigned p,unsigned target){
    bg_player *q=&bg_players[p],*v=&bg_players[target];float x=v->pos[0]-q->pos[0],z=v->pos[2]-q->pos[2];
    q->yaw=atan2f(-z,x);q->pitch=atan2f(v->pos[1]+bg_body_height(v)*.7f-q->pos[1]-bg_eye_height(q),hypotf(x,z));
}
static void demo_camera(bg_input *in,unsigned p,unsigned target){
    bg_player *q=&bg_players[p],*v=&bg_players[target];float x=v->pos[0]-q->pos[0],z=v->pos[2]-q->pos[2];
    float yaw=atan2f(-z,x),pitch=atan2f(v->pos[1]+bg_body_height(v)*.7f-q->pos[1]-bg_eye_height(q),hypotf(x,z));
    in->turn=demo_clamp(demo_angle(yaw-q->yaw)*3,-1,1);in->look=demo_clamp((pitch-q->pitch)*3,-1,1);
}
static void demo_walk(bg_input *in,unsigned p,float x,float z,float speed){
    bg_player *q=&bg_players[p];x-=q->pos[0];z-=q->pos[2];float n=hypotf(x,z);
    if(n<.05f)return;
    speed*=fminf(1,n*2);in->forward=(x*cosf(q->yaw)-z*sinf(q->yaw))/n*speed;in->strafe=(x*sinf(q->yaw)+z*cosf(q->yaw))/n*speed;
}
void bg_showcase_begin(bg_showcase_kind kind){
    demo_mode=(unsigned)kind-BG_SHOWCASE_COUNT;if(demo_mode>3)demo_mode=0;
    demo_frame=demo_aim_frames=demo_auto_frames=demo_auto_shots=demo_damage_events=0;
    demo_toggle_sent=demo_command_sent=demo_off_sent=false;demo_now=0;memset(&demo_stats,0,sizeof(demo_stats));
    bg_set_players(4);bg_set_score_limit(1000);
    bg_configure_mode(demo_mode==1?BG_MODE_TEAM_SLAYER:BG_MODE_SLAYER,demo_mode==1?(uint8_t[]){0,0,1,1}:(uint8_t[]){0,1,2,3});
    for(unsigned p=0;p<4;p++)bg_set_player_armor(p,p==0?BG_ARMOR_GUNGNIR:BG_ARMOR_SPARTAN);
    bg_reset();bg_vehicle_count=bg_pickup_count=0;
    for(unsigned p=0;p<4;p++)bg_fixture_rifle_loadout(p);
    demo_place(0,-4,4);demo_place(1,demo_mode==1?0:demo_mode==2?7:demo_mode==3?1:2,4.6f);
    demo_place(2,demo_mode==0?5:10,3);demo_place(3,demo_mode==0?8.5f:14,6);
    if(!demo_mode){demo_place(2,8,18);demo_place(3,8,-10);}
    for(unsigned p=1;p<4;p++)demo_face(p,0);
    demo_face(0,1);demo_yaw=bg_players[0].yaw;demo_pitch=bg_players[0].pitch;
    memcpy(demo_previous,bg_players[0].pos,12);memcpy(demo_start,demo_previous,12);bg_clear_events();
}
void bg_showcase_input(bg_input input[BG_PLAYERS],float seconds){
    memset(input,0,sizeof(bg_input)*BG_PLAYERS);demo_now=seconds;demo_frame++;
    float t=seconds-6;if(t<0||t>23)return;
    if(demo_mode&&!demo_toggle_sent){input[0].flashlight=true;demo_toggle_sent=true;}
    if(demo_mode&&t>.15f&&!demo_command_sent){input[0].autopilot_command=demo_mode==1?1:demo_mode==2?4:2;demo_command_sent=true;}
    if(demo_mode&&t>20&&!demo_off_sent){input[0].flashlight=true;demo_off_sent=true;}
    if(demo_mode&&t>20){input[0].forward=.35f;input[0].turn=.15f;return;}
    for(unsigned p=1;p<4;p++){
        if(bg_players[p].health<=0)continue;
        if(!demo_mode&&p>1)continue;
        if(demo_mode==1&&p==1){
            demo_walk(&input[p],p,fminf(t*.6f,11),4.6f+sinf(t*.3f)*1.2f,.4f);continue;
        }
        demo_camera(&input[p],p,0);
        if(!demo_mode)demo_walk(&input[p],p,(float[]){0,2,5,8.5f}[p],4+sinf(t*.8f+p)*1.05f,.5f);
        else if(demo_mode==3&&p==1)demo_walk(&input[p],p,bg_players[0].pos[0]+4,bg_players[0].pos[2],.25f);
        else if(p==1)demo_walk(&input[p],p,7,4+sinf(t*.7f),.3f);
        bool fire=p==1?fmodf(t,2.8f)<(demo_mode==2?.6f:.13f):p==2&&fmodf(t+1.4f,4)<.1f;
        input[p].fire=t>1&&fire;input[p].reload=bg_players[p].ammo==0;
    }
    if(demo_mode){
        unsigned target=demo_mode==1&&t<4?1:demo_mode==1?2:1;
        if(bg_players[target].health<=0)target=2;
        demo_camera(&input[0],0,target);
    }
    /* Aim-only mode never supplies turn/look or movement. The moving reticle,
     * held gun and off-axis hit ray therefore come from GUNGNIR itself. */
    input[0].fire=t>(demo_mode==1?4.5f:1)&&fmodf(t,demo_mode?2.1f:1.4f)<(demo_mode?.22f:.85f);
    input[0].reload=bg_players[0].ammo==0;
}
void bg_showcase_observe(void){
    bg_player *p=&bg_players[0];float x=p->pos[0]-demo_previous[0],z=p->pos[2]-demo_previous[2];demo_stats.traveled+=hypotf(x,z);memcpy(demo_previous,p->pos,12);
    if(bg_gungnir_target(0).player>=0)demo_aim_frames++;
    if(p->autopilot_on)demo_auto_frames++;
    for(unsigned e=0;e<bg_event_count;e++){
        const bg_event *v=&bg_events[e];
        if(v->kind==BG_EVENT_FIRE&&v->player==0){demo_stats.shots++;if(p->autopilot_on)demo_auto_shots++;}
        if(v->kind==BG_EVENT_DIE&&v->player!=0)demo_stats.kills++;
        if(v->kind==BG_EVENT_HURT||v->kind==BG_EVENT_SHIELD_HIT)demo_damage_events++;
    }
    demo_stats.passed=demo_stats.shots>8&&(demo_mode?demo_stats.traveled>3&&demo_auto_shots>3:demo_stats.kills>0&&demo_aim_frames>60);
}
unsigned bg_showcase_views(void){return 1;}
float bg_showcase_duration(void){return 30;}
const char *bg_showcase_title(void){static const char *titles[]={"GUNGNIR / AUTO AIM","GUNGNIR / FOLLOW ALLY","GUNGNIR / ELITE","GUNGNIR / PANIC"};return titles[demo_mode];}
const char *bg_showcase_caption(void){
    if(demo_now<6)return "LIVE COMBAT / SCRIPTED INPUTS";
    if(demo_mode&&demo_now>26)return "AUTO DISABLED / MANUAL MOVEMENT";
    if(!demo_mode)return "CAMERA HELD STILL / MANUAL FIRE";
    if(demo_mode==1)return demo_now<10?"UP: FOLLOW THE FRIENDLY":"LOOK AWAY / STILL FOLLOWING";
    return demo_mode==2?"LEFT / RIGHT: ELITE MOVEMENT":"DOWN: PANICKING GRUNT MOVEMENT";
}
const bg_showcase_stats *bg_showcase_telemetry(void){return &demo_stats;}
