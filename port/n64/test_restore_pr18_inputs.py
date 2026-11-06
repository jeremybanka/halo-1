import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from restore_pr18_inputs import BASE_ASSET_REF, MAP_NAMES, PACKAGE, SOURCE_REF, restore


def info(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


class RestoreTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bank = self.root / "bank"
        self.package = self.bank / PACKAGE
        self.package.mkdir(parents=True)
        self.output = self.root / "restored"
        self.data = {}
        self.manifest = {"schema": 1, "source_ref": SOURCE_REF, "base_asset_ref": BASE_ASSET_REF,
                         "maps": {}, "enemy_bank": {}, "reference_rom": {}}
        for name in sorted(MAP_NAMES):
            data = name.encode() * 10
            self.data[name] = data
            parts = []
            for i, block in enumerate((data[:20], data[20:])):
                compressed = gzip.compress(block, mtime=0)
                path = name + f".{i}.gz"
                (self.package / path).write_bytes(compressed)
                parts.append({"path": path, **info(compressed), "raw_bytes": len(block), "raw_sha256": info(block)["sha256"]})
            self.manifest["maps"][name] = {**info(data), "parts": parts}
        member = self.bank / "assets/vehicle_distance_data.c"
        member.write_bytes(b"distance bank\n")
        self.manifest["enemy_bank"][member.name] = {"path": "assets/" + member.name, **info(member.read_bytes())}
        self.save()

    def save(self):
        (self.package / "manifest.json").write_text(json.dumps(self.manifest))

    def test_restores_exact_maps_overlay_and_links(self):
        restore(self.bank, self.output)
        for name, expected in self.data.items():
            self.assertEqual((self.output / "assets" / name).read_bytes(), expected)
            self.assertEqual((self.bank / "assets" / name).read_bytes(), expected)
        self.assertEqual((self.output / "enemy-bank/vehicle_distance_data.c").read_bytes(), b"distance bank\n")

    def test_corruption_rejected_before_output_or_links(self):
        part = next(iter(self.manifest["maps"].values()))["parts"][0]
        (self.package / part["path"]).write_bytes(b"corrupt")
        with self.assertRaises(ValueError):
            restore(self.bank, self.output)
        self.assertFalse(self.output.exists())

    def test_never_overwrites_conflicting_map(self):
        name = next(iter(self.data))
        path = self.bank / "assets" / name
        path.write_bytes(b"keep my local work")
        with self.assertRaises(ValueError):
            restore(self.bank, self.output)
        self.assertEqual(path.read_bytes(), b"keep my local work")
        self.assertFalse(self.output.exists())

    def test_rejects_path_escape(self):
        part = next(iter(self.manifest["maps"].values()))["parts"][0]
        part["path"] = "../../outside.gz"
        self.save()
        with self.assertRaises(ValueError):
            restore(self.bank, self.output)

    def test_uncompressed_digest_checked_before_links(self):
        name = next(iter(self.data))
        self.manifest["maps"][name]["sha256"] = "0" * 64
        self.save()
        with self.assertRaises(ValueError):
            restore(self.bank, self.output)
        self.assertFalse((self.bank / "assets" / name).exists())

    def test_existing_output_is_preserved(self):
        self.output.mkdir()
        (self.output / "retained.txt").write_text("keep")
        with self.assertRaises(FileExistsError):
            restore(self.bank, self.output)
        self.assertEqual((self.output / "retained.txt").read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
