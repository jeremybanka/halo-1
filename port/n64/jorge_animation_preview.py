"""Prepare source-color render diagnostics and review sheets for Jorge motion."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'halo64-assets/assets/jorge';OUT=BASE/'animation-proof'

def colors():
    from model_colors import load_images,bake_triangle
    raw=json.loads((BASE/'full-cleanup/jorge-cleaned.json').read_text());paths=[]
    for i,m in enumerate(raw['material_metadata']):
        p=BASE/'full-cleanup/textures'/f'{i:02d}-color.png'
        paths.append(str(p) if p.exists() else m.get('diffuse'))
    images=load_images(paths);model={'material_colors':[[0,0,0]]*15,'material_overrides':[None]*15}
    # Linear .48/.16/.035 visor color converted to sRGB; no reflection shader.
    model['material_overrides'][6]=[184,111,53]
    data={}
    for fi,face in enumerate(raw['faces']):
        tri={'p':[raw['vertices'][v] for v in face],'uv':[raw['uv'][v] for v in face],'material':raw['materials'][fi]}
        data[str(raw['source_face_ids'][fi])]=bake_triangle(tri,images,model)
    (OUT/'vertex-color-diagnostic.json').write_text(json.dumps({'colors':data,'method':'Existing model_colors.bake_triangle on the preserved source triangles, using composited Jorge diffuse images; vertex RGB only, no normal maps. Alpha decal meshes hidden for this diagnostic, since the current character renderer has no texture-alpha path.','hidden_decal_triangles':sum(m in (11,12,13) for m in raw['materials'])}))

def render():
    import bpy
    import jorge_animation_proof as proof
    scene,rig=proof.proof_scene();objects=[o for o in scene.objects if o.get('variant')=='B'];materials={o.name:list(o.data.materials) for o in objects}
    data=json.loads((OUT/'vertex-color-diagnostic.json').read_text())
    mat=bpy.data.materials.new('N64 vertex RGB diagnostic');mat.use_nodes=True;ns=mat.node_tree.nodes;ns.clear();out=ns.new('ShaderNodeOutputMaterial');emit=ns.new('ShaderNodeEmission');attr=ns.new('ShaderNodeVertexColor');attr.layer_name='N64 source colors';mat.node_tree.links.new(attr.outputs['Color'],emit.inputs['Color']);mat.node_tree.links.new(emit.outputs[0],out.inputs[0])
    def linear(v):
        v=v/255;return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
    for ob in objects:
        ob.data=ob.data.copy();me=ob.data;ca=me.color_attributes.new('N64 source colors','FLOAT_COLOR','CORNER')
        for f,fi in zip(me.polygons,me.attributes['source_face'].data):
            for li,rgb in zip(f.loop_indices,data['colors'][str(fi.value)]):ca.data[li].color=(*map(linear,rgb),1)
        me.materials.clear();me.materials.append(mat)
        for f in me.polygons:f.material_index=0
        if ob.get('source_material') in (11,12,13):ob.hide_render=True
    scene.view_settings.exposure=0;scene.render.resolution_x=480;scene.render.resolution_y=600;scene.cycles.samples=8;scene.cycles.use_denoising=True
    for name,fraction in [('idle',0),('run',.5),('reload',.4)]:
        action=next(a for a in bpy.data.actions if a.get('source_clip')==name);proof.select_clip(scene,rig,name,action['duration_seconds']*fraction)
        proof.cleanup.camera(scene,'three_quarter');scene.camera.data.ortho_scale=2.95;scene.render.filepath=str(OUT/'renders'/f'{name}-vertex-color.png');bpy.ops.render.render(write_still=True)
    clay=bpy.data.materials.new('Untextured geometry diagnostic');clay.diffuse_color=(.46,.5,.52,1)
    for ob in objects:
        ob.hide_render=False;ob.data.materials.clear();ob.data.materials.append(clay)
    scene.view_settings.exposure=-.6
    for name,fraction in [('idle',0),('run',.5),('reload',.4)]:
        action=next(a for a in bpy.data.actions if a.get('source_clip')==name);proof.select_clip(scene,rig,name,action['duration_seconds']*fraction)
        for view in ('front','three_quarter'):
            proof.cleanup.camera(scene,view);scene.render.filepath=str(OUT/'renders'/f'{name}-clay-{view}.png');bpy.ops.render.render(write_still=True)

def sheets():
    from PIL import Image,ImageDraw,ImageFont
    font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',19)
    def sheet(name,files,columns,width=320):
        height=width*5//4+42;out=Image.new('RGB',(columns*width,((len(files)+columns-1)//columns)*height),(29,34,38));draw=ImageDraw.Draw(out)
        for i,(path,label) in enumerate(files):
            im=Image.open(path).convert('RGBA');im.thumbnail((width,width*5//4));x=i%columns*width;y=i//columns*height;out.paste(im,(x+(width-im.width)//2,y),im);draw.text((x+12,y+width*5//4+8),label,fill=(228,233,237),font=font)
        out.save(OUT/name)
    p=OUT/'renders'
    sheet('motion-contact-sheet.jpg',[(p/f'{n}-{f:03d}.png',f'{n.title()} / {f}%') for n,fs in [('idle',[0]),('run',[0,25,50,75]),('fire',[50]),('reload',[20,40,60,80,100])] for f in fs],4)
    sheet('material-diagnostics.jpg',[(p/file,label) for name,fraction in [('idle',0),('run',50),('reload',40)] for file,label in [(f'{name}-{fraction:03d}.png',name.title()+' / source materials'),(f'{name}-clay-three_quarter.png',name.title()+' / geometry'),(f'{name}-vertex-color.png',name.title()+' / vertex RGB')]],3)
    sheet('clearance-contact-sheet.jpg',[(p/f'{n}-{f:03d}-{view}.png',f'{n.title()} {f}% / {view}') for n,f in [('idle',0),('run',25),('run',75),('reload',40),('reload',80)] for view in ('front','left','back')],3)

def movies():
    import subprocess,os
    from PIL import Image,ImageDraw,ImageFont
    font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',20)
    ffmpeg=os.environ.get('JORGE_FFMPEG','ffmpeg')
    for name in ('idle','run','fire','reload'):
        subprocess.run([ffmpeg,'-y','-loglevel','error','-framerate','30','-i',str(OUT/'frames'/name/'%04d.png'),'-c:v','libx264','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(OUT/f'{name}.mp4')],check=True)
    cached={n:[Image.open(p).convert('RGB') for p in sorted((OUT/'frames'/n).glob('*.png'))] for n in ('idle','run','fire','reload')}
    frames=[];directory=OUT/'frames/overview';directory.mkdir(exist_ok=True)
    for fi in range(132):
        t=fi/15;canvas=Image.new('RGB',(840,1120),(25,30,34));draw=ImageDraw.Draw(canvas)
        for i,name in enumerate(('idle','run','fire','reload')):
            source=cached[name];index=int(t*30)%len(source)
            if name=='fire':index=min(len(source)-1,int((t%1.5)*30/4)) if t%1.5<2/3 else 0
            x=i%2*420;y=i//2*560;canvas.paste(source[index],(x,y+40));label=name.title()+(' / recoil at quarter speed' if name=='fire' else ' / original timing');draw.text((x+12,y+9),label,font=font,fill=(233,237,241))
        canvas.save(directory/f'{fi:04d}.png');small=canvas.resize((420,560));frames.append(small)
    subprocess.run([ffmpeg,'-y','-loglevel','error','-framerate','15','-i',str(directory/'%04d.png'),'-c:v','libx264','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(OUT/'jorge-animation-overview.mp4')],check=True)
    samples=frames[::12];swatch=Image.new('RGB',(140*len(samples),187))
    for i,frame in enumerate(samples):swatch.paste(frame.resize((140,187)),(i*140,0))
    palette=swatch.quantize(colors=128);indexed=[f.quantize(palette=palette,dither=Image.Dither.NONE) for f in frames]
    indexed[0].save(OUT/'jorge-animation-overview.gif',save_all=True,append_images=indexed[1:],duration=[67,67,66]*44,loop=0,optimize=True)

if __name__=='__main__':
    if '--colors' in sys.argv:colors()
    if '--render' in sys.argv:render()
    if '--sheets' in sys.argv:sheets()
    if '--movies' in sys.argv:movies()
