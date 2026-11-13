import hashlib
from pathlib import Path
import tempfile
import unittest
from character_validation import verify_gungnir


class CharacterValidation(unittest.TestCase):
    def test_shared_runtime_change_preserves_asset_gate_and_records_provenance(self):
        for shared in ('hud.c','game.c'):
            with self.subTest(shared=shared):self.check_shared_runtime(shared)

    def check_shared_runtime(self,shared):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            paths=['port/n64/'+shared,'port/n64/gungnir_render.c','halo64-assets/generated/gungnir/gungnir.bin']
            for name in paths:
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'original')
            digest=hashlib.sha256(b'original').hexdigest()
            certificate={'inputs':{n:digest for n in paths[:2]},'files':{paths[2]:digest}}
            self.assertEqual(verify_gungnir(root,certificate),{})
            (root/paths[0]).write_bytes(b'new shared runtime')
            changes=verify_gungnir(root,certificate)
            self.assertEqual(set(changes),{paths[0]});self.assertEqual(changes[paths[0]]['certificate_sha256'],digest)
            (root/paths[1]).write_bytes(b'changed character renderer')
            with self.assertRaisesRegex(ValueError,'Stale GUNGNIR'):verify_gungnir(root,certificate)
            (root/paths[1]).write_bytes(b'original');(root/paths[2]).write_bytes(b'changed bank')
            with self.assertRaisesRegex(ValueError,'Stale GUNGNIR'):verify_gungnir(root,certificate)
            (root/paths[2]).write_bytes(b'original')
            (root/paths[0]).unlink()
            with self.assertRaisesRegex(ValueError,'Missing'):verify_gungnir(root,certificate)


if __name__=='__main__':unittest.main()
