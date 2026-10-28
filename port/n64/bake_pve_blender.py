"""Bake original artist LODs and skeleton clips in Blender; no mesh reduction."""
import json,math
from pathlib import Path

def bake(source,output):
    from mathutils import Matrix,Quaternion,Vector
    data=json.loads(Path(source).read_text());result={}
    basis=Matrix(((1,0,0,0),(0,0,1,0),(0,-1,0,0),(0,0,0,1)))
    for name in ('grunt','elite'):
        model=data['models'][name];nodes=model['nodes'];actor=data['actors'][name]
        def global_pose(states):
            matrices=[]
            for i,n in enumerate(states):
                x,y,z,w=n['q'];m=Quaternion((w,-x,-y,-z)).to_matrix().to_4x4();m.translation=Vector(n['p'])
                parent=nodes[i]['parent'];matrices.append(matrices[parent]@m if parent>=0 else m)
            return matrices
        inverse=[m.inverted() for m in global_pose(nodes)];idle=actor['clips']['idle']['frames'][0]
        marker=model['markers']['right hand' if name=='grunt' else 'right hand elite'][0]
        x,y,z,w=marker['q'];marker_matrix=Quaternion((w,-x,-y,-z)).to_matrix().to_4x4();marker_matrix.translation=Vector(marker['p'])
        models=[]
        for lod in ('base00 low','base00 superlow'):
            geometry=model['source_geometry_lods'][lod]
            assert [n['name'] for n in geometry['nodes']]==[n['name'] for n in nodes]
            corners=[i for face in geometry['faces'] for i in face]
            clips={};grips={}
            for key,clip in actor['clips'].items():
                frames=[];hands=[];limit={'idle':8,'run':10,'fire':6,'death':12,'flee':10,'melee':10}[key]
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
            triangles=[{'p':clips['idle']['frames'][0][i*3:i*3+3],
                'uv':[geometry['uv'][v] for v in face],'material':geometry['materials'][i]} for i,face in enumerate(geometry['faces'])]
            models.append({**{k:v for k,v in model.items() if k.startswith('material') or k in ('textures','team_masks','team_mask_channels')},
                'source_lod':lod,'triangles':triangles,'clips':clips,'grips':grips})
        result[name]=models
    Path(output).write_text(json.dumps(result))
    print(json.dumps({n:[{'lod':m['source_lod'],'triangles':len(m['triangles']),'frames':sum(len(c['frames']) for c in m['clips'].values())} for m in models] for n,models in result.items()}))
