/* Short Normal-difficulty encounters. Checkpoints restore the score ledger,
 * actor/projectile pools and supplies; retries cannot farm the failed wave. */
static void ff_save_checkpoint(void){
    bg_ff.checkpoint=bg_ff.wave;bg_ff.checkpoint_team_score=bg_ff.team_score;
    memcpy(bg_ff.checkpoint_score,bg_ff.score,sizeof(bg_ff.score));
    ff_checkpoint_statistics=statistics;
}
static void ff_retry_checkpoint(void){
    bg_ff_state previous=bg_ff;bg_match_statistics saved=ff_checkpoint_statistics;unsigned humans=active_players;
    bg_ff_start_fight(humans,previous.fight);
    bg_ff.wave=bg_ff.checkpoint=previous.checkpoint;
    bg_ff.team_score=bg_ff.checkpoint_team_score=previous.checkpoint_team_score;
    memcpy(bg_ff.score,previous.checkpoint_score,sizeof(bg_ff.score));
    memcpy(bg_ff.checkpoint_score,previous.checkpoint_score,sizeof(bg_ff.score));
    bg_ff.elapsed=previous.elapsed;bg_ff.retries=previous.retries+1;
    statistics=ff_checkpoint_statistics=saved;
    bg_ff.phase=BG_FF_RECOVER;bg_ff.timer=8;
    for(unsigned h=0;h<humans;h++){spawn(h);bg_players[h].score=bg_ff.score[h];}
    ff_message("Checkpoint retry");
}
static bool ff_casual_rally_tick(void){
    if(bg_ff.phase!=BG_FF_RALLY)return false;
    const ff_stage*s=ff_current_stage();
    for(unsigned h=0;h<active_players;h++)if(bg_players[h].health>0&&distance2(bg_players[h].pos,s->point)<4){
        bg_ff.phase=BG_FF_RECOVER;bg_ff.timer=8;ff_resupply();ff_message(s->name);break;
    }
    return true;
}
static void ff_casual_after_tick(unsigned living){
    if(bg_ff.phase==BG_FF_WON||bg_ff.phase==BG_FF_LOST)return;
    if(bg_ff.phase!=BG_FF_WAVE||bg_ff.packet<bg_ff.packets||ff_alive()){
        if(!living)ff_retry_checkpoint();
        return;
    }
    if(bg_ff.wave==5){ff_finish(true);return;}
    bg_ff.wave++;ff_resupply();
    if(bg_ff.fight==BG_FF_COURTYARD||!(bg_ff.wave&1))ff_save_checkpoint();
    if(bg_ff.fight==BG_FF_STATION_SWEEP&&!(bg_ff.wave&1)){
        bg_ff.phase=BG_FF_RALLY;ff_message("Move to the marked sector");
    }else {bg_ff.phase=BG_FF_RECOVER;bg_ff.timer=10;ff_message("Wave clear - resupply");}
}
