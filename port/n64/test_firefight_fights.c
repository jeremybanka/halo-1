/* Finite encounter rules and source-variant promotion, with real map services. */
#include <stdio.h>
#include <assert.h>
#include "game.c"
#include "onslaught_reference.inc"
static void advance(void){bg_input in[4]={0};bg_tick(in,1.f/30);}
int main(void){
 assert(bg_map_load(9));
 const unsigned old_totals[]={276,337,395,456};
 for(unsigned humans=1;humans<=4;humans++){
  bg_ff_start(humans);unsigned total=0;
  assert(bg_ff.fight==BG_FF_ONSLAUGHT&&bg_ff.cap==4+2*humans);
  for(unsigned round=0;round<3;round++)for(unsigned wave=0;wave<5;wave++){
   bg_ff.round=round;bg_ff.wave=wave;ff_begin_wave();
   assert(bg_ff.packets==2+humans+round+(wave>=3));
   unsigned expected=0;
   for(unsigned p=0;p<bg_ff.packets;p++){
    assert(ff_packet_kind(p)==onslaught_packet_kind(p));
    const bg_ff_formation*f=&bg_ff_formations[ff_packet_kind(p)];expected+=f->count;
    for(unsigned j=0;j<f->count;j++)assert(ff_member_variant(f,j)==f->variant[j]);
   }
   assert(bg_ff.total==expected);total+=expected;
  }
  assert(total==old_totals[humans-1]);
  printf("ONSLAUGHT players=%u total=%u unchanged_schedule=1 unchanged_variants=1\n",humans,total);
 }
 for(unsigned humans=1;humans<=4;humans++){
  bg_ff_start_fight(humans,BG_FF_GAUNTLET);assert(bg_ff.fight==BG_FF_GAUNTLET&&bg_ff.cap==(humans==1?6:8));
  unsigned total=0,variants[PVE_R_COUNT]={0},species[4]={0};
  for(unsigned round=0;round<3;round++)for(unsigned wave=0;wave<5;wave++){
   bg_ff.round=round;bg_ff.wave=wave;ff_begin_wave();assert(bg_ff.packets==3+round+(wave>=3));
   total+=bg_ff.total;
   for(unsigned p=0;p<bg_ff.packets;p++){
    const bg_ff_formation*f=&bg_ff_formations[ff_packet_kind(p)];unsigned fuel=0;
    for(unsigned j=0;j<f->count;j++){
     unsigned v=ff_member_variant(f,j);variants[v]++;species[f->kind[j]]++;fuel+=v==PVE_R_GRUNT_FUEL;
     if(v){
      assert(bg_pve_variants[v].kind==f->kind[j]);
      /* The existing formation capsule checks still conservatively cover all promoted ranks. */
      assert(bg_pve_variants[v].def.radius<=bg_pve_definitions[f->kind[j]].radius);
      assert(bg_pve_variants[v].def.height<=bg_pve_definitions[f->kind[j]].height);
     }
     if(humans==1)assert(v==f->variant[j]);
     if(f->variant[j]==PVE_R_ZEALOT_SWORD||f->variant[j]==PVE_R_STEALTH_SWORD||f->variant[j]==PVE_R_GRUNT_FUEL)assert(v==f->variant[j]);
    }
    assert(fuel<=1);
   }
  }
  assert(total==276);for(unsigned k=0;k<4;k++)assert(species[k]>0);
  assert(species[BG_PVE_GRUNT]>species[BG_PVE_ELITE]&&species[BG_PVE_JACKAL]>0);
  printf("GAUNTLET players=%u total=%u cap=%u species=%u,%u,%u,%u variants=",humans,total,bg_ff.cap,species[0],species[1],species[2],species[3]);
  for(unsigned v=0;v<PVE_R_COUNT;v++)printf("%s%u",v?",":"",variants[v]);puts("");
  bg_ff.phase=BG_FF_BONUS;for(unsigned j=0;j<5;j++)assert(ff_member_variant(&bg_ff_formations[BG_FF_GRUNTS],j)==0);
  /* Both arrival paths must apply the selected source rank, including new gun poses. */
  for(unsigned f=0;f<BG_FF_FORMATIONS;f++)for(unsigned ship=0;ship<2;ship++){
   bg_ff_start_fight(humans,BG_FF_GAUNTLET);bg_ff.phase=BG_FF_RECOVER;bg_ff.timer=9999;
   assert(ff_arrive(f,ship)&&bg_ff.packet_delay==6);
   for(unsigned j=0;j<bg_ff_formations[f].count;j++){
    unsigned v=ff_member_variant(&bg_ff_formations[f],j);assert(bg_pve_actors[j].variant==v);
    if(v){assert(bg_players[4+j].weapon==bg_pve_variants[v].weapon);assert(bg_players[4+j].health==bg_pve_variants[v].def.health*bg_pve_difficulties[2].vitality);}
   }
  }
  /* Full lifecycle uses fixture kills: tests rules, not human difficulty. */
  bg_ff_start_fight(humans,BG_FF_GAUNTLET);unsigned transitions=0,last=99,max_live=0;
  for(unsigned tick=0;tick<60000&&!bg_match_finished();tick++){
   unsigned wave=bg_ff.round*5+bg_ff.wave;if(wave!=last){last=wave;transitions++;}
   for(unsigned h=0;h<humans;h++)bg_players[h].health=bg_players[h].shield=100;
   advance();unsigned live=ff_alive();if(live>max_live)max_live=live;assert(live<=bg_ff.cap);
   for(unsigned i=0;i<bg_pve_count;i++)if(bg_players[4+i].health>0&&bg_pve_actors[i].arrival!=1)damage_player_profile(4+i,0,100000,false,false,0,false,false,1);
   if(bg_ff.phase==BG_FF_READY||bg_ff.phase==BG_FF_RECOVER)bg_ff.timer=fminf(bg_ff.timer,.1f);
   if(bg_ff.phase==BG_FF_BONUS&&bg_ff.packet>=2)bg_ff.timer=0;
  }
  assert(bg_ff.phase==BG_FF_WON&&transitions==15&&bg_ff.arrival_failures==0);
  unsigned score=0;for(unsigned h=0;h<humans;h++)score+=bg_ff.score[h];assert(score==bg_ff.team_score);
  printf("GAUNTLET_COMPLETE players=%u waves=%u max_live=%u score=%u failures=%u\n",humans,transitions,max_live,score,bg_ff.arrival_failures);
  bg_reset();assert(bg_ff.fight==BG_FF_GAUNTLET&&bg_ff.round==0&&bg_ff.lives==10&&bg_ff.team_score==0);
  bg_ff.lives=0;for(unsigned h=0;h<humans;h++)kill(h,-1);bg_ff_after_tick(1.f/30);assert(bg_ff.phase==BG_FF_LOST);
 }
 bg_ff_start_fight(1,99);assert(bg_ff.fight==BG_FF_ONSLAUGHT);
 bg_pve_stop();bg_configure_mode(BG_MODE_CTF,NULL);bg_reset();assert(!bg_ff.active&&!bg_pve_is_active());
 puts("PASS Onslaught frozen schedule; Gauntlet quantity, diversity, source ranks, arrivals, 1–4P full sets, restart, defeat and PvP return");
}
