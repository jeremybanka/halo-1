"""Tests for geometry contracts that the optional tiny-model recipe relies on."""
import json
import unittest
from pathlib import Path
import numpy as np
from micro_lod_geometry import hull, restore_materials, support_hull


class MicroGeometryTests(unittest.TestCase):
    def test_hull_is_closed_outward_and_uses_only_source_points(self):
        points = np.array([(x, y, z) for x in (-1., 1.) for y in (-1., 1.) for z in (-1., 1.)])
        faces, _ = hull(points)
        mesh = {'positions': [points[i].tolist() for f in faces for i in f],
                'colors': [[12, 34, 56]]*(3*len(faces)),
                'materials': [7]*len(faces)}
        result = support_hull(mesh, 12)
        self.assertEqual(result, support_hull(mesh, 12))
        self.assertEqual(result['triangle_count'], 12)
        triangles = np.array(result['positions']).reshape(-1, 3, 3)
        normals = np.cross(triangles[:, 1]-triangles[:, 0], triangles[:, 2]-triangles[:, 0])
        self.assertTrue(np.all(np.einsum('ij,ij->i', normals, triangles.mean(1)) > 0))
        edges = {}
        for face in triangles:
            for i in range(3):
                a, b = tuple(face[i]), tuple(face[(i+1)%3])
                edges.setdefault(tuple(sorted((a, b))), []).append((a, b))
        self.assertTrue(all(len(v) == 2 and v[0] == v[1][::-1] for v in edges.values()))
        self.assertEqual(set(map(tuple, result['positions'])), set(map(tuple, points)))
        self.assertEqual(set(map(tuple, result['colors'])), {(12, 34, 56)})
        self.assertEqual(set(result['materials']), {7})

    def test_axis_extrema_survive_low_budget(self):
        points = np.array([[2., 0, 0], [-3., 0, 0], [0, 4., 0], [0, -5., 0], [0, 0, 6.], [0, 0, -7.]])
        faces, _ = hull(points)
        model = {'positions': [points[i].tolist() for f in faces for i in f],
                 'colors': [[80, 90, 100]]*(3*len(faces)), 'materials': [0]*len(faces)}
        result = np.array(support_hull(model, 4)['positions'])
        np.testing.assert_array_equal(result.min(0), points.min(0))
        np.testing.assert_array_equal(result.max(0), points.max(0))

    def test_coplanar_input_fails_instead_of_inventing_volume(self):
        with self.assertRaises(ValueError):
            hull([(0., 0., 0.), (1., 0., 0.), (1., 1., 0.), (0., 1., 0.)])

    def test_restore_retains_directed_lamp_corners_and_rgb(self):
        original = {'positions': [[i, i+1, i+2] for i in range(9)],
                    'colors': [[i, 100, 200] for i in range(9)], 'materials': [3, 0, 3]}
        reduced = {'positions': [[-i, 0, 0] for i in range(6)],
                   'colors': [[0, i, 0] for i in range(6)], 'materials': [3, 2]}
        result = restore_materials(reduced, original, [3])
        self.assertEqual(result['materials'], [2, 3, 3])
        self.assertEqual(result['positions'], reduced['positions'][3:] + original['positions'][:3] + original['positions'][6:])
        self.assertEqual(result['colors'], reduced['colors'][3:] + original['colors'][:3] + original['colors'][6:])

    def test_recipe_is_explicit_and_contains_no_mesh_payload(self):
        recipe = json.loads(Path(__file__).with_name('micro_lod_recipe.json').read_text())
        self.assertEqual(len(recipe['models']), 12)
        self.assertEqual(len(recipe['aliases']), 5)
        self.assertFalse(set(recipe['models']) & set(recipe['aliases']))
        self.assertEqual(recipe['models']['warthog']['restore_materials'], [3])
        self.assertEqual(recipe['projection_margin_pixels'], .5)
        for settings in recipe['models'].values():
            self.assertIn(settings['method'], ('collapse', 'support_hull'))
            self.assertNotIn('positions', settings)
            self.assertNotIn('colors', settings)


if __name__ == '__main__':
    unittest.main()
