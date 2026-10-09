"""Local-asset regression checks for additional banks, aliases and input guards."""
import contextlib
import copy
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from pack_micro_lods import ROOT, pack


class MicroPackingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generated = ROOT/'build/n64/generated'
        cls.source = ROOT/'build/n64/assets/micro-lods.json'
        if not cls.source.exists() or not (cls.generated/'micro_data.c').exists():
            raise unittest.SkipTest('Generate local game assets before packing regression tests')
        cls.models = json.loads(cls.source.read_text())

    def setUp(self):
        folder = ROOT/'build/n64/tests'
        folder.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='micro-pack-', dir=folder)
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)

    def run_pack(self, value):
        source = self.path/'source.json'
        source.write_text(json.dumps(value))
        with contextlib.redirect_stdout(io.StringIO()):
            pack(source, self.path/'packed', self.generated)
        return (self.path/'packed/micro_data.c').read_text()

    def test_repack_matches_reviewed_bank_and_preserves_existing_bank(self):
        before = (self.generated/'models_data.c').read_bytes()
        self.assertEqual(self.run_pack(self.models), (self.generated/'micro_data.c').read_text())
        self.assertEqual(before, (self.generated/'models_data.c').read_bytes())

    def test_absent_models_alias_existing_data_and_keep_original_bounds(self):
        text = self.run_pack({'models': {}})
        self.assertNotIn('static T3DVertPacked micro_', text)
        self.assertEqual(text.count('&bg_vehicle_lods['), 4)
        self.assertEqual(text.count('&bg_pickup_lods['), 19)
        original = (self.generated/'models_data.c').read_text()
        def rows(source, symbol):
            return re.search(r'const bg_bounds '+symbol+r'\[[^]]+\]=\{(.*?)\n\};', source, re.S)[1]
        self.assertEqual(rows(original, 'bg_model_cull_bounds'), rows(text, 'bg_pickup_micro_gate_bounds'))
        self.assertEqual(rows(original, 'bg_vehicle_lod_bounds'), rows(text, 'bg_vehicle_micro_gate_bounds'))

    def test_nonfinite_geometry_is_rejected(self):
        bad = copy.deepcopy(self.models)
        next(iter(bad['models'].values()))['positions'][0][0] = float('nan')
        with self.assertRaises(AssertionError):
            self.run_pack(bad)

    def test_invalid_material_cardinality_is_rejected(self):
        bad = copy.deepcopy(self.models)
        next(iter(bad['models'].values()))['materials'] = []
        with self.assertRaises(AssertionError):
            self.run_pack(bad)

    def test_team_colored_or_animated_asset_cannot_enter_static_bank(self):
        bad = copy.deepcopy(self.models)
        model = next(iter(bad['models'].values()))
        model['team_mask'] = [255]*len(model['positions'])
        with self.assertRaises(AssertionError):
            self.run_pack(bad)

    def test_derived_content_cannot_be_written_into_source_directory(self):
        with self.assertRaises(ValueError):
            pack(self.source, ROOT/'port/n64', self.generated)


if __name__ == '__main__':
    unittest.main()
