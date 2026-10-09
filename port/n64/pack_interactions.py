#!/usr/bin/env python3
"""Extract Xbox ready/seat clips and skin the approved meshes into a ROM pose bank.

No model reduction or new geometry. Existing indexed vertices, colors and
occlusion closures are preserved. Only two requested frames are resident.
"""
import contextlib, hashlib, json, math, struct
from pathlib import Path
import numpy as np
from pack_assets import position, floats
from pack_firstperson import prepare_model, split_details
from pack_fp_ammo import globals_for, overlay_states, prepare_ar
from extract_extended import MODEL_PATHS
ROOT=Path(__file__).resolve().parents[2]
A=ROOT/'build/n64/assets'; G=ROOT/'build/n64/generated'; F=ROOT/'build/n64/frontend-files'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def matrices(states,nodes):
    result=[]
    for r,p in globals_for(states,nodes):
        m=np.eye(4);m[:3,:3]=r;m[:3,3]=p;result.append(m)
    return np.array(result)

def run():
    from reclaimer.meta.wrappers.halo1_map import Halo1Map
    from reclaimer.animation.animation_decompilation import extract_animation
    def cache(name):
        h=Halo1Map();h.load_map(A/(name+'-decompressed.map'));return h
    with (A/'interaction-extraction.log').open('w') as log,contextlib.redirect_stdout(log):
        h=cache('bloodgulch');campaign=cache('a30')
    def meta(halo,kind,path):
        i=next(i for i,t in enumerate(halo.tag_index.tag_index) if t.class_1.enum_name==kind and t.path==path)
        m=halo.get_meta(i)
        if kind=='model_animations':halo.meta_to_tag_data(m,'antr',halo.tag_index.tag_index[i])
        return m
    globals_id=next(i for i,t in enumerate(h.tag_index.tag_index) if t.class_1.enum_name=='globals')
    assert h.get_meta(globals_id).player_controls.STEPTREE[0].minimum_weapon_swap_ticks==7
    graph=meta(h,'model_animations',r'characters\cyborg\cyborg')
    def clip(g,index):
        a=extract_animation(index,g,write_jma=False);count=g.animations.STEPTREE[index].frame_count
        # Preserve root motion and remove Reclaimer's synthetic looping frame.
        return {'name':a.name,'duration':count/30,'frames':[[{'p':[n.pos_x/100,n.pos_y/100,n.pos_z/100],
                'q':[n.rot_i,n.rot_j,n.rot_k,n.rot_w]} for n in f] for f in a.frames[:count]]}
    raw=json.loads((A/'extended-raw.json').read_text());world=json.loads((A/'extended-reduced.json').read_text())
    fpraw=json.loads((A/'firstperson-raw.json').read_text());fp=json.loads((A/'firstperson-reduced.json').read_text())
    mapping=json.loads((G/'world-mesh-sources.json').read_text())
    ammometa=json.loads((A/'firstperson-ammo.json').read_text())
    nodes=raw['models']['spartan']['nodes'];inv=np.linalg.inv(matrices(nodes,nodes))
    bank=bytearray();descriptions=[];scratch=0
    def emit(frames,duration,scale):
        nonlocal scratch
        coords=np.array([[position(p,(0,0,0)) for p in f] for f in frames]);quant=np.rint(coords*scale).astype(np.int64)
        assert quant.min()>=-32768 and quant.max()<=32767
        vertices=len(frames[0]);stride=(vertices*6+15)&~15;offset=len(bank);assert offset%16==0
        for frame in quant:
            data=frame.astype('>i2').tobytes();bank.extend(data);bank.extend(bytes(stride-len(data)))
        scratch=max(scratch,stride*2)
        bounds=[(quant.min(axis=(0,1))/scale).tolist(),(quant.max(axis=(0,1))/scale).tolist()]
        d={'offset':offset,'stride':stride,'vertices':vertices,'frames':len(frames),'duration':duration,'bounds':bounds}
        descriptions.append(d);return d
    def init(d):return '{0}' if d is None else '{'+f'{d["offset"]},{d["stride"]},{d["vertices"]},{d["frames"]},{d["duration"]:.7f}f,'+'{'+','.join(floats(v) for v in d['bounds'])+'}}'
    def skin_body(c,model,sources):
        corners=[(np.array([*p,1.]),ws) for t in model['triangles'] for p,ws in zip(t['p'],t['weights'])]
        frames=[]
        for frame in c['frames']:
            skin=matrices(frame,nodes)@inv
            frames.append([sum((skin[b]@corners[i][0])*w for b,w in corners[i][1])[:3].tolist() for i in sources])
        return emit(frames,c['duration'],128)
    def grip_for(c):
        marker=raw['models']['spartan']['markers']['right hand'][0]
        marker_matrix=matrices([marker],[{'parent':-1}])[0]
        basis=np.array([[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1]])
        frames=[]
        for f in c['frames']:
            mat=basis@matrices(f,nodes)[marker['node']]@marker_matrix@basis.T
            points=[mat[:3,3].tolist()]+[mat[:3,col].tolist() for col in range(3)]
            frames.append([[p[0],-p[2],p[1]] for p in points])
        return emit(frames,c['duration'],4096)
    ready_index=next(i for i,c in enumerate(graph.animations.STEPTREE) if c.name=='stand rifle ready')
    body_ready=clip(graph,ready_index)
    body_ready_poses=[skin_body(body_ready,world['models']['spartan'],mapping['spartan']),
                      skin_body(body_ready,world['spartan_lod'],mapping['spartan_lod'])]
    ready_bounds=np.array([d['bounds'] for d in body_ready_poses])
    for d in body_ready_poses:
        d['bounds']=[ready_bounds[:,0,:].min(axis=0).tolist(),ready_bounds[:,1,:].max(axis=0).tolist()]
    ready_grip=grip_for(body_ready)
    locomotion=[];locomotion_grips=[];locomotion_report=[]
    for name in ('crouch rifle idle','crouch rifle move-front','stand rifle land-soft','stand rifle land-hard','crouch rifle land-soft','crouch rifle land-hard'):
        c=clip(graph,next(i for i,a in enumerate(graph.animations.STEPTREE) if a.name==name))
        lods=[skin_body(c,world['models']['spartan'],mapping['spartan']),skin_body(c,world['spartan_lod'],mapping['spartan_lod'])]
        bounds=np.array([d['bounds'] for d in lods]);union=[bounds[:,0,:].min(axis=0).tolist(),bounds[:,1,:].max(axis=0).tolist()]
        for d in lods:d['bounds']=union
        locomotion.append(lods);locomotion_grips.append(grip_for(c));locomotion_report.append({'name':name,'frames':len(c['frames']),'seconds':c['duration']})
    groups=[];seats=[];clip_report=[];grips=[]
    paths=[('warthog',r'vehicles\warthog\warthog'),('ghost',r'vehicles\ghost\ghost_mp'),
           ('scorpion',r'vehicles\scorpion\scorpion_mp'),('banshee',r'vehicles\banshee\banshee')]
    idle_root=np.array(nodes[0]['p'])
    group_lookup={}
    for name,path in paths:
        v=meta(campaign if name=='banshee' else h,'vehicle',path);model=raw['models'][name]
        transforms=matrices(model['nodes'],model['nodes'])
        def marker(key):
            m=model['markers'][key][0];p=(transforms[m['node']]@np.array([*m['p'],1]))[:3]
            r=matrices([{'p':m['p'],'q':m['q']}],[{'parent':-1}])[0]
            mat=transforms[m['node']]@r
            return position(p,(0,0,0)),math.atan2(mat[1,0],mat[0,0])
        row=[];defs=list(v.unit_attrs.seats.STEPTREE)
        if name=='warthog':defs=[defs[i] for i in (0,2,1)]
        for s in defs:
            unit=next(u for u in graph.units.STEPTREE if u.label==s.label)
            ids=[unit.weapons.STEPTREE[0].animations.STEPTREE[0].animation,unit.animations.STEPTREE[7].animation,unit.animations.STEPTREE[8].animation]
            assert min(ids)>=0
            key=tuple(ids);clips=[clip(graph,i) for i in ids]
            if key not in group_lookup:
                group_lookup[key]=len(groups);packed=[]
                for ci,c in enumerate(clips):
                    # Idle retains four source samples; one-shot clips keep every Xbox frame.
                    sampled={**c,'frames':[c['frames'][round(i*(len(c['frames'])-1)/3)] for i in range(4)]} if ci==0 and len(c['frames'])>4 else c
                    packed.append([skin_body(sampled,world['models']['spartan'],mapping['spartan']),
                                   skin_body(sampled,world['spartan_lod'],mapping['spartan_lod'])])
                for lods in packed:
                    bounds=np.array([d['bounds'] for d in lods])
                    union=[bounds[:,0,:].min(axis=0).tolist(),bounds[:,1,:].max(axis=0).tolist()]
                    for d in lods:d['bounds']=union
                idle_clip=clips[0]
                grips.append(grip_for({**idle_clip,'frames':[idle_clip['frames'][round(i*(len(idle_clip['frames'])-1)/3)] for i in range(4)]}))
                groups.append(packed);clip_report.append([{'name':c['name'],'frames':len(c['frames']),'seconds':c['duration']} for c in clips])
            anchor,yaw=marker(s.marker_name)
            entry=marker(s.marker_name+' enter')[0] if s.marker_name+' enter' in model['markers'] else anchor
            exit_local=position(np.array(clips[2]['frames'][-1][0]['p'])-idle_root,(0,0,0))
            velocity=position((np.array(clips[2]['frames'][-1][0]['p'])-np.array(clips[2]['frames'][-2][0]['p']))*30,(0,0,0))
            enter_start=position(np.array(clips[1]['frames'][0][0]['p'])-idle_root,(0,0,0))
            camera=marker(s.camera_marker_name)[0] if s.camera_marker_name in model['markers'] else [anchor[0],anchor[1]+.62,anchor[2]]
            row.append({'label':s.label,'anchor':anchor,'entry':entry,'camera':camera,'yaw':yaw,'exit_offset':exit_local,'exit_velocity':velocity,
                        'enter_start':enter_start,'enter_time':clips[1]['duration'],'exit_time':clips[2]['duration'],
                        'flags':s.flags.data,'pose':group_lookup[key]})
        seats.append(row)
    hatches=[]
    for name,halo,path in [('scorpion',h,r'vehicles\scorpion\scorpion'),('banshee',campaign,r'vehicles\banshee\banshee')]:
        model=raw['models'][name];g=meta(halo,'model_animations',path);inverse=np.linalg.inv(matrices(model['nodes'],model['nodes'])[1])
        basis=np.array([[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1]])
        pair=[]
        for label in ('stand opening','stand closing'):
            ix=next(i for i,a in enumerate(g.animations.STEPTREE) if a.name==label);c=clip(g,ix);frames=[]
            for states in c['frames']:
                transform=basis@matrices(states,model['nodes'])[1]@inverse@basis.T
                points=[transform[:3,3].tolist()]+[transform[:3,c].tolist() for c in range(3)]
                frames.append([[p[0],-p[2],p[1]] for p in points])
            pair.append(emit(frames,c['duration'],4096))
        hatches.append(pair)
    # Explicit slots match asset_interaction.h; source model iteration is unrelated.
    service_keys=[('ar','reload-full'),('plasma_pistol','overheating'),('plasma_pistol','o-h-s-enter'),
        ('plasma_pistol','overheated'),('plasma_pistol','o-h-exit'),('rocket','reload-full'),('rocket','reload-empty'),
        ('plasma_rifle','overheating'),('plasma_rifle','overheated'),('plasma_rifle','o-h-exit'),
        ('pistol','reload-full'),('pistol','reload-empty'),('sniper','reload-full'),('sniper','reload-empty'),('shotgun','fire-1')]
    service=[None]*len(service_keys);service_details=service.copy();service_vents=service.copy();service_report=service.copy()
    reload_ar=shotgun_muzzle=None
    ready=[];readytimes=[];fp_report={};needle_defs=[];needle_indices=[];ar_def=scope_def=None;plasma_defs=[]
    for name,w in fp['weapons'].items():
        if name=='flamethrower':continue
        original=fpraw['weapons'][name];g=meta(h,'model_animations',MODEL_PATHS[name].rsplit('\\',1)[0]+r'\fp\fp')
        ix=next(i for i,a in enumerate(g.animations.STEPTREE) if a.name=='first-person ready');c=clip(g,ix)
        fp_report[name]={'name':c['name'],'frames':len(c['frames']),'seconds':c['duration']};readytimes.append(c['duration'])
        skeleton=original['nodes'];lookup={n['name']:i for i,n in enumerate(skeleton)}
        bindhands=matrices(fpraw['hands']['nodes'],fpraw['hands']['nodes']);bindgun=matrices(original['gun']['nodes'],original['gun']['nodes'])
        idle=matrices(original['clips']['idle']['frames'][0],skeleton)
        node_maps=[[lookup[n['name']] for n in fpraw['hands']['nodes']],[lookup[n['name']] for n in original['gun']['nodes']]]
        inverse=[np.linalg.inv(bindhands),np.linalg.inv(bindgun)]
        corners=[]
        for ti,t in enumerate(w['triangles']):
            part=int(ti>=w['hand_triangle_count'])
            for p,weights in zip(t['p'],t['weights']):
                # Recover each approved corner from the exact blended idle skin.
                # This also preserves earlier upper-arm extensions/scope separation.
                transform=sum(idle[node_maps[part][b]]@inverse[part][b]*weight for b,weight in weights)
                bind=np.linalg.solve(transform,np.array([*p,1.]));corners.append((part,weights,bind))
        def skin_fp(states):
            pose=matrices(states,skeleton);skins=[pose[node_maps[i]]@inverse[i] for i in range(2)]
            return [sum((skins[part][b]@p)*weight for b,weight in weights)[:3].tolist() for part,weights,p in corners]
        frames=[skin_fp(s) for s in c['frames']]
        mesh_source=w
        if name in ('sniper','plasma_pistol','plasma_rifle'):
            mesh_source,keep,sources,_=split_details(w,name)
            detail=emit([[f[i] for i in sources] for f in frames],c['duration'],4096)
            if name=='sniper':scope_def=detail
            else:plasma_defs.append(detail)
            frames_for_mesh=[[p for i in keep for p in f[i*3:i*3+3]] for f in frames]
        else:frames_for_mesh=frames
        mesh,_,_=prepare_model(mesh_source,name)
        ready.append(emit([[f[i] for i in mesh['sources']] for f in frames_for_mesh],c['duration'],256))
        if name=='ar':
            copy={**w,'clips':{'idle':{'frames':frames},'fire':w['clips']['fire'],'reload':w['clips']['reload'],'melee':w['clips']['melee']}}
            ar=prepare_ar({'weapons':{'ar':copy}},ammometa)
            # prepare_ar already converted to Y-up/4096; invert for emit.
            ar_def=emit([[[p[0]/4096,-p[2]/4096,p[1]/4096] for p in f] for f in ar['poses'][0]],c['duration'],4096)
        # Preserve every Xbox 30 Hz frame for contact-sensitive reloads and
        # the plasma pistol's separate enter / vent loop / exit states.
        service_names=['first-person '+label for weapon,label in service_keys if weapon==name]
        for clip_name in service_names:
            index=service_keys.index((name,clip_name.removeprefix('first-person ')))
            sc=clip(g,next(i for i,a in enumerate(g.animations.STEPTREE) if a.name==clip_name))
            full=[skin_fp(states) for states in sc['frames']]
            # Terminal hold (or loop seam) supplies exactly one sample per
            # source tick to the common (frames-1)/duration interpolator.
            full.append(full[0] if clip_name=='first-person overheated' else full[-1])
            if name in ('plasma_pistol','plasma_rifle','sniper'):
                service_details[index]=emit([[f[i] for i in sources] for f in full],sc['duration'],4096)
                body=[[p for i in keep for p in f[i*3:i*3+3]] for f in full]
            else:body=full
            if name in ('plasma_pistol','plasma_rifle','shotgun'):
                model=meta(h,'model',MODEL_PATHS[name].rsplit('\\',1)[0]+r'\fp\fp')
                markers={m.name:m.marker_instances.STEPTREE[0] for m in model.markers.STEPTREE}
                vents=[]
                for states in sc['frames']:
                    pose=matrices(states,skeleton);points=[]
                    for key in (('primary trigger',)*2 if name=='shotgun' else ('vent',)*3 if name=='plasma_rifle' else ('vent_rear','vent_mid','vent_front')):
                        marker=markers[key];bone=node_maps[1][marker.node_index]
                        points.append((pose[bone]@np.array([*marker.translation,1]))[:3].tolist())
                    vents.append(points)
                vents.append(vents[0] if clip_name=='first-person overheated' else vents[-1])
                if name=='shotgun':shotgun_muzzle=emit(vents,sc['duration'],4096)
                else:service_vents[index]=emit(vents,sc['duration'],4096)
            service[index]=emit([[f[i] for i in mesh['sources']] for f in body],sc['duration'],256)
            service_report[index]={'weapon':name,'name':clip_name,'source_frames':len(sc['frames']),'seconds':sc['duration']}
            if name=='ar':
                copy={**w,'clips':{**w['clips'],'idle':{'frames':full}}}
                ar=prepare_ar({'weapons':{'ar':copy}},ammometa)
                reload_ar=emit([[[p[0]/4096,-p[2]/4096,p[1]/4096] for p in f] for f in ar['poses'][0]],sc['duration'],4096)
        if name=='needler':
            for vi,ci in enumerate(mesh['sources']):
                part,weights,p=corners[ci]
                if part and any('needle' in original['gun']['nodes'][b]['name'] for b,_ in weights):needle_indices.append(vi)
            for ammo,overlay in enumerate(ammometa['needler']['frames']):
                fs=[];folded={i for i,o in enumerate(overlay) if sum(x*x for x in o['q'][:3])>.2}
                for states in c['frames']:
                    poses=skin_fp(overlay_states(states,overlay,ammometa['needler']['flags']));result=[]
                    allmat=matrices(overlay_states(states,overlay,ammometa['needler']['flags']),skeleton)
                    for vi in needle_indices:
                        ci=mesh['sources'][vi];bone=node_maps[1][corners[ci][1][0][0]]
                        result.append(allmat[bone][:3,3].tolist() if bone in folded else poses[ci])
                    fs.append(result)
                needle_defs.append(emit(fs,c['duration'],256))
    assert len(ready)==8 and len(seats[2])==5
    ready.append(ready[0]);readytimes.append(readytimes[0]) # Optional PC extra aliases Xbox AR.
    F.mkdir(exist_ok=True);(F/'interactions.bin').write_bytes(bank)
    lines=['/* Generated owned Xbox animation metadata. */','#include "asset_interaction.h"']
    lines.append('const bg_rom_pose bg_locomotion_poses[6][2]={'+','.join('{'+','.join(init(d) for d in lods)+'}' for lods in locomotion)+'};')
    lines.append('const bg_rom_pose bg_locomotion_grips[6]={'+','.join(init(d) for d in locomotion_grips)+'};')
    lines.append('const bg_rom_pose bg_hatch_poses[2][2]={'+','.join('{'+','.join(init(d) for d in pair)+'}' for pair in hatches)+'};')
    lines.append('const bg_rom_pose bg_seat_poses[][3][2]={'+','.join('{'+','.join('{'+','.join(init(d) for d in lods)+'}' for lods in group)+'}' for group in groups)+'};')
    for symbol,ds in [('bg_service_vents',service_vents),('bg_service_poses',service),('bg_service_details',service_details),('bg_ready_plasma',plasma_defs),('bg_ready_poses',ready),('bg_ready_needles',needle_defs),('bg_seat_grips',grips),('bg_body_ready_poses',body_ready_poses)]:lines.append('const bg_rom_pose '+symbol+'['+str(len(ds))+']={'+','.join(init(d) for d in ds)+'};')
    for symbol,d in [('bg_shotgun_fire_muzzle',shotgun_muzzle),('bg_reload_ar_digits',reload_ar),('bg_ready_ar_digits',ar_def),('bg_ready_scope',scope_def),('bg_body_ready_grip',ready_grip)]:lines.append('const bg_rom_pose '+symbol+'='+init(d)+';')
    lines.append('const uint16_t bg_ready_needle_vertices[]={'+','.join(map(str,needle_indices))+'};')
    lines.append(f'const unsigned bg_interaction_scratch_bytes={scratch};')
    (G/'interaction_assets.c').write_text('\n'.join(lines)+'\n')
    defs=['/* Source tag seat markers/timings; generated by pack_interactions.py. */','#include "interaction.h"',
          'const uint8_t bg_seat_counts[4]={3,1,5,1};','const float bg_ready_times[9]='+floats(readytimes)+';',
          'const bg_seat_definition bg_seat_definitions[4][BG_VEHICLE_SEATS]={']
    for row in seats:
        defs.append('{')
        for s in row:
            defs.append('{'+','.join([floats(s['anchor']),floats(s['entry']),floats(s['camera']),f'{s["yaw"]:.7f}f',floats(s['exit_offset']),floats(s['exit_velocity']),floats(s['enter_start']),f'{s["enter_time"]:.7f}f',f'{s["exit_time"]:.7f}f',str(s['flags']),str(s['pose'])])+'},')
        defs.append('},')
    defs.append('};');(G/'interaction_defs.c').write_text('\n'.join(defs)+'\n')
    inputs={str(p.relative_to(ROOT)):sha(p) for p in [A/'extended-raw.json',A/'extended-reduced.json',A/'firstperson-raw.json',A/'firstperson-reduced.json',A/'firstperson-ammo.json',A/'bloodgulch-decompressed.map',A/'a30-decompressed.map',G/'models_data.c',G/'firstperson_data.c',G/'world-mesh-sources.json',Path(__file__)]}
    files={str(p.relative_to(ROOT)):sha(p) for p in [G/'interaction_assets.c',G/'interaction_defs.c',F/'interactions.bin']}
    report={'inputs':inputs,'files':files,'rom_bytes':len(bank),'scratch_bytes':scratch,'seats':seats,'locomotion':locomotion_report,'body_clips':clip_report,'ready':fp_report,'service':service_report,'hold_ticks':7}
    (G/'interaction-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'rom_bytes':len(bank),'scratch_bytes':scratch,'body_groups':len(groups),'ready':fp_report},indent=2))
if __name__=='__main__':run()
