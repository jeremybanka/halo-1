#!/usr/bin/env python3
"""Extract multiplayer models, original skeleton clips, HUD and audio from owned Xbox caches.

Run after extract_assets.py. Every output is local under build/n64/assets.
"""
import argparse, audioop, contextlib, hashlib, json, struct, wave, zlib
from pathlib import Path

MODEL_PATHS={
'ar':r'weapons\assault rifle\assault rifle','pistol':r'weapons\pistol\pistol',
'plasma_pistol':r'weapons\plasma pistol\plasma pistol','plasma_rifle':r'weapons\plasma rifle\plasma rifle',
'needler':r'weapons\needler\needler','shotgun':r'weapons\shotgun\shotgun',
'sniper':r'weapons\sniper rifle\sniper rifle','rocket':r'weapons\rocket launcher\rocket launcher',
'warthog':r'vehicles\warthog\warthog','ghost':r'vehicles\ghost\ghost',
'scorpion':r'vehicles\scorpion\scorpion_mp\scorpion_mp','banshee':r'vehicles\banshee\banshee',
'frag':r'weapons\frag grenade\frag grenade','plasma_grenade':r'weapons\plasma grenade\plasma grenade',
'flamethrower':r'weapons\flamethrower\flamethrower','spartan':r'characters\cyborg\cyborg',
'healthpack':r'powerups\healthpack\healthpack','overshield':r'powerups\over shield\over shield',
'camouflage':r'powerups\active camoflage\active camoflage'}
AUDIO_TAGS={
'ar':458,'pistol':548,'plasma_pistol':1368,'plasma_rifle':911,'needler':1583,'shotgun':994,'sniper':1254,'rocket':1169,
'flamethrower':1468,'reload':280,'pistol_reload':499,'needler_reload':1534,'shotgun_reload':946,'sniper_reload':1194,
'rocket_reload':1119,'explosion':776,'plasma_explosion':1274,'warthog':652,'ghost':859,'scorpion':763,
'jump':598,'footstep':571,'shield_hit':224,'shield_charge':226,'death':235,'respawn':1663,'slayer':1653,'game_over':1633,
'double_kill':1646,'triple_kill':1647,'killing_spree':1650,'teleporter':1659,'ambience':1804,
'banshee':('a30',1491),'warthog_gun':698,'scorpion_gun':776,'ghost_gun':911,
'banshee_gun':('a30',1552),'banshee_bomb':('a30',1593)}
# These are the sound references in the original vehicle firing effects.
# Verify identical decoded samples before sharing the runtime PCM buffer.
AUDIO_ALIASES={'scorpion_gun':'explosion','ghost_gun':'plasma_rifle','banshee_gun':'plasma_rifle'}
AUDIO_LIMITS={'warthog_gun':.6,'banshee_bomb':1}
ANIM_NAMES={'idle':'stand rifle idle','run':'stand rifle move-front','fire':'stand rifle ar fire-1',
'reload':'stand rifle ar reload-1','death':'h-kill front gut','jump':'stand rifle airborne',
'melee':'stand rifle ar melee','throw':'stand rifle throw-grenade','drive':'W-driver unarmed idle',
'passenger':'W-passenger rifle idle','gunner':'W-gunner fixed idle'}
HUD_TAGS={'unit_backgrounds':221,'unit_meters':222,'weapon_backgrounds':223,'ammo_outlines':287,
'ammo_icons':288,'ammo_alphas':289,'ammo_meters':290,'reticles':291,'numbers':1445,'radar':1440,
'radar_mask':1441,'blip':1446,'health':1690,'multiplayer':1442,'sniper_reticles':501,
'scope_pistol_mask':503,'scope_sniper_mask':1207,'scope_sniper_ticks':1204}


def extract_hud(halo,output):
    from reclaimer.bitmaps.bitmap_decompilation import extract_bitmaps
    directory=output/'hud';directory.mkdir(exist_ok=True)
    result={}
    for name,ix in HUD_TAGS.items():
        meta=halo.get_meta(ix);halo.meta_to_tag_data(meta,'bitm',halo.tag_index.tag_index[ix])
        extract_bitmaps(meta,name,out_dir=directory,bitmap_ext='png',halo_map=halo)
        paths=sorted(p for p in directory.glob(name+'*.png')
                     if p.name==name+'.png' or p.name.startswith(name+'__'))
        result[name]={'files':[str(p.resolve()) for p in paths],
            'sequences':[{'name':s.sequence_name,'first_bitmap':s.first_bitmap_index,'bitmap_count':s.bitmap_count,
            'sprites':[{'bitmap':a.bitmap_index,'bounds':[a.left_side,a.top_side,a.right_side,a.bottom_side],
                        'registration':[a.registration_point_x,a.registration_point_y]} for a in s.sprites.STEPTREE]} for s in meta.sequences.STEPTREE]}
    return result


def write_metadata(halo,output):
    """Keep source tag settings alongside derived runtime assets for auditing."""
    def serial(block):
        if isinstance(block,(int,float,str,bool)):return block
        if hasattr(block,'enum_name'):return block.enum_name
        if hasattr(block,'filepath'):return block.filepath
        if isinstance(block,(bytes,bytearray)):return '<raw>'
        if hasattr(block,'desc') and block.desc.get('NAME_MAP'):
            return {k:serial(getattr(block,k)) for k in block.desc['NAME_MAP']
                    if k not in ('pointer','id','path_pointer','path_length')}
        if isinstance(block,(list,tuple)):return [serial(v) for v in block]
        return None
    entries=halo.tag_index.tag_index
    hud_ids=(220,233,283,284,285,500,660,706,769,863,952,1039,1040,1124,1198,1312,1384,1397,1430,1537)
    hud={'tags':{entries[i].path:serial(halo.get_meta(i)) for i in hud_ids}}
    (output/'hud-layout.json').write_text(json.dumps(hud,indent=2))
    weapons={}
    for i,t in enumerate(entries):
        if t.class_1.enum_name!='weapon':continue
        a=halo.get_meta(i).weap_attrs
        weapons[t.path]={'magazines':[{k:getattr(m,k) for k in
            ('rounds_total_initial','rounds_total_maximum','rounds_loaded_maximum','reload_time')}
            for m in a.magazines.STEPTREE],
            'triggers':[{'rate':list(x.firing.rounds_per_second),'pellets':x.projectile.projectiles_per_shot,
              'error':list(x.projectile.error_angle),'projectile':x.projectile.projectile.filepath}
              for x in a.triggers.STEPTREE]}
    transform=lambda p:[p.x-68,p.z,-(p.y+118)]
    scenario=halo.scnr_meta
    vehicles=[{'path':scenario.vehicles_palette.STEPTREE[v.type].name.filepath,
               'position':transform(v.position),'yaw':v.rotation.y} for v in scenario.vehicles.STEPTREE]
    equipment=[{'path':v.item_collection.filepath,'position':transform(v.position),'yaw':v.facing}
               for v in scenario.netgame_equipments.STEPTREE]
    (output/'gameplay-data.json').write_text(json.dumps({'weapons':weapons,'vehicles':vehicles,'equipment':equipment},indent=2))
    projectiles,damage_effects={},[]
    for i,t in enumerate(entries):
        if t.class_1.enum_name=='projectile':
            meta=halo.get_meta(i);halo.meta_to_tag_data(meta,'proj',t);physics=meta.proj_attrs.physics
            value={'initial_velocity':physics.initial_velocity,'final_velocity':physics.final_velocity,
                   'maximum_range':meta.proj_attrs.detonation.maximum_range}
            ref=physics.impact_damage
            if (ref.id&65535)<len(entries):
                d=halo.get_meta(ref.id).damage;mod=halo.get_meta(ref.id).damage_modifiers
                value.update(damage=d.damage_lower_bound,damage_upper=list(d.damage_upper_bound),
                             shield_modifier=mod.cyborg_energy_shield,health_modifier=mod.cyborg_armor,
                             headshot=bool(d.flags.headshot))
            projectiles[t.path]=value
        elif t.class_1.enum_name=='damage_effect' and any(n in t.path for n in
                ('rocket launcher','needler','frag grenade','plasma grenade','scorpion','warthog','ghost')):
            meta=halo.get_meta(i)
            damage_effects.append({'path':t.path,'radius':list(meta.radius),'damage':meta.damage.damage_lower_bound,
                'upper':list(meta.damage.damage_upper_bound),'shield':meta.damage_modifiers.cyborg_energy_shield,
                'health':meta.damage_modifiers.cyborg_armor})
        elif t.class_1.enum_name=='model_collision_geometry' and 'cyborg' in t.path:
            (output/'cyborg-collision.txt').write_text(str(halo.get_meta(i)))
    (output/'projectile-data.json').write_text(json.dumps(projectiles,indent=2))
    (output/'more-damage.json').write_text(json.dumps(damage_effects,indent=2))


def open_cache(path, output):
    from reclaimer.meta.wrappers.halo1_map import Halo1Map
    data=path.read_bytes(); size=struct.unpack_from('<I',data,8)[0]
    if len(data)<size:data=data[:2048]+zlib.decompress(data[2048:])
    if len(data)!=size:raise ValueError('Cache size mismatch')
    target=output/(path.stem+'-decompressed.map');target.write_bytes(data)
    halo=Halo1Map();halo.load_map(target);return halo


def extract_audio(caches,output):
    from reclaimer.sounds.sound_decompilation import extract_h1_sounds
    sound_dir=output/'sounds';sound_dir.mkdir(exist_ok=True)
    sounds={}
    for name,source in AUDIO_TAGS.items():
        cache,ix=source if isinstance(source,tuple) else ('bloodgulch',source)
        halo=caches[cache];entry=halo.tag_index.tag_index[ix]
        meta=halo.get_meta(ix);halo.meta_to_tag_data(meta,'snd!',entry)
        extract_h1_sounds(meta,name,out_dir=sound_dir,decode_adpcm=True)
        files=sorted((sound_dir/name).rglob('*.wav'))
        if not files:raise ValueError('Audio decode failed '+name)
        with wave.open(str(files[0])) as w:
            rate=w.getframerate();pcm=w.readframes(w.getnframes());channels=w.getnchannels();width=w.getsampwidth()
        if channels==2:pcm=audioop.tomono(pcm,width,.5,.5)
        pcm=audioop.ratecv(pcm,width,1,rate,11025,None)[0]
        if width!=2:pcm=audioop.lin2lin(pcm,width,2)
        loop=name in ('warthog','ghost','scorpion','banshee','flamethrower','ambience')
        # Keep ordinary tails/voice up to four seconds and engine loops to two.
        # Unique vehicle shots have shorter budgets; aliases keep their source.
        seconds=AUDIO_LIMITS.get(name,2 if loop else 4)
        pcm8=audioop.lin2lin(pcm[:round(11025*seconds)*2],2,1)
        out=sound_dir/(name+'.s8');out.write_bytes(pcm8)
        sounds[name]={'file':str(out.resolve()),'rate':11025,'count':len(pcm8),
                      'loop':loop,'tag':entry.path,'source_cache':cache}
        if name in AUDIO_ALIASES:
            alias=AUDIO_ALIASES[name]
            if pcm8!=Path(sounds[alias]['file']).read_bytes():
                raise ValueError(f'Audio source alias differs: {name} / {alias}')
            sounds[name]['alias']=alias
    return sounds


def extract(output, maps):
    from reclaimer.model.model_decompilation import extract_model
    from reclaimer.animation.animation_decompilation import extract_animation
    from reclaimer.bitmaps.bitmap_decompilation import extract_bitmaps
    from PIL import Image
    output.mkdir(exist_ok=True,parents=True)
    result={'models':{},'animations':{},'audio':{},'hud':{},'sources':{}}
    with (output/'extended-extraction.log').open('w') as log,contextlib.redirect_stdout(log):
        halo=open_cache(maps/'bloodgulch.map',output);entries=halo.tag_index.tag_index
        result['sources']['bloodgulch']=hashlib.sha256((maps/'bloodgulch.map').read_bytes()).hexdigest()
        campaign=None
        def bitmap(h,tag_id,name,directory):
            m=h.get_meta(tag_id);h.meta_to_tag_data(m,'bitm',h.tag_index.tag_index[tag_id&65535])
            extract_bitmaps(m,name,out_dir=directory,bitmap_ext='png',halo_map=h)
            return m,sorted(p for p in directory.glob(name+'*.png')
                            if p.name==name+'.png' or p.name.startswith(name+'__'))
        texture_dir=output/'model-textures';texture_dir.mkdir(exist_ok=True)
        for name,path in MODEL_PATHS.items():
            h=halo;ix=next((i for i,t in enumerate(entries) if t.class_1.enum_name=='model' and t.path==path),None)
            if ix is None:
                if campaign is None:
                    campaign=open_cache(maps/'a30.map',output)
                    result['sources']['a30']=hashlib.sha256((maps/'a30.map').read_bytes()).hexdigest()
                h=campaign;ix=next((i for i,t in enumerate(h.tag_index.tag_index) if t.class_1.enum_name=='model' and t.path==path),None)
            if ix is None:raise ValueError('Required model missing: '+path)
            meta=h.get_meta(ix);h.meta_to_tag_data(meta,'mode',h.tag_index.tag_index[ix])
            # Xbox single-node vertices use -3 in the first palette slot and
            # the actual bone in the second slot. Reclaimer's JMS constructor
            # discards that second slot at zero blend weight; normalize the
            # rigid encoding before exporting so the original bone survives.
            for geometry in meta.geometries.STEPTREE:
                for part in geometry.parts.STEPTREE:
                    verts=part.compressed_vertices.STEPTREE.data
                    for off in range(0,len(verts),32):
                        if verts[off+28]>=128 and verts[off+29]<128:
                            verts[off+28],verts[off+29]=verts[off+29],verts[off+28]
            lods=extract_model(meta,write_jms=False)
            target=310 if name=='spartan' else 600 if name in ('warthog','ghost','scorpion','banshee') else 200
            lods=[m for m in lods if m.tris]
            model=min(lods,key=lambda m:abs(len(m.tris)-target))
            textures=[]
            for si,s in enumerate(meta.shaders.STEPTREE):
                shader=h.get_meta(s.shader.id); tex=None
                if hasattr(shader,'soso_attrs'):
                    ref=shader.soso_attrs.maps.diffuse_map
                    if ref.id!=0xffffffff:
                        _,paths=bitmap(h,ref.id,name+'_'+str(si),texture_dir)
                        if paths:
                            tex=str(paths[0].resolve());im=Image.open(tex).convert('RGB');im.thumbnail((64,64));im.save(tex)
                textures.append(tex)
            result['models'][name]={'name':model.name,'path':path,
                'vertices':[[v.pos_x/100,v.pos_y/100,v.pos_z/100] for v in model.verts],
                'uv':[[v.tex_u,v.tex_v] for v in model.verts],
                'weights':[[v.node_0,v.node_1,v.node_1_weight] for v in model.verts],
                'faces':[[t.v0,t.v1,t.v2] for t in model.tris],
                'materials':[t.shader for t in model.tris],'textures':textures,
                'nodes':[{'name':n.name,'parent':n.parent_index,'q':[n.rot_i,n.rot_j,n.rot_k,n.rot_w],
                          'p':[n.pos_x/100,n.pos_y/100,n.pos_z/100]} for n in model.nodes],
                'markers':{marker.name:[{'node':inst.node_index,'p':list(inst.translation),'q':list(inst.rotation)}
                                        for inst in marker.marker_instances.STEPTREE] for marker in meta.markers.STEPTREE}}
            if name=='banshee':
                from vehicle_pose import bake_pose
                animation_id=next(i for i,t in enumerate(h.tag_index.tag_index)
                                  if t.class_1.enum_name=='model_animations' and t.path==path)
                animations=h.get_meta(animation_id)
                h.meta_to_tag_data(animations,'antr',h.tag_index.tag_index[animation_id])
                ai=next(i for i,a in enumerate(animations.animations.STEPTREE) if a.name=='stand closing')
                closing=extract_animation(ai,animations,write_jma=False)
                closing.apply_root_node_info_to_states(undo=True)
                # Reclaimer adds a synthetic initial-pose sentinel at the end.
                terminal=closing.frames[animations.animations.STEPTREE[ai].frame_count-1]
                states=[{'p':[n.pos_x/100,n.pos_y/100,n.pos_z/100],
                         'q':[n.rot_i,n.rot_j,n.rot_k,n.rot_w]} for n in terminal]
                bake_pose(result['models'][name],states,'stand closing:terminal')
        anim=halo.get_meta(160);halo.meta_to_tag_data(anim,'antr',entries[160])
        for name,tag_name in ANIM_NAMES.items():
            ix=next(i for i,a in enumerate(anim.animations.STEPTREE) if a.name==tag_name)
            clip=extract_animation(ix,anim,write_jma=False)
            if clip is None:raise ValueError('Could not decode '+tag_name)
            # Remove locomotion root displacement: the game simulation owns world movement.
            clip.apply_root_node_info_to_states(undo=True)
            source_frame_count=anim.animations.STEPTREE[ix].frame_count
            frames=clip.frames
            if name=='death':
                # Reclaimer appends frame 0 to close every base JMA clip.
                # A clamped death must end on the real grounded terminal pose,
                # not that synthetic standing pose added for looping exports.
                if clip.anim_type=='overlay' or len(frames)!=source_frame_count+1:
                    raise ValueError('Unexpected death animation frame layout')
                frames=frames[:source_frame_count]
            result['animations'][name]={'tag_name':tag_name,'type':clip.anim_type,
                'duration':source_frame_count/30 if name=='death' else len(frames)/30,
                'source_frame_count':source_frame_count,
                'rot_flags':clip.rot_flags_int,'trans_flags':clip.trans_flags_int,'scale_flags':clip.scale_flags_int,
                'frames':[[{'p':[n.pos_x/100,n.pos_y/100,n.pos_z/100],
                            'q':[n.rot_i,n.rot_j,n.rot_k,n.rot_w],'s':n.scale} for n in f] for f in frames]}
        if campaign is None:campaign=open_cache(maps/'a30.map',output)
        result['audio']=extract_audio({'bloodgulch':halo,'a30':campaign},output)
        result['hud']=extract_hud(halo,output)
        write_metadata(halo,output)
    (output/'extended-raw.json').write_text(json.dumps(result))
    print(json.dumps({'models':{k:len(v['faces']) for k,v in result['models'].items()},
        'animations':{k:len(v['frames']) for k,v in result['animations'].items()},
        'audio_bytes':sum(v['count'] for v in result['audio'].values() if 'alias' not in v),'hud_atlases':len(result['hud'])},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--maps',type=Path,default=Path('build/assets/halo-retail/maps'))
    p.add_argument('--output',type=Path,default=Path('build/n64/assets'))
    p.add_argument('--hud-only',action='store_true',help='Refresh HUD bitmaps and metadata without extracting models/audio')
    a=p.parse_args()
    if a.hud_only:
        source=a.output/'extended-raw.json';result=json.loads(source.read_text())
        with (a.output/'hud-extraction.log').open('w') as log,contextlib.redirect_stdout(log):
            halo=open_cache(a.maps/'bloodgulch.map',a.output)
            result['hud']=extract_hud(halo,a.output);write_metadata(halo,a.output)
        source.write_text(json.dumps(result));print(json.dumps({'hud_atlases':len(result['hud'])}))
    else:extract(a.output,a.maps)
