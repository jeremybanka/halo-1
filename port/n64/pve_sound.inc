/* Two couch-wide speech streams. PCM stays in ROM, with separate DMA windows
 * and resampling cursors; split-screen never duplicates a speaker's line. */
#include "pve_roster.h"
typedef struct {bg_sound_stream stream;bg_audio_asset asset;uint32_t offset;uint16_t generation;int8_t actor;uint8_t priority,event;} pve_speech_channel;
static pve_speech_channel pve_speech[2];
static int8_t pve_speech_window[2][1024] __attribute__((aligned(16)));
static unsigned pve_voice_sequence[BG_PVE_KINDS][PVE_V_COUNT];
static uint32_t pve_voice_rom;
static const int8_t*pve_read_voice(unsigned channel,unsigned at,unsigned bytes){
    uint32_t address=pve_voice_rom+pve_speech[channel].offset+at;
    unsigned prefix=address&15,span=(prefix+bytes+15)&~15u;
    assertf(span<=sizeof(pve_speech_window[channel]),"Covenant speech window");
    data_cache_hit_invalidate(pve_speech_window[channel],span);dma_read(pve_speech_window[channel],address&~15u,span);
    return pve_speech_window[channel]+prefix;
}
static const int8_t*pve_read_voice0(unsigned at,unsigned bytes){return pve_read_voice(0,at,bytes);}
static const int8_t*pve_read_voice1(unsigned at,unsigned bytes){return pve_read_voice(1,at,bytes);}
static void pve_sound_reset(void){
    memset(pve_speech,0,sizeof(pve_speech));memset(pve_voice_sequence,0,sizeof(pve_voice_sequence));
    voices[17]=voices[18]=(voice){0};
}
static void pve_sound_event(const bg_event*e){
    int actor=e->player-BG_PLAYERS;unsigned speech=e->weapon;
    if(actor<0||actor>=(int)bg_pve_count||speech>=PVE_V_COUNT)return;
    bg_pve_actor*a=&bg_pve_actors[actor];if(a->generation!=(unsigned)e->amount)return;
    if(bg_players[e->player].health<=0&&speech!=PVE_V_DEATH&&speech!=PVE_V_FUEL_EXPLOSION)return;
    unsigned choices[64],count=0;
    for(unsigned i=0;i<bg_pve_voice_count;i++)if(bg_pve_voices[i].kind==(speech>=PVE_V_FUEL_FIRE?4:a->kind)&&bg_pve_voices[i].event==speech){assertf(count<64,"Speech permutations");choices[count++]=i;}
    if(!count)return;
    float distance=1e9f;unsigned listener=0;
    for(unsigned h=0;h<bg_player_count();h++){float d=0;for(unsigned k=0;k<3;k++){float x=e->pos[k]-bg_players[h].pos[k];d+=x*x;}if(d<distance){distance=d;listener=h;}}
    if(distance>45*45)return;
    /* Priority and override thresholds are the CE unit_dialogue.c ordering.
     * Admission is bounded to two voices rather than CE's full speech queue. */
    static const uint8_t priorities[PVE_V_COUNT]={5,1,1,9,2,10,5,5,5,5,5,5};
    static const uint8_t overrides[11]={0,0,1,1,2,2,5,5,7,7,10};
    unsigned priority=priorities[speech],channel=2;
    for(unsigned c=0;c<2;c++)if(voices[17+c].asset&&pve_speech[c].actor==actor){
        if(priority<overrides[pve_speech[c].priority])return;
        channel=c;break;
    }
    if(channel==2)for(unsigned c=0;c<2;c++)if(!voices[17+c].asset){channel=c;break;}
    if(channel==2)for(unsigned c=0;c<2;c++)if(priority>pve_speech[c].priority&&priority>=overrides[pve_speech[c].priority]){channel=c;break;}
    if(channel==2)return;
    if(!pve_voice_rom)pve_voice_rom=dfs_rom_addr("pve-voices.bin");
    assertf(pve_voice_rom,"Covenant dialogue bank");
    unsigned selected=choices[pve_voice_sequence[a->kind][speech]++%count];const bg_pve_voice*s=&bg_pve_voices[selected];
    pve_speech_channel*c=&pve_speech[channel];*c=(pve_speech_channel){.asset={.count=s->bytes,.rate=11025},.offset=s->offset,.actor=actor,.generation=a->generation,.priority=priority,.event=speech};
    unsigned pan=bg_player_count()==4?(listener%2?176:80):128;
    int volume=(int)(150/(1+sqrtf(distance)*.08f));
    voices[17+channel]=(voice){.asset=&c->asset,.step=(11025u<<16)/rate,.left=volume*(256-pan)/256,.right=volume*pan/256};
#ifdef BG_PROFILE
    debugf("COVENANT_VOICE actor=%u generation=%u kind=%u event=%u sample=%u bytes=%u\n",(unsigned)actor,a->generation,a->kind,speech,selected,(unsigned)s->bytes);
#endif
}
static void pve_sound_refill(unsigned count){
    for(unsigned i=0;i<2;i++){
        pve_speech_channel*c=&pve_speech[i];voice*v=&voices[17+i];if(!v->asset)continue;
        if(!bg_pve_is_active()||c->actor<0||c->actor>=(int)bg_pve_count||bg_pve_actors[c->actor].generation!=c->generation||(bg_players[BG_PLAYERS+c->actor].health<=0&&c->event!=PVE_V_DEATH&&c->event!=PVE_V_FUEL_EXPLOSION)){v->asset=NULL;continue;}
        bg_sound_stream_refill(&c->stream,v,&c->asset,count,i?pve_read_voice1:pve_read_voice0);
    }
}
