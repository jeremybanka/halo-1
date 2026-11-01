"""Render the actual Jorge body palettes and build matching menu portraits.

Run with Blender -b --factory-startup -P this_file. Geometry/banks are unchanged.
"""
from pathlib import Path
import sys, re
sys.path.insert(0,str(Path(__file__).resolve().parent))
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
A=ROOT/'halo64-assets';OUT=A/'assets/jorge/armor-palettes'
NAMES=('red','blue','yellow','green')
TONES=(((225,45,38),(169,43,68),(226,80,49),(235,110,32),(71,152,57)),
       ((39,92,215),(32,124,190),(84,77,190),(165,60,210),(235,110,32)),
       ((215,179,44),(198,140,50),(225,200,85),(71,152,57),(165,60,210)))

def palette(colors,mask,profile):
    result=colors.astype(int).copy()
    mask=np.asarray(mask)
    kinds=mask&15
    if profile!=3:
        shade=result.max(axis=1)[:,None]
        for kind,tone in zip((1,3,4,5,6),TONES[profile]):
            recolored=(shade*(64+3*np.array(tone)//4)+127)//255
            result[kinds==kind]=recolored[kinds==kind]
    gray=(colors.astype(int)@np.array([54,183,19])+128)//256
    result[kinds==2]=gray[kinds==2,None]
    dark=(mask&16)!=0
    result[dark]=result[dark]*4//5
    return result

def masks(lod):
    source=(A/'generated/jorge_data.c').read_text()
    name='bg_jorge'+('_lod' if lod=='far' else '')+'_palette_mask'
    return np.array(list(map(int,re.search(name+r'\[\]=\{([^}]+)\}',source)[1].split(','))))

def render():
    import bpy
    from mathutils import Matrix, Vector, Quaternion
    import jorge_surgical_cleanup as studio
    import jorge_half_budget as half
    AXIS=Matrix(((0,0,-1),(-1,0,0),(0,1,0)))
    OUT.mkdir(parents=True,exist_ok=True)
    for lod in ('near','far'):
        d=np.load(A/f'assets/jorge/playable-lods/{lod}/packed-preview.npz')
        for profile,name in enumerate(NAMES):
            scene=bpy.data.scenes.new(lod+' '+name);bpy.context.window.scene=scene;studio.studio(scene)
            scene.view_settings.exposure=0;scene.cycles.samples=8
            scene.render.resolution_x=240;scene.render.resolution_y=300;scene.camera.data.ortho_scale=2.95
            mesh=bpy.data.meshes.new('Unchanged packed body');mesh.from_pydata(d['frames_0'][0]/512@np.array(AXIS).T*3.048,[],d['triangles'])
            colors=palette(d['colors'],masks(lod),profile)
            ca=mesh.color_attributes.new(name='Palette',type='FLOAT_COLOR',domain='CORNER')
            for loop,c in zip(mesh.loops,ca.data):c.color_srgb=(*colors[loop.vertex_index]/255,1)
            mat=bpy.data.materials.new('Runtime color');mat.use_nodes=True;ns=mat.node_tree.nodes;ns.clear()
            vc=ns.new('ShaderNodeVertexColor');vc.layer_name=ca.name;out=ns.new('ShaderNodeOutputMaterial');mat.node_tree.links.new(vc.outputs['Color'],out.inputs['Surface'])
            mesh.materials.append(mat);ob=bpy.data.objects.new('Jorge',mesh);scene.collection.objects.link(ob)
            weapon=bpy.data.objects.new('Production AR',bpy.data.meshes.new('AR'));scene.collection.objects.link(weapon);half.port_ar(weapon)
            hand=d['grips_0'][0];q=Quaternion((hand[6],*hand[3:6]))
            matrix=(AXIS@q.to_matrix()@Matrix(((1,0,0),(0,0,1),(0,-1,0)))).to_4x4();matrix.translation=AXIS@Vector(hand[:3])*3.048;weapon.matrix_world=matrix
            for view in ('front','three_quarter','back'):
                studio.camera(scene,view);scene.render.filepath=str(OUT/f'{lod}-{name}-{view}.png');bpy.ops.render.render(write_still=True)
            bpy.data.libraries.write(str(OUT/f'{lod}-{name}.blend'),{scene},compress=True)

def portraits():
    from PIL import Image,ImageDraw
    rows=[];sheet=Image.new('RGB',(960,650),(35,39,42));draw=ImageDraw.Draw(sheet)
    for profile,name in enumerate(NAMES):
        im=Image.open(OUT/f'near-{name}-three_quarter.png').convert('RGBA')
        crop=im.crop(im.getbbox());crop.thumbnail((31,39),Image.Resampling.LANCZOS)
        portrait=Image.new('RGBA',(32,40));portrait.alpha_composite(crop,((32-crop.width)//2,40-crop.height))
        portrait.save(OUT/f'portrait-{name}.png')
        v=np.array(portrait,dtype=np.uint16).reshape(-1,4)
        rows.append(((v[:,0]>>3)<<11)|((v[:,1]>>3)<<6)|((v[:,2]>>3)<<1)|(v[:,3]>64))
        for j,lod in enumerate(('near','far')):
            im=Image.open(OUT/f'{lod}-{name}-three_quarter.png').convert('RGBA')
            sheet.paste(im,(240*profile,25+325*j),im);draw.text((240*profile+10,8+325*j),name.title()+' / '+lod,fill='white')
    sheet.save(OUT/'palette-comparison.png')
    for view in ('front','back'):
        sheet=Image.new('RGB',(960,650),(35,39,42));draw=ImageDraw.Draw(sheet)
        for profile,name in enumerate(NAMES):
            for j,lod in enumerate(('near','far')):
                im=Image.open(OUT/f'{lod}-{name}-{view}.png').convert('RGBA')
                sheet.paste(im,(240*profile,25+325*j),im)
                draw.text((240*profile+10,8+325*j),name.title()+' / '+lod,fill='white')
        sheet.save(OUT/f'palette-{view}-comparison.png')
    # Keep the historical single-portrait symbol as the accepted green variant.
    array=lambda a:'{'+','.join(hex(int(v)) for v in a)+'}'
    (A/'generated/jorge_portrait.c').write_text('#include "asset_jorge.h"\nconst uint16_t bg_jorge_portraits[BG_PROFILE_COUNT][32*40] __attribute__((aligned(16)))={'+','.join(array(a) for a in rows)+'};\nconst uint16_t bg_jorge_portrait[32*40] __attribute__((aligned(16)))='+array(rows[3])+';\n')

if __name__=='__main__':
    if '--portraits' in sys.argv:portraits()
    else:render()
