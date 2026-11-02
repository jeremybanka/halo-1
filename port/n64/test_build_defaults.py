"""The distributable cartridge contains both multiplayer and Firefight."""
import unittest
from build import parse_args,rom_name

class UnifiedCartridge(unittest.TestCase):
    def test_default_and_explicit_combined_game(self):
        for flags in ([],['--firefight']):
            with self.subTest(flags=flags):
                args=parse_args(flags);self.assertTrue(args.firefight);self.assertFalse(args.pve_squad);self.assertEqual(rom_name(args)+'.z64','halo-64.z64')
    def test_multiplayer_only_is_explicitly_named_diagnostic(self):
        args=parse_args(['--no-firefight']);self.assertFalse(args.firefight);self.assertEqual(rom_name(args)+'.z64','halo-64-multiplayer-only.z64')
    def test_direct_squad_diagnostic_stays_separate_from_menu_boot(self):
        args=parse_args(['--pve-squad']);self.assertFalse(args.firefight);self.assertTrue(args.pve_squad)
    def test_native_inspections_use_the_combined_runtime(self):
        for page in range(7):
            args=parse_args(['--gungnir-qa',str(page)]);self.assertTrue(args.firefight);self.assertTrue(args.model_qa)
    def test_firefight_frontend_can_still_drive_production_menus(self):
        args=parse_args(['--firefight-qa','4']);self.assertTrue(args.firefight);self.assertEqual(args.frontend_qa,4)

if __name__=='__main__':unittest.main()
