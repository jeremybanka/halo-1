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
static void frame(bg_input in[4]){bg_clear_events();bg_tick(in,1.f/30);}
static unsigned events(bg_event_kind kind){unsigned n=0;for(unsigned e=0;e<bg_event_count;e++)n+=bg_events[e].kind==kind;return n;}
static void equip0(unsigned weapon){bg_give_weapon(0,weapon);bg_player*p=&bg_players[0];p->weapon=p->inventory[p->slot]=weapon;p->ammo=bg_weapon_defs[weapon].magazine;p->cooldown=p->weapon_ready=0;p->fire_ticks[p->slot]=65535;}
static void timing_tests(void){
    /* Cone length and angle remain correct when looking horizontally or up. */
    for(unsigned axis=0;axis<3;axis++)for(unsigned i=0;i<32;i++){
        float d[3]={0},out[3];d[axis]=1;float fraction=i/31.f;
        bg_combat_cone(d,.01f,.1f,fraction,fraction,out);
        close_to(out[0]*out[0]+out[1]*out[1]+out[2]*out[2],1);
        close_to(acosf(fminf(1,out[axis])),.01f+.09f*fraction);
    }
    shield_fixture_reset();equip0(BG_W_NEEDLER);bg_players[0].pitch=1;bg_input in[4]={0};in[0].fire=true;
    unsigned shots=0,first=0,second=0;
    for(unsigned t=0;t<30;t++){frame(in);if(events(BG_EVENT_FIRE)){if(shots==1)second=t;else if(!shots)first=t;shots++;}}
    assert(first==0&&second==6&&shots==9); /* Reevaluate ramp before every shot. */
    close_to(bg_players[0].trigger_rate[0],1);in[0].fire=false;
    for(unsigned t=0;t<6;t++)frame(in);close_to(bg_players[0].trigger_rate[0],0);
    /* Cancel on either side of the source halfway threshold. */
    for(unsigned late=0;late<2;late++){
        shield_fixture_reset();bg_players[0].ammo=10;in[0]=(bg_input){.reload=true};frame(in);in[0]=(bg_input){0};
        unsigned wait=late?50:10;while(wait--)frame(in);
        in[0].melee=true;frame(in);assert(bg_players[0].reload==0&&bg_players[0].melee_tick>0);
        assert(bg_players[0].ammo==(late?60:10));
    }
    /* An off-axis target enters the source sweep even when the central aim
     * ray misses. It receives exactly one hit, at key+1, not at input. */
    shield_fixture_reset();bg_player*a=&bg_players[0],*b=&bg_players[1];
    memcpy(b->pos,a->pos,12);b->pos[0]+=.55f;b->pos[2]+=.27f;b->yaw=3.14159265f;
    b->shield_delay=6;in[0]=(bg_input){.melee=true};frame(in);assert(b->shield==100);in[0]=(bg_input){0};
    for(unsigned t=0;t<bg_trigger_profiles[BG_W_AR].melee_key;t++){frame(in);assert(b->shield==100);}
    frame(in);assert(events(BG_EVENT_HURT)==1&&b->shield<100&&b->health==100);
    float shield=b->shield;for(unsigned t=0;t<8;t++)frame(in);close_to(b->shield,shield);
    /* Switching before the hit frame cancels it. */
    shield_fixture_reset();memcpy(bg_players[1].pos,bg_players[0].pos,12);bg_players[1].pos[0]+=.55f;
    in[0]=(bg_input){.melee=true};frame(in);in[0]=(bg_input){.switch_weapon=true};frame(in);in[0]=(bg_input){0};
    for(unsigned t=0;t<10;t++)frame(in);assert(bg_players[1].shield==100&&bg_players[0].melee_tick==0);
}
static void projectile_tests(void){
    /* No impact damage; fuse starts on attachment and credits original owner. */
    shield_fixture_reset();bg_projectile*q=bg_projectile_create();q->kind=BG_P_NEEDLE;q->owner=0;q->life=8;
    memcpy(q->pos,bg_players[1].pos,12);q->pos[0]-=.3f;q->pos[1]+=.35f;q->velocity[0]=15;
    shield_fixture_ticks(1);assert(bg_players[1].needles==1&&bg_players[1].shield==100);
    shield_fixture_ticks(21);assert(bg_players[1].shield==100);
    shield_fixture_ticks(2);close_to(bg_players[1].shield,100-10.f/75*100);assert(bg_players[1].needles==0);
    /* Seven attached needles produce one delayed burst, never on impact.
     * Fresh needles reset the uncombined siblings' individual timers. */
    shield_fixture_reset();bg_input in[4]={0};
    for(unsigned n=0;n<7;n++){
        q=bg_projectile_create();q->kind=BG_P_NEEDLE;q->owner=0;q->life=8;memcpy(q->pos,bg_players[1].pos,12);
        q->pos[0]-=.3f;q->pos[1]+=.35f;q->velocity[0]=15;frame(in);assert(!events(BG_EVENT_SUPERCOMBINE));
        for(unsigned t=0;t<2;t++)frame(in);
    }
    assert(bg_players[1].shield==100);unsigned bursts=0;
    for(unsigned t=0;t<50;t++){frame(in);bursts+=events(BG_EVENT_SUPERCOMBINE);}
    assert(bursts==1&&bg_players[1].shield==0&&bg_players[1].needles==0);
    /* Mid-air frag time alone cannot detonate it; after a bounce its arming
     * timer still imposes 1.5 seconds from launch. */
    shield_fixture_reset();q=bg_projectile_create();q->kind=BG_P_FRAG;q->owner=0;q->life=.5f;q->radius=2.5f;
    memcpy(q->pos,bg_players[0].pos,12);q->pos[1]+=20;shield_fixture_ticks(30);assert(bg_projectile_at(0));
    q=bg_projectile_at(0);q->attached=-2;q->countdown=true;q->life=.01f;
    shield_fixture_ticks(14);assert(bg_projectile_at(0));shield_fixture_ticks(1);assert(!bg_projectile_at(0));
    /* Target selection is retained at launch, without acquiring a bystander. */
    shield_fixture_reset();q=bg_projectile_create();q->kind=BG_P_NEEDLE;q->owner=0;q->life=8;q->tracked=1;
    memcpy(q->pos,bg_players[0].pos,12);q->pos[1]+=3;q->velocity[0]=4;float initial=sqrtf(q->velocity[0]*q->velocity[0]);
    frame(in);q=bg_projectile_at(0);assert(q&&q->tracked==1);close_to(sqrtf(q->velocity[0]*q->velocity[0]+q->velocity[1]*q->velocity[1]+q->velocity[2]*q->velocity[2]),initial);
    float heading[3];memcpy(heading,q->velocity,12);bg_players[1].health=0;frame(in);q=bg_projectile_at(0);assert(q);for(unsigned a=0;a<3;a++)close_to(q->velocity[a],heading[a]);
}

static void stun_and_fall_tests(void){
    shield_fixture_reset();impact(BG_D_PLASMA_RIFLE,false);
    bg_player*p=&bg_players[1];assert(p->body_stun>0&&p->stun_time>0);
    float first=p->body_stun;impact(BG_D_PLASMA_RIFLE,false);assert(p->body_stun>=first);
    shield_fixture_ticks((unsigned)ceilf(bg_stun_config[4]*30)+2);assert(p->body_stun==0&&p->stun_time==0);
    for(unsigned severe=0;severe<2;severe++){
        shield_fixture_reset();p=&bg_players[0];float floor=p->pos[1];
        p->pos[1]+=severe?8:1;p->vy=0;p->grounded=false;
        for(unsigned t=0;t<180&&p->health>0;t++){shield_fixture_ticks(1);if(p->grounded)break;}
        if(severe)assert(p->health<=0);else assert(p->health==100&&p->shield==100&&p->grounded&&p->pos[1]<floor+.1f);
    }
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
    timing_tests();projectile_tests();stun_and_fall_tests();
    puts("PASS: source cadence, cone, reload cancellation, timed sweep, individual needle fuses, retained guidance and grenade arming");
    return 0;
}
