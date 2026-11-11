"""Exercise corruption, path isolation, repeat use and historical verification."""
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import subprocess
import tarfile
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'port/n64'))
sys.path.insert(0, str(ROOT/'tools'))
from build_inputs import MAPS, PACKAGE, PackageReader, connect, digest, restore
from n64 import verify_bank, locked_bank, checked_output
from n64_toolchain import unpack, deb_payload


def record(data):
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


class InputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bank = self.root/'halo64-assets'
        self.package = self.bank/PACKAGE
        self.package.mkdir(parents=True)
        self.data = {n: (n+'\n').encode()*7 for n in MAPS}
        self.m = {'schema': 1, 'maps': {}, 'enemy_bank': {}}
        for n, raw in self.data.items():
            compressed = gzip.compress(raw, mtime=0)
            (self.package/(n+'.gz')).write_bytes(compressed)
            self.m['maps'][n] = {**record(raw), 'parts': [{**record(compressed),
                'path': n+'.gz', 'raw_bytes': len(raw), 'raw_sha256': record(raw)['sha256']}]}
        self.save()
        self.reader = PackageReader(bank=self.bank)
        self.cache = self.root/'build/cache'

    def save(self):
        p = self.package/'manifest.json'
        p.write_text(json.dumps(self.m))
        self.expected = digest(p)

    def test_restore_repeat_and_links(self):
        restored, m = restore(self.reader, self.cache, self.expected)
        connect(self.root, restored, m)
        before = {n: (restored/n).stat().st_ino for n in MAPS}
        with mock.patch.object(self.reader, 'read', wraps=self.reader.read) as read:
            again, _ = restore(self.reader, self.cache, self.expected)
            self.assertEqual(read.call_count, 1)  # manifest only, no decompression
        self.assertEqual(restored, again)
        self.assertEqual(before, {n: (restored/n).stat().st_ino for n in MAPS})
        for n in MAPS:
            dest = self.bank/'assets'/n if n.endswith('-decompressed.map') else self.root/'build/assets/halo-retail/maps'/n
            self.assertEqual(dest.read_bytes(), self.data[n])

    def test_wrong_manifest_does_not_restore(self):
        with self.assertRaises(ValueError):
            restore(self.reader, self.cache, '0'*64)
        self.assertFalse(self.cache.exists())

    def test_compressed_corruption_does_not_publish(self):
        n = next(iter(MAPS))
        (self.package/(n+'.gz')).write_bytes(b'corrupt')
        with self.assertRaises(ValueError):
            restore(self.reader, self.cache, self.expected)
        self.assertFalse((self.cache/self.expected).exists())
        self.assertFalse((self.bank/'assets/a30-decompressed.map').exists())

    def test_uncompressed_corruption_does_not_publish(self):
        self.m['maps'][next(iter(MAPS))]['parts'][0]['raw_sha256'] = '0'*64
        self.save()
        with self.assertRaises(ValueError):
            restore(self.reader, self.cache, self.expected)
        self.assertFalse((self.cache/self.expected).exists())

    def test_corrupt_cache_is_preserved_and_rejected(self):
        restored, _ = restore(self.reader, self.cache, self.expected)
        p = restored/next(iter(MAPS)); p.write_bytes(b'keep for diagnosis')
        with self.assertRaises(ValueError):
            restore(self.reader, self.cache, self.expected)
        self.assertEqual(p.read_bytes(), b'keep for diagnosis')

    def test_conflicting_existing_file_is_preserved(self):
        restored, m = restore(self.reader, self.cache, self.expected)
        p = self.bank/'assets/a30-decompressed.map'; p.parent.mkdir(exist_ok=True); p.write_bytes(b'local work')
        with self.assertRaises(ValueError):
            connect(self.root, restored, m)
        self.assertEqual(p.read_bytes(), b'local work')
        self.assertFalse((self.root/'build/assets').exists())

    def test_external_parent_symlink_is_rejected(self):
        restored, m = restore(self.reader, self.cache, self.expected)
        external = self.root/'outside'; external.mkdir()
        # A sibling of the checkout represents another worktree/archive.
        checkout = self.root/'checkout'; checkout.mkdir()
        (checkout/'halo64-assets').symlink_to(self.bank, target_is_directory=True)
        with self.assertRaises(ValueError):
            connect(checkout, restored, m)

    def test_package_traversal_is_rejected(self):
        self.m['maps'][next(iter(MAPS))]['parts'][0]['path'] = '../escape.gz'
        self.save()
        with self.assertRaises(ValueError):
            restore(self.reader, self.cache, self.expected)

    def test_oversized_chunk_is_rejected(self):
        part = self.m['maps'][next(iter(MAPS))]['parts'][0]
        part['raw_bytes'] = 33*1024*1024
        self.save()
        with self.assertRaises(ValueError):
            restore(self.reader, self.cache, self.expected)


class VerificationTests(unittest.TestCase):
    def test_output_cannot_escape_guarded_cache(self):
        with tempfile.TemporaryDirectory() as t:
            cache=Path(t)/'build/n64-bootstrap'; cache.mkdir(parents=True)
            self.assertEqual(checked_output(cache, cache/'new-rom'), (cache/'new-rom').resolve())
            with self.assertRaises(ValueError): checked_output(cache, cache.parent/'unreserved')
            with self.assertRaises(ValueError): checked_output(cache, cache)

    def test_debian_compiler_payload_is_extracted_without_installing(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); data=io.BytesIO()
            with tarfile.open(fileobj=data,mode='w:gz') as tar:
                entry=tarfile.TarInfo('opt/libdragon/bin/compiler'); entry.size=3
                tar.addfile(entry,io.BytesIO(b'elf'))
            payload=data.getvalue()
            header=f'{"data.tar.gz/":<16}{0:<12}{0:<6}{0:<6}{"100644":<8}{len(payload):<10}`\n'.encode()
            archive=root/'compiler.deb';archive.write_bytes(b'!<arch>\n'+header+payload)
            files=deb_payload(archive,root/'expanded')
            self.assertEqual((files/'opt/libdragon/bin/compiler').read_bytes(),b'elf')

    def test_fresh_asset_initialization_uses_exact_pin(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); repo = root/'remote'; repo.mkdir()
            def git(*args):
                return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.DEVNULL, text=True).strip()
            git('init'); git('config', 'user.name', 'Test'); git('config', 'user.email', 'test@example.invalid')
            (repo/'asset.txt').write_text('immutable source asset\n')
            git('add', 'asset.txt'); git('commit', '-m', 'asset')
            pin = git('rev-parse', 'HEAD')
            checkout = root/'checkout'; checkout.mkdir(); cache = checkout/'build/cache'; cache.mkdir(parents=True)
            bank = locked_bank(checkout, cache, pin, str(repo))
            self.assertEqual((bank/'asset.txt').read_text(), 'immutable source asset\n')
            self.assertEqual(subprocess.check_output(['git', '-C', str(bank), 'rev-parse', 'HEAD'], text=True).strip(), pin)
            self.assertEqual(locked_bank(checkout, cache, pin, str(repo)), bank)

    def test_historical_correction_is_exactly_scoped(self):
        with tempfile.TemporaryDirectory() as t:
            b = Path(t); (b/'report.json').write_bytes(b'published report')
            old = record(b'older report!!!!')
            old['bytes'] = len(b'published report')
            (b/'bank-manifest.json').write_text(json.dumps({'files': [{'path': 'report.json', **old}]}))
            correction = {'recorded_sha256': old['sha256'], 'published_sha256': digest(b/'report.json')}
            lock = {'historical_snapshot_corrections': {'exact-pin': {'report.json': correction}}}
            self.assertEqual(len(verify_bank(b, 'exact-pin', lock)['historical_corrections']), 1)
            with self.assertRaises(ValueError): verify_bank(b, 'other-pin', lock)
            (b/'report.json').write_bytes(b'different report')
            with self.assertRaises(ValueError): verify_bank(b, 'exact-pin', lock)

    def test_archive_cannot_escape(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); archive = root/'bad.tar'
            with tarfile.open(archive, 'w') as tar:
                info = tarfile.TarInfo('../escape'); info.size = 1
                tar.addfile(info, io.BytesIO(b'x'))
            with self.assertRaises((tarfile.FilterError, ValueError)):
                unpack(archive, root/'expanded')
            self.assertFalse((root/'escape').exists())


if __name__ == '__main__':
    unittest.main()
