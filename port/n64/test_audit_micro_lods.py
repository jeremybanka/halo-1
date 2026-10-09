"""Adversarial checks for the independently decoded optional micro C bank."""
import copy
import unittest
from audit_micro_lods import validate_c


def fixture():
    triangle = [[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]]
    source = {'ar': {'positions': triangle*2, 'colors': [[100, 100, 100]]*6,
                     'materials': [0, 1], 'triangle_count': 2, 'source_bank': 'ar_pickup_lod'}}
    preview = {'ar': {'positions': triangle*2, 'colors': [[100, 100, 100]]*6}}
    text = '''static T3DVertPacked micro_ar[] __attribute__((aligned(16)))={
{{0,0,0},0,{1024,0,0},0,0x646464ff,0x646464ff,{0,0},{0,0}},
{{0,1024,0},0,{0,0,0},0,0x646464ff,0x646464ff,{0,0},{0,0}},
{{1024,0,0},0,{0,1024,0},0,0x646464ff,0x646464ff,{0,0},{0,0}},
};
static int16_t micro_ar_indices[]={0,1,2,3,4,5,0,0};
static const bg_mesh_batch micro_ar_batches[]={{0,6,0,6}};
'''
    return source, preview, text


class MicroCValidatorTests(unittest.TestCase):
    def test_valid_material_separated_coincident_triangles(self):
        result = validate_c(*fixture())
        self.assertEqual(result['ar']['vertices'], 6)
        self.assertTrue(result['ar']['material_boundaries_preserved'])

    def test_reusing_vertex_across_materials_fails_even_when_pixels_match(self):
        source, preview, text = fixture()
        text = text.replace('{0,1,2,3,4,5,0,0}', '{0,1,2,0,1,2,0,0}')
        with self.assertRaisesRegex(AssertionError, 'material seam'):
            validate_c(source, preview, text)

    def test_wrong_winding_is_detected(self):
        source, preview, text = fixture()
        text = text.replace('{0,1,2,3,4,5,0,0}', '{0,2,1,3,4,5,0,0}')
        preview = copy.deepcopy(preview)
        preview['ar']['positions'][1:3] = preview['ar']['positions'][1:3][::-1]
        with self.assertRaises(AssertionError):
            validate_c(source, preview, text)

    def test_color_cap_is_relative_to_original_corner(self):
        source, preview, text = fixture()
        text = text.replace('0x646464ff', '0xc86464ff', 1)
        preview = copy.deepcopy(preview)
        preview['ar']['colors'][0] = [200, 100, 100]
        with self.assertRaisesRegex(AssertionError, 'source color drift'):
            validate_c(source, preview, text)

    def test_index_outside_loaded_batch_fails(self):
        source, preview, text = fixture()
        text = text.replace('{0,1,2,3,4,5,0,0}', '{0,1,2,3,4,6,0,0}')
        with self.assertRaises(AssertionError):
            validate_c(source, preview, text)


if __name__ == '__main__':
    unittest.main()
