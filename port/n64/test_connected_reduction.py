"""Blender integration regression for reducing an animated material seam.

Run through Blender Python/MCP. The fixture has duplicate UV vertices on a
closed two-material sphere: reducing material islands independently tears it.
"""
import math
import unittest
try:
    import bpy
    import bmesh
except ImportError:
    bpy = None
from geometry_reduce import reduce_geometry


@unittest.skipUnless(bpy, 'Requires Blender')
class ConnectedReductionTests(unittest.TestCase):
    def test_closed_material_seam_survives_collapse_and_skinning(self):
        scene = bpy.data.scenes.new('Connected reduction regression')
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=1)
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        model = dict(vertices=[], faces=[], uv=[], weights=[], materials=[],
                     nodes=[{'name': 'upper'}, {'name': 'lower'}])
        for face in bm.faces:
            start = len(model['vertices'])
            for v in face.verts:
                model['vertices'].append(list(v.co))
                model['uv'].append([v.co.x*.5+.5, v.co.y*.5+.5])
                model['weights'].append([0, 1, (v.co.z+1)*.5])
            model['faces'].append([start, start+1, start+2])
            model['materials'].append(int(face.calc_center_median().z > 0))
        bm.free()
        obj, tris, weighted, report = reduce_geometry(
            scene, model, 'Connected seam test', 64,
            bone_labels={0: 'arm', 1: 'arm'}, partition_colors=False,
            partition_materials=False, project_surface=False)
        try:
            self.assertLess(len(tris), len(model['faces']))
            self.assertEqual(len(report['parts']), 1)
            self.assertEqual({t['material'] for t in tris}, {0, 1})
            edges = {}
            skins = {}
            for t in tris:
                points = [tuple(p) for p in t['p']]
                for p, weights, uv in zip(points, t['weights'], t['uv']):
                    self.assertTrue(all(math.isfinite(x) for x in (*p, *uv)))
                    self.assertAlmostEqual(sum(w for _, w in weights), 1)
                    self.assertTrue(all(0 <= w <= 1 for _, w in weights))
                    if p in skins:
                        self.assertEqual(skins[p], weights)
                    skins[p] = weights
                for i, a in enumerate(points):
                    b = points[(i+1)%3]
                    edges.setdefault(tuple(sorted((a,b))), []).append((a,b))
            self.assertTrue(all(len(e)==2 and e[0]==e[1][::-1] for e in edges.values()),
                            'Every edge must retain an outward-facing reverse partner')
        finally:
            mesh = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.meshes.remove(mesh)
            bpy.data.scenes.remove(scene)


if __name__ == '__main__':
    unittest.main()
