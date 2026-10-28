#!/usr/bin/env python3
"""Pack the private objective bank using the normal indexed mesh/pose codecs."""
import argparse,hashlib,json,math,shutil
from pathlib import Path
from pack_assets import position
from pack_mesh import indexed_mesh,emit_batches
from pack_firstperson import prepare_model
from pack_animation import emit_clip,clip_initializer
from model_colors import load_images,bake_triangle

FLAG_FP_SCALE=4096

def pack(source,out,frontend):
    from PIL import Image
    out.mkdir(parents=True,exist_ok=True);frontend.mkdir(parents=True,exist_ok=True)
    world=json.loads((source/'extended-raw.json').read_text())['models']
    fp=json.loads((source/'firstperson-reduced.json').read_text())['weapons']
    details=json.loads((source/'objective-details.json').read_text())
    cloth=json.loads((source/'cloth-config.json').read_text())
    # Extraction records absolute source paths. Rebind owned-bank inputs to
    # this checkout so a cloned private bank can be repacked unchanged.
    referenced=set()
    def local(value):
        if isinstance(value,dict):return {k:local(v) for k,v in value.items()}
        if isinstance(value,list):return [local(v) for v in value]
        if isinstance(value,str) and '/assets/objectives/' in value:
            path=source.resolve()/value.split('/assets/objectives/',1)[1]
            if path.suffix in ('.png','.s8'):
                assert path.is_file(),path
                referenced.add(path)
            return str(path)
        return value
    world,fp,details=local(world),local(fp),local(details)
    lines=['/* Generated from owned source; private bank only. */','#include "asset_objectives.h"']
    def xyz(v):return '{'+','.join(map(str,v))+'}'
    def rgba(c):return (c[0]<<24)|(c[1]<<16)|(c[2]<<8)|255
    tex=[]
    for path in details['textures']:
        atlas=Image.new('RGBA',(64,32),'white');atlas.paste(Image.open(path).convert('RGBA').resize((64,31),Image.Resampling.LANCZOS),(0,0))
        tex.append([((r>>3)<<11)|((g>>3)<<6)|((b>>3)<<1)|int(a>=96) for r,g,b,a in atlas.getdata()])
    lines.append('const uint16_t bg_flag_textures[2][2048] __attribute__((aligned(16)))={'+','.join(xyz(t) for t in tex)+'};')
    models={};animations={};report={};flag_corners={}
    for name,model in world.items():
        triangles=[{'p':[model['vertices'][i] for i in f],'uv':[model['uv'][i] for i in f],'material':m} for f,m in zip(model['faces'],model['materials'])]
        if name=='flag':
            banner=[t for t in triangles if t['material']==model['banner_material']]
            assert len(banner)==2
            flag_corners['world']=[position(p,(0,0,0)) for p in (banner[0]['p'][0],banner[0]['p'][1],banner[1]['p'][2])]
            triangles=[t for t in triangles if t['material']!=model['banner_material']]
        points=[];colors=[];uvs=[];images=load_images(model['textures'])
        for t in triangles:
            banner=t['material']==model.get('banner_material',-1)
            points.extend([[round(x*1024) for x in position(p,(0,0,0))] for p in t['p']])
            colors.extend([[255,255,255]]*3 if banner else bake_triangle(t,images,model))
            uvs.extend([[round(u*63*32),round(v*30*32)] for u,v in t['uv']] if banner else [[16,1008]]*3)
        mesh=indexed_mesh(points,colors,[0]*len(points),reorder_static=True,
                          material_keys=[(t['material'],tuple(uvs[i*3+j])) for i,t in enumerate(triangles) for j in range(3)])
        mesh['uvs']=[uvs[i] for i in mesh['sources']]
        models['world_'+name]=(mesh,len(triangles),max(math.sqrt(sum(x*x for x in p)) for p in model['vertices']))
    for name,w in fp.items():
        segments=None
        if name=='flag':
            banner=[i for i,t in enumerate(w['triangles'])
                    if w['material_names'][t['material']]=='objective flag banner']
            assert banner==list(range(len(w['triangles'])-2,len(w['triangles'])))
            flag_corners['fp']={name:[[[round(v*FLAG_FP_SCALE) for v in position(f[i],(0,0,0))]
                for i in (-6,-5,-1)] for f in c['frames']] for name,c in w['clips'].items()}
            w={**w,'triangles':w['triangles'][:-2],
               'clips':{n:{**c,'frames':[f[:-6] for f in c['frames']]} for n,c in w['clips'].items()}}
        mesh,clips,preview=prepare_model(w,name,FLAG_FP_SCALE if name=='flag' else 256,
                                       16 if name=='flag' else 8,segments)
        models['fp_'+name]=(mesh,len(w['triangles']),1)
        animations[name]=clips
    packed={}
    for name,(mesh,tris,radius) in models.items():
        verts=mesh['vertices'];lines.append(f'static T3DVertPacked {name}[] __attribute__((aligned(16)))={{')
        for i in range(0,len(verts),2):
            a,b=verts[i:i+2];lines.append('{'+f'{xyz(a[0])},0,{xyz(b[0])},0,0x{rgba(a[1]):08x},0x{rgba(b[1]):08x},{xyz(mesh["uvs"][i])},{xyz(mesh["uvs"][i+1])}'+'},')
        lines.append('};');emit_batches(lines,name,mesh)
        if name.startswith('fp_'):
            lines.append(f'static const uint8_t {name}_mask[]='+xyz([v[2] for v in verts])+';')
            for cname,clip in animations[name[3:]].items():
                packed[name,cname]=emit_clip(lines,name+'_'+cname,clip,
                    FLAG_FP_SCALE if name=='fp_flag' else 256,16 if name=='fp_flag' else 8)
        report[name]={'vertices':len(verts),'triangles':tris,'batches':len(mesh['batches'])}
    def initializer(name):
        mesh,tris,radius=models[name]
        return '{'+f'{name},{len(mesh["vertices"])},{radius:.6f}f,{name}_batches,{name}_indices,{len(mesh["batches"])},{tris}'+'}'
    for kind,symbol in [('world','bg_objective_models'),('fp','bg_objective_fp_models')]:
        lines.append(f'const bg_model_asset {symbol}[2]={{'+','.join(initializer(kind+'_'+n) for n in ('flag','ball'))+'};')
    lines.append('const uint8_t *const bg_objective_fp_team_masks[2]={fp_flag_mask,fp_ball_mask};')
    lines.append('const bg_anim_asset bg_objective_fp_animations[2][BG_FP_CLIPS]={')
    for name in ('flag','ball'):
        lines.append('{')
        for cname,clip in animations[name].items():
            lines.append(clip_initializer('fp_'+name+'_'+cname,clip,packed['fp_'+name,cname],
                                          'NULL' if name=='flag' else None))
        lines.append('},')
    lines.append('};')
    lines.append('const uint16_t *const bg_flag_fp_positions[BG_FP_CLIPS]={'+
                 ','.join('fp_flag_'+name for name in animations['flag'])+'};')
    lines.append('const float bg_flag_world_corners[3][3]='+xyz([xyz([float(v).hex()+'f' for v in p]) for p in flag_corners['world']])+';')
    for name,frames in flag_corners['fp'].items():
        lines.append('static const int16_t flag_corners_'+name+'[][3][3]='+xyz([xyz([xyz(p) for p in f]) for f in frames])+';')
    lines.append('const int16_t (*const bg_flag_fp_corners[BG_FP_CLIPS])[3][3]='+xyz(['flag_corners_'+n for n in animations['flag']])+';')
    physics=cloth['physics'];lines.append('const bg_cloth_physics bg_flag_cloth_physics='+xyz([float(physics[k]).hex()+'f' for k in ('width','height','gravity','drag')])+';')
    lines.append('const float bg_flag_wind_noise[3][64][3]='+xyz([xyz([xyz([float(v).hex()+'f' for v in p]) for p in axis]) for axis in cloth['noise']])+';')
    weather=[]
    assert sorted(w["id"] for w in cloth["maps"].values())==list(range(13))
    for name,w in cloth['maps'].items():
        symbol='flag_weather_'+name
        if w['nodes']:
            lines.append('static const bg_cloth_weather_node '+symbol+'[]='+xyz([xyz([xyz([float(v).hex()+'f' for v in n['plane']]),n['back'],n['front']]) for n in w['nodes']])+';')
        values=[xyz([float(v).hex()+'f' for v in w['speed']]),float(w['yaw']).hex()+'f',float(w['pitch']).hex()+'f',xyz([float(v).hex()+'f' for v in w['variation']])]
        values += [float(w[k]).hex()+'f' for k in ('magnitude','local_weight','local_rate')]
        values += [symbol if w['nodes'] else 'NULL',w['root'],len(w['nodes'])]
        weather.append("["+str(w["id"])+"]="+xyz(values))
    lines.append('const bg_cloth_weather bg_flag_weather[13]='+xyz(weather)+';')
    (out/'objectives_data.c').write_text('\n'.join(lines)+'\n')
    for name,a in details['audio'].items():shutil.copyfile(a['file'],frontend/('mode_'+name+'.s8'))
    report['animation_bytes']=sum(p['bytes'] for p in packed.values())
    report['flag_position_scale']=FLAG_FP_SCALE
    report['flag_coordinate_bits']=16
    report['cloth']={'vertices':30,'triangles':40,'source_vertices':16*13,'source_triangles':15*12*2,'grid':[6,5],
                     'physics':physics,'weather_nodes':sum(len(w['nodes']) for w in cloth['maps'].values())}
    root=Path(__file__).resolve().parents[2]
    inputs=[Path(__file__).resolve(),source/'extended-raw.json',source/'firstperson-raw.json',source/'firstperson-reduced.json',source/'objective-details.json',source/'cloth-config.json']
    inputs += [root/'port/n64'/n for n in ('pack_firstperson.py','pack_animation.py','pack_mesh.py','model_colors.py','reduce_objectives.py','reduce_firstperson.py')]
    inputs += sorted(referenced)
    outputs=[out/'objectives_data.c']+[frontend/('mode_'+name+'.s8') for name in details['audio']]
    report['schema']=1
    report['inputs']={str(p.resolve().relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    report['files']={str(p.resolve().relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in outputs}
    (out/'objectives-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--frontend',type=Path,required=True)
    a=p.parse_args();pack(a.source,a.output,a.frontend)
