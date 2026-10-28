"""Pack the private squad art, source tag settings and source decision bodies."""
import argparse,contextlib,hashlib,json,re
from pathlib import Path
from pack_mesh import emit_batches,indexed_mesh,trajectory_keys,remap_clip
from model_colors import load_images,bake_triangle,bake_team_mask
from pack_assets import position
from pack_animation import emit_clip,clip_initializer
from test_render_matrix import function
ROOT=Path(__file__).resolve().parents[2]
NAMES=('grunt','elite');CLIPS=('idle','run','fire','death','flee','melee')
def braces(v):return '{'+','.join(map(str,v))+'}'
def f(v):return float(v).hex()+'f'
def prepare_model(w):
    images=load_images(w['textures']);metadata=w['material_metadata']
    masks=load_images([m.get('multipurpose_fullres') for m in metadata])
    channels=[2 if m.get('color_change_source')=='A' else None for m in metadata]
    points=[];colors=[];tints=[];materials=[]
    for t in w['triangles']:
        points.extend([[round(v*128) for v in position(p,(0,0,0))] for p in t['p']])
        colors.extend(bake_triangle(t,images,w));tints.extend(bake_team_mask(t,masks,channels));materials.extend([t['material']]*3)
    mesh=indexed_mesh(points,colors,tints,trajectory_keys(w['clips'],128,16),color_tolerance=8,material_keys=materials)
    return mesh,{n:remap_clip(c,mesh['sources']) for n,c in w['clips'].items()}

def pack(source,out):
    source=source.resolve();out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    data=json.loads((source/'squad-baked.json').read_text());raw=json.loads((source/'squad-source.json').read_text())
    lines=['/* Private original CE geometry and animation. */','#include "asset_pve.h"'];models=[];anims=[];grips=[];report={}
    for name in NAMES:
        model_rows=[];anim_rows=[];grip_rows=[];report[name]=[]
        for lod,w in enumerate(data[name]):
            symbol=f'pve_{name}_{lod}';mesh,clips=prepare_model(w)
            verts=mesh['vertices'];colors=raw['actors'][name]['variant']['change_colors']
            if not colors:colors=raw['actors'][name]['biped']['obje_attrs']['change_colors'][0]['permutations']
            tint=[(lo+hi)*.5 for lo,hi in zip(colors[0]['color_lower_bound'].values(),colors[0]['color_upper_bound'].values())] if colors else None
            lines.append('static T3DVertPacked '+symbol+'[] __attribute__((aligned(16)))={')
            for i in range(0,len(verts),2):
                pair=[]
                for v in verts[i:i+2]:
                    rgb=v[1]
                    if tint:rgb=[round(c*(1-v[2]/255+v[2]/255*tint[j])) for j,c in enumerate(rgb)]
                    pair.append((braces(v[0]),(rgb[0]<<24)|(rgb[1]<<16)|(rgb[2]<<8)|255))
                lines.append('{'+f'{pair[0][0]},0,{pair[1][0]},0,0x{pair[0][1]:08x},0x{pair[1][1]:08x},{{0,0}},{{0,0}}'+'},')
            lines.append('};');emit_batches(lines,symbol,mesh)
            model_rows.append(braces([symbol,len(verts),'2.f',symbol+'_batches',symbol+'_indices',len(mesh['batches']),len(w['triangles'])]))
            clip_rows=[];motion_bytes=0
            for key in CLIPS:
                clip=clips[key];prefix=symbol+'_'+key;packed=emit_clip(lines,prefix,clip,128,16);motion_bytes+=packed['bytes']
                clip_rows.append(clip_initializer(prefix,clip,packed).rstrip(','))
                if lod==0:
                    hand=w['grips'][key];hs='pve_'+name+'_hand_'+key
                    lines.append('static const bg_attachment_pose '+hs+'[]='+braces([braces([braces(map(f,p['pos'])),braces(map(f,p['quat']))]) for p in hand['poses']])+';')
                    grip_rows.append(braces([hs,len(hand['poses']),f(hand['duration'])]))
            anim_rows.append(braces(clip_rows));report[name].append({'lod':w['source_lod'],'triangles':len(w['triangles']),'vertices':len(verts),'batches':len(mesh['batches']),'animation_bytes':motion_bytes})
        models.append(braces(model_rows));anims.append(braces(anim_rows));grips.append(braces(grip_rows))
    lines+=['const bg_model_asset bg_pve_models[2][2]='+braces(models)+';',
        'const bg_pve_animation bg_pve_animations[2][2][PVE_CLIPS]='+braces(anims)+';',
        'const bg_attachment_clip bg_pve_grips[2][PVE_CLIPS]='+braces(grips)+';']
    (out/'pve_data.c').write_text('\n'.join(lines)+'\n')
    # Extract actual original selector bodies; compact platform adapters live
    # in pve_source.inc. Unsupported campaign/vehicle actions are explicit there.
    source_functions=[('actor_type_grunt.c','grunt_decide_action','static void grunt_decide_action(long actor_index)'),('actor_type_elite.c','elite_decide_action','static void elite_decide_action(long actor_index)'),('actions.c','actor_action_handle_panic_transition','static boolean actor_action_handle_panic_transition(long actor_index,short minimum_panic_type,boolean communicate_failure,short force_panic_type)')]
    bodies=[]
    for path,name,signature in source_functions:
        text=(ROOT/'source/ai'/path).read_text();bodies.append(signature+'{'+function(text,name)+'}\n')
    (out/'pve_source_decisions.inc').write_text('/* Generated verbatim source function bodies. */\n'+'\n'.join(bodies[::-1]))
    from reclaimer.meta.wrappers.halo1_map import Halo1Map
    from extract_extended import tag_values
    from extract_combat import PROFILES
    from reclaimer.enums import materials_list
    with (out/'rules-extract.log').open('w') as log,contextlib.redirect_stdout(log):
        h=Halo1Map();h.load_map(source/'a30-decompressed.map');es=h.tag_index.tag_index
        multiplayer=Halo1Map();multiplayer.load_map(source/'bloodgulch-decompressed.map')
        def tag(path,kind):
            for cache in ((multiplayer,h) if kind=='damage_effect' else (h,multiplayer)):
                i=next((i for i,e in enumerate(cache.tag_index.tag_index) if e.path==path and e.class_1.enum_name==kind),None)
                if i is not None:return tag_values(cache.get_meta(i))
            raise ValueError((path,kind))
        rows=[];rules={}
        for name in NAMES:
            a=raw['actors'][name];actor=a['actor'];variant=a['variant'];b=a['biped']['bipd_attrs'];r=variant['ranged_combat'];burst=variant['burst_geometry'];defense=actor['defensive'];panic=actor['panic'];melee=variant['berserking_and_melee']
            collision=tag(a['biped']['obje_attrs']['collision_model'],'model_collision_geometry');(source/(name+'-collision.json')).write_text(json.dumps(collision,indent=2)+'\n')
            bodymat=collision['materials'][collision['indirect_damage_material']]['material_type'];shieldmat=collision['shield']['shield_material_type']
            values=dict(health=variant['unit_properties']['body_vitality'] or collision['body']['maximum_body_vitality'],shield=variant['unit_properties']['shield_vitality'] or collision['shield']['maximum_shield_vitality'],height=b['camera_collision_and_autoaim']['standing_collision_height'],radius=b['camera_collision_and_autoaim']['collision_radius'],eye=b['camera_collision_and_autoaim']['standing_camera_height'],gun=list(actor['perception']['standing_gun_offset'].values()),vision=actor['perception']['max_vision_distance'],vision_angle=actor['perception']['max_vision_angle'],notice=actor['perception']['combat_perception_time'],range=r['maximum_firing_distance'],rate=r['rate_of_fire'],error=r['projectile_error'],damage_scale=r['weapon_damage_modifier'],desired=list(r['desired_combat_range'].values()),first_delay=list(r['first_burst_delay_time'].values()),burst=list(burst['burst_duration'].values()),pause=list(burst['burst_separation'].values()),panic_damage=panic['panic_damage_threshold'],leader_panic=panic['leader_killed_panic_chance'],cower=list(panic['cowering_time'].values()),hide_shield=defense['hide_shield_fraction'],emerge_shield=defense['attack_shield_fraction'],hide=list(defense['hide_behind_cover_time'].values()),evade_delay=defense['evasion_delay_time'],melee_range=melee['melee_range'],melee_delay=actor['berserk']['melee_attack_delay'],berserk_damage=actor['berserk']['berserk_damage_amount'],berserk_threshold=actor['berserk']['berserk_damage_threshold'],shield_delay=collision['shield']['stun_time'],shield_recharge=collision['shield']['recharge_time'])
            values.update(body_material=materials_list.index(bodymat),shield_material=materials_list.index(shieldmat),move_speed=a['clips']['run']['speed'],flee_speed=a['clips']['flee']['speed'],melee_key=a['clips']['melee']['keyframe'],melee_duration=a['clips']['melee']['duration'],melee_damage=list(a['melee_damage']['damage']['damage_upper_bound'].values()) if a['melee_damage'] else [0,0])
            damage={}
            for ident,weapon,leaf in PROFILES:
                path='weapons\\'+weapon+'\\'+leaf if weapon else 'globals\\'+leaf
                mods=tag(path,'damage_effect')['damage_modifiers'];damage[ident]=[mods[bodymat],mods[shieldmat]]
            row=['.'+k+'='+(braces(map(f,v)) if isinstance(v,list) else f(v)) for k,v in values.items()]
            row.append('.damage={'+','.join('[BG_D_'+k+']='+braces(map(f,v)) for k,v in damage.items())+'}')
            rows.append(braces(row));rules[name]={**values,'damage':damage,'body_material':bodymat,'shield_material':shieldmat}
    (out/'pve_defs.c').write_text('#include "pve.h"\n#include "combat.h"\nconst bg_pve_definition bg_pve_definitions[2]='+braces(rows)+';\n')
    report['rules']=rules;report['inputs']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'port/n64/extract_pve.py',ROOT/'port/n64/bake_pve_blender.py',source/'squad-source.json',source/'squad-baked.json',*(ROOT/'source/ai'/p for p,_,_ in source_functions)]}
    (out/'pve-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k in NAMES},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();pack(a.source,a.output)
