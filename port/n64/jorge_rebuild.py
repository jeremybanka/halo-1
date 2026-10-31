"""Hand-authored semantic Jorge demake. No decimation modifiers or source-face collapse.
All dimensions in meters, measured against the retail reference. Front is -Y.
"""
import bpy,bmesh,math,json
from mathutils import Vector
from jorge_workshop import OUT,setup,camera,render_views
PALETTE={'olive':(.16,.21,.08,1),'olive_light':(.24,.30,.13,1),'olive_dark':(.08,.11,.04,1),
 'suit':(.035,.042,.044,1),'metal':(.09,.105,.1,1),'yellow':(.40,.24,.045,1),
 'red':(.20,.055,.04,1),'visor':(.65,.25,.045,1),'glass_dark':(.075,.055,.025,1),'marking':(.65,.65,.50,1)}
class Builder:
 def __init__(self):
  self.scene=bpy.data.scenes.new('Jorge - 600 triangle reconstruction');bpy.context.window.scene=self.scene
  self.col=bpy.data.collections.new('Jorge - authored low poly parts');self.scene.collection.children.link(self.col)
  self.mats={};self.parts=[]
  for n,c in PALETTE.items():
   m=bpy.data.materials.new('Jorge / '+n);m.diffuse_color=c;m.use_nodes=True
   bs=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED');bs.inputs['Base Color'].default_value=c
   bs.inputs['Roughness'].default_value=.72
   if n=='visor':bs.inputs['Metallic'].default_value=.45;bs.inputs['Roughness'].default_value=.24
   self.mats[n]=m
 def mesh(self,name,v,f,mat,category):
  me=bpy.data.meshes.new(name);me.from_pydata(v,[],f);me.update()
  ob=bpy.data.objects.new(name,me);self.col.objects.link(ob)
  me.materials.append(self.mats[mat]);ob['role']=category;ob['method']='authored planar primitive'
  bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
  me.calc_loop_triangles();self.parts.append(ob);return ob
 def rings(self,name,rings,n,mat,category,axis=None):
  # rings: center, half-width, half-depth; a rectangle with intentional chamfered corners.
  shapes={4:[(-1,-1),(1,-1),(1,1),(-1,1)],
   6:[(-.65,-1),(.65,-1),(1,0),(.65,1),(-.65,1),(-1,0)],
   8:[(-.65,-1),(.65,-1),(1,-.65),(1,.65),(.65,1),(-.65,1),(-1,.65),(-1,-.65)]}
  vs=[]
  if axis:
   z=Vector(axis).normalized();x=Vector((0,1,0)).cross(z).normalized();y=z.cross(x)
  else:x,y=Vector((1,0,0)),Vector((0,1,0))
  for c,w,d in rings:
   vs.extend([list(Vector(c)+x*(u*w)+y*(v*d)) for u,v in shapes[n]])
  fs=[tuple(reversed(range(n)))]
  for j in range(len(rings)-1):
   fs.extend([(j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i) for i in range(n)])
  fs.append(tuple(range((len(rings)-1)*n,len(rings)*n)))
  return self.mesh(name,vs,fs,mat,category)
 def box(self,name,c,size,mat,cat):
  x,y,z=c;w,d,h=[a/2 for a in size]
  return self.rings(name,[((x,y,z-h),w,d),((x,y,z+h),w,d)],4,mat,cat)
 def prism(self,name,profile,yfront,yback,mat,cat):
  n=len(profile);v=[(x,y,z) for y in (yfront,yback) for x,z in profile]
  f=[tuple(reversed(range(n))),tuple(range(n,n*2))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
  return self.mesh(name,v,f,mat,cat)

def rebuild():
 b=Builder()
 # Torso: wide clavicles taper to a narrow abdominal joint.
 b.rings('Torso armored core',[((0,.01,1.34),.21,.14),((0,.015,1.73),.28,.19),((0,.03,1.97),.245,.16)],6,'olive','torso')
 abd=b.rings('Abdominal undersuit and belt',[((0,-.005,1.18),.235,.15),((0,-.005,1.30),.24,.16),((0,-.015,1.48),.20,.14)],4,'suit','waist')
 abd.data.materials.append(b.mats['olive_light'])
 for f in abd.data.polygons[1:5]:f.material_index=1
 b.rings('Pelvis and hip joint',[((0,-.025,1.03),.10,.105),((0,0,1.25),.25,.15)],4,'suit','waist')
 # Collar is an open horseshoe, not a solid block across the face.
 verts=[]
 path=[(-.23,-.14,1.97),(-.255,.07,2.035),(-.19,.235,2.09),(.19,.235,2.09),(.255,.07,2.035),(.23,-.14,1.97)]
 for x,y,z in path:verts += [(x,y,z-.12),(x,y,z),(x*.76,y*.76,z-.025),(x*.76,y*.76,z-.12)]
 faces=[]
 for j in range(len(path)-1):
  for i in range(3):faces.append((j*4+i,j*4+(i+1)%4,(j+1)*4+(i+1)%4,(j+1)*4+i))
 faces += [(3,2,1,0),tuple(range(20,24))]
 b.mesh('Raised protective collar',verts,faces,'red','collar')
 # Gold front plate, with clipped shoulder corners and central lower tab.
 b.prism('Yellow chest cuirass',[(-.235,1.91),(-.17,1.99),(.17,1.99),(.235,1.91),(.14,1.66),(-.14,1.66)],-.27,-.19,'yellow','torso')
 # Broad cylinder across lower chest captures the signature breathing/armor hardware.
 b.rings('Chest power coupling',[((-.205,-.275,1.70),.065,.065),((.205,-.275,1.70),.065,.065)],6,'metal','torso',axis=(1,0,0))
 b.box('Central chest latch',(0,-.29,1.82),(.085,.045,.11),'metal','torso')
 # Helmet: strong forehead, narrow visor, tapered chin. Distinct silhouette at 32 tris.
 shell=b.rings('Grenadier helmet shell',[((0,-.055,2.005),.095,.135),((0,-.045,2.075),.125,.175),((0,-.035,2.19),.145,.19),((0,-.025,2.305),.105,.125)],6,'olive','helmet')
 # Visor wraps around a broad central face with two angled side panels.
 b.mesh('Copper wrap visor',[(-.105,-.17,2.075),(-.075,-.238,2.075),(.075,-.238,2.075),(.105,-.17,2.075),(-.115,-.17,2.16),(-.078,-.24,2.16),(.078,-.24,2.16),(.115,-.17,2.16)],[(0,1,5,4),(1,2,6,5),(2,3,7,6)],'visor','helmet')
 b.prism('Grenadier jaw guard',[(-.095,2.08),(-.07,2.01),(.07,2.01),(.095,2.08)],-.245,-.19,'olive_light','helmet')
 b.prism('Forehead sensor crest',[(-.06,2.19),(-.045,2.30),(.045,2.30),(.06,2.19)],-.29,-.225,'metal','helmet')
 # The pack is a separate authored prop, attached with the retail backpack marker.
 b.rings('Field pack main case',[((0,.38,1.38),.20,.13),((0,.38,1.65),.265,.155),((0,.37,1.93),.245,.14)],6,'olive_dark','pack')
 b.box('Field pack left upper pod',(.16,.39,2.025),(.20,.28,.32),'olive','pack')
 b.box('Field pack right upper pod',(-.16,.39,2.025),(.20,.28,.32),'olive','pack')
 # Shoulders differ deliberately: the left slab is taller, the right shell rounded.
 b.prism('Left Grenadier shoulder slab',[(.24,1.89),(.33,1.97),(.54,1.90),(.56,1.67),(.42,1.59),(.27,1.68)],-.025,.24,'olive_dark','shoulders')
 b.prism('Right EVA shoulder shell',[(-.28,1.89),(-.37,1.98),(-.54,1.90),(-.60,1.71),(-.46,1.62),(-.30,1.71)],-.125,.17,'red','shoulders')
 # Limb shells follow the source rest pose; black inset joints separate armor masses.
 for s,label in [(-1,'Right'),(1,'Left')]:
  upper0=(s*.35,.01,1.80);upper1=(s*.49,-.035,1.59)
  b.rings(label+' upper arm',[(upper1,.105,.105),(upper0,.125,.125)],6,'olive','arms',axis=Vector(upper0)-Vector(upper1))
  b.rings(label+' gauntlet',[((s*.63,-.19,1.32),.075,.09),((s*.58,-.15,1.43),.105,.12),((s*.51,-.09,1.57),.09,.11)],4,'olive_dark','arms',axis=(s*-.12,.10,.25))
  b.rings(label+' glove',[((s*.66,-.385,1.14),.047,.055),((s*.64,-.24,1.36),.07,.075)],4,'suit','hands',axis=(s*-.02,.145,.22))
  # Thigh gets a broad plate and squared silhouette, calf a tapered six-sided shell.
  b.rings(label+' thigh armor',[((s*.255,.015,.77),.125,.115),((s*.18,.005,1.22),.145,.15)],6,'olive_light','legs')
  b.rings(label+' knee joint',[((s*.275,.015,.60),.11,.105),((s*.26,.015,.82),.12,.11)],4,'suit','legs')
  b.prism(label+' knee plate',[(s*.27-.105,.68),(s*.27-.075,.81),(s*.27+.075,.81),(s*.27+.105,.68),(s*.27,.59)],-.155,-.07,'metal','legs')
  b.rings(label+' shin armor',[((s*.295,.02,.19),.105,.105),((s*.285,.015,.65),.14,.15)],6,'olive','legs')
  b.rings(label+' armored boot',[((s*.30,-.085,.0),.13,.205),((s*.30,-.07,.215),.12,.19)],6,'olive_dark','boots')
 # Small color patches on existing panels provide definition without added triangles.
 for ob in b.parts:
  if 'gauntlet' in ob.name:
   ob.data.materials.append(b.mats['metal']);ob.data.polygons[1].material_index=1
  if 'thigh' in ob.name:
   ob.data.materials.append(b.mats['olive_dark'])
   ob.data.polygons[3 if 'Right' in ob.name else 5].material_index=1
  if 'armored boot' in ob.name:
   for v in ob.data.vertices:
    if v.index%6 in (0,1):v.co.x=(v.co.x-(.30 if 'Left' in ob.name else -.30))/.65+(.30 if 'Left' in ob.name else -.30)
  if 'shin' in ob.name:
   ob.data.materials.append(b.mats['olive_dark']);ob.data.polygons[1].material_index=1
 setup(b.scene)
 bpy.context.view_layer.update()
 report=[]
 for o in b.parts:
  o.data.calc_loop_triangles();report.append({'name':o.name,'triangles':len(o.data.loop_triangles),'role':o['role']})
 print('TOTAL',sum(x['triangles'] for x in report));print(json.dumps(report))
 (OUT/'rebuild-counts.json').write_text(json.dumps(report,indent=2))
 camera(b.scene,'three_quarter')
 bpy.data.libraries.write(str(OUT/'jorge-lowpoly.blend'),{b.scene},fake_user=True)
 return b
