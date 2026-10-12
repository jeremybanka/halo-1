#include "hud_messages.h"
#include "shield_fixture.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static bg_input input[4];
static void step(unsigned ticks) {
    while (ticks--) {
        bg_clear_events();
        bg_tick(input, 1.f / 30);
        bg_hud_messages_update();
    }
}
static void reset(void) {
    bg_set_players(4); bg_reset(); bg_hud_messages_reset();
    bg_vehicle_count = bg_pickup_count = 0;
    memset(input, 0, sizeof(input));
    for (unsigned p = 0; p < 4; p++) {
        bg_players[p].pos[0] = -12.f + p * 8.f;
        bg_players[p].pos[2] = 5;
        bg_players[p].pos[1] = bg_floor(bg_players[p].pos[0], 5, 100) + .015f;
        bg_players[p].weapon_ready = bg_players[p].cooldown = 0;
        bg_players[p].use_latched = false;
        bg_player_profiles[p] = p;
    }
}
static void staged(bg_event_kind kind, int player, int item, int count) {
    bg_clear_events();
    bg_events[0] = (bg_event){.kind=kind,.player=player,.weapon=item,.amount=count};
    bg_event_count = 1;
    bg_hud_messages_update(); bg_clear_events();
}
static void receipt(unsigned viewer, unsigned index, const char *text) {
    bg_notice out[BG_NOTICE_SLOTS]; char actual[64];
    unsigned count = bg_hud_messages_get(viewer, out);
    assert(count > index);
    bg_hud_message_text(viewer, &out[index], actual, sizeof(actual));
    if (strcmp(actual, text)) fprintf(stderr, "got '%s', wanted '%s'\n", actual, text);
    assert(!strcmp(actual, text));
}
static void actual_pickups(void) {
    reset();
    bg_player *p = &bg_players[0];
    int i = bg_add_pickup(BG_W_AR, p->pos);
    input[0].interact = true; step(12); input[0].interact = false;
    assert(!bg_pickups[i].active && p->weapon == BG_W_AR);
    receipt(0,0,"+ Assault Rifle");
    step(35); p->reserve=595; p->ammo=7;
    i=bg_add_pickup(BG_W_AR,p->pos);bg_pickups[i].reserve=3;bg_pickups[i].ammo=11;
    step(1); assert(p->reserve==600 && p->ammo==7);
    receipt(0,0,"+5 Assault Rifle"); receipt(0,1,"+ Assault Rifle");
    p->reserve=0; step(1); receipt(0,0,"+14 Assault Rifle");
    bg_notice other[BG_NOTICE_SLOTS]; assert(bg_hud_messages_get(1,other)==0);
    reset();p=&bg_players[0];p->grenades[0]=3;
    i=bg_add_pickup(BG_PICK_FRAG,p->pos);bg_pickups[i].quantity=3;
    step(1);receipt(0,0,"+1 Frag Grenade");
    p->grenades[0]=0;step(1);receipt(0,0,"+3 Frag Grenades");
    for (int kind=BG_PICK_HEALTH;kind<=BG_PICK_CAMO;kind++) {
        if(kind==BG_PICK_FRAG||kind==BG_PICK_PLASMA)continue;
        reset();p=&bg_players[0];p->health=20;
        bg_add_pickup(kind,p->pos);step(1);
        receipt(0,0,kind==BG_PICK_HEALTH?"+ Health Pack":kind==BG_PICK_OVERSHIELD?"+ Overshield":"+ Active Camo");
    }
}
static void bounded_queue_and_fade(void) {
    reset();
    for(unsigned i=0;i<5;i++)staged(BG_EVENT_AMMO,0,i,1);
    bg_notice out[BG_NOTICE_SLOTS];assert(bg_hud_messages_get(0,out)==4);
    assert(out[0].item==4&&out[3].item==1);
    staged(BG_EVENT_AMMO,0,1,49);receipt(0,0,"+50 Pistol");
    assert(bg_hud_messages_get(0,out)==4);
    assert(bg_hud_message_alpha(&out[0])==255);
    step(60);assert(bg_hud_messages_get(0,out)==4);assert(bg_hud_message_alpha(&out[0])==255);
    step(30);assert(bg_hud_messages_get(0,out)==4);
    unsigned alpha=bg_hud_message_alpha(&out[0]);assert(alpha>=68&&alpha<=69);
    step(30);assert(bg_hud_messages_get(0,out)==0);
    staged(BG_EVENT_AMMO,0,BG_W_AR,50);receipt(0,0,"+50 Assault Rifle");
    bg_hud_messages_reset();assert(bg_hud_messages_get(0,out)==0);
}
static void actual_kill_and_profile_identity(void) {
    reset();bg_players[0].shield=0;bg_players[0].health=1;
    shield_fixture_shot(0,20);step(1);assert(bg_players[0].health==0);
    receipt(0,0,"Player 2 killed Player 1");
    bg_player_profiles[0]=2;bg_player_profiles[1]=0;
    staged(BG_EVENT_KILL,1,0,1);
    receipt(0,0,"Player 1 killed Player 3");receipt(1,0,"You killed Player 3");
    receipt(2,0,"Player 1 killed Player 3");
    staged(BG_EVENT_DOUBLE_KILL,1,0,2);receipt(1,0,"Double Kill!");
    staged(BG_EVENT_TRIPLE_KILL,2,0,3);receipt(2,0,"Triple Kill!");
    staged(BG_EVENT_TRIPLE_KILL,2,0,4);receipt(2,0,"Killtacular!");
    staged(BG_EVENT_KILLING_SPREE,3,0,5);receipt(3,0,"Killing Spree!");
    staged(BG_EVENT_KILL,-1,0,1);receipt(0,0,"Player 3 died");
}
static void switch_reminder(void) {
    reset();bg_player*p=&bg_players[0];p->inventory[1]=BG_W_PISTOL;
    p->magazines[1]=8;p->reserves[1]=24;
    assert(bg_hud_switch_target(p)==-1);
    p->ammo=p->reserve=0;assert(bg_hud_switch_target(p)==BG_W_PISTOL);
    p->reload=.5f;assert(bg_hud_switch_target(p)==-1);p->reload=0;
    p->magazines[1]=p->reserves[1]=0;assert(bg_hud_switch_target(p)==-1);
    p->magazines[1]=8;p->health=0;assert(bg_hud_switch_target(p)==-1);
}
int main(void) {
    actual_pickups(); bounded_queue_and_fade(); actual_kill_and_profile_identity(); switch_reminder();
    assert(sizeof(bg_notice)*BG_PLAYERS*BG_NOTICE_SLOTS==256);
    puts("PASS: real weapon/ammo/grenade/health/powerup events; partial transfers; quantity aggregation; four isolated bounded queues; original 2+2s fade; kill/profile identity; awards; reset");
}
