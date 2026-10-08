#include "combat.h"
#include "shield_fixture.h"
#include <stdio.h>
static void close_to(float actual,float expected){if(fabsf(actual-expected)>=.002f)fprintf(stderr,"actual %.9g expected %.9g\n",actual,expected);assert(fabsf(actual-expected)<.002f);}
static unsigned shots(unsigned kind,bool head,bool legs){
    const bg_damage_profile*d=&bg_damage_profiles[kind];float shield=100,health=100;
    unsigned n=0;while(health>0&&n<100){bg_combat_apply(d,bg_combat_amount(d,1,.5f),head,legs,false,&shield,&health);n++;}
    return n;
}
static void impact(unsigned kind,bool head){
    bg_player*p=&bg_players[1];bg_projectile*q=bg_projectile_create();assert(q);
    q->kind=BG_P_PLASMA;q->damage_profile=kind;q->owner=0;q->life=1;
    memcpy(q->pos,p->pos,12);q->pos[0]-=.5f;q->pos[1]+=head?.60f:.36f;q->velocity[0]=30;
    shield_fixture_ticks(1);
}
int main(void){
    assert(shots(BG_D_PISTOL,true,false)==3);
    assert(shots(BG_D_PISTOL,false,false)==5);
    assert(shots(BG_D_SNIPER,true,false)==1);
    assert(shots(BG_D_SNIPER,false,false)==2);
    printf("AR body %u; pistol body/head %u/%u; sniper body/head %u/%u\n",shots(BG_D_AR,false,false),shots(BG_D_PISTOL,false,false),shots(BG_D_PISTOL,true,false),shots(BG_D_SNIPER,false,false),shots(BG_D_SNIPER,true,false));
    float s=100,h=100;
    bg_combat_apply(&bg_damage_profiles[BG_D_PISTOL],75,true,false,false,&s,&h);
    assert(s==0&&h==100); /* Exactly absorbed: no damage reaches head. */
    for(unsigned kind=BG_D_AR;kind<BG_D_COUNT;kind++){
        const bg_damage_profile*d=&bg_damage_profiles[kind];
        float a=bg_combat_amount(d,1,.5f);
        s=0;h=100;bg_combat_apply(d,a,false,false,false,&s,&h);
        float body=100-h;s=0;h=100;bg_combat_apply(d,a,false,true,false,&s,&h);
        if(body<99)close_to(100-h,body*bg_combat_leg_scale);
    }
    s=100;h=100;bg_combat_apply(&bg_damage_profiles[BG_D_PLASMA_RIFLE],13,false,false,false,&s,&h);
    close_to(s,100-26.f/75*100);assert(h==100);
    s=0;h=100;bg_combat_apply(&bg_damage_profiles[BG_D_PLASMA_RIFLE],13,true,false,false,&s,&h);
    close_to(h,100-13.f/75*100); /* Double body damage on an unshielded head. */
    const bg_damage_profile*shotgun=&bg_damage_profiles[BG_D_SHOTGUN];
    close_to(bg_combat_range_scale(shotgun,1.5f),1);close_to(bg_combat_range_scale(shotgun,3),0);
    close_to(bg_combat_amount(shotgun,0,.1f),8);
    assert(bg_combat_range_scale(shotgun,2)>0&&bg_combat_range_scale(shotgun,2)<1);
    for(unsigned level=1;level<=3;level++){
        s=level*100;h=100;bg_combat_apply(&bg_damage_profiles[BG_D_OVERCHARGE],70,false,false,false,&s,&h);
        assert(s==0&&h==100);
    }
    s=0;h=100;bg_combat_apply(&bg_damage_profiles[BG_D_OVERCHARGE],70,false,false,false,&s,&h);close_to(h,44);
    s=100;h=100;bg_combat_apply(&bg_damage_profiles[BG_D_MELEE],40,false,false,false,&s,&h);close_to(s,100-56.f/75*100);assert(h==100);
    s=300;h=100;bg_combat_apply(&bg_damage_profiles[BG_D_MELEE],40,false,false,true,&s,&h);assert(s==0&&h==0);
    assert(bg_combat_amount(&bg_damage_profiles[BG_D_MELEE],0,.5f)==40);
    assert(bg_combat_amount(&bg_damage_profiles[BG_D_MELEE],1,.5f)==55);
    assert(bg_combat_amount(&bg_damage_profiles[BG_D_MELEE],1.5f,.5f)==62.5f);
    shield_fixture_reset();bg_players[1].shield=300;impact(BG_D_OVERCHARGE,false);
    assert(bg_players[1].shield==0&&bg_players[1].health==100);
    unsigned breaks=0;for(unsigned i=0;i<bg_event_count;i++)breaks+=bg_events[i].kind==BG_EVENT_SHIELD_BREAK;assert(breaks==1);
    bg_players[1].shield_overcharging=true;bg_players[1].shield=150;impact(BG_D_OVERCHARGE,false);assert(bg_players[1].shield>150&&bg_players[1].health==100);
    shield_fixture_reset();bg_players[1].shield=0;bg_players[1].shield_delay=6;
    for(unsigned i=0;i<10;i++){shield_fixture_shot(1,.1f);shield_fixture_ticks(1);}
    close_to(bg_players[1].health,99);
    puts("PASS: source damage breakpoints, EMP/overshield, material/head/leg responses, range energy, melee scaling and fractional health");
    return 0;
}
