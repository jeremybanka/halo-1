#include "shield_fixture.h"
#include "shields.h"
#include <stdio.h>
static unsigned events(bg_event_kind kind){unsigned count=0;for(unsigned i=0;i<bg_event_count;i++)count+=bg_events[i].kind==kind;return count;}
int main(void){
    shield_fixture_reset();bg_player*p=&bg_players[1];
    assert(bg_shield_glow(p)==0&&bg_shield_sounds(p)==0);
    shield_fixture_shot(1,40);shield_fixture_ticks(1);
    assert(p->shield==60&&p->health==100&&events(BG_EVENT_SHIELD_HIT)==1&&events(BG_EVENT_SHIELD_BREAK)==0);
    assert(bg_shield_glow(p)==1);
    shield_fixture_ticks(75);assert(bg_shield_glow(p)==0&&p->shield==60);
    shield_fixture_shot(1,60);shield_fixture_ticks(1);
    assert(p->shield==0&&p->health==100&&events(BG_EVENT_SHIELD_BREAK)==1&&p->shield_break==2.25f);
    assert(bg_shield_glow(p)==0&&bg_shield_sounds(p)==BG_SHIELD_DOWN);
    shield_fixture_shot(1,5);shield_fixture_ticks(1);
    assert(p->health==95&&!events(BG_EVENT_SHIELD_HIT)&&!events(BG_EVENT_SHIELD_BREAK));
    shield_fixture_ticks(179);assert(p->shield==0);
    for(unsigned i=0;i<3&&!p->shield_charging;i++)shield_fixture_ticks(1);
    assert(p->shield_charging&&events(BG_EVENT_SHIELD)==1);
    assert(bg_shield_sounds(p)==(BG_SHIELD_CHARGE|BG_SHIELD_LOW));
    shield_fixture_ticks(35);assert(p->shield>25&&bg_shield_sounds(p)==BG_SHIELD_CHARGE);
    shield_fixture_shot(1,2);shield_fixture_ticks(1);
    assert(!p->shield_charging&&p->shield_delay==6&&bg_shield_sounds(p)==0);
    shield_fixture_ticks(305);assert(p->shield==100&&p->health==95&&bg_shield_sounds(p)==0&&bg_shield_glow(p)==0);
    /* Pickup charge, protection, expiry and non-stacking match source rules. */
    bg_add_pickup(BG_PICK_OVERSHIELD,p->pos);shield_fixture_ticks(1);
    assert(p->shield_overcharging&&p->shield_charging&&p->shield==100);
    shield_fixture_shot(1,200);shield_fixture_ticks(1);assert(p->health==95&&p->shield>100&&bg_shield_glow(p)==1);
    shield_fixture_ticks(59);assert(!p->shield_overcharging&&fabsf(p->shield-300)<.01f&&!p->shield_charging);
    bg_add_pickup(BG_PICK_OVERSHIELD,p->pos);shield_fixture_ticks(1);assert(bg_pickups[1].active);
    shield_fixture_ticks(59);assert(fabsf(p->shield-(300-100.f/45*2))<.02f&&bg_shield_glow(p)==0);
    shield_fixture_shot(1,110);shield_fixture_ticks(1);assert(p->shield>100&&p->shield<200&&bg_shield_glow(p)==1&&!events(BG_EVENT_SHIELD_BREAK));
    /* Respawn must reset every presentation and charge latch. */
    shield_fixture_shot(1,1000);shield_fixture_ticks(1);assert(p->health==0&&bg_shield_sounds(p)==0);
    shield_fixture_ticks(92);assert(p->health==100&&p->shield==100&&p->shield_break==0&&p->shield_hit==0&&!p->shield_overcharging);
    for(unsigned page=0;page<3;page++){
        shield_fixture_stage(page);
        printf("page %u:",page);for(unsigned i=0;i<4;i++)printf(" p%u=%.1f/%.2f/%.2f/%u",i,bg_players[i].shield,bg_players[i].shield_hit,bg_players[i].shield_break,bg_shield_sounds(&bg_players[i]));puts("");
        assert(bg_players[0].shield==100&&bg_players[3].shield>200);
    }
    puts("PASS: hit/depletion/health damage, six-second stun, recharge interruption/completion, low/down/charge audio states, source overshield acquisition/protection/decay, death and respawn");
}
