"""Pack the private squad art, source tag settings and source decision bodies."""
import argparse,contextlib,hashlib,json,re,struct,gzip
from pathlib import Path
from pack_mesh import emit_batches,indexed_mesh,trajectory_keys,remap_clip
from model_colors import load_images,bake_triangle,bake_team_mask
from pack_assets import position
from pack_animation import emit_clip,clip_initializer,compact_clip
from test_render_matrix import function
ROOT=Path(__file__).resolve().parents[2]
NAMES=('grunt','elite','jackal','hunter');CLIPS=('idle','run','fire','death','flee','melee','throw','evade_left','evade_right','ride','exit','crouch')
def braces(v):return '{'+','.join(map(str,v))+'}'
def f(v):return float(v).hex()+'f'
def material_mode(meta):
    shader=meta.get('shader',{})
    if meta['class']=='shader_model':
        return int(bool(shader.get('soso_attrs',{}).get('model_shader',{}).get('flags',{}).get('two_sided')))
    flags=shader.get('sotr_attrs',{}).get('generic_transparent_shader',{}).get('flags',{})
    return 2|int(bool(flags.get('two_sided')))

def prepare_model(w,model_candidate=False):
    images=load_images(w['textures']);metadata=w['material_metadata']
    masks=load_images([m.get('multipurpose_fullres') for m in metadata])
    channels=[2 if m.get('color_change_source')=='A' else None for m in metadata]
    points=[];colors=[];tints=[];materials=[]
    for t in w['triangles']:
        points.extend([[round(v*128) for v in position(p,(0,0,0))] for p in t['p']])
        colors.extend(t.get('colors') or bake_triangle(t,images,w));tints.extend(t.get('tints') or bake_team_mask(t,masks,channels));materials.extend([t['material']]*3)
    segments=None;modes=[]
    if model_candidate:
        segments=[];start=0;previous=None
        for i,t in enumerate(w['triangles']):
            mode=material_mode(metadata[t['material']])
            if previous is not None and mode!=previous:segments.append((start*3,(i-start)*3));modes.append(previous);start=i
            previous=mode
        segments.append((start*3,len(points)-start*3));modes.append(previous)
    tolerance=48 if w.get('crunch_palette') else 24 if model_candidate and w['source_lod'].startswith('n64 ') else 8
    mesh=indexed_mesh(points,colors,tints,trajectory_keys(w['clips'],128,16),segments=segments,color_tolerance=tolerance,material_keys=materials)
    mesh['batch_modes']=[mode for mode,(_,count) in zip(modes,mesh['segments']) for _ in range(count)] if model_candidate else [0]*len(mesh['batches'])
    mesh['alphas']=[160 if model_candidate and material_mode(metadata[materials[s]])&2 else 255 for s in mesh['sources']]
    return mesh,{n:remap_clip(c,mesh['sources']) for n,c in w['clips'].items()}

def emit_rom_clip(lines,name,clip,motion):
    packed=compact_clip(clip,128,16)
    motion.extend(bytes(-len(motion)%16));packed['rom_offset']=len(motion)
    motion.extend(struct.pack('>'+str(len(packed['values']))+'H',*packed['values']))
    motion.extend(bytes(16))
    lines.append('static const uint16_t '+name+'_indices[]='+braces(packed['indices'])+';')
    return packed

def pack(source,out,model_candidate=False,visual_only=False):
    motion=bytearray();needler_rows=[];needler_sources={}
    source=source.resolve();out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    baked=source/'squad-baked.json.gz'
    if not baked.exists():baked=source/'squad-baked.json'
    data=json.loads(gzip.decompress(baked.read_bytes()) if baked.suffix=='.gz' else baked.read_bytes());raw=json.loads((source/'squad-source.json').read_text())
    lod_count=len(data['grunt']);assert lod_count in (2,3) and all(len(data[n])==lod_count for n in (*NAMES,'spirit'))
    lines=['/* Private original CE geometry and animation. */','#include "asset_pve.h"'];models=[];anims=[];grips=[];report={}
    shield_arrays=[];mode_rows=[]
    for name in (*NAMES,'spirit'):
        model_rows=[];anim_rows=[];grip_rows=[];surface_rows=[];report[name]=[]
        for lod,w in enumerate(data[name]):
            shared=next((i for i in range(lod) if w['source_lod']==data[name][i]['source_lod']),None)
            if shared is not None:
                model_rows.append(model_rows[shared]);anim_rows.append(anim_rows[shared]);surface_rows.append(surface_rows[shared]);report[name].append({**report[name][shared],'shared_with_lod':shared})
                if name=='jackal':shield_arrays.append(shield_arrays[shared])
                continue
            symbol=f'pve_{name}_{lod}';mesh,clips=prepare_model(w,model_candidate)
            verts=mesh['vertices'];colors=raw['actors'][name]['variant']['change_colors'] if name!='spirit' else []
            if not colors and name!='spirit':
                changes=raw['actors'][name]['biped']['obje_attrs']['change_colors'];colors=changes[0]['permutations'] if changes else []
            tint=[(lo+hi)*.5 for lo,hi in zip(colors[0]['color_lower_bound'].values(),colors[0]['color_upper_bound'].values())] if colors else None
            lines.append('static T3DVertPacked '+symbol+'[] __attribute__((aligned(16)))={')
            for i in range(0,len(verts),2):
                pair=[]
                for vi,v in enumerate(verts[i:i+2],i):
                    rgb=v[1]
                    if tint:rgb=[round(c*(1-v[2]/255+v[2]/255*tint[j])) for j,c in enumerate(rgb)]
                    pair.append((braces(v[0]),(rgb[0]<<24)|(rgb[1]<<16)|(rgb[2]<<8)|mesh['alphas'][vi]))
                lines.append('{'+f'{pair[0][0]},0,{pair[1][0]},0,0x{pair[0][1]:08x},0x{pair[1][1]:08x},{{0,0}},{{0,0}}'+'},')
            lines.append('};');emit_batches(lines,symbol,mesh)
            lines.append('static const uint8_t '+symbol+'_modes[]='+braces(mesh['batch_modes'])+';');surface_rows.append(symbol+'_modes')
            if name=='jackal':
                shield=set(w['shield_corners']);mask=[int(s in shield) for s in mesh['sources']]
                lines.append('static const uint8_t '+symbol+'_shield[]='+braces(mask)+';');shield_arrays.append(symbol+'_shield')
            model_rows.append(braces([symbol,len(verts),'2.f',symbol+'_batches',symbol+'_indices',len(mesh['batches']),len(w['triangles'])]))
            clip_rows=[];motion_bytes=0;clip_cache={}
            for key in CLIPS:
                clip=clips[key];cache_key=json.dumps(clip,separators=(',',':'))
                if cache_key in clip_cache:prefix,packed=clip_cache[cache_key]
                else:
                    prefix=symbol+'_'+key;packed=emit_rom_clip(lines,prefix,clip,motion);motion_bytes+=packed['bytes'];clip_cache[cache_key]=(prefix,packed)
                clip_rows.append(clip_initializer(prefix,clip,packed,'(const uint16_t*)(uintptr_t)'+str(packed['rom_offset'])).rstrip(','))
                if lod==0:
                    hand=w['grips'][key];hs='pve_'+name+'_hand_'+key
                    lines.append('static const bg_attachment_pose '+hs+'[]='+braces([braces([braces(map(f,p['pos'])),braces(map(f,p['quat']))]) for p in hand['poses']])+';')
                    grip_rows.append(braces([hs,len(hand['poses']),f(hand['duration'])]))
            anim_rows.append(braces(clip_rows));report[name].append({'lod':w['source_lod'],'triangles':len(w['triangles']),'vertices':len(verts),'batches':len(mesh['batches']),'animation_bytes':motion_bytes,'batch_modes':mesh['batch_modes']})
        models.append(braces(model_rows));anims.append(braces(anim_rows));grips.append(braces(grip_rows));mode_rows.append(braces(surface_rows))
    lines+=['const bg_model_asset bg_pve_models[BG_PVE_MODELS][BG_PVE_LODS]='+braces(models)+';',
        'const bg_pve_animation bg_pve_animations[BG_PVE_MODELS][BG_PVE_LODS][PVE_CLIPS]='+braces(anims)+';',
        'const bg_attachment_clip bg_pve_grips[BG_PVE_MODELS][PVE_CLIPS]='+braces(grips)+';',
        'const uint8_t *const bg_pve_shield_vertices[BG_PVE_LODS]='+braces(shield_arrays)+';',
        'const uint8_t *const bg_pve_batch_modes[BG_PVE_MODELS][BG_PVE_LODS]='+braces(mode_rows)+';'
    ]
    (out/'pve-motion.bin').write_bytes(motion)
    if lod_count==3:
        from pack_crunch import bounds_source
        lines.extend(bounds_source(data))
    (out/'pve_data.c').write_text('\n'.join(lines)+'\n')
    if visual_only:
        report['lod_count']=lod_count
        report['motion']={'bytes':len(motion),'sha256':hashlib.sha256(motion).hexdigest(),'layout':'16-bit big-endian pose tracks; original frame timing and interpolation'}
        (out/'pve-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return

    # Extract actual original selector bodies; compact platform adapters live
    # in pve_source.inc. Unsupported campaign/vehicle actions are explicit there.
    source_functions=[('actor_type_grunt.c','grunt_decide_action','static void grunt_decide_action(long actor_index)'),('actor_type_elite.c','elite_decide_action','static void elite_decide_action(long actor_index)'),('actions.c','actor_action_handle_panic_transition','static boolean actor_action_handle_panic_transition(long actor_index,short minimum_panic_type,boolean communicate_failure,short force_panic_type)')]
    source_functions[0:0]=[(f'actor_type_{n}.c',f'{n}_decide_action',f'static void {n}_decide_action(long actor_index)') for n in ('jackal','hunter')]
    source_functions[0:0]=[('actions.c',n,f'static boolean {n}(long actor_index)') for n in ('actor_action_handle_grenade_throwing','actor_action_consider_grenade')]
    bodies=[]
    for path,name,signature in source_functions:
        text=(ROOT/'source/ai'/path).read_text();bodies.append(signature+'{'+function(text,name)+'}\n')
    (out/'pve_source_decisions.inc').write_text('/* Generated verbatim source function bodies. */\n'+'\n'.join(bodies[::-1]))
    from reclaimer.meta.wrappers.halo1_map import Halo1Map
    from extract_extended import tag_values
    from extract_combat import PROFILES
    from reclaimer.enums import materials_list
    with (out/'rules-extract.log').open('w') as log,contextlib.redirect_stdout(log):
        h=Halo1Map();h.load_map(source/(raw.get('campaign','a30')+'-decompressed.map'));es=h.tag_index.tag_index
        multiplayer=Halo1Map();multiplayer.load_map(source/'bloodgulch-decompressed.map')
        def tag(path,kind):
            for cache in ((multiplayer,h) if kind=='damage_effect' else (h,multiplayer)):
                i=next((i for i,e in enumerate(cache.tag_index.tag_index) if e.path==path and e.class_1.enum_name==kind),None)
                if i is not None:return tag_values(cache.get_meta(i))
            raise ValueError((path,kind))
        rows=[];rules={};hit_lines=['#include "pve.h"'];hit_rows=[]
        for name in NAMES:
            a=raw['actors'][name];actor=a['actor'];variant=a['variant'];b=a['biped']['bipd_attrs'];r=variant['ranged_combat'];burst=variant['burst_geometry'];defense=actor['defensive'];panic=actor['panic'];melee=variant['berserking_and_melee']
            collision=tag(a['biped']['obje_attrs']['collision_model'],'model_collision_geometry');(source/(name+'-collision.json')).write_text(json.dumps(collision,indent=2)+'\n')
            bodymat=collision['materials'][collision['indirect_damage_material']]['material_type'];shieldmat=collision['shield']['shield_material_type']
            values=dict(health=variant['unit_properties']['body_vitality'] or collision['body']['maximum_body_vitality'],shield=variant['unit_properties']['shield_vitality'] or collision['shield']['maximum_shield_vitality'],height=b['camera_collision_and_autoaim']['standing_collision_height'],radius=b['camera_collision_and_autoaim']['collision_radius'],eye=b['camera_collision_and_autoaim']['standing_camera_height'],gun=list(actor['perception']['standing_gun_offset'].values()),vision=actor['perception']['max_vision_distance'],vision_angle=actor['perception']['max_vision_angle'],notice=actor['perception']['combat_perception_time'],range=r['maximum_firing_distance'],rate=r['rate_of_fire'],error=r['projectile_error'],damage_scale=r['weapon_damage_modifier'],desired=list(r['desired_combat_range'].values()),first_delay=list(r['first_burst_delay_time'].values()),burst=list(burst['burst_duration'].values()),pause=list(burst['burst_separation'].values()),panic_damage=panic['panic_damage_threshold'],leader_panic=panic['leader_killed_panic_chance'],cower=list(panic['cowering_time'].values()),hide_shield=defense['hide_shield_fraction'],emerge_shield=defense['attack_shield_fraction'],hide=list(defense['hide_behind_cover_time'].values()),evade_delay=defense['evasion_delay_time'],melee_range=melee['melee_range'],melee_delay=actor['berserk']['melee_attack_delay'],berserk_damage=actor['berserk']['berserk_damage_amount'],berserk_threshold=actor['berserk']['berserk_damage_threshold'],shield_delay=collision['shield']['stun_time'],shield_recharge=collision['shield']['recharge_time'])
            values.update(indirect_material=collision['indirect_damage_material'],body_material=materials_list.index(bodymat),shield_material=materials_list.index(shieldmat),move_speed=a['clips']['run']['speed'],flee_speed=a['clips']['flee']['speed'],melee_key=a['clips']['melee']['keyframe'],melee_duration=a['clips']['melee']['duration'],melee_damage=list(a['melee_damage']['damage']['damage_upper_bound'].values()) if a['melee_damage'] else [0,0])
            g=variant['grenades'];values.update(pursue_shield=defense['pursue_shield_fraction'],grenade_chance=g['grenade_chance'],grenade_check=g['grenade_check_time'],grenade_timeout=g['encounter_grenade_timeout'],grenade_range=list(g['grenade_ranges'].values()),grenade_speed=g['grenade_velocity']*30,grenade_collateral=g['collateral_damage_radius'],grenade_radius=g['enemy_radius'],grenade_stimulus={'never':0,'visible_target':1,'seek_cover':2}[g['grenade_stimulus']],grenade_minimum=g['minimum_enemy_count'],throw_key=a['clips']['throw']['keyframe'],throw_duration=a['clips']['throw']['duration'],evade_duration=a['clips']['evade_left']['duration'],exit_duration=a['clips']['exit']['duration'],fire_key=a['clips']['fire']['keyframe'],fire_duration=a['clips']['fire']['duration'],turn_rate=b['moving_turning_speed'])
            items=variant['items'];values.update(evade_cover_chance=defense['evasion_seek_cover_chance'],drop_loaded=list(items['drop_weapon_loaded'].values()),no_grenade_drop=items['dont_drop_grenades_chance'],grenade_count=list(items['grenade_count'].values()))
            damage={}
            material_damage=[{} for _ in collision['materials']]
            for ident,weapon,leaf in PROFILES:
                path='weapons\\'+weapon+'\\'+leaf if weapon else 'globals\\'+leaf
                mods=tag(path,'damage_effect')['damage_modifiers'];damage[ident]=[mods[bodymat],mods[shieldmat]]
                for mi,m in enumerate(collision['materials']):material_damage[mi][ident]=mods[m['material_type']]
            row=['.'+k+'='+(braces(map(f,v)) if isinstance(v,list) else f(v)) for k,v in values.items()]
            row.append('.damage={'+','.join('[BG_D_'+k+']='+braces(map(f,v)) for k,v in damage.items())+'}')
            rows.append(braces(row))
            if name in ('grunt','elite'):
                np='characters'+chr(92)+name+chr(92)+('grunt minor needler' if name=='grunt' else r'elite minor\elite minor needler')
                nv=tag(np,'actor_variant');assert nv['actor_definition']==variant['actor_definition'] and nv['unit']==variant['unit']
                needler_sources[name]={'path':np,'variant':nv};nr=nv['ranged_combat'];nb=nv['burst_geometry'];v=dict(values)
                v.update(range=nr['maximum_firing_distance'],rate=nr['rate_of_fire'],error=nr['projectile_error'],damage_scale=nr['weapon_damage_modifier'],desired=list(nr['desired_combat_range'].values()),first_delay=list(nr['first_burst_delay_time'].values()),burst=list(nb['burst_duration'].values()),pause=list(nb['burst_separation'].values()))
                nrow=['.'+k+'='+(braces(map(f,q)) if isinstance(q,list) else f(q)) for k,q in v.items()];nrow.append(row[-1]);needler_rows.append(braces(nrow))
            rules[name]={**values,'damage':damage,'body_material':bodymat,'shield_material':shieldmat}
            hit=data[name][0]['hit'];symbol='pve_hit_'+name
            hit_lines.append('static const uint16_t '+symbol+'_triangles[][3]='+braces([braces(v) for v in hit['faces']])+';')
            hit_lines.append('static const uint8_t '+symbol+'_materials[]='+braces(hit['materials'])+';')
            hit_anims=[]
            for key in CLIPS:
                clip=hit['clips'][key];prefix=symbol+'_'+key;packed=emit_clip(hit_lines,prefix,clip,128,16);hit_anims.append(clip_initializer(prefix,clip,packed).rstrip(','))
            hit_lines.append('static const bg_pve_animation '+symbol+'_clips[]='+braces(hit_anims)+';')
            mr=[]
            for mi,m in enumerate(collision['materials']):
                ds='{'+','.join('[BG_D_'+k+']='+f(v) for k,v in material_damage[mi].items())+'}'
                mr.append(braces([materials_list.index(m['material_type']),int(bool(m['flags']['head'])),f(m['shield_leak_percentage']),f(m['shield_damage_multiplier']),f(m['body_damage_multiplier']),ds]))
            hit_lines.append('static const bg_pve_hit_material '+symbol+'_rules[]='+braces(mr)+';')
            hit_rows.append(braces([symbol+'_triangles',symbol+'_materials',len(hit['faces']),symbol+'_clips',symbol+'_rules',len(mr)]))
        needle=tag(r'weapons\needler\needle','projectile')['proj_attrs']['material_responses']
        (source/'needle-responses.json').write_text(json.dumps(needle,indent=2)+'\n')
        # The Hunter weapon is an NPC-only source projectile, not a rocket reskin.
        weapon=raw['weapon'][r'weapons\fuel rod gun\hunter fuel rod']['weap_attrs']['triggers'][0]
        projectile_path=weapon['projectile']['projectile'];pr=tag(projectile_path,'projectile')['proj_attrs']
        effect=tag(pr['detonation']['effect'],'effect') if pr.get('detonation',{}).get('effect') else None
        explosion=tag(next(p['type'] for ev in effect['events'] for p in ev['parts'] if p['effect_class']=='damage_effect' and 'fuel rod' in p['type']),'damage_effect')
        fuel={'weapon':weapon,'projectile':pr,'effect':effect,'damage':explosion}
        (source/'fuel-source.json').write_text(json.dumps(fuel,indent=2)+'\n')
    hit_lines.insert(1,'#include "combat.h"');hit_lines.append('const bg_pve_hit_mesh bg_pve_hits[BG_PVE_KINDS]='+braces(hit_rows)+';')
    (out/'pve_collision.c').write_text('\n'.join(hit_lines)+'\n')
    difficulty=raw['globals'][r'globals\globals']['difficulties'][0];dr=[]
    for level in ('easy','normal','hard','imposs'):
        e=difficulty['enemy_scales'];r=difficulty['ranged_combat_scales'];c=difficulty['close_combat_scales']
        dr.append(braces(map(f,[e['damage'][level],e['vitality'][level],e['shield'][level],e['recharge'][level],r['rate_of_fire'][level],r['projectile_error'][level],r['new_target_delay'][level],r['burst_separation'][level],c['melee_delay'][level],c['grenade_chance'][level],c['grenade_timer'][level]])))
    fd=explosion['damage'];fuel_values=[pr['physics']['initial_velocity']*30,pr['physics']['air_gravity_scale'],sum(fd['damage_upper_bound'].values())*.5,explosion['radius']['to'],weapon['charging']['charging_time'],fd['damage_lower_bound'],explosion['radius']['from']]
    fuel_row=braces([*map(f,fuel_values),braces(f(explosion['damage_modifiers'][m]) for m in materials_list)])
    seats=[]
    for side in ('l','r'):
        for i in range(1,5):
            marker=raw['models']['spirit']['markers'][f'cd-passenger{side}0{i}'][0]
            node=raw['models']['spirit']['nodes'][marker['node']]
            assert node['parent']==-1 and node['q']==[0,0,0,1], 'Rebake hierarchical Spirit markers'
            seats.append(position([a+b for a,b in zip(marker['p'],node['p'])],(0,0,0)))
    seat_source='const float bg_spirit_seats[8][3]='+braces([braces(map(f,p)) for p in seats])+';\n'
    needle_source='const uint8_t bg_pve_needle_reflect[33]='+braces(int(n['response']=='reflect') for n in needle)+';\nconst float bg_pve_needle_noise[33]='+braces(f(n['angular_noise']) for n in needle)+';\nconst float bg_pve_needle_friction[33]='+braces(f(n['parallel_refriction']) for n in needle)+';\n'
    (out/'pve_defs.c').write_text('#include "pve.h"\n#include "combat.h"\nconst bg_pve_definition bg_pve_definitions[BG_PVE_KINDS]='+braces(rows)+';\nconst bg_pve_definition bg_pve_needler_definitions[2]='+braces(needler_rows)+';\nconst bg_pve_difficulty bg_pve_difficulties[4]='+braces(dr)+';\nconst bg_pve_fuel bg_pve_fuel_rod='+fuel_row+';\n'+seat_source+needle_source)
    (source/'needler-variants.json').write_text(json.dumps(needler_sources,indent=2)+'\n')
    report['motion']={'bytes':len(motion),'sha256':hashlib.sha256(motion).hexdigest(),'layout':'16-bit big-endian pose tracks; ROM offsets in render clips, 16-byte alignment/padding'}
    report['rules']=rules;report['inputs']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'port/n64/extract_pve.py',ROOT/'port/n64/bake_pve_blender.py',source/'squad-source.json',baked,*(ROOT/'source/ai'/p for p,_,_ in source_functions)]}
    report['lod_count']=lod_count
    (out/'pve-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k in NAMES},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--model-candidate',action='store_true');p.add_argument('--visual-only',action='store_true');a=p.parse_args();pack(a.source,a.output,a.model_candidate,a.visual_only)
