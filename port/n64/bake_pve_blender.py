"""Bake original artist LODs and skeleton clips in Blender; no mesh reduction."""
import json,math,gzip
from pathlib import Path

def bake(source,output):
    from mathutils import Matrix,Quaternion,Vector
    data=json.loads(Path(source).read_text());result={}
    basis=Matrix(((1,0,0,0),(0,0,1,0),(0,-1,0,0),(0,0,0,1)))
    for name,model in data['models'].items():
        nodes=model['nodes'];actor=data['spirit'] if name=='spirit' else data['actors'][name]
        keys=tuple(data['actors']['grunt']['clips'])
        if name=='spirit':actor={**actor,'clips':{key:actor['clips']['exit' if key=='exit' else 'idle'] for key in keys}}
        def global_pose(states):
            matrices=[]
            for i,n in enumerate(states):
                x,y,z,w=n['q'];m=Quaternion((w,-x,-y,-z)).to_matrix().to_4x4();m.translation=Vector(n['p'])
                parent=nodes[i]['parent'];matrices.append(matrices[parent]@m if parent>=0 else m)
            return matrices
        inverse=[m.inverted() for m in global_pose(nodes)];idle=actor['clips']['idle']['frames'][0]
        marker_key=next((k for k in model['markers'] if k.startswith('right hand')),None)
        marker=model['markers'][marker_key][0] if marker_key else {'node':0,'q':[0,0,0,1],'p':[0,0,0]}
        x,y,z,w=marker['q'];marker_matrix=Quaternion((w,-x,-y,-z)).to_matrix().to_4x4();marker_matrix.translation=Vector(marker['p'])
        hit_vertices=[];hit_faces=[];hit_materials=[]
        if name!='spirit':
            for node in actor.get('collision',{}).get('nodes',[]):
                ni=next(i for i,n in enumerate(nodes) if n['name']==node['name'])
                if not node['bsps']:continue
                # Choose the intact normal permutation. Jackal head has an
                # armored alternative at index zero; its base head is index one.
                bi=1 if name=='jackal' and node['name']=='bip01 head' and len(node['bsps'])>1 else 0
                bsp=node['bsps'][bi];base=len(hit_vertices)
                hit_vertices.extend((ni,v[:3]) for v in bsp['vertices'])
                for si,s in enumerate(bsp['surfaces']):
                    edge=s[1];start=edge;poly=[]
                    for _ in range(len(bsp['edges'])+1):
                        e=bsp['edges'][edge]
                        if e[4]==si:poly.append(base+e[0]);edge=e[2]
                        else:assert e[5]==si;poly.append(base+e[1]);edge=e[3]
                        if edge==start:break
                    else:raise ValueError('Collision polygon did not close')
                    for k in range(1,len(poly)-1):hit_faces.append([poly[0],poly[k],poly[k+1]]);hit_materials.append(s[4])
        models=[]
        lods=('base00 low','base00 superlow') if 'base00 low' in model['source_geometry_lods'] else (model['source_lod'],)*2
        for lod_index,lod in enumerate(lods):
            geometry=model['source_geometry_lods'][lod]
            assert [n['name'] for n in geometry['nodes']]==[n['name'] for n in nodes]
            corners=[i for face in geometry['faces'] for i in face]
            clips={};grips={};hit_clips={}
            for key,clip in actor['clips'].items():
                frames=[];hands=[];hit_frames=[];limit={'idle':8,'run':10,'fire':10,'death':12,'flee':10,'melee':12,'throw':12,'evade_left':10,'evade_right':10,'ride':4,'exit':16,'crouch':4}[key]
                count=min(limit,len(clip['frames']))
                for f in range(count):
                    states=clip['frames'][round(f*(len(clip['frames'])-1)/max(1,count-1))]
                    if clip['type']=='overlay':
                        combined=[]
                        for i,(a,b) in enumerate(zip(idle,states)):
                            ax,ay,az,aw=a['q'];bx,by,bz,bw=b['q']
                            q=Quaternion((bw,bx,by,bz))@Quaternion((aw,ax,ay,az)) if clip['rot_flags']&(1<<i) else Quaternion((aw,ax,ay,az))
                            combined.append({'p':[a['p'][j]+(b['p'][j] if clip['trans_flags']&(1<<i) else 0) for j in range(3)],'q':[q.x,q.y,q.z,q.w]})
                        states=combined
                    pose=global_pose(states);skin=[a@b for a,b in zip(pose,inverse)]
                    if lod_index==0:hit_frames.append([list(pose[ni]@Vector(p)) for ni,p in hit_vertices])
                    points=[]
                    for vertex in corners:
                        p=Vector(geometry['vertices'][vertex]);a,b,w=geometry['weights'][vertex]
                        value=skin[a]@p if b<0 or w==0 else (skin[a]@p)*(1-w)+(skin[b]@p)*w
                        assert all(math.isfinite(v) for v in value);points.append(list(value))
                    frames.append(points)
                    hand=basis@pose[marker['node']]@marker_matrix@basis.inverted();q=hand.to_quaternion().normalized()
                    hands.append({'pos':list(hand.translation),'quat':[q.x,q.y,q.z,q.w]})
                clips[key]={'frames':frames,'duration':clip['duration'],'tag_name':clip['name']}
                grips[key]={'poses':hands,'duration':clip['duration']}
                if lod_index==0:hit_clips[key]={'frames':hit_frames,'duration':clip['duration']}
            triangles=[{'p':clips['idle']['frames'][0][i*3:i*3+3],
                'uv':[geometry['uv'][v] for v in face],'material':geometry['materials'][i]} for i,face in enumerate(geometry['faces'])]
            models.append({**{k:v for k,v in model.items() if k.startswith('material') or k in ('textures','team_masks','team_mask_channels')},
                'source_lod':lod,'triangles':triangles,'clips':clips,'grips':grips,
                'shield_corners':[j for i,m in enumerate(geometry['materials']) if name=='jackal' and model['material_metadata'][m]['path'].endswith('jackal shield') for j in range(i*3,i*3+3)],
                'hit':{'faces':hit_faces,'materials':hit_materials,'clips':hit_clips} if lod_index==0 and hit_faces else None})
        result[name]=models
    payload=json.dumps(result).encode()
    Path(output).write_bytes(gzip.compress(payload,mtime=0) if str(output).endswith(".gz") else payload)
    print(json.dumps({n:[{'lod':m['source_lod'],'triangles':len(m['triangles']),'frames':sum(len(c['frames']) for c in m['clips'].values())} for m in models] for n,models in result.items()}))
