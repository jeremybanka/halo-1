"""Coverage/metrics checks for the original-font menu asset conversion."""
import unittest
from types import SimpleNamespace as Obj

from extract_menu_assets import FIRST, COUNT, WIDTH, HEIGHT, font_bank


def source_font(width=13, height=10):
    pixels = bytearray()
    chars = []
    for code in range(FIRST, FIRST + COUNT):
        w, h = (-2, 0) if code == FIRST else (width, height)
        chars.append(Obj(character=code, bitmap_width=w, bitmap_height=h,
                         character_width=width + 2, bitmap_origin_x=-1,
                         bitmap_origin_y=height, pixels_offset=len(pixels)))
        pixels.extend((code * 3 + i * 17) % 256 for i in range(max(0, w * h)))
    return Obj(characters=Obj(STEPTREE=chars), pixels=Obj(STEPTREE=pixels))


class FontPackingTests(unittest.TestCase):
    def test_empty_source_bitmap_keeps_advance_without_unsigned_wrap(self):
        _, _, glyphs = font_bank(source_font())
        self.assertEqual(glyphs[0][3:6], [0, 0, 15])

    def test_metrics_and_original_bitmap_samples_are_preserved(self):
        meta = source_font()
        pages, _, glyphs = font_bank(meta)
        for c, g in zip(meta.characters.STEPTREE[1:], glyphs[1:]):
            p, x, y, w, h, advance, ox, oy = g
            self.assertEqual((w, h, advance, ox, oy), (13, 10, 15, -1, 10))
            expected = bytes(meta.pixels.STEPTREE[c.pixels_offset:c.pixels_offset + w*h])
            self.assertEqual(pages[p].crop((x, y, x+w, y+h)).tobytes(), expected)

    def test_i4_is_nearest_coverage_with_no_spatial_resampling(self):
        pages, data, _ = font_bank(source_font())
        source = b''.join(page.tobytes() for page in pages)
        actual = [n for byte in data for n in (byte >> 4, byte & 15)]
        self.assertEqual(actual, [(value + 8) // 17 for value in source])
        self.assertLessEqual(max(abs(value - quant*17) for value, quant in zip(source, actual)), 8)

    def test_each_page_fits_tmem_and_glyphs_have_clear_filter_guards(self):
        pages, data, glyphs = font_bank(source_font())
        self.assertGreater(len(pages), 1)
        self.assertEqual(len(data), len(pages) * 4096)
        occupied = set()
        for p, x, y, w, h, *_ in glyphs:
            self.assertTrue(1 <= x and x+w < WIDTH and 1 <= y and y+h < HEIGHT)
            if not w or not h:
                continue
            for yy in range(y-1, y+h+1):
                for xx in range(x-1, x+w+1):
                    key = p, xx, yy
                    self.assertNotIn(key, occupied)
                    occupied.add(key)
                    if xx in (x-1, x+w) or yy in (y-1, y+h):
                        self.assertEqual(pages[p].getpixel((xx, yy)), 0)

    def test_conversion_is_deterministic(self):
        a = font_bank(source_font())
        b = font_bank(source_font())
        self.assertEqual(a[1:], b[1:])


if __name__ == '__main__':
    unittest.main()
