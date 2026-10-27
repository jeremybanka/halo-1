#!/usr/bin/env python3
"""Extract original flag/skull models and FP clips into the private asset bank."""
import argparse,json,contextlib,shutil
from pathlib import Path
import extract_extended
import extract_firstperson

PATHS={name:rf'weapons\{name}\{name}' for name in ('flag','ball')}
def extract(output,maps):
    output.mkdir(parents=True,exist_ok=True)
    (output/'extended-raw.json').write_text(json.dumps({'models':{},'sources':{}}))
    previous=extract_extended.MODEL_PATHS
    try:
        extract_extended.MODEL_PATHS=PATHS
        extract_extended.extract(output,maps,models_only=True,include_source_lods=True)
    finally:extract_extended.MODEL_PATHS=previous
    extract_firstperson.extract(output,model_paths=PATHS)
    from reclaimer.meta.wrappers.halo1_map import Halo1Map
    from reclaimer.bitmaps.bitmap_decompilation import extract_bitmaps
    from vehicle_pose import globals_for
    with (output/'objective-details.log').open('w') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
        h=Halo1Map();h.load_map(output/'bloodgulch-decompressed.map');entries=h.tag_index.tag_index
        def index(kind,path):return next(i for i,t in enumerate(entries) if t.class_1.enum_name==kind and t.path==path)
        cloth=extract_extended.tag_values(h.get_meta(index('flag',PATHS['flag'])))
        images=[]
        for team in ('flag_red','flags_blue'):
            i=index('bitmap',rf'weapons\flag\bitmaps\{team}');m=h.get_meta(i);h.meta_to_tag_data(m,'bitm',entries[i])
            extract_bitmaps(m,team,out_dir=output,bitmap_ext='png',halo_map=h)
            images.append(str(next(output.glob(team+'*.png')).resolve()))
        world=json.loads((output/'extended-raw.json').read_text())
        fp=json.loads((output/'firstperson-raw.json').read_text())
        def banner(model,markers,firstperson=False):
            top=markers['flag top'][0];bottom=markers['flag bottom'][0]
            assert top['node']==bottom['node']
            node=top['node'];r,p=globals_for(model['nodes'])[node]
            width=(cloth['width']-1)*cloth['cell_width']
            local=[top['p'],bottom['p'],[bottom['p'][0]-width,*bottom['p'][1:]],[top['p'][0]-width,*top['p'][1:]]]
            points=[[p[a]+sum(r[a][j]*v[j] for j in range(3)) for a in range(3)] for v in local]
            start=len(model['vertices']);material=len(model['textures'])
            model['vertices']+=points;model['uv']+=[[0,0],[0,1],[1,1],[1,0]];model['weights']+=[[node,-1,0]]*4
            model['faces']+=[[start,start+1,start+2],[start,start+2,start+3]];model['materials']+=[material]*2
            model['textures']+=[images[0]];model['textures_fullres']+=[images[0]]
            for key,value in [('material_names','objective flag banner'),('material_types','shader_model'),('material_colors',None),('material_overrides',None),('texture_sources',r'weapons\flag\bitmaps\flag_red'),('material_multipurpose',None),('material_change_source',0),('material_metadata',{'path':'objective flag banner'}),('team_masks',None),('team_mask_channels',None)]:
                if key in model:model[key].append(value)
            model['banner_material']=material
        for name,m in world['models'].items():
            authored=min(m['source_geometry_lods'].values(),key=lambda a:len(a['faces']))
            m.update(authored)
        banner(world['models']['flag'],world['models']['flag']['markers'])
        meta=h.get_meta(index('model',r'weapons\flag\fp\fp'))
        markers={m.name:[{'node':v.node_index,'p':list(v.translation)} for v in m.marker_instances.STEPTREE] for m in meta.markers.STEPTREE}
        banner(fp['weapons']['flag']['gun'],markers,True)
        (output/'extended-raw.json').write_text(json.dumps(world))
        (output/'firstperson-raw.json').write_text(json.dumps(fp))
        names=('capture_the_flag','oddball','race','king_of_the_hill','team_king_of_the_hill','team_oddball','team_race','team_slayer','play_ball','blue_team_has_the_flag','blue_team_flag_returned','blue_team_score','red_team_has_the_flag','red_team_flag_returned','red_team_score')
        previous=extract_extended.AUDIO_TAGS
        try:
            extract_extended.AUDIO_TAGS={name:index('sound','sound\\dialog\\multiplayer1\\'+name) for name in names}
            audio=extract_extended.extract_audio({'bloodgulch':h},output)
        finally:extract_extended.AUDIO_TAGS=previous
        (output/'objective-details.json').write_text(json.dumps({'cloth':cloth,'textures':images,'audio':audio},indent=2)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--maps',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();extract(a.output,a.maps)
