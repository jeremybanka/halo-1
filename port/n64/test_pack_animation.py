"""Check exact motion decoding and interpolation after corner-track sharing."""
import unittest
from pack_animation import compact_clip
from pack_assets import position


class AnimationPackingTest(unittest.TestCase):
    def test_seams_share_only_identical_complete_motion(self):
        clip = {'frames': [
            [[-.2, .1, .3], [-.2, .1, .3], [-.2, .1, .3]],
            [[.4, -.1, .5], [.4, -.1, .5], [.41, -.1, .5]],
            [[.1, .1, .2], [.1, .1, .2], [.1, .1, .2]],
        ]}
        packed = compact_clip(clip, 256)
        self.assertEqual(packed['indices'], [0, 0, 1])
        self.assertEqual(packed['tracks'], 2)
        for fi in range(2):
            for vi, index in enumerate(packed['indices']):
                a = [round(x * 256) for x in position(clip['frames'][fi][vi], (0, 0, 0))]
                b = [round(x * 256) for x in position(clip['frames'][fi + 1][vi], (0, 0, 0))]
                for fraction in (0, 1, 127, 128, 255, 256):
                    for axis in range(3):
                        x = packed['values'][(fi * packed['tracks'] + index) * 3 + axis]
                        y = packed['values'][((fi + 1) * packed['tracks'] + index) * 3 + axis]
                        decoded = packed['origin'][axis] + x + int((y - x) * fraction / 256)
                        self.assertEqual(decoded, a[axis] + int((b[axis] - a[axis]) * fraction / 256))

    def test_excessive_span_fails_instead_of_wrapping(self):
        with self.assertRaises(ValueError):
            compact_clip({'frames': [[[0, 0, 0]], [[2, 0, 0]]]}, 256)


if __name__ == '__main__':
    unittest.main()
