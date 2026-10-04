#ifndef BG_FRONTEND_H
#define BG_FRONTEND_H
#include "menu.h"
/* Availability belongs to the catalog, never to presentation/navigation. */
typedef struct { const char *name; bool available; } bg_front_entry;
extern const bg_front_entry bg_front_maps[13],bg_front_types[26];
typedef enum { BG_FRONT_MAIN, BG_FRONT_MULTIPLAYER, BG_FRONT_JOIN,
 BG_FRONT_MAP, BG_FRONT_TYPE, BG_FRONT_PREGAME, BG_FRONT_PLAY,
 BG_FRONT_RESULTS, BG_FRONT_SETTINGS, BG_FRONT_PROFILE, BG_FRONT_CONTROLS, BG_FRONT_QUIT } bg_front_page;
typedef enum { BG_FRONT_NONE, BG_FRONT_START_MATCH, BG_FRONT_RESUME_MATCH,
 BG_FRONT_LEAVE_MATCH } bg_front_action;
typedef enum { BG_FRONT_SILENT, BG_FRONT_CURSOR, BG_FRONT_ACCEPT,
 BG_FRONT_BACK, BG_FRONT_BEEP } bg_front_sound;
typedef struct {
 bg_front_page page,return_page;
 unsigned row,host,map,type,count,settings_profile;
 bool joined[4],ready[4]; unsigned profile[4],ports[4];
 bg_control_style styles[4];
 int final_scores[4],winner;
 bg_match_statistics statistics;
 uint64_t deadline; int countdown,last_beep;
 bg_menu navigation;
 bg_front_sound sound;
} bg_frontend;
void bg_front_init(bg_frontend *f);
bg_front_action bg_front_update(bg_frontend *f,const bg_control_state input[4],uint64_t now);
bool bg_front_available(bg_front_page page,unsigned item);
void bg_front_results(bg_frontend *f,const int scores[4],int winner);
void bg_front_quit(bg_frontend *f);
void bg_front_map_controls(const bg_frontend *f,const bg_control_state physical[4],bg_control_state logical[4]);
unsigned bg_front_joined(const bg_frontend *f);
#endif
