"""Extract a bounded CE Covenant squad from owned caches; outputs stay private."""
import argparse, contextlib, hashlib, json
from pathlib import Path
import extract_extended as ext

NAMES = ('grunt', 'elite')

def extract(output, maps):
    output.mkdir(parents=True, exist_ok=True)
    (output/'extended-raw.json').write_text(json.dumps({'models':{},'sources':{}}))
    previous=ext.MODEL_PATHS
    try:
        ext.MODEL_PATHS={name:rf'characters\{name}\{name}' for name in NAMES}
        ext.extract(output,maps,models_only=True,include_source_lods=True)
    finally:ext.MODEL_PATHS=previous
    from reclaimer.animation.animation_decompilation import extract_animation
    result=json.loads((output/'extended-raw.json').read_text())
    with (output/'actors.log').open('w') as log,contextlib.redirect_stdout(log):
        h=ext.open_cache(maps/'a30.map',output);entries=h.tag_index.tag_index
        def index(kind,path):return next(i for i,e in enumerate(entries) if e.class_1.enum_name==kind and e.path==path)
        actors={}
        for name in NAMES:
            path=rf'characters\{name}\{name}'
            variant=path+(' minor plasma pistol' if name=='grunt' else r' minor\elite minor plasma rifle')
            data=ext.tag_values(h.get_meta(index('actor_variant',variant)))
            actor=ext.tag_values(h.get_meta(index('actor',data['actor_definition'])))
            biped=ext.tag_values(h.get_meta(index('biped',data['unit'])))
            ai=index('model_animations',path);anim=h.get_meta(ai);h.meta_to_tag_data(anim,'antr',entries[ai])
            names=[a.name for a in anim.animations.STEPTREE]
            wanted={'idle':'stand pistol idle','run':'stand pistol move-front','fire':'stand pistol pp fire-1' if name=='grunt' else 'stand pistol pr fire-1',
                    'death':'h-kill front gut','flee':'flee pistol move-front','melee':'stand pistol melee'}
            clips={}
            for key,prefix in wanted.items():
                matches=[i for i,n in enumerate(names) if n==prefix or n.startswith(prefix+'%')]
                if not matches:
                    matches=[i for i,n in enumerate(names) if (key=='fire' and n.startswith('stand pistol') and 'fire' in n) or (key=='melee' and n.startswith('stand pistol') and 'melee' in n)]
                if not matches and key=='flee':matches=[names.index('stand pistol move-front')]
                if not matches and key=='melee' and name=='grunt':matches=[i for i,n in enumerate(names) if n.startswith('stand pistol idle')][:1]
                if not matches:raise ValueError((name,key,names))
                i=matches[0];clip=extract_animation(i,anim,write_jma=False)
                clip.apply_root_node_info_to_states(undo=True)
                count=anim.animations.STEPTREE[i].frame_count
                frames=clip.frames[:count] if key=='death' else clip.frames
                clips[key]={'speed':sum((r.dx*r.dx+r.dy*r.dy)**.5 for r in clip.root_node_info)/max(1,len(clip.root_node_info))*.3,'keyframe':anim.animations.STEPTREE[i].key_frame_index/30,'name':names[i],'type':clip.anim_type,'duration':count/30,
                    'rot_flags':clip.rot_flags_int,'trans_flags':clip.trans_flags_int,'scale_flags':clip.scale_flags_int,
                    'frames':[[{'p':[n.pos_x/100,n.pos_y/100,n.pos_z/100],'q':[n.rot_i,n.rot_j,n.rot_k,n.rot_w],'s':n.scale} for n in f] for f in frames]}
            melee=biped['unit_attrs']['melee_damage']
            melee=ext.tag_values(h.get_meta(index('damage_effect',melee))) if melee else None
            actors[name]={'melee_damage':melee,'actor_path':data['actor_definition'],'variant_path':variant,'actor':actor,'variant':data,'biped':biped,'clips':clips}
        result['actors']=actors
    (output/'squad-source.json').write_text(json.dumps(result))
    print(json.dumps({n:{'lods':{k:len(v['faces']) for k,v in result['models'][n]['source_geometry_lods'].items()},'clips':{k:v['name'] for k,v in actors[n]['clips'].items()}} for n in NAMES},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--maps',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();extract(a.output,a.maps)
