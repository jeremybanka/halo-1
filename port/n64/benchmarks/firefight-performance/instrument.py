#!/usr/bin/env python3
"""Create an isolated, timing-only game.c; production sources are never edited."""
import argparse, hashlib, json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]

def replace(text, old, new):
    assert text.count(old) == 1, (old, text.count(old))
    return text.replace(old, new)

def wrap(text, signature, arguments, field, result='void'):
    start = text.index(signature)
    brace = text.index('{', start)
    depth = 1; end = brace + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}'); end += 1
    name = re.search(r'(\w+)\s*\(', signature)[1]
    original = text[start:end].replace(name+'(', name+'_instrumented_body(', 1)
    call = f'{name}_instrumented_body({arguments})'
    returned = f'{result} value={call};' if result != 'void' else call+';'
    wrapper = signature + '{uint32_t t=get_ticks_us();diag.'+field+'_calls++;'+returned+'diag.'+field+'_us+=get_ticks_us()-t;'+('return value;' if result != 'void' else '')+'}'
    return text[:start]+original+'\n'+wrapper+text[end:]

def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    names=['game.c','pve_game.inc','pve_nav.inc','pve_tick.inc','pve_collision.inc']
    files={n:(ROOT/'port/n64'/n).read_text() for n in names}
    fields=['tick','director','humans','vehicles','actors','projectiles','after','sees','selectors','destination','path','capsule','hit']
    counters=['bfs','nodes','hit_triangles']
    decl='static struct {unsigned '+','.join([k+s for k in fields for s in ('_us','_calls')]+counters)+';} diag;\n'
    files['game.c']=replace(files['game.c'],'uint32_t bg_tick_profile[3];','uint32_t bg_tick_profile[3];\n'+decl)
    # Non-overlapping top-level tick sections. More detailed sections below are nested.
    g=files['game.c'];g=replace(g,'    match_time += dt;','    uint32_t diag_begin=get_ticks_us(), diag_section=diag_begin;\n    match_time += dt;')
    g=replace(g,'    bg_ff_tick(dt);','    bg_ff_tick(dt);\n    diag.director_us+=get_ticks_us()-diag_section;diag.director_calls++;diag_section=get_ticks_us();')
    g=replace(g,'        update_vehicles(inputs, dt);','        diag.humans_us+=get_ticks_us()-diag_section;diag.humans_calls++;diag_section=get_ticks_us();\n        update_vehicles(inputs, dt);\n        diag.vehicles_us+=get_ticks_us()-diag_section;diag.vehicles_calls++;diag_section=get_ticks_us();')
    g=replace(g,'        bg_pve_tick(dt);','        bg_pve_tick(dt);\n        diag.actors_us+=get_ticks_us()-diag_section;diag.actors_calls++;diag_section=get_ticks_us();')
    g=replace(g,'        update_projectiles(dt);','        update_projectiles(dt);\n        diag.projectiles_us+=get_ticks_us()-diag_section;diag.projectiles_calls++;diag_section=get_ticks_us();')
    g=replace(g,'        bg_ff_after_tick(dt);','        bg_ff_after_tick(dt);\n        diag.after_us+=get_ticks_us()-diag_section;diag.after_calls++;')
    fmt='DETAIL tick=%u';args=['bg_pve_tick_number']
    for k in fields:
        for s in ('_us','_calls'):fmt+=f' {k+s}=%u';args.append('diag.'+k+s)
    for k in counters:fmt+=f' {k}=%u';args.append('diag.'+k)
    emit='    diag.tick_us+=get_ticks_us()-diag_begin;diag.tick_calls++;\n    if(diag.tick_calls==30){debugf("'+fmt+'\\n",'+','.join(args)+');memset(&diag,0,sizeof(diag));}\n'
    g=replace(g,'    mode_advance_spawn_clock(dt);','    mode_advance_spawn_clock(dt);\n'+emit);files['game.c']=g
    n=files['pve_nav.inc'];n=replace(n,'    pve_nav_goal[target]=goal;','    diag.bfs++;pve_nav_goal[target]=goal;')
    n=replace(n,'    }}\n}\nstatic void pve_destination','    }}\n    diag.nodes+=last;\n}\nstatic void pve_destination')
    n=wrap(n,'static void pve_path(unsigned target,const float pos[3])','target,pos','path')
    n=wrap(n,'static void pve_destination(unsigned i)','i','destination');files['pve_nav.inc']=n
    g=files['pve_game.inc'];g=wrap(g,'static bool pve_sees(unsigned i,unsigned target)','i,target','sees','bool')
    line='    if(a->kind==BG_PVE_GRUNT)grunt_decide_action(i);else if(a->kind==BG_PVE_ELITE)elite_decide_action(i);else if(a->kind==BG_PVE_JACKAL)jackal_decide_action(i);else hunter_decide_action(i);'
    g=replace(g,line,'    uint32_t select_begin=get_ticks_us();\n'+line+'\n    diag.selectors_us+=get_ticks_us()-select_begin;diag.selectors_calls++;');files['pve_game.inc']=g
    files['pve_tick.inc']=replace(files['pve_tick.inc'],'bg_move_capsule(p,dt);','{uint32_t t=get_ticks_us();bg_move_capsule(p,dt);diag.capsule_us+=get_ticks_us()-t;diag.capsule_calls++;}')
    g=files['pve_collision.inc'];g=replace(g,'    for(unsigned t=0;t<m->triangles_count;t++){','    diag.hit_triangles+=m->triangles_count;\n    for(unsigned t=0;t<m->triangles_count;t++){')
    g=wrap(g,'float bg_pve_hit_ray(unsigned unit,const float o[3],const float dir[3],float nearest,int*region)','unit,o,dir,nearest,region','hit','float');files['pve_collision.inc']=g
    manifest={}
    for n,text in files.items():
        (a.output/n).write_text(text);manifest[n]={'original_sha256':hashlib.sha256((ROOT/'port/n64'/n).read_bytes()).hexdigest(),'instrumented_sha256':hashlib.sha256(text.encode()).hexdigest()}
    (a.output/'instrumentation.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(a.output/'game.c')
if __name__=='__main__':main()
