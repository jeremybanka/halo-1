"""Generate diagnostic copies, keeping playable vehicle/game arithmetic intact."""
from pve_draw_audit_source import replace

HEADER=r'''
#ifndef BG_VEHICLE_COST_AUDIT_H
#define BG_VEHICLE_COST_AUDIT_H
#include <stdint.h>
#include <libdragon.h>
#include "blam/vehicle_profile.h"
typedef struct {
 unsigned ai,goals,clearance,rays,floors,controller,friendly,arc,arc_pause_us,arc_pause_calls;
 unsigned ai_calls,clearance_calls,ray_calls,floor_calls,controller_calls,friendly_calls,arc_calls;
 unsigned contact_us,contact_calls,contact_hits,resolve_us,resolve_calls,resolve_hits,contact_triangles;
 unsigned physics[BG_VP_COUNT],physics_calls[BG_VP_COUNT],steps,wreck_us,wreck_calls,splatter_us,splatter_calls;
} vehicle_audit_kind;
extern vehicle_audit_kind vehicle_audit[6];
extern unsigned vehicle_audit_kind_id,vehicle_audit_frame;
void vehicle_audit_report(unsigned tick);
#endif
'''

GAME_HELPERS=r'''
vehicle_audit_kind vehicle_audit[6];
unsigned vehicle_audit_kind_id,vehicle_audit_frame;
static void vehicle_audit_report_one(unsigned tick,unsigned kind){
 vehicle_audit_kind*a=&vehicle_audit[kind];
 if(!a->steps&&!a->ai_calls&&!a->contact_calls&&!a->resolve_calls&&!a->wreck_calls)return;
 debugf("VA_AI tick=%u ticks=30 kind=%u total=%u goals=%u clearance=%u rays=%u floors=%u controller=%u friendly=%u arc=%u calls=%u clearance_calls=%u ray_calls=%u floor_calls=%u controller_calls=%u friendly_calls=%u arc_calls=%u arc_pause_us=%u arc_pause_calls=%u\n",tick,kind,a->ai,a->goals,a->clearance,a->rays,a->floors,a->controller,a->friendly,a->arc,a->ai_calls,a->clearance_calls,a->ray_calls,a->floor_calls,a->controller_calls,a->friendly_calls,a->arc_calls,a->arc_pause_us,a->arc_pause_calls);
 debugf("VA_PHYS tick=%u ticks=30 kind=%u steps=%u step=%u force=%u ground=%u feature_build=%u feature_test=%u integrate=%u sweep=%u pairs=%u control=%u publish=%u suspension=%u ground_calls=%u build_calls=%u test_calls=%u sweep_calls=%u pairs_calls=%u wreck=%u wreck_calls=%u splatter=%u splatter_calls=%u contact=%u contact_calls=%u contact_hits=%u resolve=%u resolve_calls=%u resolve_hits=%u contact_triangles=%u\n",tick,kind,a->steps,a->physics[BG_VP_STEP],a->physics[BG_VP_FORCE],a->physics[BG_VP_GROUND],a->physics[BG_VP_FEATURE_BUILD],a->physics[BG_VP_FEATURE_TEST],a->physics[BG_VP_INTEGRATE],a->physics[BG_VP_SWEEP],a->physics[BG_VP_PAIRS],a->physics[BG_VP_CONTROL],a->physics[BG_VP_PUBLISH],a->physics[BG_VP_SUSPENSION],a->physics_calls[BG_VP_GROUND],a->physics_calls[BG_VP_FEATURE_BUILD],a->physics_calls[BG_VP_FEATURE_TEST],a->physics_calls[BG_VP_SWEEP],a->physics_calls[BG_VP_PAIRS],a->wreck_us,a->wreck_calls,a->splatter_us,a->splatter_calls,a->contact_us,a->contact_calls,a->contact_hits,a->resolve_us,a->resolve_calls,a->resolve_hits,a->contact_triangles);
}
void vehicle_audit_report(unsigned tick){for(unsigned kind=0;kind<6;kind++)vehicle_audit_report_one(tick,kind);memset(vehicle_audit,0,sizeof(vehicle_audit));}
static float audit_floor(float x,float z,float ceiling){uint32_t t=get_ticks_us();float r=bg_floor(x,z,ceiling);vehicle_audit[vehicle_audit_kind_id].floors+=get_ticks_us()-t;vehicle_audit[vehicle_audit_kind_id].floor_calls++;return r;}
static float audit_ray(const float o[3],const float d[3],float reach){uint32_t t=get_ticks_us();float r=bg_raycast(o,d,reach);vehicle_audit[vehicle_audit_kind_id].rays+=get_ticks_us()-t;vehicle_audit[vehicle_audit_kind_id].ray_calls++;return r;}
'''

DRAW_HELPERS=r'''
static unsigned va_vertices,va_triangles;
static uint32_t va_clock;
static void va_category(unsigned view,const char*category){
 if(vehicle_audit_frame==1){
  uint32_t submitted=get_ticks_us(),drained=submitted;
#ifdef BG_GPU_DIAGNOSTIC
  rspq_wait();drained=get_ticks_us();
#endif
  debugf("VA_DRAW view=%u category=%s vertices=%u triangles=%u submit=%u remaining=%u span=%u\n",view,category,submitted_vertices-va_vertices,triangles-va_triangles,(unsigned)(submitted-va_clock),(unsigned)(drained-submitted),(unsigned)(drained-va_clock));
 }
 va_vertices=submitted_vertices;va_triangles=triangles;va_clock=get_ticks_us();
}
'''

def generate(directory, frozen):
    sources={name:(directory/name).read_text() for name in ('main.c','game.c','scene.c','combat_geometry.c','blam/vehicle_physics.c','pve_game.inc','pve_vehicles.inc')}
    sources['vehicle_cost_audit.h']=HEADER
    game='#include "vehicle_cost_audit.h"\n'+sources['game.c']
    game=replace(game,'#include "pve_game.inc"',GAME_HELPERS+'\n#include "pve_game.inc"')
    game=replace(game,'        BG_VP_END(BG_VP_PLAYER_CONTACTS);','        BG_VP_END(BG_VP_PLAYER_CONTACTS);\n        vehicle_audit[v->kind].splatter_us+=get_ticks_us()-bg_vp_begin;vehicle_audit[v->kind].splatter_calls++;')
    game=replace(game,'    if(++bg_collision_profile.ticks==30){','    if(++bg_collision_profile.ticks==30){\n        vehicle_audit_report(bg_pve_tick_number);')
    sources['game.c']=game
    vehicles=sources['pve_vehicles.inc']
    # Wrappers retain short-circuit call sites and original query arguments.
    vehicles=replace(vehicles,'static float pve_vehicle_clearance(','static float pve_vehicle_clearance_original(')
    vehicles=replace(vehicles,'static void pve_vehicle_inputs(',r'''
static float pve_vehicle_clearance(const bg_vehicle*v,const float direction[3],float reach){uint32_t t=get_ticks_us();float r=pve_vehicle_clearance_original(v,direction,reach);vehicle_audit[v->kind].clearance+=get_ticks_us()-t;vehicle_audit[v->kind].clearance_calls++;return r;}
static bool audit_friendly(unsigned i,const float o[3],const float target[3]){uint32_t t=get_ticks_us();bool r=pve_friendly_line(i,o,target);vehicle_audit[vehicle_audit_kind_id].friendly+=get_ticks_us()-t;vehicle_audit[vehicle_audit_kind_id].friendly_calls++;return r;}
static bool audit_arc(float pause,const float o[3],const float target[3],float speed,float gravity,bool high,float direction[3]){uint32_t t=get_ticks_us();bool r=pve_ballistic_arc(o,target,speed,gravity,high,direction);unsigned elapsed=get_ticks_us()-t;vehicle_audit[vehicle_audit_kind_id].arc+=elapsed;vehicle_audit[vehicle_audit_kind_id].arc_calls++;if(pause>0){vehicle_audit[vehicle_audit_kind_id].arc_pause_us+=elapsed;vehicle_audit[vehicle_audit_kind_id].arc_pause_calls++;}return r;}
static void pve_vehicle_inputs(''')
    # Only vehicle movement goal/support rays are replaced by timing wrappers.
    vehicles=vehicles.replace('bg_floor(','audit_floor(').replace('bg_raycast(','audit_ray(')
    vehicles=replace(vehicles,'        a->vehicle_timer+=dt;', '        vehicle_audit_kind_id=v->kind;uint32_t va_start=get_ticks_us(),va_part=va_start;vehicle_audit[v->kind].ai_calls++;\n        a->vehicle_timer+=dt;')
    vehicles=replace(vehicles,'if(a->target<0||bg_players[a->target].health<=0)continue;','if(a->target<0||bg_players[a->target].health<=0){vehicle_audit[v->kind].ai+=get_ticks_us()-va_start;continue;}')
    vehicles=replace(vehicles,'if(distance<.01f)continue;','if(distance<.01f){vehicle_audit[v->kind].ai+=get_ticks_us()-va_start;continue;}')
    vehicles=replace(vehicles,'        float movement[3];','        vehicle_audit[v->kind].goals+=get_ticks_us()-va_part;\n        float movement[3];')
    vehicles=replace(vehicles,'        bg_vehicle_ai_movement(', '        va_part=get_ticks_us();\n        bg_vehicle_ai_movement(')
    vehicles=replace(vehicles,'        p->yaw=atan2f(outface[1]', '        vehicle_audit[v->kind].controller+=get_ticks_us()-va_part;vehicle_audit[v->kind].controller_calls++;\n        p->yaw=atan2f(outface[1]')
    vehicles=replace(vehicles,'!pve_friendly_line(i,origin,target)','!audit_friendly(i,origin,target)')
    vehicles=replace(vehicles,'can_fire&&pve_ballistic_arc(', 'can_fire&&audit_arc(a->burst_pause,')
    vehicles=replace(vehicles,'a->burst_pause=pve_range(d->pause)*scale->pause;continue;', 'a->burst_pause=pve_range(d->pause)*scale->pause;vehicle_audit[v->kind].ai+=get_ticks_us()-va_start;continue;')
    pos=vehicles.rindex('    }\n}')
    vehicles=vehicles[:pos]+'        vehicle_audit[v->kind].ai+=get_ticks_us()-va_start;\n'+vehicles[pos:]
    sources['pve_vehicles.inc']=vehicles
    physics='#include "../vehicle_cost_audit.h"\n'+sources['blam/vehicle_physics.c']
    physics=replace(physics,'void bg_vehicle_physics_step(', 'static void vehicle_step_original(')
    physics=replace(physics,'void bg_vehicle_physics_wreck(', 'static void vehicle_wreck_original(')
    physics+=r'''
void bg_vehicle_physics_step(unsigned i,const bg_input*input){
 bg_vehicle_metrics before=bg_vehicle_profile;unsigned kind=bg_vehicles[i].kind;
 vehicle_step_original(i,input);vehicle_audit_kind*a=&vehicle_audit[kind];a->steps++;
 for(unsigned p=0;p<BG_VP_COUNT;p++){a->physics[p]+=bg_vehicle_profile.us[p]-before.us[p];a->physics_calls[p]+=bg_vehicle_profile.calls[p]-before.calls[p];}
}
void bg_vehicle_physics_wreck(unsigned i){uint32_t t=get_ticks_us();vehicle_wreck_original(i);vehicle_audit[bg_vehicles[i].kind].wreck_us+=get_ticks_us()-t;vehicle_audit[bg_vehicles[i].kind].wreck_calls++;}
'''
    sources['blam/vehicle_physics.c']=physics
    combat='#include "vehicle_cost_audit.h"\n'+sources['combat_geometry.c']
    combat=replace(combat,'float a[3],b[3],d2=bg_capsule_triangle(p->pos,h,r,&tri,a,b);','vehicle_audit[v->kind].contact_triangles++;\n            float a[3],b[3],d2=bg_capsule_triangle(p->pos,h,r,&tri,a,b);')
    combat=replace(combat,'bool bg_vehicle_contacts_player(const bg_vehicle*v,const bg_player*p){return vehicle_player_contact(v,p,NULL);}', 'bool bg_vehicle_contacts_player(const bg_vehicle*v,const bg_player*p){uint32_t t=get_ticks_us();bool r=vehicle_player_contact(v,p,NULL);vehicle_audit[v->kind].contact_us+=get_ticks_us()-t;vehicle_audit[v->kind].contact_calls++;vehicle_audit[v->kind].contact_hits+=r;return r;}')
    combat=replace(combat,'bool bg_vehicle_resolve_player(const bg_vehicle*v,bg_player*p){return vehicle_player_contact(v,p,p);}', 'bool bg_vehicle_resolve_player(const bg_vehicle*v,bg_player*p){uint32_t t=get_ticks_us();bool r=vehicle_player_contact(v,p,p);vehicle_audit[v->kind].resolve_us+=get_ticks_us()-t;vehicle_audit[v->kind].resolve_calls++;vehicle_audit[v->kind].resolve_hits+=r;return r;}')
    sources['combat_geometry.c']=combat
    main='#include "vehicle_cost_audit.h"\n'+sources['main.c']
    if frozen:
        main=replace(main,'#ifndef BG_BENCHMARK\n        sys_get_heap_stats(&heap);','#if 0\n        sys_get_heap_stats(&heap);')
        main=replace(main,'        if(photo_exported<\n','        if(photo_exported<\n#if 1\n            9\n#elif 0\n')
        main=replace(main,'#elif 0\n#ifdef BG_PVE_MODEL_QA','#elif defined(BG_PVE_MODEL_QA)')
        main=replace(main,'            debugf("FF_PHOTO_END\\n");','            debugf("FF_PHOTO_END\\n");\n            vehicle_audit_frame=photo_exported;')
        main=replace(main,'        bg_scene_prepare(slot, views, game_time);','        if(!vehicle_audit_frame)debugf("VA_STATE tick=%u time=%.6f alive=%u\\n",bg_pve_tick_number,game_time,(bg_players[0].health>0)+(bg_players[1].health>0)+(bg_players[2].health>0)+(bg_players[3].health>0));\n        bg_scene_prepare(slot, views, game_time);')
    sources['main.c']=main
    if frozen:
        scene='#include "vehicle_cost_audit.h"\n'+sources['scene.c']
        scene=replace(scene,'static void draw_view(unsigned p) {',DRAW_HELPERS+'\nstatic void draw_view(unsigned p) {\n#ifdef BG_GPU_DIAGNOSTIC\n if(vehicle_audit_frame==1)rspq_wait();\n#endif\n va_clock=get_ticks_us();va_vertices=submitted_vertices;va_triangles=triangles;')
        scene=replace(scene,'    bg_player *player = &bg_players[p];\n#ifdef BG_PROFILE\n    uint64_t begin','    bg_player *player = &bg_players[p];\n    if(!vehicle_audit_frame)debugf("VA_CAMERA view=%u x=%d y=%d width=%d height=%d eye=%.6f,%.6f,%.6f yaw=%.6f pitch=%.6f hp=%.3f\\n",p,(int)vp->offset[0],(int)vp->offset[1],(int)vp->size[0],(int)vp->size[1],eye.v[0]/BG_SCALE,eye.v[1]/BG_SCALE,eye.v[2]/BG_SCALE,player->yaw,player->pitch,player->health);\n#ifdef BG_PROFILE\n    uint64_t begin')
        for n,name in enumerate(('world','vehicles','players','pickups','effects','firstperson')):
            scene=replace(scene,f'    category_triangles[{n}] += triangles - before;',f'    va_category(p,"{name}");\n    category_triangles[{n}] += triangles - before;')
        scene=replace(scene,'    pve_draw(p);','    pve_draw(p);\n    va_category(p,"covenant");')
        scene=replace(scene,'        if (vehicle_view_lods[p][i]) {','        if (vehicle_view_lods[p][i] && vehicle_audit_frame!=i+2 && vehicle_audit_frame!=6) {\n            unsigned va_before=submitted_vertices,va_before_tri=triangles;')
        scene=replace(scene,'            if (wreck) {\n                rdpq_sync_pipe();\n                rdpq_mode_combiner(RDPQ_COMBINER_SHADE);\n            }','            if(!vehicle_audit_frame)debugf("VA_HULL view=%u vehicle=%u kind=%u lod=%u vertices=%u triangles=%u pos=%.6f,%.6f,%.6f yaw=%.6f pitch=%.6f health=%.3f\\n",p,i,v->kind,vehicle_view_lods[p][i],submitted_vertices-va_before,triangles-va_before_tri,v->pos[0],v->pos[1],v->pos[2],v->yaw,v->pitch,v->health);\n            if (wreck) {\n                rdpq_sync_pipe();\n                rdpq_mode_combiner(RDPQ_COMBINER_SHADE);\n            }')
        sources['scene.c']=scene
    return sources
