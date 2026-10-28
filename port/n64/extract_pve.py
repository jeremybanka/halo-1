"""Extract a bounded CE Covenant squad from owned caches; outputs stay private."""
import argparse, contextlib, hashlib, json, struct
from pathlib import Path
import extract_extended as ext

NAMES = ('grunt', 'elite')

def extract(output, maps, full=False):
    names=('grunt','elite','jackal','hunter') if full else NAMES
    campaign='b30' if full else 'a30'
    output.mkdir(parents=True, exist_ok=True)
    (output/'extended-raw.json').write_text(json.dumps({'models':{},'sources':{}}))
    previous=ext.MODEL_PATHS
    try:
        ext.MODEL_PATHS={name:rf'characters\{name}\{name}' for name in names}
        if full:ext.MODEL_PATHS['spirit']=r'vehicles\c_dropship\c_dropship'
        ext.extract(output,maps,models_only=True,include_source_lods=True,campaign_name=campaign)
    finally:ext.MODEL_PATHS=previous
    from reclaimer.animation.animation_decompilation import extract_animation
    result=json.loads((output/'extended-raw.json').read_text())
    with (output/'actors.log').open('w') as log,contextlib.redirect_stdout(log):
        h=ext.open_cache(maps/(campaign+'.map'),output);entries=h.tag_index.tag_index
        def index(kind,path):return next(i for i,e in enumerate(entries) if e.class_1.enum_name==kind and e.path==path)
        actors={}
        for name in names:
            path=rf'characters\{name}\{name}'
            variant=path+(' minor plasma pistol' if name in ('grunt','jackal') else r' minor\elite minor plasma rifle' if name=='elite' else '')
            data=ext.tag_values(h.get_meta(index('actor_variant',variant)))
            actor=ext.tag_values(h.get_meta(index('actor',data['actor_definition'])))
            biped=ext.tag_values(h.get_meta(index('biped',data['unit'])))
            ai=index('model_animations',path);anim=h.get_meta(ai);h.meta_to_tag_data(anim,'antr',entries[ai])
            names=[a.name for a in anim.animations.STEPTREE]
            wanted={'idle':'stand pistol idle','run':'stand pistol move-front','fire':'stand pistol pp fire-1' if name=='grunt' else 'stand pistol pr fire-1',
                    'death':'h-kill front gut','flee':'flee pistol move-front','melee':'stand pistol melee'}
            if full:
                wanted.update(throw='stand pistol throw-grenade',evade_left='stand pistol evade-left',evade_right='stand pistol evade-right',ride='CD-passengerL01 pistol idle',exit='CD-passengerL01 exit',crouch='crouch pistol idle')
            if name=='hunter':wanted.update(idle='crouch unarmed idle',run='stand unarmed move-front',fire='crouch unarmed fr fire-1',flee='stand unarmed move-front',melee='stand unarmed melee',throw='crouch unarmed idle',evade_left='stand unarmed dive-left',evade_right='stand unarmed dive-right',ride='CD-passengerL01 idle',crouch='crouch unarmed idle')
            clips={}
            for key,prefix in wanted.items():
                matches=[i for i,n in enumerate(names) if n==prefix or n.startswith(prefix+'%')]
                if not matches:
                    matches=[i for i,n in enumerate(names) if (key=='fire' and n.startswith('stand pistol') and 'fire' in n) or (key=='melee' and n.startswith('stand pistol') and 'melee' in n)]
                if not matches and key=='flee':matches=[i for i,n in enumerate(names) if n.startswith('stand pistol move-front')][:1]
                if not matches and key in ('melee','throw') and name in ('grunt','jackal'):matches=[i for i,n in enumerate(names) if n.startswith('stand pistol idle')][:1]
                if not matches:raise ValueError((name,key,names))
                i=matches[0];clip=extract_animation(i,anim,write_jma=False)
                clip.apply_root_node_info_to_states(undo=True)
                count=anim.animations.STEPTREE[i].frame_count
                frames=clip.frames[:count] if key in ('death','exit','throw','melee','evade_left','evade_right') else clip.frames
                clips[key]={'speed':sum((r.dx*r.dx+r.dy*r.dy)**.5 for r in clip.root_node_info)/max(1,len(clip.root_node_info))*.3,'keyframe':anim.animations.STEPTREE[i].key_frame_index/30,'name':names[i],'type':clip.anim_type,'duration':count/30,
                    'rot_flags':clip.rot_flags_int,'trans_flags':clip.trans_flags_int,'scale_flags':clip.scale_flags_int,
                    'frames':[[{'p':[n.pos_x/100,n.pos_y/100,n.pos_z/100],'q':[n.rot_i,n.rot_j,n.rot_k,n.rot_w],'s':n.scale} for n in f] for f in frames]}
            melee=biped['unit_attrs']['melee_damage']
            melee=ext.tag_values(h.get_meta(index('damage_effect',melee))) if melee else None
            collision=h.get_meta(index('model_collision_geometry',biped['obje_attrs']['collision_model']))
            collision_data=ext.tag_values(collision)
            fmts={'bsp3d_nodes':'3i','planes':'4f','leaves':'Hhi','bsp2d_references':'2i','bsp2d_nodes':'3f2i','surfaces':'2iBBh','edges':'6i','vertices':'3fi'}
            for ni,node in enumerate(collision.nodes.STEPTREE):
                for bi,bsp in enumerate(node.bsps.STEPTREE):
                    collision_data['nodes'][ni]['bsps'][bi]={k:list(struct.iter_unpack('<'+fmt,bytes(getattr(bsp,k).STEPTREE))) for k,fmt in fmts.items()}
            actors[name]={'melee_damage':melee,'actor_path':data['actor_definition'],'variant_path':variant,'actor':actor,'variant':data,'biped':biped,'clips':clips,'collision':collision_data}
        if full:
            path=r'vehicles\c_dropship\c_dropship';ai=index('model_animations',path);anim=h.get_meta(ai);h.meta_to_tag_data(anim,'antr',entries[ai]);clips={}
            for key,prefix in [('idle','idle'),('exit','stand opening')]:
                i=next(i for i,a in enumerate(anim.animations.STEPTREE) if a.name==prefix);clip=extract_animation(i,anim,write_jma=False);clip.apply_root_node_info_to_states(undo=True);count=anim.animations.STEPTREE[i].frame_count
                clips[key]={'speed':0,'keyframe':0,'name':prefix,'type':clip.anim_type,'duration':max(count,1)/30,'rot_flags':clip.rot_flags_int,'trans_flags':clip.trans_flags_int,'scale_flags':clip.scale_flags_int,'frames':[[{'p':[n.pos_x/100,n.pos_y/100,n.pos_z/100],'q':[n.rot_i,n.rot_j,n.rot_k,n.rot_w],'s':n.scale} for n in f] for f in clip.frames[:count]]}
            result['spirit']={'vehicle':ext.tag_values(h.get_meta(index('vehicle',path))),'clips':clips}
            for kind in ('globals','projectile','weapon'):
                selected=[(i,e) for i,e in enumerate(entries) if e.class_1.enum_name==kind and (kind=='globals' or 'fuel rod' in e.path)]
                result[kind]={e.path:ext.tag_values(h.get_meta(i)) for i,e in selected}
        result['campaign']=campaign
        result['actors']=actors
    (output/'squad-source.json').write_text(json.dumps(result))
    print(json.dumps({n:{'lods':{k:len(v['faces']) for k,v in result['models'][n]['source_geometry_lods'].items()},'clips':{k:v['name'] for k,v in actors[n]['clips'].items()}} for n in actors},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--maps',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--full',action='store_true');a=p.parse_args();extract(a.output,a.maps,a.full)
