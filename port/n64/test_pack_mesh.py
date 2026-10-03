"""Regression checks for N64 batch boundaries, skin identity and color seams."""
import copy
import unittest
from pack_mesh import indexed_mesh, MODEL_COLOR_TOLERANCE, model_color_tolerance


class MeshPackingTests(unittest.TestCase):
    def test_color_bound_does_not_chain_across_a_seam(self):
        points = [[0, 0, 0]] * 6
        for bank, name in [('world', 'ghost'), ('firstperson', 'rocket'), ('world', 'spartan')]:
            bound = model_color_tolerance(bank, name)
            colors = [[i * bound, 0, 0] for i in range(6)]
            for reorder in (False, True):
                result = indexed_mesh(points, colors, [0] * 6,
                                      color_tolerance=bound, reorder_static=reorder)
                self.assertEqual([rgb[0] for rgb in result['colors']],
                                 [0, 0, 2 * bound, 2 * bound, 4 * bound, 4 * bound])

    def test_each_channel_bound_and_maximum_tolerance_are_enforced(self):
        points = [[0, 0, 0]] * 6
        for bound in (24, 32, 48):
            colors = [[0, 0, 0], [bound] * 3, [bound + 1, 0, 0],
                      [0, bound + 1, 0], [0, 0, bound + 1], [bound] * 3]
            result = indexed_mesh(points, colors, [0] * 6, color_tolerance=bound)
            self.assertEqual(result['indices'][:2], [0, 0])
            self.assertEqual(len(set(result['indices'][2:5])), 3)
            self.assertNotIn(0, result['indices'][2:5])
        with self.assertRaises(AssertionError):
            indexed_mesh(points, colors, [0] * 6, color_tolerance=MODEL_COLOR_TOLERANCE + 1)

    def test_reviewed_model_exceptions_and_unknown_models(self):
        self.assertEqual(model_color_tolerance('world', 'ghost'), 24)
        self.assertEqual(model_color_tolerance('world', 'ghost_lod'), 24)
        self.assertEqual(model_color_tolerance('firstperson', 'rocket'), 32)
        self.assertEqual(model_color_tolerance('world', 'rocket'), 48)
        self.assertEqual(model_color_tolerance('world', 'rocket_pickup_lod'), 48)
        self.assertEqual(model_color_tolerance('firstperson', 'flamethrower'), 24)
        with self.assertRaises(KeyError):
            model_color_tolerance('world', 'unreviewed_model')

    def test_material_mask_and_motion_all_protect_identical_color_corners(self):
        points = [[0, 0, 0]] * 6
        colors = [[80, 100, 120]] * 6
        materials = [0, 1, 0, 0, 0, 1]
        masks = [0, 0, 255, 0, 0, 0]
        motion = [(0,), (0,), (0,), (1,), (0,), (0,)]
        result = indexed_mesh(points, colors, masks, motion,
                              material_keys=materials)
        self.assertEqual(result['indices'][:6], [0, 1, 2, 3, 0, 1])
        # Static global canonicalization must enforce the same material seam.
        static = indexed_mesh(points, colors, masks, material_keys=materials,
                              reorder_static=True)
        self.assertEqual(len(static['vertices']), 4)
        at = 0
        for first, _, ii, ic in static['batches']:
            for index in static['indices'][ii:ii + ic]:
                original = static['triangle_order'][at // 3] * 3 + at % 3
                representative = static['sources'][first + index]
                self.assertEqual(materials[original], materials[representative])
                self.assertEqual(masks[original], masks[representative])
                at += 1

    def test_skin_trajectories_and_team_masks_remain_distinct(self):
        points = [[0, 0, 0]] * 6
        colors = [[100, 120, 130]] * 6
        result = indexed_mesh(points, colors, [0, 0, 255, 0, 0, 255],
                              [(0, 1), (0, 2), (0, 1), (0, 1), (0, 2), (0, 1)])
        self.assertEqual(result['indices'][:6], [0, 1, 2, 0, 1, 2])
        self.assertEqual(len(result['vertices']), 4)  # three identities + pair padding

    def test_rigid_parts_cannot_share_vertices(self):
        result = indexed_mesh([[0, 0, 0]] * 6, [[0, 0, 0]] * 6, [0] * 6,
                              segments=[(0, 3), (3, 3)])
        self.assertEqual(result['segments'], [(0, 1), (1, 1)])
        self.assertEqual([batch[0] for batch in result['batches']], [0, 2])
        self.assertEqual(result['sources'], [0, 0, 3, 3])

    def test_vertex_and_index_limits_roll_over_independently(self):
        for unique in (False, True):
            points = [[i if unique else i % 3, 0, 0] for i in range(303)]
            result = indexed_mesh(points, [[0, 0, 0]] * 303, [0] * 303)
            self.assertEqual(sum(batch[3] for batch in result['batches']), 303)
            for first, count, index_first, index_count in result['batches']:
                self.assertEqual(first % 2, 0)
                self.assertEqual(index_first % 4, 0)
                self.assertLessEqual(count, 60)
                self.assertLessEqual(index_count, 120)
                self.assertLessEqual(count * 36 + ((index_count + 3) & ~3) * 2, 70 * 36)


class StaticCacheOrderingTests(unittest.TestCase):
    @staticmethod
    def grid():
        faces = []
        for y in range(8):
            for x in range(9):
                a, b = [x, y, 0], [x + 1, y, 0]
                c, d = [x, y + 1, 0], [x + 1, y + 1, 0]
                faces.extend(((a, b, c), (c, b, d)))
        # Source order separates the two halves of each quad. The cache
        # candidate can reunite neighbors without changing any surface.
        return [p for face in faces[::2] + faces[1::2] for p in face]

    def assert_expansion(self, packed, points, colors, masks):
        corner = 0
        self.assertEqual(sorted(packed['triangle_order']), list(range(len(points) // 3)))
        for first, count, ii, ic in packed['batches']:
            self.assertEqual(first % 2, 0)
            self.assertEqual(ii % 4, 0)
            self.assertLessEqual(count, 60)
            self.assertLessEqual(ic, 120)
            for index in packed['indices'][ii:ii + ic]:
                original = packed['triangle_order'][corner // 3] * 3 + corner % 3
                vertex = packed['vertices'][first + index]
                self.assertEqual(vertex[0], points[original])
                self.assertEqual(vertex[2], masks[original])
                self.assertLessEqual(max(abs(a - b) for a, b in zip(vertex[1], colors[original])), MODEL_COLOR_TOLERANCE)
                corner += 1
        self.assertEqual(corner, len(points))

    def test_cache_order_reduces_loads_and_preserves_indexed_winding(self):
        points = self.grid()
        colors = [[50, 70, 90]] * len(points)
        masks = [0] * len(points)
        baseline = indexed_mesh(points, colors, masks)
        packed = indexed_mesh(points, colors, masks, reorder_static=True)
        self.assertLess(len(packed['vertices']), len(baseline['vertices']))
        self.assertLessEqual(len(packed['batches']), len(baseline['batches']))
        self.assert_expansion(packed, points, colors, masks)

    def test_color_bounds_use_immutable_original_corners_across_batches(self):
        points = self.grid()
        colors = [[(i % 7) * 8, 80, 130] for i in range(len(points))]
        original = copy.deepcopy(colors)
        masks = [0] * len(points)
        packed = indexed_mesh(points, colors, masks, reorder_static=True)
        self.assertEqual(colors, original)
        self.assert_expansion(packed, points, original, masks)
        for source, vertex in zip(packed['sources'], packed['vertices']):
            self.assertEqual(vertex[1], original[source])

    def test_overlapping_coplanar_faces_keep_their_relative_order(self):
        points = self.grid()
        # A later opposite-winding overlay shares an area and must stay later
        # even when its three vertices are attractive to the current cache.
        overlap = [[0, 0, 0], [0, 1, 0], [1, 0, 0]]
        points += overlap
        colors = [[30, 50, 70]] * (len(points) - 3) + [[200, 40, 40]] * 3
        packed = indexed_mesh(points, colors, [0] * len(points), reorder_static=True)
        self.assertLess(packed['triangle_order'].index(0), packed['triangle_order'].index(len(points) // 3 - 1))
        self.assert_expansion(packed, points, colors, [0] * len(points))

    def test_vehicle_parts_keep_separate_batches_and_source_ranges(self):
        part = self.grid()
        points = part + part
        count = len(part)
        packed = indexed_mesh(points, [[30, 50, 70]] * len(points), [0] * len(points),
                              segments=[(0, count), (count, count)], reorder_static=True)
        self.assertEqual(sorted(packed['triangle_order'][:count // 3]), list(range(count // 3)))
        self.assertEqual(sorted(packed['triangle_order'][count // 3:]), list(range(count // 3, count * 2 // 3)))
        for part_id, (first, batches) in enumerate(packed['segments']):
            for vb, vc, _, _ in packed['batches'][first:first + batches]:
                self.assertTrue(all(part_id * count <= source < (part_id + 1) * count
                                    for source in packed['sources'][vb:vb + vc]))

    def test_animated_mesh_cannot_enable_static_reordering(self):
        with self.assertRaisesRegex(AssertionError, 'Animated'):
            indexed_mesh([[0, 0, 0]] * 3, [[0, 0, 0]] * 3, [0] * 3,
                         motion_keys=[(0,)] * 3, reorder_static=True)


if __name__ == '__main__':
    unittest.main()
