"""Extract CE rank/loadout, weapon, animation and speech inputs from owned caches.

All outputs are private. The accepted symmetric meshes are retained; the new
weapon stances are skinned on those meshes with the original animation graph.
"""
import argparse, audioop, contextlib, copy, hashlib, json, wave
from pathlib import Path
import extract_extended as ext

VARIANTS = (
    ('grunt_major_pp','b30',r'characters\grunt\grunt major plasma pistol'),
    ('grunt_major_nd','b30',r'characters\grunt\grunt major needler'),
    ('elite_major_pr','b30',r'characters\elite\elite major\elite major plasma rifle'),
    ('elite_major_nd','a50',r'characters\elite\elite major\elite major needler'),
    ('jackal_major','b30',r'characters\jackal\jackal major plasma pistol'),
    ('grunt_specops_nd','d40',r'characters\grunt\grunt specops needler'),
    ('grunt_fuel','c40',r'characters\grunt\grunt specops fuel rod'),
    ('elite_specops_pr','d40',r'characters\elite\elite specops\elite specops plasma rifle'),
    ('elite_specops_nd','d40',r'characters\elite\elite specops\elite specops needler'),
    ('zealot_pr','a50',r'characters\elite\elite commander\elite commander plasma rifle'),
    ('zealot_sword','b30',r'characters\elite\elite commander\elite commander energy sword'),
    ('stealth_pr','b30',r'characters\elite\elite stealth\stealth elite plasma rifle'),
    ('stealth_major_pr','b30',r'characters\elite\elite stealth\stealth elite major plasma rifle'),
    ('stealth_sword','a50',r'characters\elite\elite stealth\stealth elite major energy sword'),
)

def extract(maps, base, output):
    from reclaimer.animation.animation_decompilation import extract_animation
    from reclaimer.sounds.sound_decompilation import extract_h1_sounds
    output.mkdir(parents=True,exist_ok=True)
    raw=json.loads((base/'squad-source.json').read_text())
    report={'variants':{},'sounds':[], 'caches':{},'weapons':{}}
    caches={}
    def cache(name):
        if name not in caches:
            caches[name]=ext.open_cache(maps/(name+'.map'),output)
            report['caches'][name]=hashlib.sha256((maps/(name+'.map')).read_bytes()).hexdigest()
        return caches[name]
    def index(h,kind,path):return next(i for i,e in enumerate(h.tag_index.tag_index) if e.class_1.enum_name==kind and e.path==path)
    def tag(h,kind,path):return ext.tag_values(h.get_meta(index(h,kind,path)))
    with (output/'extraction.log').open('w') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
        for ident,cn,path in VARIANTS:
            h=cache(cn);v=tag(h,'actor_variant',path);a=tag(h,'actor',v['actor_definition']);b=tag(h,'biped',v['unit'])
            w=tag(h,'weapon',v['ranged_combat']['weapon'])
            collision=tag(h,'model_collision_geometry',b['obje_attrs']['collision_model'])
            report['variants'][ident]={'path':path,'cache':cn,'variant':v,'actor':a,'biped':b,'collision':collision,'weapon':w}
        h=cache('c40')
        for name,path in [('fuel',r'weapons\fuel rod gun\fuel rod'),('sword',r'weapons\energy sword\energy sword')]:
            w=tag(h,'weapon',path);r={'path':path,'tag':w};report['weapons'][name]=r
            r['melee']=tag(h,'damage_effect',w['weap_attrs']['melee']['player_damage']) if name=='sword' else None
            if name=='fuel':
                pr=tag(h,'projectile',w['weap_attrs']['triggers'][0]['projectile']['projectile']);r['projectile']=pr
                fx=tag(h,'effect',pr['proj_attrs']['detonation']['effect']);r['effect']=fx
                dp=next(p['type'] for e in fx['events'] for p in e['parts'] if p['effect_class']=='damage_effect')
                r['damage']=tag(h,'damage_effect',dp)
            item=w['item_attrs'];r['detonation']=item
            for key,value in item.items():
                if isinstance(value,str) and value and 'detonation' in key:
                    try:
                        fx=tag(h,'effect',value);r[key]=fx
                        dp=next((p['type'] for e in fx['events'] for p in e['parts'] if p['effect_class']=='damage_effect'),None)
                        if dp:r[key+'_damage']=tag(h,'damage_effect',dp)
                    except StopIteration:pass
        # Alternate clips keep logical action ordering. Missing weapon-class
        # slots inherit the source's ordinary action, never a synthetic pose.
        for name,stance in [('grunt','missle'),('elite','sword')]:
            ai=index(h,'model_animations',rf'characters\{name}\{name}');anim=h.get_meta(ai);h.meta_to_tag_data(anim,'antr',h.tag_index.tag_index[ai])
            names=[a.name for a in anim.animations.STEPTREE]
            original=raw['actors'][name]['clips'];alternate=copy.deepcopy(original)
            wanted={'idle':f'stand {stance} idle','run':f'stand {stance} move-front'}
            if name=='elite':wanted.update(melee='stand sword melee%0',throw='stand sword throw-grenade',evade_left='stand sword evade-left',evade_right='stand sword evade-right',crouch='crouch sword idle',flee='stand sword move-front')
            # The Grunt missile class has no firing overlay in CE. Retain its
            # two-handed stance during charging/discharge instead of a PP pose.
            if name=='grunt':wanted.update(fire='stand missle idle',flee='stand missle move-front')
            for key,prefix in wanted.items():
                i=next(i for i,n in enumerate(names) if n==prefix or n.startswith(prefix+'%'));c=extract_animation(i,anim,write_jma=False)
                c.apply_root_node_info_to_states(undo=True);a=anim.animations.STEPTREE[i];count=a.frame_count
                frames=c.frames[:count] if key in ('melee','throw','evade_left','evade_right') else c.frames
                alternate[key]={'speed':sum((r.dx*r.dx+r.dy*r.dy)**.5 for r in c.root_node_info)/max(1,len(c.root_node_info))*.3,
                    'keyframe':a.key_frame_index/30,'name':names[i],'type':c.anim_type,'duration':count/30,
                    'root_motion':[[r.dx/100,r.dy/100,r.dz/100] for r in c.root_node_info],
                    'rot_flags':c.rot_flags_int,'trans_flags':c.trans_flags_int,'scale_flags':c.scale_flags_int,
                    'frames':[[{'p':[n.pos_x/100,n.pos_y/100,n.pos_z/100],'q':[n.rot_i,n.rot_j,n.rot_k,n.rot_w],'s':n.scale} for n in f] for f in frames]}
            raw['actors'][name]['clips'].update({'alt_'+k:v for k,v in alternate.items()})
        for name in ('jackal','hunter'):
            clips=raw['actors'][name]['clips'];clips.update({'alt_'+k:copy.deepcopy(v) for k,v in list(clips.items())})
        # Preserve all dialogue tag references; ship a bounded set of complete
        # permutations for gameplay events. Empty source fields stay silent.
        paths={
            'spot':('combat','new_combat_alone'), 'combat':('idle','combat'),
            'idle':('idle','noncombat'),'panic':('idle','flee'),
            'pain':('involuntary','pain_body_minor'),'death':('involuntary','death_violent'),
            'grenade':('shouting','grenade_throwing'),'kill':('killing_people','killed_enemy_player'),
            'leader':('friends_dying','friend_died'),
        }
        report['dialogue']={}
        for kind,name in enumerate(('grunt','elite','jackal','hunter')):
            path=rf'sound\dialog\{name}'+(rf'\conditional\{name}' if kind<2 else '\\'+name)
            d=tag(h,'dialogue',path);report['dialogue'][name]=d
            # Resolve names directly from the tag schema across its groups.
            leaves={k:v for group in d.values() if isinstance(group,dict) for k,v in group.items() if isinstance(v,str)}
            for event,(_,key) in paths.items():
                sound=leaves.get(key,'')
                if event=='spot':sound=leaves.get('new_combat_alone','') or leaves.get('new_combat_group','') or leaves.get('surprised','')
                if not sound:continue
                ix=index(h,'sound',sound);entry=h.tag_index.tag_index[ix];meta=h.get_meta(ix);h.meta_to_tag_data(meta,'snd!',entry)
                folder=f'{name}-{event}';extract_h1_sounds(meta,folder,out_dir=output/'sounds',decode_adpcm=True)
                files=sorted((output/'sounds'/folder).rglob('*.wav'))
                for wav in files[:4]:
                    with wave.open(str(wav)) as w:
                        pcm=w.readframes(w.getnframes());rate=w.getframerate();width=w.getsampwidth();channels=w.getnchannels()
                    if channels==2:pcm=audioop.tomono(pcm,width,.5,.5)
                    pcm=audioop.ratecv(pcm,width,1,rate,11025,None)[0];pcm=audioop.lin2lin(pcm,width,1)
                    file=f'voice-{len(report["sounds"]):03d}.s8';(output/file).write_bytes(pcm)
                    report['sounds'].append({'kind':kind,'event':event,'tag':sound,'permutation':str(wav.relative_to(output)),'file':file,'bytes':len(pcm),'rate':11025,'sha256':hashlib.sha256(pcm).hexdigest()})
        # Original weapon/animation cues accompany the new armaments.
        fire=tag(h,'effect',r'weapons\fuel rod gun\effects\fuel rod fire')
        fire_sound=next(p['type'] for e in fire['events'] for p in e['parts'] if p['effect_class']=='sound')
        effect_paths={'fuel_fire':fire_sound,'sword_swing':r'sound\sfx\impulse\animations\elite\stand_sword_melee_oh','fuel_explosion':r'sound\sfx\weapons\fuel rod gun\explosion'}
        for event,path in effect_paths.items():
            ix=index(h,'sound',path);entry=h.tag_index.tag_index[ix];meta=h.get_meta(ix);h.meta_to_tag_data(meta,'snd!',entry)
            extract_h1_sounds(meta,event,out_dir=output/'sounds',decode_adpcm=True)
            for wav in sorted((output/'sounds'/event).rglob('*.wav'))[:2]:
                with wave.open(str(wav)) as w:pcm=w.readframes(w.getnframes());rate=w.getframerate();width=w.getsampwidth();channels=w.getnchannels()
                if channels==2:pcm=audioop.tomono(pcm,width,.5,.5)
                pcm=audioop.lin2lin(audioop.ratecv(pcm,width,1,rate,11025,None)[0],width,1)
                file=f'voice-{len(report["sounds"]):03d}.s8';(output/file).write_bytes(pcm)
                report['sounds'].append({'kind':4,'event':event,'tag':path,'permutation':str(wav.relative_to(output)),'file':file,'bytes':len(pcm),'rate':11025,'sha256':hashlib.sha256(pcm).hexdigest()})
        from extract_combat import PROFILES
        report['camo_damage']={}
        for ident,weapon,leaf in PROFILES:
            path='weapons\\'+weapon+'\\'+leaf if weapon else 'globals\\'+leaf
            for candidate in (h,cache('bloodgulch'),cache('b30')):
                try:damage=tag(candidate,'damage_effect',path);break
                except StopIteration:continue
            else:raise ValueError(path)
            report['camo_damage'][ident]=damage['damage']['active_camouflage_damage']
        raw['roster']=report
        (output/'squad-source.json').write_text(json.dumps(raw,separators=(',',':')))
        (output/'roster-source.json').write_text(json.dumps(report,indent=2)+'\n')
        previous=ext.MODEL_PATHS
        try:
            ext.MODEL_PATHS={'fuel':r'weapons\fuel rod gun\fuel rod gun','sword':r'weapons\energy sword\energy sword'}
            weapon_out=output/'weapons';weapon_out.mkdir(exist_ok=True);(weapon_out/'extended-raw.json').write_text('{"models":{},"sources":{}}')
            ext.extract(weapon_out,maps,models_only=True,include_source_lods=True,campaign_name='c40')
        finally:ext.MODEL_PATHS=previous
    print(json.dumps({'variants':len(report['variants']),'sounds':len(report['sounds']),'sound_bytes':sum(s['bytes'] for s in report['sounds'])}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--maps',type=Path,required=True);p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();extract(a.maps,a.base,a.output)
