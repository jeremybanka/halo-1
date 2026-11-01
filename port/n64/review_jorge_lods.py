"""Matched source/near/far views with the production AR; run in Blender."""
from pathlib import Path
import sys,json,math
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
import jorge_lods as lods
import jorge_animation_proof as animation
import jorge_surgical_cleanup as studio
import jorge_half_budget as half
import numpy as np
from mathutils import Matrix,Vector,Quaternion

AXIS=Matrix(((0,0,-1),(-1,0,0),(0,1,0)))

def packed():
    """Read the actual packed RGB and animation grid, including CE's two LODs."""
    folder=lods.OUT/'review';folder.mkdir(exist_ok=True)
    ce=json.loads((lods.ROOT/'halo64-assets/assets/extended-reduced.json').read_text())
    preview=json.loads(half.AR_SOURCE.read_text())
    report=json.loads((lods.ROOT/'halo64-assets/generated/extended-report.json').read_text())
    ref=np.load(lods.SOURCE/'gameplay-poses.npz');refmeta=json.loads((lods.SOURCE/'gameplay-poses.json').read_text())
    headfaces=[i for i,c in enumerate(refmeta['components'][::3]) if c.startswith('body-03:') or c=='body-06:000']
    headpoints=ref['frames_0'][0,np.unique(ref['triangles'][headfaces])]@np.array(AXIS).T*3.048
    headcenter=Vector((headpoints.min(0)+headpoints.max(0))/2)
    for name in ('personal','near','far','spartan','spartan_lod'):
        standard=name.startswith('spartan')
        if standard:
            raw=preview[name];points=np.array(raw['positions']);faces=np.arange(len(points)).reshape(-1,3)
            colors=np.array(raw['colors']);mask=np.rint(np.array(raw['team_mask'])*255).astype(int)[:,None]
            colors=(colors*(65025-mask*(255-np.array((57,183,69))))+32512)//65025
            order=[i*3+c for i in report['triangle_order'][name] for c in range(3)]
            clips=ce['animations' if name=='spartan' else 'animations_lod']
        else:
            source=lods.SOURCE if name=='personal' else lods.OUT/name
            data=np.load(source/'packed-preview.npz');points=data['positions'];faces=data['triangles'];colors=data['colors']
            meta=json.loads((source/'gameplay-poses.json').read_text())
        scene=bpy.data.scenes.new('Packed '+name);bpy.context.window.scene=scene;studio.studio(scene)
        scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=0
        scene.camera.data.ortho_scale=2.95;scene.cycles.samples=8
        mesh=bpy.data.meshes.new(name);mesh.from_pydata(points@np.array(AXIS).T*3.048,[],faces)
        ca=mesh.color_attributes.new(name='Packed RGB',type='FLOAT_COLOR',domain='CORNER')
        for loop,c in zip(mesh.loops,ca.data):c.color_srgb=(*colors[loop.vertex_index]/255,1)
        mat=bpy.data.materials.new(name+' unlit');mat.use_nodes=True;ns=mat.node_tree.nodes;ns.clear()
        vc=ns.new('ShaderNodeVertexColor');vc.layer_name=ca.name;output=ns.new('ShaderNodeOutputMaterial');mat.node_tree.links.new(vc.outputs['Color'],output.inputs['Surface'])
        mesh.materials.append(mat);ob=bpy.data.objects.new(name,mesh);scene.collection.objects.link(ob)
        weapon=bpy.data.objects.new('Production AR',bpy.data.meshes.new('AR'));scene.collection.objects.link(weapon);half.port_ar(weapon)
        for clip,fraction,view in [('idle',0,v) for v in ('front','back','left','right','three_quarter')]+[('run',.25,'three_quarter'),('reload',.4,'three_quarter')]:
            if standard:
                frames=clips[clip]['frames'];f=fraction*(len(frames)-1);a=int(f);b=min(a+1,len(frames)-1);t=f-a
                p=(np.round(np.array(frames[a])*128)*(1-t)+np.round(np.array(frames[b])*128)*t)/128
                p=p[order][:,[0,2,1]]*np.array((1,1,-1))
                poses=ce['weapon_attachment'][clip]['poses'];hands=[]
                for i in (a,b):hands.append([*poses[i]['pos'],*poses[i]['quat']])
            else:
                ci=next(i for i,c in enumerate(meta['clips']) if c['name']==clip);frames=data['frames_'+str(ci)]
                f=fraction*(len(frames)-1);a=int(f);b=min(a+1,len(frames)-1);t=f-a
                p=(frames[a]*(1-t)+frames[b]*t)/512;hands=data['grips_'+str(ci)][[a,b]]
            mesh.vertices.foreach_set('co',(p@np.array(AXIS).T*3.048).ravel());mesh.update()
            q0=Quaternion((hands[0][6],*hands[0][3:6]));q1=Quaternion((hands[1][6],*hands[1][3:6]))
            if q0.dot(q1)<0:q1.negate()
            q=Quaternion([x*(1-t)+y*t for x,y in zip(q0,q1)]);q.normalize()
            matrix=(AXIS@q.to_matrix()@Matrix(((1,0,0),(0,0,1),(0,-1,0)))).to_4x4()
            matrix.translation=AXIS@(Vector(hands[0][:3]).lerp(Vector(hands[1][:3]),t))*3.048
            weapon.matrix_world=matrix
            for size in ((96,48,400) if clip=='idle' else (96,48)):
                scene.render.resolution_x=scene.render.resolution_y=size;studio.camera(scene,view)
                scene.render.filepath=str(folder/f'packed-{name}-{clip}-{fraction}-{view}-{size}.png');bpy.ops.render.render(write_still=True)
            if clip=='idle' and view in ('front','left','three_quarter'):
                # Matched head crops retain the same viewing direction.
                direction=(scene.camera.location-Vector((0,0,1.15))).normalized()
                scene.camera.location=headcenter+direction*3
                scene.camera.rotation_euler=(-direction).to_track_quat('-Z','Y').to_euler();scene.camera.data.ortho_scale=.52
                scene.render.resolution_x=scene.render.resolution_y=240
                weapon.hide_render=True
                scene.render.filepath=str(folder/f'head-{name}-{view}.png');bpy.ops.render.render(write_still=True)
                weapon.hide_render=False;scene.camera.data.ortho_scale=2.95
        print('PACKED REVIEW',name,flush=True)

def run():
    folder=lods.OUT/'review';folder.mkdir(exist_ok=True)
    for name,path in [('personal',lods.SOURCE/'jorge-playable-personal.blend'),
                      ('near',lods.OUT/'near/jorge-near.blend'),('far',lods.OUT/'far/jorge-far.blend')]:
        bpy.ops.wm.open_mainfile(filepath=str(path))
        scene=next(s for s in bpy.data.scenes if any(o.get('texture_variant')=='ce_spartan' for o in s.objects))
        bpy.context.window.scene=scene;rig=next(o for o in scene.objects if o.type=='ARMATURE')
        mat=bpy.data.materials.new('Exact body vertex color preview');mat.use_nodes=True
        nodes=mat.node_tree.nodes;nodes.clear();vc=nodes.new('ShaderNodeVertexColor');vc.layer_name=lods.COLOR
        output=nodes.new('ShaderNodeOutputMaterial');mat.node_tree.links.new(vc.outputs['Color'],output.inputs['Surface'])
        for o in scene.objects:
            if o.type=='MESH':
                if o.get('texture_variant')=='ce_spartan':o.data.materials.clear();o.data.materials.append(mat)
                else:o.hide_render=True
        weapon=bpy.data.objects.new('Production AR',bpy.data.meshes.new('AR placeholder'));scene.collection.objects.link(weapon);half.port_ar(weapon)
        scene.render.resolution_x=320;scene.render.resolution_y=400;scene.cycles.samples=4
        scene.camera.data.ortho_scale=2.95
        for clip,fraction,view in [('idle',0,v) for v in ('front','back','left','right','three_quarter')]+[('run',.25,'three_quarter'),('reload',.4,'three_quarter')]:
            action=next(a for a in bpy.data.actions if a.get('source_clip')==clip)
            animation.select_clip(scene,rig,clip,action['duration_seconds']*fraction)
            weapon.matrix_world=rig.matrix_world@rig.pose.bones['b_r_grip'].matrix
            studio.camera(scene,view)
            scene.render.filepath=str(folder/f'{name}-{clip}-{fraction}-{view}.png');bpy.ops.render.render(write_still=True)
        print('REVIEWED',name,flush=True)

def coverage_reviews():
    folder=lods.OUT/'review';meta=json.loads((lods.SOURCE/'gameplay-poses.json').read_text())
    source=np.load(lods.SOURCE/'packed-preview.npz')
    for lod in ('near','far'):
        report=json.loads((lods.OUT/lod/'coverage-full.json').read_text())
        row=max(report['views'],key=lambda r:(r['largest_new_hole'],r['new_holes']))
        ci=next(i for i,c in enumerate(meta['clips']) if c['name']==row['clip'])
        samples=source['frames_'+str(ci)];f=row['fraction']*(len(samples)-1);a=int(f);b=min(a+1,len(samples)-1);t=f-a
        reference=(samples[a]*(1-t)+samples[b]*t)/512@np.array(AXIS).T*3.048
        center=Vector((reference.min(0)+reference.max(0))/2)
        vi=row['view'];direction=Vector((math.sin(vi*math.pi/4),-math.cos(vi*math.pi/4),.12) if vi<8 else (.7,-1,.65) if vi==8 else (-.7,1,.65)).normalized()
        for name,path in [('source',lods.SOURCE),('reduced',lods.OUT/lod)]:
            data=np.load(path/'packed-preview.npz');samples=data['frames_'+str(ci)];p=(samples[a]*(1-t)+samples[b]*t)/512@np.array(AXIS).T*3.048
            scene=bpy.data.scenes.new('Coverage '+lod+' '+name);bpy.context.window.scene=scene;studio.studio(scene)
            scene.view_settings.exposure=0;scene.render.resolution_x=scene.render.resolution_y=400;scene.cycles.samples=8
            mesh=bpy.data.meshes.new('Coverage');mesh.from_pydata(p,[],data['triangles'])
            ca=mesh.color_attributes.new(name='RGB',type='FLOAT_COLOR',domain='CORNER')
            for loop,c in zip(mesh.loops,ca.data):c.color_srgb=(*data['colors'][loop.vertex_index]/255,1)
            mat=bpy.data.materials.new('Unlit');mat.use_nodes=True;ns=mat.node_tree.nodes;ns.clear()
            vc=ns.new('ShaderNodeVertexColor');vc.layer_name=ca.name;out=ns.new('ShaderNodeOutputMaterial');mat.node_tree.links.new(vc.outputs['Color'],out.inputs['Surface'])
            mesh.materials.append(mat);ob=bpy.data.objects.new('Body',mesh);scene.collection.objects.link(ob)
            scene.camera.location=center+direction*5;scene.camera.rotation_euler=(-direction).to_track_quat('-Z','Y').to_euler();scene.camera.data.ortho_scale=2.95
            scene.render.filepath=str(folder/f'coverage-{lod}-{name}.png');bpy.ops.render.render(write_still=True)
        (folder/f'coverage-{lod}-case.json').write_text(json.dumps(row,indent=2)+'\n')

if __name__=='__main__':
    coverage_reviews() if '--coverage' in sys.argv else packed() if '--packed' in sys.argv else run()
