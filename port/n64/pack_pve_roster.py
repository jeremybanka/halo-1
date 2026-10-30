"""Pack an isolated source-driven roster bank; original triangle shapes survive."""
import argparse,copy,gzip,hashlib,json,math,shutil
from pathlib import Path
import pack_pve as pp
from pack_animation import emit_clip,clip_initializer
from pack_crunch import palette
from pack_mesh import indexed_mesh,emit_batches
from pack_assets import position
from model_colors import bake_triangle,load_images
from extract_pve_roster import VARIANTS

ROOT=Path(__file__).resolve().parents[2]
B=pp.braces;F=pp.f

def rules(a,raw,base,name,alternate=False):
    """The same source fields consumed by the bounded production adapters."""
    v=a['variant'];actor=a['actor'];b=a['biped']['bipd_attrs'];c=a['collision']
    r=v['ranged_combat'];burst=v['burst_geometry'];de=actor['defensive'];panic=actor['panic'];melee=v['berserking_and_melee'];g=v['grenades'];items=v['items']
    d=copy.deepcopy(base[name]);d.pop('damage');d['body_material']=base[name]['body_material'];d['shield_material']=base[name]['shield_material']
    from reclaimer.enums import materials_list
    d.update(body_material=materials_list.index(c['materials'][c['indirect_damage_material']]['material_type']),shield_material=materials_list.index(c['shield']['shield_material_type']),indirect_material=c['indirect_damage_material'],
        health=v['unit_properties']['body_vitality'] if v['unit_properties']['body_vitality']>0 or v['unit_properties']['shield_vitality']>0 else c['body']['maximum_body_vitality'],shield=v['unit_properties']['shield_vitality'] if v['unit_properties']['body_vitality']>0 or v['unit_properties']['shield_vitality']>0 else c['shield']['maximum_shield_vitality'],
        height=b['camera_collision_and_autoaim']['standing_collision_height'],radius=b['camera_collision_and_autoaim']['collision_radius'],eye=b['camera_collision_and_autoaim']['standing_camera_height'],gun=list(actor['perception']['standing_gun_offset'].values()),
        vision=actor['perception']['max_vision_distance'],vision_angle=actor['perception']['max_vision_angle'],notice=actor['perception']['combat_perception_time'],
        range=r['maximum_firing_distance'],rate=r['rate_of_fire'],error=r['projectile_error'],damage_scale=r['weapon_damage_modifier'],desired=list(r['desired_combat_range'].values()),first_delay=list(r['first_burst_delay_time'].values()),burst=list(burst['burst_duration'].values()),pause=list(burst['burst_separation'].values()),
        panic_damage=panic['panic_damage_threshold'],leader_panic=panic['leader_killed_panic_chance'],cower=list(panic['cowering_time'].values()),hide_shield=de['hide_shield_fraction'],emerge_shield=de['attack_shield_fraction'],hide=list(de['hide_behind_cover_time'].values()),evade_delay=de['evasion_delay_time'],
        melee_range=melee['melee_range'],melee_delay=actor['berserk']['melee_attack_delay'],berserk_damage=actor['berserk']['berserk_damage_amount'],berserk_threshold=actor['berserk']['berserk_damage_threshold'],shield_delay=c['shield']['stun_time'],shield_recharge=c['shield']['recharge_time'],
        pursue_shield=de['pursue_shield_fraction'],grenade_chance=g['grenade_chance'],grenade_check=g['grenade_check_time'],grenade_timeout=g['encounter_grenade_timeout'],grenade_range=list(g['grenade_ranges'].values()),grenade_speed=g['grenade_velocity']*30,grenade_collateral=g['collateral_damage_radius'],grenade_radius=g['enemy_radius'],grenade_stimulus={'never':0,'visible_target':1,'seek_cover':2}[g['grenade_stimulus']],grenade_minimum=g['minimum_enemy_count'],turn_rate=b['moving_turning_speed'],
        evade_cover_chance=de['evasion_seek_cover_chance'],drop_loaded=list(items['drop_weapon_loaded'].values()),no_grenade_drop=items['dont_drop_grenades_chance'],grenade_count=list(items['grenade_count'].values()))
    clips=raw['actors'][name]['clips'];prefix='alt_' if alternate else ''
    for field,key,value in [('move_speed','run','speed'),('flee_speed','flee','speed'),('melee_key','melee','keyframe'),('melee_duration','melee','duration'),('throw_key','throw','keyframe'),('throw_duration','throw','duration'),('evade_duration','evade_left','duration'),('exit_duration','exit','duration'),('fire_key','fire','keyframe'),('fire_duration','fire','duration')]:d[field]=clips[prefix+key][value]
    if a['weapon']['weap_attrs']['flags']['ai_uses_weapon_melee_damage']:d['melee_damage']=list(raw['roster']['weapons']['sword']['melee']['damage']['damage_upper_bound'].values())
    d['damage']=base[name]['damage']
    return d

def definition(d):
    return B(['.'+k+'='+(B(map(F,v)) if isinstance(v,list) else F(v)) for k,v in d.items() if k!='damage']+['.damage={'+','.join('[BG_D_'+k+']='+B(map(F,v)) for k,v in d['damage'].items())+'}'])

def pack(source,out):
    from reclaimer.enums import materials_list
    out.mkdir(parents=True,exist_ok=True);raw=json.loads((source/'squad-source.json').read_text());r=raw['roster']
    original=json.loads(gzip.decompress((ROOT/'halo64-assets/assets/covenant-symmetry/source/squad-baked.json.gz').read_bytes()))
    rebuilt=json.loads(gzip.decompress((source/'rebaked.json.gz').read_bytes()));data=copy.deepcopy(original)
    for name,models in data.items():
        for lod,m in enumerate(models):
            if name in rebuilt:
                # Base poses/colors stay exactly as appraised; only new source
                # stances enter the bank. All trajectories participate in welding.
                alt=rebuilt[name][lod]
                for k in ('clips','grips'):
                    m[k].update({n:v for n,v in alt[k].items() if n.startswith('alt_')})
                if lod==0:m['hit']['clips'].update({n:v for n,v in alt['hit']['clips'].items() if n.startswith('alt_')})
            else:
                for k in ('clips','grips'):
                    m[k].update({'alt_'+n:copy.deepcopy(v) for n,v in list(m[k].items())})
            if len(m['clips'])!=24:raise ValueError((name,lod,len(m['clips'])))
    (source/'squad-baked.json.gz').write_bytes(gzip.compress(json.dumps(data,separators=(',',':')).encode(),mtime=0))
    pp.CLIPS=pp.CLIPS+tuple('alt_'+k for k in pp.CLIPS)
    pp.pack(source,out,model_candidate=True,visual_only=True)
    base=json.loads((ROOT/'halo64-assets/generated/pve/pve-report.json').read_text())['rules']
    lines=['#include "pve_roster.h"','#include "game.h"','#include "combat.h"'];rows=['{0}'];rule_report={}
    color_rows=['{0}'];color_lines=['#include "asset_pve.h"'];meshes={}
    for name in ('grunt','elite','jackal'):
        meshes[name]=[pp.prepare_model(m,True)[0] for m in data[name]]
    for ident,_,_ in VARIANTS:
        a=r['variants'][ident];name=a['path'].split('\\')[1];kind=('grunt','elite','jackal','hunter').index(name)
        arm=1 if ident=='grunt_fuel' else 2 if 'sword' in ident else 0
        d=rules(a,raw,base,name,bool(arm));rank=3 if ident.startswith('zealot') else 2 if 'specops' in ident or arm==1 else 1 if 'major' in ident else 0
        weapon='BG_W_NEEDLER' if a['variant']['ranged_combat']['weapon'].endswith('needler') else 'BG_W_PLASMA_PISTOL' if kind!=1 else 'BG_W_PLASMA_RIFLE'
        flags=a['variant']['flags'];flags=int(bool(flags['active_camouflage']))+2*int(bool(flags['super_active_camouflage']))+4*int(bool(flags['cannot_use_ranged_weapons']))
        cs=a['variant']['change_colors'] or a['biped']['obje_attrs']['change_colors'][0]['permutations']
        tint=[(x+y)*.5 for x,y in zip(cs[0]['color_lower_bound'].values(),cs[0]['color_upper_bound'].values())]
        melee=r['weapons']['sword']['melee'] if arm==2 else None
        radius=melee['radius']['to'] if melee else 0
        # Source attack damage is local to the animated melee/hand marker, not
        # the actor variant's tactical charge range (12 units for commanders).
        hand=data[name][0]['grips']['alt_melee' if arm else 'melee'];phase=d['melee_key']/max(hand['duration'],.001);pose=hand['poses'][min(len(hand['poses'])-1,round(phase*(len(hand['poses'])-1)))]['pos']
        reach=math.hypot(pose[0],pose[2])+radius
        mods=[melee['damage_modifiers'][m] for m in materials_list] if melee else [1]*33
        row=B([json.dumps(ident),definition(d),kind,weapon,rank,arm,flags,B(map(F,tint)),F(reach),F(radius),B(map(F,mods))]);rows.append(row)
        rule_report[ident]={'definition':d,'rank':rank,'kind':kind,'weapon':weapon,'armament':arm,'flags':flags,'tint':tint,'strike_reach':reach,'source':a['path']}
        colors=[]
        for lod,mesh in enumerate(meshes[name]):
            values=[]
            for vi,v in enumerate(mesh['vertices']):
                rgb=[round(c*(1-v[2]/255+v[2]/255*tint[j])) for j,c in enumerate(v[1])]
                if name=='elite' and max(tint)>.01:
                    # CE's Elite shader obtains much of its armor brightness
                    # from environment/specular lighting. An unlit multiply
                    # makes red and gold both nearly black on the N64. Flatten
                    # that lighting into a ramp while keeping the source hue,
                    # source color-change mask and uncolored undersuit intact.
                    hue=[c/max(tint) for c in tint];mask=v[2]/255
                    rgb=[round(c*(1-mask)+min(220,c*2.5+30)*hue[j]*mask) for j,c in enumerate(v[1])]
                values.append((rgb[0]<<24)|(rgb[1]<<16)|(rgb[2]<<8)|mesh['alphas'][vi])
            symbol=f'roster_{ident}_{lod}';color_lines.append('static const uint32_t '+symbol+'[]='+B(hex(v) for v in values)+';');colors.append(symbol)
        color_rows.append(B(colors))
    lines.append('const bg_pve_variant bg_pve_variants[PVE_R_COUNT]='+B(rows)+';')
    lines.append('const float bg_pve_camo_damage[26]='+B('[BG_D_'+k+']='+F(v) for k,v in r['camo_damage'].items())+';')
    color_lines.append('const uint32_t *const bg_pve_variant_colors[PVE_R_COUNT][BG_PVE_LODS]='+B(color_rows)+';')
    def fuel_row(d,pr,charge):
        damage=d['damage'];return B([*map(F,[pr['physics']['initial_velocity']*30,pr['physics']['air_gravity_scale'],sum(damage['damage_upper_bound'].values())*.5,d['radius']['to'],charge,damage['damage_lower_bound'],d['radius']['from']]),B(F(d['damage_modifiers'][m]) for m in materials_list)])
    fuel=r['weapons']['fuel'];pr=fuel['projectile']['proj_attrs']
    lines.append('const bg_pve_fuel bg_pve_grunt_fuel='+fuel_row(fuel['damage'],pr,fuel['tag']['weap_attrs']['triggers'][0]['charging']['charging_time'])+';')
    lines.append('const bg_pve_fuel bg_pve_dropped_fuel='+fuel_row(fuel['detonation_effect_damage'],pr,0)+';')
    for name in ('fuel','sword'):lines.append('const float bg_pve_'+name+'_drop_delay[2]='+B(map(F,r['weapons'][name]['detonation']['detonation_delay'].values()))+';')
    alt_rows=[]
    for name in ('grunt','elite'):
        clips=[]
        for key in pp.CLIPS[12:]:
            clip=data[name][0]['hit']['clips'][key];prefix='roster_hit_'+name+'_'+key;packed=emit_clip(lines,prefix,clip,128,16);clips.append(clip_initializer(prefix,clip,packed).rstrip(','))
        alt_rows.append(B(clips))
    lines.append('const bg_pve_animation bg_pve_alt_hit_clips[2][12]='+B(alt_rows)+';')
    voice=bytearray();voices=[];events=('spot','combat','idle','panic','pain','death','grenade','kill','leader','fuel_fire','sword_swing','fuel_explosion')
    for sound in r['sounds']:
        pcm=(source/sound['file']).read_bytes();assert hashlib.sha256(pcm).hexdigest()==sound['sha256']
        voice.extend(bytes(-len(voice)%16));offset=len(voice);voice.extend(pcm);voice.extend(bytes(16))
        voices.append(B([offset,len(pcm),sound['kind'],events.index(sound['event'])]))
    (out/'pve-voices.bin').write_bytes(voice)
    lines.append('const bg_pve_voice bg_pve_voices[]='+B(voices)+';\nconst unsigned bg_pve_voice_count='+str(len(voices))+';')
    (out/'pve_roster.c').write_text('\n'.join(lines)+'\n');(out/'pve_roster_colors.c').write_text('\n'.join(color_lines)+'\n')
    weapons=json.loads((source/'weapons/extended-raw.json').read_text())['models'];wl=['#include "asset_pve.h"'];wr=[];weapon_report={}
    for name,m in weapons.items():
        choices=[(k,g) for k,g in m['source_geometry_lods'].items() if not k.startswith('~')];choices.sort(key=lambda x:len(x[1]['faces']))
        g=choices[0][1];images=load_images(m['textures']);points=[];colors=[]
        for face,material in zip(g['faces'],g['materials']):
            t={'p':[g['vertices'][v] for v in face],'uv':[g['uv'][v] for v in face],'material':material}
            points.extend([[round(x*1024) for x in position(p,(0,0,0))] for p in t['p']]);colors.extend(bake_triangle(t,images,m))
        mesh=indexed_mesh(points,colors,[0]*len(points),color_tolerance=8,reorder_static=True);symbol='pve_weapon_'+name
        wl.append('static T3DVertPacked '+symbol+'[] __attribute__((aligned(16)))={')
        for a,b in zip(mesh['vertices'][::2],mesh['vertices'][1::2]):
            rgba=lambda v:hex((v[1][0]<<24)|(v[1][1]<<16)|(v[1][2]<<8)|255)
            wl.append('{'+B(a[0])+',0,'+B(b[0])+',0,'+rgba(a)+','+rgba(b)+',{0,0},{0,0}},')
        wl.append('};');emit_batches(wl,symbol,mesh)
        wr.append(B([symbol,len(mesh['vertices']),'2.f',symbol+'_batches',symbol+'_indices',len(mesh['batches']),len(g['faces'])]));weapon_report[name]={'lod':choices[0][0],'triangles':len(g['faces']),'vertices':len(mesh['vertices'])}
    wl.append('const bg_model_asset bg_pve_roster_weapons[2]='+B(wr)+';');(out/'pve_roster_weapons.c').write_text('\n'.join(wl)+'\n')
    report=json.loads((out/'pve-report.json').read_text());report['roster']={'variants':rule_report,'weapons':weapon_report,'elite_palette':'source hue and multipurpose mask; flattened lighting ramp min(220,albedo*2.5+30), black specops retains source multiply','speech_permutations':len(voices),'speech_bytes':len(voice),'source_sha256':hashlib.sha256((source/'roster-source.json').read_bytes()).hexdigest()};report['clips']=24
    (out/'pve-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['roster'],indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();pack(a.source.resolve(),a.output.resolve())
