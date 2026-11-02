#include "game.c"
#include "controls.h"
#include "autopilot_strategy.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
static bg_input inputs[4];
static void tick(unsigned n){while(n--){bg_clear_events();bg_tick(inputs,1.f/30);assert(bg_autonav_work()<=256);}}
static void setup(unsigned map){
    bg_map_unload();assert(bg_map_load(map));bg_configure_mode(BG_MODE_SLAYER,(uint8_t[]){0,1,2,3});bg_set_players(4);bg_set_score_limit(1000);
    for(unsigned p=0;p<4;p++)bg_set_player_armor(p,p==0?BG_ARMOR_GUNGNIR:BG_ARMOR_SPARTAN);bg_reset();memset(inputs,0,sizeof(inputs));bg_vehicle_count=bg_pickup_count=0;
}
static void shields_controls(void){
    setup(BG_MAP_BLOOD_GULCH);bg_player *p=&bg_players[0];assert(p->shield==150&&p->health==100&&!p->autopilot_on&&p->autopilot_follow==-1);
    for(unsigned i=0;i<600;i++)tick_player_resources(0,&inputs[0],1.f/30);assert(p->shield==150);
    p->shield=0;p->shield_delay=0;for(unsigned i=0;i<181;i++)tick_player_resources(0,&inputs[0],1.f/30);assert(p->shield==150);
    p->shield_overcharging=true;for(unsigned i=0;i<62;i++)tick_player_resources(0,&inputs[0],1.f/30);assert(p->shield>349&&p->shield<=350);
    for(unsigned i=0;i<2800;i++)tick_player_resources(0,&inputs[0],1.f/30);assert(p->shield==150);
    inputs[0].flashlight=true;tick_player_resources(0,&inputs[0],1.f/30);assert(p->autopilot_on&&!p->flashlight_on);tick_player_resources(0,&inputs[0],1.f/30);assert(!p->autopilot_on);inputs[0].flashlight=false;
    bg_control_state raw={.pressed=BG_BUTTON_B,.held=BG_BUTTON_B};bg_input out;
    bg_controls_map(&out,&raw,BG_CONTROLS_DUKE,false);assert(out.flashlight&&!out.reload);
    bg_controls_map(&out,&raw,BG_CONTROLS_BOND,false);assert(!out.flashlight&&out.reload&&out.interact);
    for(unsigned style=0;style<2;style++)for(unsigned bit=0;bit<4;bit++){
        raw=(bg_control_state){.held=BG_BUTTON_D_UP<<bit,.pressed=BG_BUTTON_D_UP<<bit};bg_controls_map(&out,&raw,style,false);bg_controls_armor(&out,&raw,style,BG_ARMOR_GUNGNIR,false);assert(!out.autopilot_command);
        bg_controls_armor(&out,&raw,style,BG_ARMOR_GUNGNIR,true);assert(out.autopilot_command==(1u<<bit));assert(!out.zoom&&!out.melee&&!out.switch_grenade&&!out.crouch);
    }
    kill(0,1);assert(!p->autopilot_on);p->respawn=0;tick(1);assert(p->health==100&&p->shield==150&&p->armor==BG_ARMOR_GUNGNIR&&!p->autopilot_on);
    puts("PASS: GUNGNIR 150 shields, recharge, 350 overshield/decay, death/respawn, flashlight replacement and scheme-preserving controls");
}
static void aiming(void){
    setup(BG_MAP_BLOOD_GULCH);bg_player *p=&bg_players[0];
    memcpy(p->pos,(float[]){0,bg_floor(0,0,20)+.015f,0},12);p->yaw=p->pitch=0;p->weapon=BG_W_PISTOL;p->weapon_ready=0;
    for(unsigned i=1;i<4;i++){bg_players[i].health=100;bg_players[i].vehicle=-1;bg_players[i].pos[0]=5+i;bg_players[i].pos[1]=p->pos[1];bg_players[i].pos[2]=i==1?.4f:i==2?1.f:3.f;}
    bg_aim_target t=bg_gungnir_target(0);assert(t.player==1);float yaw,pitch;bg_gungnir_weapon_angles(0,&yaw,&pitch);assert(yaw<-.01f&&p->yaw==0&&p->pitch==0);
    float direction[3]={1,0,0},origin[3]={p->pos[0],p->pos[1]+bg_eye_height(p),p->pos[2]};assisted_shot(0,direction,origin);float expected[3];sub(expected,t.point,origin);normalize(expected);for(unsigned a=0;a<3;a++)assert(fabsf(expected[a]-direction[a])<1e-6f);
    for(unsigned w=0;w<BG_WEAPON_COUNT;w++)for(unsigned zoom=0;zoom<3;zoom++){
        p->weapon=w;p->zoom=zoom;assert(bg_gungnir_aim_active(p)==(zoom==0));if(zoom){assert(bg_gungnir_target(0).player==-1);bg_gungnir_weapon_angles(0,&yaw,&pitch);assert(yaw==p->yaw&&pitch==p->pitch);}
    }
    p->weapon=BG_W_PISTOL;p->zoom=0;uint8_t teams[4]={0,0,1,1};bg_configure_mode(BG_MODE_TEAM_SLAYER,teams);assert(bg_gungnir_target(0).player==2);
    bg_players[2].invisibility=10;bg_players[2].camo_opacity=0;assert(bg_gungnir_target(0).player==-1);bg_players[2].invisibility=0;
    /* Move a solid vehicle into the aim ray. It must occlude acquisition. */
    float block[3]={3,p->pos[1],.5f};int vehicle=bg_add_vehicle(BG_V_SCORPION,block,0);assert(vehicle>=0);assert(bg_gungnir_target(0).player==-1);bg_vehicle_count=0;
    /* Every split layout uses the same shorter-dimension radius. */
    bg_configure_mode(BG_MODE_SLAYER,(uint8_t[]){0,1,2,3});for(unsigned count=1;count<=4;count++){bg_set_players(count);if(count>1)assert(bg_gungnir_target(0).player==1);}
    bg_set_players(4);bg_players[2].health=bg_players[3].health=0;bool wall=false;
    for(unsigned a=0;a<bg_spawn_count&&!wall;a++)for(unsigned b=0;b<bg_spawn_count&&!wall;b++)if(a!=b){
        memcpy(p->pos,bg_spawns[a].pos,12);memcpy(bg_players[1].pos,bg_spawns[b].pos,12);
        float eye[3]={p->pos[0],p->pos[1]+bg_eye_height(p),p->pos[2]},d[3];bool blocked=true;
        for(unsigned h=0;h<3;h++){float target[3]={bg_players[1].pos[0],bg_players[1].pos[1]+bg_body_height(&bg_players[1])*(float[]){.7f,.9f,.5f}[h],bg_players[1].pos[2]};sub(d,target,eye);float length=sqrtf(dot(d,d));if(length<1||length>100){blocked=false;break;}normalize(d);if(bg_raycast(eye,d,length)>=length-.015f){blocked=false;break;}}
        if(blocked){sub(d,bg_players[1].pos,p->pos);p->yaw=atan2f(-d[2],d[0]);p->pitch=atan2f(bg_players[1].pos[1]+bg_body_height(&bg_players[1])*.7f-eye[1],hypotf(d[0],d[2]));assert(bg_gungnir_target(0).player==-1);wall=true;}
    }
    assert(wall);memcpy(p->pos,(float[]){0,bg_floor(0,0,20)+.015f,0},12);p->yaw=p->pitch=0;
    vehicle=bg_add_vehicle(BG_V_WARTHOG,p->pos,0);assert(vehicle>=0);p->vehicle=vehicle;p->seat_state=BG_SEAT_STABLE;bool passenger=false,driver=false;
    for(unsigned seat=0;seat<bg_seat_counts[BG_V_WARTHOG];seat++){
        p->seat=seat;
        if(bg_player_personal_weapon(p)){float eye[3];bg_vehicle_camera_position(&bg_vehicles[vehicle],seat,eye);memcpy(bg_players[1].pos,eye,12);bg_players[1].pos[0]+=8;bg_players[1].pos[1]-=bg_body_height(&bg_players[1])*.7f;assert(bg_gungnir_aim_active(p)&&bg_gungnir_target(0).player==1);passenger=true;}
        else{assert(!bg_gungnir_aim_active(p));driver=true;}
    }
    assert(passenger&&driver);p->vehicle=-1;bg_vehicle_count=0;
    puts("PASS: nearest screen-center enemy, off-axis shot/gun agreement, unchanged camera, allies/cloak/terrain/vehicle occlusion, passengers, 1-4 layouts and zoom exclusion");
}
static void viewport_aim(void){
    setup(BG_MAP_BLOOD_GULCH);
    for(unsigned views=1;views<=4;views++)for(unsigned owner=0;owner<views;owner++){
        unsigned enemy=(owner+1)%4;
        for(unsigned i=0;i<4;i++)bg_players[i].health=0;
        bg_player *p=&bg_players[owner],*q=&bg_players[enemy];
        p->health=q->health=100;p->armor=BG_ARMOR_GUNGNIR;q->armor=BG_ARMOR_SPARTAN;
        memcpy(p->pos,(float[]){0,bg_floor(0,0,20)+.015f,0},12);
        p->yaw=p->pitch=0;p->zoom=0;p->vehicle=-1;p->weapon=BG_W_AR;
        memcpy(q->pos,(float[]){6,p->pos[1]+bg_eye_height(p)-bg_body_height(q)*.7f,1.65f},12);
        q->vehicle=-1;q->invisibility=0;
        bg_set_view_count(views);assert(bg_player_count()==4&&bg_view_count()==views);
        bg_view_rect rect=bg_view_area(views,owner);
        bool wide=rect.w==320&&rect.h==120;
        /* This tangent lies inside the full/quarter-screen ring, outside
         * the wide half-screen ring. Four actors stay active in every case. */
        assert(bg_gungnir_target(owner).player==(wide?-1:(int)enemy));
        q->pos[2]=.6f;assert(bg_gungnir_target(owner).player==(int)enemy);
        p->zoom=1;assert(bg_gungnir_target(owner).player==-1);p->zoom=0;
    }
    bg_set_players(2);assert(bg_view_count()==2);bg_set_players(4);
    puts("PASS: aim cone uses the rendered 1/2/3/4-view layout with four live actor slots, including wide P3 and zoom exclusion");
}
static void navigation(void){
    unsigned moving_maps=0;
    for(unsigned map=0;map<13;map++){
        setup(map);assert(bg_autonav_load());unsigned starts=0,covered=0;uint16_t source=BG_NAV_NONE,goal=BG_NAV_NONE;float a[3],b[3];
        for(unsigned i=0;i<bg_spawn_count;i++)if(bg_slayer_spawns[i]){starts++;float pos[3];memcpy(pos,bg_spawns[i].pos,12);pos[1]=bg_floor(pos[0],pos[2],pos[1]+.5f)+.015f;uint16_t n=bg_autonav_node(pos);if(n!=BG_NAV_NONE){covered++;if(source==BG_NAV_NONE){source=n;bg_autonav_position(n,a);}}}
        assert(source!=BG_NAV_NONE&&covered>0);
        /* Select a certified reachable route in each map, independently of
         * simulation. Then let the actual movement-only follow mode walk it. */
        for(unsigned spawn_index=0;spawn_index<bg_spawn_count&&goal==BG_NAV_NONE;spawn_index++)if(bg_slayer_spawns[spawn_index]){
            float start_position[3];memcpy(start_position,bg_spawns[spawn_index].pos,12);start_position[1]=bg_floor(start_position[0],start_position[2],start_position[1]+.5f)+.015f;source=bg_autonav_node(start_position);if(source==BG_NAV_NONE)continue;bg_autonav_position(source,a);
            for(unsigned k=0;k<8&&goal==BG_NAV_NONE;k++){
                float angle=k*.78539816f,dir[3]={cosf(angle),0,sinf(angle)};uint16_t g=bg_autonav_goal(a,dir,4);
                if(g==source||g==BG_NAV_NONE)continue;float candidate[3];bg_autonav_position(g,candidate);if(distance2(a,candidate)<2.5f)continue;
                bg_autonav_request(0,source,g);for(unsigned t=0;t<300;t++)bg_autonav_service();bool jump=false;float point[3];if(bg_autonav_waypoint(0,a,point,&jump)){goal=g;bg_autonav_position(g,b);}bg_autonav_cancel(0);
            }
        }
        assert(goal!=BG_NAV_NONE);bg_player *p=&bg_players[0];memcpy(p->pos,a,12);memcpy(bg_players[1].pos,b,12);for(unsigned q=2;q<4;q++){bg_players[q].health=0;bg_players[q].respawn=10000;}
        bg_configure_mode(BG_MODE_TEAM_SLAYER,(uint8_t[]){0,0,1,1});p->autopilot_on=true;p->autopilot_style=BG_AUTOPILOT_FOLLOW;p->autopilot_follow=1;
        p->yaw=.4f;p->pitch=.12f;float initial=distance2(a,b);int ammo=p->ammo,reserve=p->reserve;unsigned shots=0;
        for(unsigned t=0;t<600;t++){tick(1);for(unsigned e=0;e<bg_event_count;e++)shots+=bg_events[e].kind==BG_EVENT_FIRE;if(distance2(p->pos,bg_players[1].pos)<1.3f*1.3f)break;}
        fprintf(stderr,"FOLLOW map%u health%.1f initial%.4f final%.4f ammo%d/%d camera%.4f %.4f start%.3f %.3f %.3f goal%.3f %.3f %.3f final%.3f %.3f %.3f target%.3f %.3f %.3f\n",map,p->health,initial,distance2(p->pos,b),p->ammo,ammo,p->yaw,p->pitch,a[0],a[1],a[2],b[0],b[1],b[2],p->pos[0],p->pos[1],p->pos[2],bg_players[1].pos[0],bg_players[1].pos[1],bg_players[1].pos[2]);
        assert(p->health>0&&distance2(p->pos,bg_players[1].pos)<1.7f&&p->yaw==.4f&&p->pitch==.12f&&p->ammo==ammo&&p->reserve==reserve&&!shots);moving_maps++;
        /* The movement adapter must preserve every nonmovement input byte. */
        bg_input manual={.fire=true,.grenade=true,.reload=true,.interact=true,.switch_weapon=true,.switch_grenade=true,.zoom=true,.turn=.3f,.look=-.2f,.secondary_fire=true},expected=manual;
        bg_gungnir_move(0,&manual,1.f/30);manual.forward=expected.forward;manual.strafe=expected.strafe;manual.jump=expected.jump;manual.crouch=expected.crouch;assert(!memcmp(&manual,&expected,sizeof(manual)));
        printf("PASS map%u: %u/%u starts have nearby graph nodes; follow walked certified route, navigation RAM %u, weapons/camera manual\n",map,covered,starts,bg_autonav_memory());
    }
    assert(moving_maps==13);bg_autonav_reset();assert(bg_autonav_memory()==0);
}
static void strategies(void){
    setup(BG_MAP_BLOOD_GULCH);bg_player *p=&bg_players[0];bg_autopilot_strategy_reset(0);
    bg_autopilot_strategy s=bg_autopilot_decide(0,false,true,true,false,0);assert(!s.retreat&&s.near_range==4&&s.far_range==8);
    p->shield=50;s=bg_autopilot_decide(0,false,true,true,false,0);assert(s.retreat);p->shield=90;s=bg_autopilot_decide(0,false,true,true,false,0);assert(s.retreat);p->shield=150;s=bg_autopilot_decide(0,false,true,true,false,0);assert(!s.retreat);
    s=bg_autopilot_decide(0,false,true,true,true,0);assert(s.retreat&&s.evade);s=bg_autopilot_decide(0,false,true,true,false,0);s=bg_autopilot_decide(0,false,true,true,false,0);assert(!s.retreat);
    bg_autopilot_strategy_reset(0);s=bg_autopilot_decide(0,true,true,true,false,0);assert(s.retreat);bg_autopilot_strategy_reset(1);bg_players[1].shield=100;s=bg_autopilot_decide(1,false,true,true,false,0);assert(!s.retreat);
    puts("PASS: original Elite attack/cover/emerge/danger transitions, blind-panic Grunt strategy and independent player state");
}
static void mode_commands(void){
    setup(BG_MAP_BLOOD_GULCH);bg_player *p=&bg_players[0];
    memcpy(p->pos,(float[]){0,bg_floor(0,0,20)+.015f,0},12);p->yaw=p->pitch=0;
    memcpy(bg_players[1].pos,p->pos,12);bg_players[1].pos[0]+=5;
    bg_players[2].health=bg_players[3].health=0;
    bg_input manual={.forward=.7f,.strafe=-.2f,.jump=true,.turn=.3f,.fire=true},saved=manual;
    bg_gungnir_move(0,&manual,1.f/30);assert(!memcmp(&manual,&saved,sizeof(manual)));
    bg_gungnir_toggle(0);manual.autopilot_command=1;bg_gungnir_move(0,&manual,1.f/30);
    assert(p->autopilot_style==BG_AUTOPILOT_FOLLOW&&p->autopilot_follow==1);
    p->yaw=1.5f;manual.autopilot_command=0;bg_gungnir_move(0,&manual,1.f/30);assert(p->autopilot_follow==1);
    manual.autopilot_command=2;bg_gungnir_move(0,&manual,1.f/30);assert(p->autopilot_style==BG_AUTOPILOT_PANIC);
    for(unsigned bit=4;bit<=8;bit*=2){manual.autopilot_command=bit;bg_gungnir_move(0,&manual,1.f/30);assert(p->autopilot_style==BG_AUTOPILOT_ELITE&&p->autopilot_side==(bit==4?-1:1));}
    bg_gungnir_toggle(0);manual=saved;bg_gungnir_move(0,&manual,1.f/30);assert(!memcmp(&manual,&saved,sizeof(manual)));
    /* Exercise four independent movement adapters and their shared bounded
     * path service; no adapter can consume camera or weapon buttons. */
    for(unsigned i=0;i<4;i++){bg_players[i].health=100;bg_players[i].armor=BG_ARMOR_GUNGNIR;bg_gungnir_reset(i);bg_gungnir_toggle(i);}
    for(unsigned frame=0;frame<120;frame++){
        bg_autonav_service();assert(bg_autonav_work()<=256);
        for(unsigned i=0;i<4;i++){manual=saved;manual.autopilot_command=frame==0?(i==3?2:4):0;bg_gungnir_move(i,&manual,1.f/30);assert(manual.fire==saved.fire&&manual.turn==saved.turn);}
    }
    /* Exercise the real weapon path with autopilot enabled, beyond checking
     * that the movement adapter preserves the fire input byte. */
    setup(BG_MAP_BLOOD_GULCH);p=&bg_players[0];bg_gungnir_toggle(0);
    p->weapon=p->inventory[p->slot]=BG_W_PISTOL;p->ammo=10;p->weapon_ready=p->cooldown=p->reload=0;store_inventory(p);
    float yaw=p->yaw,pitch=p->pitch;inputs[0].fire=true;tick(1);unsigned fires=0;
    for(unsigned e=0;e<bg_event_count;e++)fires+=bg_events[e].kind==BG_EVENT_FIRE&&bg_events[e].player==0;
    assert(p->autopilot_on&&p->ammo==9&&fires==1&&p->yaw==yaw&&p->pitch==pitch);
    inputs[0].fire=false;tick(1);assert(p->ammo==9);
    puts("PASS: D-pad mode transitions, persistent follow identity, manual movement restored on toggle and four simultaneous bounded pilots");
}
int main(void){shields_controls();aiming();viewport_aim();strategies();mode_commands();navigation();puts("PASS: GUNGNIR gameplay and all-map movement autopilot");}
