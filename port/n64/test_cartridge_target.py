import unittest
from build import cartridge_target


class SummerCartTarget(unittest.TestCase):
    def test_extended_rom_capacity(self):
        self.assertFalse(cartridge_target(64*1024*1024)['extended_rom_required'])
        self.assertTrue(cartridge_target(78*1024*1024)['extended_rom_required'])
        with self.assertRaisesRegex(SystemExit,'78 MiB'):cartridge_target(78*1024*1024+1)


if __name__=='__main__':unittest.main()
