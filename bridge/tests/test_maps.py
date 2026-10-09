import struct
import unittest
import zlib

from pda_bridge.maps import dds_to_png, parse_level_map


def _dxt5_solid(r: int, g: int, b: int) -> bytes:
    def rgb565(rv, gv, bv):
        return (rv * 31 // 255) << 11 | (gv * 63 // 255) << 5 | (bv * 31 // 255)

    c0 = rgb565(r, g, b)
    block = bytes((255, 0)) + b"\x00" * 6 + struct.pack("<HH", c0, 0) + b"\x00" * 4
    header = bytearray(128)
    header[:4] = b"DDS "
    struct.pack_into("<I", header, 12, 4)
    struct.pack_into("<I", header, 16, 4)
    header[84:88] = b"DXT5"
    return bytes(header) + block


class MapParseTest(unittest.TestCase):
    def test_level_map_ignores_sub_level(self) -> None:
        text = """
[level_map]
bound_rect = -335.000000,-630.000000,415.000000,870.000000
texture = map\\map_escape
[sub_level_map]
bound_rect = 1,2,3,4
texture = map\\map_other
"""
        self.assertEqual(parse_level_map(text), (-335.0, -630.0, 415.0, 870.0, "map\\map_escape"))

    def test_rejects_empty_rect(self) -> None:
        self.assertIsNone(parse_level_map("[level_map]\nbound_rect = 1, 1, 1, 2\ntexture = map\\map_x\n"))

    def test_solid_dxt5_becomes_png(self) -> None:
        png = dds_to_png(_dxt5_solid(200, 10, 10))
        self.assertIsNotNone(png)
        assert png is not None
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        rest = png[8:]
        payload = b""
        while rest:
            length = struct.unpack(">I", rest[:4])[0]
            tag, chunk, rest = rest[4:8], rest[8 : 8 + length], rest[12 + length :]
            if tag == b"IDAT":
                payload += chunk
        raw = zlib.decompress(payload)
        # Filter byte then RGB. One 4x4 block becomes one pixel.
        self.assertEqual(raw[0], 0)
        self.assertGreater(raw[1], 180)
        self.assertLess(raw[2], 40)
        self.assertLess(raw[3], 40)


if __name__ == "__main__":
    unittest.main()
