#include <libdragon.h>
#include <math.h>
#include <string.h>
#include "game.h"
#include "asset_models.h"
#include "sound.h"
#include "asset_frontend.h"
#include <stdlib.h>

/* Bounded software mixer: eight effects and four vehicle engines. Samples are
 * the supplied Xbox ADPCM decoded offline to signed 8-bit PCM, never synthesized.
 * A split-screen listener belongs to the whole couch; pan by viewport column. */
typedef bg_sound_voice voice;
static voice voices[14];
static unsigned replacement;
static int rate;
static float footsteps[4], shield_sound[4];
static FILE *title_music;
static int8_t music_buffer[4096];
static unsigned music_at,music_count,music_fraction;
static bg_audio_asset menu_effects[4];
void bg_sound_frontend(bool active){
    if(active==(title_music!=NULL))return;
    memset(voices,0,sizeof(voices));
    if(active){
        title_music=fopen("rom:/music.s8","rb");assertf(title_music,"Missing title music");
        music_at=music_count=music_fraction=0;
        static const char *const paths[]={"rom:/cursor.s8","rom:/forward.s8","rom:/back.s8","rom:/countdown.s8"};
        for(unsigned i=0;i<4;i++){
            FILE *f=fopen(paths[i],"rb");assertf(f,"Missing menu sound");
            fseek(f,0,SEEK_END);unsigned n=ftell(f);rewind(f);
            int8_t *samples=malloc(n);assertf(samples,"Menu sound RAM");
            assertf(fread(samples,1,n,f)==n,"Menu sound read");fclose(f);
            menu_effects[i]=(bg_audio_asset){samples,n,11025,false};
        }
    }else{
        fclose(title_music);title_music=NULL;
        for(unsigned i=0;i<4;i++){free((void*)menu_effects[i].samples);menu_effects[i]=(bg_audio_asset){0};}
        bg_sound_announce(BG_S_SLAYER);
        /* The regular update starts vehicle effects after the new match. */
        voices[13]=(voice){.asset=&bg_audio_assets[BG_S_AMBIENCE],.step=((uint32_t)bg_audio_assets[BG_S_AMBIENCE].rate<<16)/rate,.left=9,.right=9,.loop=true};
    }
}
void bg_sound_front_effect(unsigned effect){
    if(!title_music||!effect||effect>4)return;
    const bg_audio_asset *a=&menu_effects[effect-1];
    voices[0]=(voice){.asset=a,.step=((uint32_t)a->rate<<16)/rate,.left=96,.right=96};
}
static void mix_title(int16_t *out,unsigned count){
    if(!title_music)return;
    unsigned step=(11025u<<16)/rate;
    for(unsigned f=0;f<count;f++){
        if(music_at>=music_count){
            music_count=fread(music_buffer,1,sizeof(music_buffer),title_music);music_at=0;
            if(!music_count){fseek(title_music,bg_shell_music_loop,SEEK_SET);music_count=fread(music_buffer,1,sizeof(music_buffer),title_music);}
            assertf(music_count,"Title music loop read");
        }
        int sample=music_buffer[music_at]*70;
        for(unsigned c=0;c<2;c++){int value=out[f*2+c]+sample;out[f*2+c]=value>32767?32767:value< -32768?-32768:value;}
        music_fraction+=step;music_at+=music_fraction>>16;music_fraction&=65535;
    }
}

static void play(unsigned channel,unsigned sound,int volume,int pan,bool loop) {
    if(sound>=BG_S_COUNT || !bg_audio_assets[sound].count)return;
    voice*v=&voices[channel];v->asset=&bg_audio_assets[sound];v->frame=v->fraction=0;
    v->step=((uint32_t)v->asset->rate<<16)/rate;v->loop=loop;
    v->left=volume*(256-pan)/256;v->right=volume*pan/256;
}
void bg_sound_announce(unsigned sound){play(12,sound,160,128,false);}
void bg_sound_init(void) {
    audio_init(22050,6);rate=audio_get_frequency();
    memset(voices,0,sizeof(voices));bg_sound_announce(BG_S_SLAYER);play(13,BG_S_AMBIENCE,18,128,true);
}
static unsigned reload_sound(int weapon) {
    static const unsigned sounds[BG_WEAPON_COUNT]={BG_S_RELOAD,BG_S_PISTOL_RELOAD,BG_S_RELOAD,BG_S_RELOAD,
        BG_S_NEEDLER_RELOAD,BG_S_SHOTGUN_RELOAD,BG_S_SNIPER_RELOAD,BG_S_ROCKET_RELOAD,BG_S_RELOAD};
    return sounds[weapon<0||weapon>=BG_WEAPON_COUNT?0:weapon];
}
void bg_sound_update(void) {
    for(unsigned i=0;i<bg_event_count;i++){
        const bg_event*e=&bg_events[i];unsigned sound=BG_S_COUNT;int volume=112;
        int p=e->player>=0&&e->player<4?e->player:0,pan=bg_player_count()==4?(p%2?176:80):128;
        switch(e->kind){
            case BG_EVENT_GAME_OVER:bg_sound_announce(BG_S_GAME_OVER);continue;
            case BG_EVENT_DOUBLE_KILL:bg_sound_announce(BG_S_DOUBLE_KILL);continue;
            case BG_EVENT_TRIPLE_KILL:bg_sound_announce(BG_S_TRIPLE_KILL);continue;
            case BG_EVENT_KILLING_SPREE:bg_sound_announce(BG_S_KILLING_SPREE);continue;
            case BG_EVENT_TELEPORTER:sound=BG_S_TELEPORTER;volume=112;break;
            case BG_EVENT_FIRE:
                sound=e->weapon<BG_WEAPON_COUNT?(unsigned)e->weapon:BG_S_AR;
                if(bg_players[p].vehicle>=0){
                    bg_vehicle*v=&bg_vehicles[bg_players[p].vehicle];int seat=bg_players[p].seat;
                    if(v->kind==BG_V_WARTHOG&&seat==1)sound=BG_S_WARTHOG_GUN;
                    else if(v->kind==BG_V_SCORPION&&seat==0)sound=e->weapon==BG_W_AR?BG_S_WARTHOG_GUN:BG_S_SCORPION_GUN;
                    else if(v->kind==BG_V_GHOST&&seat==0)sound=BG_S_GHOST_GUN;
                    else if(v->kind==BG_V_BANSHEE&&seat==0)sound=e->weapon==BG_W_ROCKET?BG_S_BANSHEE_BOMB:BG_S_BANSHEE_GUN;
                }
                break;
            case BG_EVENT_RELOAD:sound=reload_sound(e->weapon);volume=100;break;
            case BG_EVENT_JUMP:sound=BG_S_JUMP;volume=65;break;
            case BG_EVENT_LAND:sound=BG_S_FOOTSTEP;volume=65;break;
            case BG_EVENT_HURT:if(bg_players[p].shield_delay>shield_sound[p]+.1f){sound=BG_S_SHIELD_HIT;shield_sound[p]=bg_players[p].shield_delay;}break;
            case BG_EVENT_DIE:sound=BG_S_DEATH;break;
            case BG_EVENT_RESPAWN:sound=BG_S_RESPAWN;break;
            case BG_EVENT_EXPLOSION:sound=e->weapon==BG_EXPLOSION_PLASMA?BG_S_PLASMA_EXPLOSION:BG_S_EXPLOSION;volume=160;break;
            case BG_EVENT_VEHICLE_DESTROYED:sound=BG_S_EXPLOSION;volume=180;break;
            case BG_EVENT_SHIELD:sound=BG_S_SHIELD_CHARGE;volume=80;break;
            default:break;
        }
        if(sound<BG_S_COUNT){
            float nearest=1e10f;
            for(unsigned j=0;j<bg_player_count();j++){
                float distance=0;for(unsigned a=0;a<3;a++){float d=bg_players[j].pos[a]-e->pos[a];distance+=d*d;}
                nearest=fminf(nearest,distance);
            }
            volume=(int)(volume/(1+nearest*.012f));
            play(replacement++%8,sound,volume,pan,false);
        }
    }
    for(unsigned p=0;p<4;p++){
        bg_player*player=&bg_players[p];shield_sound[p]=fminf(shield_sound[p],player->shield_delay);
        if(player->grounded&&player->health>0&&player->vehicle<0&&player->gait-footsteps[p]>3.2f){
            play(replacement++%8,BG_S_FOOTSTEP,35,p%2?176:80,false);footsteps[p]=player->gait;
        }
        if(player->gait<footsteps[p])footsteps[p]=player->gait;
        if(p>=bg_player_count()||player->health<=0||player->vehicle<0||player->seat!=0){voices[8+p].asset=NULL;continue;}
        bg_vehicle*v=&bg_vehicles[player->vehicle];
        unsigned sample=v->kind==BG_V_WARTHOG?BG_S_WARTHOG:v->kind==BG_V_SCORPION?BG_S_SCORPION:v->kind==BG_V_BANSHEE?BG_S_BANSHEE:BG_S_GHOST;
        if(voices[8+p].asset!=&bg_audio_assets[sample])play(8+p,sample,40,p%2?176:80,true);
        if(!voices[8+p].asset)continue;
        voices[8+p].step=(uint32_t)((float)((uint32_t)voices[8+p].asset->rate<<16)/rate*(.75f+fabsf(v->speed)*.065f));
    }
}
void bg_sound_pump(void) {
    while(audio_can_write()){
        int16_t*out=audio_write_begin();int count=audio_get_buffer_length();
        bg_sound_mix(voices,14,out,(unsigned)count);mix_title(out,(unsigned)count);
        audio_write_end();
    }
}
