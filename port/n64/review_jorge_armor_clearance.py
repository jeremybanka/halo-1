"""Matched packed-color repair views, including folded vehicle poses.

Blender: --before PATH --output PATH --candidate
Python:  --output PATH --sheet
The before folder holds near/far packed-preview.npz and jorge_data.c.
"""
from pathlib import Path
import argparse,json,re,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import numpy as np
import review_armor_palettes as palettes

CASES=[('idle',0,'chest'),('idle',0,'codpiece'),('run',.45,'body'),
       ('reload',.45,'body'),('passenger',0,'body'),('B-driver exit',.45,'body')]

def render(before,output):
    import bpy
    from mathutils import Matrix,Vector,Quaternion
    import jorge_surgical_cleanup as studio
    import jorge_half_budget as half
    axis=Matrix(((0,0,-1),(-1,0,0),(0,1,0)))
    output.mkdir(parents=True,exist_ok=True)
    root=palettes.A/'assets/jorge/playable-lods'
    meta=json.loads((root/'near/gameplay-poses.json').read_text())
    for lod in ('near','far'):
        for version,folder in [('before',before),('after',root)]:
            d=np.load(folder/lod/'packed-preview.npz')
            if version=='after':mask=palettes.masks(lod)
            else:
                name='bg_jorge'+('_lod' if lod=='far' else '')+'_palette_mask'
                mask=np.array(list(map(int,re.search(name+r'\[\]=\{([^}]+)\}',(before/'jorge_data.c').read_text())[1].split(','))))
            colors=palettes.palette(d['colors'],mask,0)
            scene=bpy.data.scenes.new(lod+' '+version);bpy.context.window.scene=scene;studio.studio(scene)
            scene.view_settings.exposure=0;scene.cycles.samples=8
            scene.render.resolution_x=240;scene.render.resolution_y=300
            mesh=bpy.data.meshes.new('Packed body');mesh.from_pydata(d['positions']@np.array(axis).T*3.048,[],d['triangles'])
            ca=mesh.color_attributes.new(name='RGB',type='FLOAT_COLOR',domain='CORNER')
            for loop,c in zip(mesh.loops,ca.data):c.color_srgb=(*colors[loop.vertex_index]/255,1)
            mat=bpy.data.materials.new('Runtime palette');mat.use_nodes=True;ns=mat.node_tree.nodes;ns.clear()
            vc=ns.new('ShaderNodeVertexColor');vc.layer_name=ca.name;out=ns.new('ShaderNodeOutputMaterial');mat.node_tree.links.new(vc.outputs['Color'],out.inputs['Surface'])
            mesh.materials.append(mat);ob=bpy.data.objects.new('Jorge',mesh);scene.collection.objects.link(ob)
            weapon=bpy.data.objects.new('Production AR',bpy.data.meshes.new('AR'));scene.collection.objects.link(weapon);half.port_ar(weapon)
            for i,(clip,fraction,region) in enumerate(CASES):
                ci=next(i for i,c in enumerate(meta['clips']) if c['name']==clip)
                frames=d['frames_'+str(ci)];f=fraction*(len(frames)-1);a=int(f);b=min(a+1,len(frames)-1);t=f-a
                points=(frames[a]*(1-t)+frames[b]*t)/512@np.array(axis).T*3.048
                mesh.vertices.foreach_set('co',points.ravel());mesh.update()
                hands=d['grips_'+str(ci)][[a,b]];q0=Quaternion((hands[0][6],*hands[0][3:6]));q1=Quaternion((hands[1][6],*hands[1][3:6]))
                if q0.dot(q1)<0:q1.negate()
                q=Quaternion([x*(1-t)+y*t for x,y in zip(q0,q1)]);q.normalize()
                matrix=(axis@q.to_matrix()@Matrix(((1,0,0),(0,0,1),(0,-1,0)))).to_4x4()
                matrix.translation=axis@Vector(hands[0][:3]*(1-t)+hands[1][:3]*t)*3.048;weapon.matrix_world=matrix
                weapon.hide_render=region!='body' or clip=='B-driver exit'
                # Match cameras from the same before mesh in both versions.
                ref=np.load(before/lod/'packed-preview.npz');r=ref['frames_'+str(ci)]
                rp=(r[a]*(1-t)+r[b]*t)/512@np.array(axis).T*3.048
                center=Vector((rp.min(0)+rp.max(0))/2)
                direction=Vector((0,-6,.2) if region!='body' else (3,-6,.6))
                if region=='chest':center=Vector((0,0,1.95));scale=1.05
                elif region=='codpiece':center=Vector((0,0,1.28));scale=.85
                else:scale=2.95
                scene.camera.location=center+direction;scene.camera.rotation_euler=(-direction).to_track_quat('-Z','Y').to_euler();scene.camera.data.ortho_scale=scale
                scene.render.filepath=str(output/f'{i}-{lod}-{version}.png');bpy.ops.render.render(write_still=True)

def sheet(output):
    from PIL import Image,ImageDraw
    image=Image.new('RGB',(960,325*len(CASES)),(35,39,42));draw=ImageDraw.Draw(image)
    for i,(clip,fraction,region) in enumerate(CASES):
        for col,(lod,version) in enumerate([('near','before'),('near','after'),('far','before'),('far','after')]):
            im=Image.open(output/f'{i}-{lod}-{version}.png').convert('RGBA');image.paste(im,(col*240,i*325+25),im)
            draw.text((col*240+8,i*325+8),f'{lod} {version} / {clip if region=="body" else region}',fill='white')
    image.save(output/'repair-comparison.png')
    image.crop((0,0,960,650)).save(output/'repair-closeups.png')

if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    p=argparse.ArgumentParser();p.add_argument('--before',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--sheet',action='store_true');p.add_argument('--candidate',action='store_true');a=p.parse_args(args)
    if a.sheet:sheet(a.output)
    else:render(a.before,a.output)
