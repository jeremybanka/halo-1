"""SVOD reads must skip hash tables and reject incomplete or unsafe volumes."""
import struct
import tempfile
import unittest
from pathlib import Path

from extract_svod import SvodReader


class SvodTests(unittest.TestCase):
    def test_reads_across_subpart_hash_and_part_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with (root/'Data0000').open('wb') as f:
                f.seek(2*0x1000+SvodReader.GROUP_DATA-3);f.write(b'abc')
                f.seek(3*0x1000+SvodReader.GROUP_DATA);f.write(b'def')
                f.seek(2*0x1000+202*(SvodReader.GROUP_DATA+0x1000)+SvodReader.GROUP_DATA-3)
                f.write(b'ghi')
            with (root/'Data0001').open('wb') as f:
                f.seek(2*0x1000);f.write(b'jkl')
            reader=SvodReader(root)
            try:
                self.assertEqual(reader.read_at(SvodReader.GROUP_DATA-3,6),b'abcdef')
                self.assertEqual(reader.read_at(SvodReader.PART_DATA-3,6),b'ghijkl')
                with self.assertRaises(ValueError):reader.read_at(SvodReader.PART_DATA,4)
                with self.assertRaises(FileNotFoundError):reader.read_at(2*SvodReader.PART_DATA,1)
            finally:reader.close()

    def test_directory_names_and_truncated_entries_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in (b'..',b'../escape',b'a\\b',b'a/b'):
                entry=struct.pack('<HHIIBB',0,0,90,12,0,len(name))+name
                descriptor=bytearray(2048)
                descriptor[:20]=descriptor[-20:]=b'MICROSOFT*XBOX*MEDIA'
                struct.pack_into('<II',descriptor,20,40,len(entry))
                with (root/'Data0000').open('wb') as f:
                    f.seek(0x2000+32*2048);f.write(descriptor)
                    f.seek(0x2000+40*2048);f.write(entry)
                reader=SvodReader(root)
                try:
                    with self.assertRaises(ValueError):list(reader.files())
                finally:reader.close()


if __name__=='__main__':unittest.main()
