"""Jorge source inspection and intentional low-poly reconstruction workshop."""
from pathlib import Path
import json,math,hashlib
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'halo64-assets/assets/jorge'
VIEWS={'front':(0,-6,1.17),'back':(0,6,1.17),'left':(6,0,1.17),'right':(-6,0,1.17),'three_quarter':(4,-6,3.0)}
def point(v):return (v[1]*3.048,-v[0]*3.048,v[2]*3.048)
def setup(scene):
 scene.render.engine='CYCLES';scene.cycles.samples=24
 scene.render.resolution_x=640;scene.render.resolution_y=800;scene.render.resolution_percentage=100
 scene.render.image_settings.file_format='PNG';scene.render.film_transparent=True
 scene.world=bpy.data.worlds.new('Jorge studio');scene.world.use_nodes=True
 next(n for n in scene.world.node_tree.nodes if n.type=='BACKGROUND').inputs[0].default_value=(.3,.3,.3,1)
 scene.view_settings.view_transform='Standard'
 for name,loc,power,size in [('Key',(3,-4,5),450,4),('Fill',(-4,-2,3),300,4),('Rim',(1,4,4),550,3)]:
  d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size
  o=bpy.data.objects.new(name,d);scene.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,1.2))-o.location).to_track_quat('-Z','Y').to_euler()
 d=bpy.data.cameras.new('Reference camera');o=bpy.data.objects.new('Reference camera',d);scene.collection.objects.link(o)
 d.type='ORTHO';d.ortho_scale=2.66;scene.camera=o
 camera(scene,'three_quarter')
def camera(scene,view):
 scene.camera.location=VIEWS[view];scene.camera.rotation_euler=(Vector((0,0,1.15))-scene.camera.location).to_track_quat('-Z','Y').to_euler()
def source():
 raw=json.loads((OUT/'jorge-original.json').read_text())
 # Assemble the separately authored field pack using its original biped marker.
 from mathutils import Matrix
 pack=json.loads((OUT/'backpack-original.json').read_text());xf=Matrix(json.loads((OUT/'backpack-attachment.json').read_text())['matrix'])
 base=len(raw['vertices']);mb=len(raw['material_metadata'])
 raw['vertices'] += [list((xf@Vector((*v,1)))[:3]) for v in pack['vertices']]
 raw['uv'] += pack['uv'];raw['faces'] += [[i+base for i in f] for f in pack['faces']]
 raw['materials'] += [i+mb for i in pack['materials']];raw['regions'] += ['backpack']*len(pack['faces'])
 raw['material_metadata'] += pack['material_metadata']
 scene=bpy.data.scenes.new('Jorge - intact retail reference');bpy.context.window.scene=scene
 co=bpy.data.collections.new('Original - immutable retail mesh');scene.collection.children.link(co)
 mats=[]
 for i,meta in enumerate(raw['material_metadata']):
  mat=bpy.data.materials.new(meta['path'].split('\\')[-1]);mat.use_nodes=True
  bs=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');bs.inputs['Roughness'].default_value=.7
  tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(meta['diffuse'],check_existing=True)
  tex.image.alpha_mode='NONE' if i<11 or i>=14 else 'STRAIGHT'
  color=tex.outputs['Color']
  if meta.get('cc') and i!=6:
   mask=mat.node_tree.nodes.new('ShaderNodeTexImage');mask.image=bpy.data.images.load(meta['cc'],check_existing=True);mask.image.colorspace_settings.name='Non-Color'
   sep=mat.node_tree.nodes.new('ShaderNodeSeparateColor');mat.node_tree.links.new(mask.outputs['Color'],sep.inputs['Color'])
   # Presentation approximation of runtime armor colors; original textures remain untouched.
   for channel,tint in [('Red',(.42,.48,.22,1)),('Green',(.5,.52,.35,1)),('Blue',(.42,.08,.055,1))]:
    mix=mat.node_tree.nodes.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY'
    mat.node_tree.links.new(sep.outputs[channel],mix.inputs[0]);mat.node_tree.links.new(color,mix.inputs[1]);mix.inputs[2].default_value=tint;color=mix.outputs[0]
  if i==6:
   bs.inputs['Base Color'].default_value=(.48,.16,.035,1);bs.inputs['Metallic'].default_value=.65;bs.inputs['Roughness'].default_value=.22
  else:mat.node_tree.links.new(color,bs.inputs['Base Color'])
  if 11<=i<14:mat.node_tree.links.new(tex.outputs['Alpha'],bs.inputs['Alpha'])
  if i==13:
   sep=mat.node_tree.nodes.new('ShaderNodeSeparateColor');mat.node_tree.links.new(tex.outputs['Color'],sep.inputs['Color'])
   mat.node_tree.links.new(sep.outputs['Red'],bs.inputs['Base Color']);mat.node_tree.links.new(sep.outputs['Green'],bs.inputs['Alpha'])
  mats.append(mat)
 inventory=[]
 for region in sorted(set(raw['regions'])):
  for mi,mat in enumerate(mats):
   fs=[f for f,m,r in zip(raw['faces'],raw['materials'],raw['regions']) if m==mi and r==region]
   if not fs:continue
   ids=sorted({v for f in fs for v in f});remap={v:i for i,v in enumerate(ids)}
   me=bpy.data.meshes.new(region+' / '+mat.name);me.from_pydata([point(raw['vertices'][i]) for i in ids],[],[[remap[v] for v in f] for f in fs]);me.materials.append(mat)
   uv=me.uv_layers.new(name='Original UV')
   for f,indices in zip(me.polygons,fs):
    f.use_smooth=True
    for li,i in zip(f.loop_indices,indices):uv.data[li].uv=(raw['uv'][i][0],1-raw['uv'][i][1])
   ob=bpy.data.objects.new(me.name,me);co.objects.link(ob);ob['source_region']=region;ob['source_material']=mi
   ob['source_unchanged']=True;ob.hide_select=True
   inventory.append({'name':ob.name,'triangles':len(fs),'vertices':len(ids),'dimensions':list(ob.dimensions),'bounds':[[min(v.co[a] for v in me.vertices),max(v.co[a] for v in me.vertices)] for a in range(3)]})
 setup(scene);bpy.context.view_layer.update()
 report={'triangles':len(raw['faces']),'vertices':len(raw['vertices']),'source_nodes':len(raw['nodes']),
 'objects':inventory,'source_sha256':hashlib.sha256((OUT/'jorge-original.json').read_bytes()).hexdigest(),
 'material_note':'Original diffuse and UVs; runtime color masks tinted for presentation. Visor uses copper metal approximation. No game shader recreation.'}
 (OUT/'source-inspection.json').write_text(json.dumps(report,indent=2))
 for im in bpy.data.images:
  if im.filepath and str(OUT) in bpy.path.abspath(im.filepath):im.pack()
 bpy.data.libraries.write(str(OUT/'jorge-original.blend'),{scene},fake_user=True)
 print('Source',report['triangles'],'triangles;',len(inventory),'objects')
 return scene

def render_views(scene,prefix):
 folder=OUT/'renders';folder.mkdir(exist_ok=True)
 for view in VIEWS:
  camera(scene,view);scene.render.filepath=str(folder/(prefix+'-'+view+'.png'));bpy.ops.render.render(write_still=True,scene=scene.name)
if __name__=='__main__':
 import sys
 if '--render-source' in sys.argv:render_views(bpy.context.scene,'before')
