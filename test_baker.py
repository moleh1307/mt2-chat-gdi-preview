# SPDX-License-Identifier: GPL-2.0-or-later
import importlib.util
from pathlib import Path
import struct
import sys
import unittest
import zlib

spec = importlib.util.spec_from_file_location('baker', Path(__file__).with_name('bake_chat_gdi.py'))
baker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baker)


class BakerChecks(unittest.TestCase):
    def test_engine_abc_uses_truncated_b_and_ceil_advance(self):
        self.assertEqual(baker.engine_metrics(.2, 5.8, .2), (8, 7))
        self.assertEqual(baker.engine_metrics(-.4, 6.2, .1), (8, 6))
        self.assertEqual(baker.engine_metrics(0, 4, 0), (5, 4))

    def test_charset_contains_turkish_and_reference(self):
        chars = baker.character_set()
        self.assertEqual(len(chars), len(set(chars)))
        self.assertTrue(set('ÇĞİÖŞÜçğıöşüYou have gained 11 experience points.').issubset(chars))

    def test_png_preserves_exact_binary_rgba_and_crc(self):
        pixels = b'\xff\xff\xff\xff\0\0\0\0'
        data = baker.png_rgba(2, 1, pixels)
        self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
        pos, idat = 8, b''
        while pos < len(data):
            count = struct.unpack('>I', data[pos:pos + 4])[0]
            name = data[pos + 4:pos + 8]
            payload = data[pos + 8:pos + 8 + count]
            crc = struct.unpack('>I', data[pos + 8 + count:pos + 12 + count])[0]
            self.assertEqual(crc, zlib.crc32(name + payload) & 0xffffffff)
            if name == b'IDAT':
                idat += payload
            pos += count + 12
        self.assertEqual(zlib.decompress(idat), b'\0' + pixels)
        with self.assertRaises(ValueError):
            baker.png_rgba(2, 2, pixels)

    @unittest.skipIf(sys.platform == 'win32', 'Native Windows is the target backend')
    def test_other_platforms_refuse_to_fabricate_gdi_output(self):
        with self.assertRaisesRegex(RuntimeError, 'Native Windows GDI is required'):
            baker.bake()


if __name__ == '__main__':
    unittest.main()
