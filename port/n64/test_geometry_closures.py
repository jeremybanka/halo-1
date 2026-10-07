"""Blender integration tests; run this module through Blender Python or MCP."""
import copy
import unittest
try:
 import bpy
except ImportError:
 bpy=None
from geometry_closures import close_model


@unittest.skipUnless(bpy,'Requires Blender BMesh')
class ClosureTests(unittest.TestCase):
 def fixture(self):
  # Outward box with an open top, inside the reviewed Spartan neck region.
  v=[(x,y,z) for z in (.592,.595) for y in (-.01,.01) for x in (-.01,.01)]
  faces=[(0,2,3),(0,3,1),(0,1,5),(0,5,4),(1,3,7),(1,7,5),(3,2,6),(3,6,7),(2,0,4),(2,4,6)]
  tris=[{'p':[list(v[i]) for i in f],'uv':[[0,0],[1,0],[0,1]],'weights':[[[0,1]]]*3,'material':0,'part':0} for f in faces]
  return {'triangles':tris}
 def test_closure_retains_surface_and_all_animation_trajectories(self):
  m=self.fixture();before=copy.deepcopy(m['triangles']);points=[p for t in before for p in t['p']]
  clips={'idle':{'frames':[points,[[x+1,y+2,z+3] for x,y,z in points]]}}
  report,mesh=close_model(m,'spartan',clips)
  self.assertEqual(report['after']-report['before'],2)
  self.assertEqual(m['triangles'][:len(before)],before)
  self.assertEqual(len(clips['idle']['frames'][0]),len(m['triangles'])*3)
  for a,b in zip(*clips['idle']['frames']):
   for axis,delta in enumerate((1,2,3)):self.assertAlmostEqual(b[axis]-a[axis],delta)
  # Every directed edge is paired with its reverse: no residual hole and no
  # flipped cap which would disappear from the exterior with CULL_BACK.
  edges={}
  for t in m['triangles']:
   for i in range(3):
    a,b=tuple(t['p'][i]),tuple(t['p'][(i+1)%3]);edges.setdefault(tuple(sorted((a,b))),[]).append((a,b))
  self.assertTrue(all(len(e)==2 and e[0]==e[1][::-1] for e in edges.values()))
  bpy.data.meshes.remove(mesh)
 def test_unreviewed_open_surface_is_not_filled(self):
  m=self.fixture();before=copy.deepcopy(m)
  report,mesh=close_model(m,'rocket')
  self.assertEqual(m,before);self.assertEqual(report['closures'],[])
  bpy.data.meshes.remove(mesh)


if __name__=='__main__':unittest.main()
