/* Two bounded ROM windows for source vehicle fire, independent of dialogue. */
static bg_sound_stream enemy_sound_stream[2];
static bg_audio_asset enemy_sound_assets[2];
static uint32_t enemy_sound_rom[2];
static int8_t enemy_sound_window[2][1024] __attribute__((aligned(16)));
static const int8_t*enemy_sound_read(unsigned n,unsigned at,unsigned bytes){
    uint32_t address=enemy_sound_rom[n]+at;unsigned prefix=address&15,span=(prefix+bytes+15)&~15u;
    assert(span<=sizeof(enemy_sound_window[n]));data_cache_hit_invalidate(enemy_sound_window[n],span);dma_read(enemy_sound_window[n],address&~15u,span);return enemy_sound_window[n]+prefix;
}
static const int8_t*enemy_sound_read0(unsigned at,unsigned bytes){return enemy_sound_read(0,at,bytes);}
static const int8_t*enemy_sound_read1(unsigned at,unsigned bytes){return enemy_sound_read(1,at,bytes);}
static void enemy_sound_fire(unsigned kind,const float pos[3]){
    unsigned n=kind==BG_V_SHADE;const char*name=n?"enemy-shade.s8":"enemy-wraith.s8";
    float distance=1e9f;unsigned listener=0;
    for(unsigned h=0;h<bg_player_count();h++){float d=0;for(unsigned k=0;k<3;k++){float x=pos[k]-bg_players[h].pos[k];d+=x*x;}if(d<distance){distance=d;listener=h;}}
    if(distance>100*100)return;
    if(!enemy_sound_rom[n]){enemy_sound_rom[n]=dfs_rom_addr(name);enemy_sound_assets[n]=(bg_audio_asset){.count=dfs_rom_size(name),.rate=11025};assert(enemy_sound_rom[n]&&enemy_sound_assets[n].count);}
    unsigned pan=bg_player_count()==4?(listener%2?176:80):128;int volume=160/(1+sqrtf(distance)*.08f);
    enemy_sound_stream[n]=(bg_sound_stream){0};voices[19+n]=(voice){.asset=&enemy_sound_assets[n],.step=(11025u<<16)/rate,.left=volume*(256-pan)/256,.right=volume*pan/256};
}
static void enemy_sound_refill(unsigned count){
    for(unsigned n=0;n<2;n++)if(voices[19+n].asset)bg_sound_stream_refill(&enemy_sound_stream[n],&voices[19+n],&enemy_sound_assets[n],count,n?enemy_sound_read1:enemy_sound_read0);
}
static bg_sound_stream enemy_engine_stream[4];
static bg_audio_asset enemy_engine_assets[2];
static uint32_t enemy_engine_rom[2],enemy_engine_size[2];
static int enemy_engine_kind[4]={-1,-1,-1,-1},enemy_engine_vehicle[4]={-1,-1,-1,-1};
static int8_t enemy_engine_window[4][1024] __attribute__((aligned(16)));
static const int8_t*enemy_engine_read(unsigned c,unsigned at,unsigned bytes){
    unsigned kind=enemy_engine_kind[c];uint32_t address=enemy_engine_rom[kind]+at%enemy_engine_size[kind];
    unsigned prefix=address&15,span=(prefix+bytes+15)&~15u;assert(span<=1024);
    /* The loop file repeats its first KiB, allowing one aligned wrapping DMA. */
    data_cache_hit_invalidate(enemy_engine_window[c],span);dma_read(enemy_engine_window[c],address&~15u,span);return enemy_engine_window[c]+prefix;
}
static const int8_t*enemy_engine_read0(unsigned a,unsigned b){return enemy_engine_read(0,a,b);}
static const int8_t*enemy_engine_read1(unsigned a,unsigned b){return enemy_engine_read(1,a,b);}
static const int8_t*enemy_engine_read2(unsigned a,unsigned b){return enemy_engine_read(2,a,b);}
static const int8_t*enemy_engine_read3(unsigned a,unsigned b){return enemy_engine_read(3,a,b);}
static void enemy_engines_refill(unsigned count){
    const int8_t*(*read[4])(unsigned,unsigned)={enemy_engine_read0,enemy_engine_read1,enemy_engine_read2,enemy_engine_read3};
    for(unsigned c=0;c<4;c++)if(enemy_engine_kind[c]>=0&&voices[8+c].asset){
        enemy_engine_stream[c].at%=enemy_engine_size[enemy_engine_kind[c]];
        bg_sound_stream_refill(&enemy_engine_stream[c],&voices[8+c],&enemy_engine_assets[enemy_engine_kind[c]],count,read[c]);
    }
}
static void enemy_engines_update(void){
    bool used[BG_MAX_VEHICLES]={0};
    for(unsigned c=0;c<4;c++){
        int selected=-1;float nearest=1600;unsigned listener=0;
        for(unsigned n=0;n<bg_vehicle_count;n++)if(!used[n]&&bg_vehicles[n].active&&bg_vehicles[n].occupants[0]>=0){
            for(unsigned h=0;h<bg_player_count();h++){float d=0;for(unsigned a=0;a<3;a++){float x=bg_vehicles[n].pos[a]-bg_players[h].pos[a];d+=x*x;}
                if(d<nearest){nearest=d;selected=n;listener=h;}}
        }
        if(selected<0){voices[8+c].asset=NULL;enemy_engine_kind[c]=enemy_engine_vehicle[c]=-1;continue;}
        used[selected]=true;bg_vehicle*v=&bg_vehicles[selected];unsigned pan=bg_player_count()==4?(listener%2?176:80):128;int volume=(v->kind==BG_V_SHADE?20:40)/(1+sqrtf(nearest)*.08f);
        if(v->kind==BG_V_WRAITH||v->kind==BG_V_SHADE){
            unsigned k=v->kind==BG_V_SHADE;
            if(!enemy_engine_rom[k]){const char*name=k?"enemy-shade-engine.s8":"enemy-wraith-engine.s8";enemy_engine_rom[k]=dfs_rom_addr(name);enemy_engine_size[k]=dfs_rom_size(name)-1024;assert(enemy_engine_rom[k]&&enemy_engine_size[k]);enemy_engine_assets[k]=(bg_audio_asset){.count=UINT32_MAX,.rate=11025};}
            if(enemy_engine_kind[c]!=(int)k||enemy_engine_vehicle[c]!=selected||!voices[8+c].asset){enemy_engine_stream[c]=(bg_sound_stream){0};voices[8+c]=(voice){.asset=&enemy_engine_assets[k],.step=(11025u<<16)/rate};}
            enemy_engine_kind[c]=k;
        }else{
            unsigned sound=v->kind==BG_V_WARTHOG?BG_S_WARTHOG:v->kind==BG_V_SCORPION?BG_S_SCORPION:v->kind==BG_V_BANSHEE?BG_S_BANSHEE:BG_S_GHOST;
            if(enemy_engine_kind[c]>=0||voices[8+c].asset!=&bg_audio_assets[sound])play(8+c,sound,volume,pan,true);
            enemy_engine_kind[c]=-1;
            voices[8+c].step=(uint32_t)((float)((uint32_t)bg_audio_assets[sound].rate<<16)/rate*(.75f+fabsf(v->speed)*.065f));
        }
        enemy_engine_vehicle[c]=selected;voices[8+c].left=volume*(256-pan)/256;voices[8+c].right=volume*pan/256;
    }
}
