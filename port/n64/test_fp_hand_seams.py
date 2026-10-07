"""Owned-asset regression: two continuous animated hands with open sleeve ends."""
from collections import defaultdict
import json
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[2]/'build/n64/assets/firstperson-reduced.json'


@unittest.skipUnless(SOURCE.exists(), 'Requires locally extracted/reduced Xbox assets')
class HandSeamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(SOURCE.read_text())

    def test_two_open_sleeve_ends_and_no_torn_material_seams(self):
        w = self.data['weapons']['ar']
        tris = w['triangles'][:w['hand_triangle_count']]
        edges = defaultdict(list)
        for t in tris:
            p = [tuple(round(x, 6) for x in v) for v in t['p']]
            for i, a in enumerate(p):
                b = p[(i+1)%3]
                edges[tuple(sorted((a,b)))].append((a,b))
        boundary = defaultdict(set)
        for e in edges.values():
            if len(e) == 1:
                a,b = e[0]; boundary[a].add(b); boundary[b].add(a)
            else:
                self.assertEqual(len(e), 2)
                self.assertEqual(e[0], e[1][::-1])
        self.assertTrue(all(len(v)==2 for v in boundary.values()))
        remaining = set(boundary); loops = 0
        while remaining:
            pending = [remaining.pop()]; loops += 1
            while pending:
                for v in boundary[pending.pop()] & remaining:
                    remaining.remove(v); pending.append(v)
        self.assertEqual(loops, 2, 'Only the two intentional sleeve ends may be open')

    def test_shared_corners_follow_identical_animation_trajectories(self):
        for name, weapon in self.data['weapons'].items():
            n = weapon['hand_triangle_count']
            groups = defaultdict(list)
            for i, p in enumerate(p for t in weapon['triangles'][:n] for p in t['p']):
                groups[tuple(p)].append(i)
            for clip, data in weapon['clips'].items():
                for frame in data['frames']:
                    self.assertEqual(len(frame), len(weapon['triangles'])*3)
                    for group in groups.values():
                        for i in group[1:]:
                            self.assertEqual(frame[i], frame[group[0]], (name, clip, i))


if __name__ == '__main__':
    unittest.main()
