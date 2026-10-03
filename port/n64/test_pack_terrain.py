"""Portable invariants for the terrain's ordered, wrap-preserving batches."""
import copy
import unittest
from pack_terrain import UV_PERIOD, indexed_terrain


def vertex(x=0, color=100, s=0, t=0):
    return (x, 0, 0, color, color, color, s, t)


class TerrainPackingTests(unittest.TestCase):
    def verify(self, triangles, chunks):
        original = [v for tri in triangles for v in tri]
        expanded = []
        for chunk in chunks:
            vs, ix = chunk['vertices'], chunk['indices']
            self.assertLessEqual((len(vs) + 1) & ~1, 60)
            self.assertLessEqual(len(ix), 120)
            self.assertEqual(len(ix) % 3, 0)
            self.assertLessEqual(((len(vs) + 1) & ~1) * 36 + ((len(ix) + 3) & ~3) * 2, 70 * 36)
            expanded.extend(vs[i] for i in ix)
        self.assertEqual(len(original), len(expanded))
        for first in range(0, len(original), 3):
            shift = tuple(original[first][a] - expanded[first][a] for a in (6, 7))
            self.assertTrue(all(x % UV_PERIOD == 0 for x in shift))
            for before, after in zip(original[first:first + 3], expanded[first:first + 3]):
                self.assertEqual(before[:3], after[:3])
                self.assertLessEqual(max(abs(before[a] - after[a]) for a in (3, 4, 5)), 8)
                self.assertEqual(tuple(before[a] - after[a] for a in (6, 7)), shift)
                self.assertTrue(all(-32768 <= after[a] <= 32767 for a in (6, 7)))

    def test_merge_cannot_drift_from_original_colors(self):
        triangles = [[vertex(color=c)] * 3 for c in (0, 8, 16, 24, 32, 40)]
        original = copy.deepcopy(triangles)
        chunks = indexed_terrain(triangles)
        self.assertEqual([v[3] for v in chunks[0]['vertices']], [0, 16, 32])
        self.assertEqual(triangles, original)
        self.verify(triangles, chunks)

    def test_global_uv_identity_and_integer_wrapping(self):
        triangles = [[vertex(0, s=100000, t=-100000), vertex(1, s=101024, t=-100000), vertex(2, s=100000, t=-99000)],
                     [vertex(2, s=100000, t=-99000), vertex(1, s=101024, t=-100000), vertex(3, s=101024, t=-100000)]]
        chunks = indexed_terrain(triangles)
        self.assertEqual(len(chunks[0]['vertices']), 4)
        self.verify(triangles, chunks)

    def test_vertex_index_and_uv_limits_split_independently(self):
        fixtures = [
            [[vertex(x=i * 3 + j) for j in range(3)] for i in range(100)],
            [[vertex(x=j) for j in range(3)] for _ in range(100)],
            [[vertex(x=j, s=i * 32000) for j in range(3)] for i in range(100)],
        ]
        for triangles in fixtures:
            chunks = indexed_terrain(triangles)
            self.assertGreater(len(chunks), 1)
            self.verify(triangles, chunks)

    def test_single_unrepresentable_triangle_fails(self):
        with self.assertRaisesRegex(ValueError, 'signed16 UV'):
            indexed_terrain([[vertex(s=-40000), vertex(s=40000), vertex()]])

    def test_fitting_coordinates_cannot_overflow_uv_edge_subtraction(self):
        with self.assertRaisesRegex(ValueError, 'signed16 UV edge differences'):
            indexed_terrain([[vertex(s=-20000), vertex(s=20000), vertex()]])


if __name__ == '__main__':
    unittest.main()
