"""Render the exact packed game mesh, colors and poses beside the CE Spartan."""
import bpy,json,sys
import numpy as np
from mathutils import Vector,Matrix,Quaternion
import jorge_playable_reduce as task
import jorge_animation_proof as anim
import jorge_half_budget as half
import jorge_surgical_cleanup as cleanup
import jorge_playable_reference as standard
OUT=task.OUT;AXIS=standard.AXIS;LOCAL=standard.LOCAL

def setup():
    d=np.load(OUT/'packed-preview.npz');meta=json.loads((OUT/'runtime-report.json').read_text());s=bpy.data.scenes.new('Jorge - exact N64 preview');bpy.context.window.scene=s;cleanup.studio(s);s.camera.data.ortho_scale=2.95
    me=bpy.data.meshes.new('Jorge packed vertices');me.from_pydata(d['positions'].tolist(),[],d['triangles'].tolist());color=me.color_attributes.new(name='Runtime RGB',type='FLOAT_COLOR',domain='CORNER')
    for l,c in zip(me.loops,color.data):c.color_srgb=(*[x/255 for x in d['colors'][l.vertex_index]],1)
    mat=bpy.data.materials.new('Jorge original packed unlit color');mat.use_nodes=True;n=mat.node_tree.nodes;n.clear();vc=n.new('ShaderNodeVertexColor');vc.layer_name=color.name;o=n.new('ShaderNodeOutputMaterial');mat.node_tree.links.new(vc.outputs['Color'],o.inputs['Surface']);me.materials.append(mat)
    ob=bpy.data.objects.new('Jorge - exact N64 body',me);s.collection.objects.link(ob)
    weapon=bpy.data.objects.new('AR reference',bpy.data.meshes.new('placeholder'));s.collection.objects.link(weapon);half.port_ar(weapon)
    return s,ob,weapon,d,meta

def pose(state,i,fraction):
    s,ob,weapon,d,meta=state;bpy.context.window.scene=s;frames=d['frames_'+str(i)];f=fraction*(len(frames)-1);a=int(f);b=min(a+1,len(frames)-1);t=f-a;p=(frames[a]*(1-t)+frames[b]*t)/meta['position_scale']
    coords=p@np.array(AXIS).T*anim.SCALE;ob.data.vertices.foreach_set('co',coords.ravel());ob.data.update()
    hands=d['grips_'+str(i)];h=hands[a]*(1-t)+hands[b]*t;q0=Quaternion((hands[a][6],*hands[a][3:6]));q1=Quaternion((hands[b][6],*hands[b][3:6]));q=q0.slerp(q1,t)
    m=(AXIS@q.to_matrix()@LOCAL).to_4x4();m.translation=AXIS@Vector(h[:3])*anim.SCALE;weapon.matrix_world=m
    weapon.hide_render=(i>=18 and 'rifle' not in meta['clips'][i]['name']) or i in (4,8,10)

def run():
    folder=OUT/'runtime-renders';folder.mkdir(exist_ok=True);state=setup();s=state[0];s.cycles.samples=4;s.render.resolution_x=480;s.render.resolution_y=600
    pose(state,0,0)
    for view in ('front','back','left','right','three_quarter'):
        cleanup.camera(s,view);s.render.filepath=str(folder/f'jorge-idle-{view}.png');bpy.ops.render.render(write_still=True)
    s.render.resolution_x=320;s.render.resolution_y=400
    for i,c in enumerate(state[-1]['clips']):
        pose(state,i,.45);cleanup.camera(s,'three_quarter');s.camera.data.ortho_scale=3.6 if i>=18 or i==4 else 2.95
        s.render.filepath=str(folder/f'motion-{i:02d}.png');bpy.ops.render.render(write_still=True)
    pose(state,0,0);s.camera.data.ortho_scale=2.95;cleanup.camera(s,'three_quarter')
    bpy.data.libraries.write(str(OUT/'jorge-runtime-preview.blend'),{s},fake_user=True)
    state=standard.setup('spartan');s=state[0];s.cycles.samples=4;s.render.resolution_x=480;s.render.resolution_y=600;standard.pose(state,'idle',0)
    for view in ('front','back','left','right','three_quarter'):
        cleanup.camera(s,view);s.render.filepath=str(folder/f'spartan-idle-{view}.png');bpy.ops.render.render(write_still=True)
    (OUT/'standard-reference.json').write_text(json.dumps(state[-1],indent=2)+'\n')
if __name__=='__main__':run()
