"""Local PDA map photos from the installed game.

Level bounds live in each level's level.ltx inside Anomaly's level archives.
The picture is a DDS next to the game (GAMMA's high-res map mod, or another
mod that wins in MO2). Nothing from the install is copied into the repository.
"""

from __future__ import annotations

import logging
import re
import struct
import subprocess
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("pda.map")

_LEVEL_ID = re.compile(r"^[A-Za-z0-9_]+$")
_BOUND = re.compile(
    r"bound_rect\s*=\s*(-?\d+(?:\.\d+)?)f?\s*,\s*(-?\d+(?:\.\d+)?)f?\s*,\s*(-?\d+(?:\.\d+)?)f?\s*,\s*(-?\d+(?:\.\d+)?)f?",
    re.I,
)
_TEXTURE = re.compile(r"texture\s*=\s*(\S+)")
_CREATE_NO_WINDOW = 0x08000000


@dataclass(frozen=True)
class LevelMap:
    level: str
    x1: float
    z1: float
    x2: float
    z2: float
    texture: str

    def as_dict(self, image: str | None) -> dict:
        body = {
            "level": self.level,
            "x1": self.x1,
            "z1": self.z1,
            "x2": self.x2,
            "z2": self.z2,
            "texture": self.texture,
        }
        if image:
            body["image"] = image
        return body


def parse_level_map(text: str) -> tuple[float, float, float, float, str] | None:
    """Read [level_map] only. [sub_level_map] uses the same keys and must not win."""
    section = None
    bounds = None
    texture = None
    for raw in text.splitlines():
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            if section == "level_map" and bounds and texture:
                break
            section = line[1:-1].strip()
            continue
        if section != "level_map":
            continue
        found = _BOUND.search(line)
        if found:
            bounds = tuple(float(part) for part in found.groups())
            continue
        found = _TEXTURE.search(line)
        if found:
            texture = found.group(1).replace("/", "\\")
    if not bounds or not texture:
        return None
    x1, z1, x2, z2 = bounds
    if x2 <= x1 or z2 <= z1:
        return None
    return x1, z1, x2, z2, texture


def _rgb565(value: int) -> tuple[int, int, int]:
    return (
        ((value >> 11) & 31) * 255 // 31,
        ((value >> 5) & 63) * 255 // 63,
        (value & 31) * 255 // 31,
    )


def _dxt_palette(c0: int, c1: int) -> list[tuple[int, int, int]]:
    r0, g0, b0 = _rgb565(c0)
    r1, g1, b1 = _rgb565(c1)
    if c0 > c1:
        return [
            (r0, g0, b0),
            (r1, g1, b1),
            ((2 * r0 + r1) // 3, (2 * g0 + g1) // 3, (2 * b0 + b1) // 3),
            ((r0 + 2 * r1) // 3, (g0 + 2 * g1) // 3, (b0 + 2 * b1) // 3),
        ]
    return [
        (r0, g0, b0),
        (r1, g1, b1),
        ((r0 + r1) // 2, (g0 + g1) // 2, (b0 + b1) // 2),
        (0, 0, 0),
    ]


def _block_average(colors: list[tuple[int, int, int]], indices: list[int]) -> tuple[int, int, int]:
    r = g = b = 0
    for index in indices:
        cr, cg, cb = colors[index]
        r += cr
        g += cg
        b += cb
    n = len(indices)
    return r // n, g // n, b // n


def dds_to_png(data: bytes) -> bytes | None:
    """DXT1/DXT5 to PNG, one pixel per 4x4 block. Other formats are skipped."""
    if len(data) < 128 or data[:4] != b"DDS ":
        return None
    height, width = struct.unpack_from("<II", data, 12)
    fourcc = data[84:88]
    if width < 4 or height < 4 or width % 4 or height % 4:
        return None
    if fourcc == b"DXT1":
        block = 8
    elif fourcc == b"DXT5":
        block = 16
    else:
        return None
    blocks_x, blocks_y = width // 4, height // 4
    needed = 128 + blocks_x * blocks_y * block
    if len(data) < needed:
        return None
    rgb = bytearray(blocks_x * blocks_y * 3)
    offset = 128
    pixel = 0
    for _by in range(blocks_y):
        for _bx in range(blocks_x):
            chunk = data[offset : offset + block]
            offset += block
            color_at = 8 if block == 16 else 0
            c0, c1 = struct.unpack_from("<HH", chunk, color_at)
            bits = struct.unpack_from("<I", chunk, color_at + 4)[0]
            indices = [(bits >> (2 * i)) & 3 for i in range(16)]
            r, g, b = _block_average(_dxt_palette(c0, c1), indices)
            rgb[pixel : pixel + 3] = bytes((r, g, b))
            pixel += 3
    return _png(blocks_x, blocks_y, bytes(rgb))


def _png(width: int, height: int, rgb: bytes) -> bytes:
    def chunk(tag: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + rgb[y * width * 3 : (y + 1) * width * 3] for y in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")


class MapLibrary:
    def __init__(self, roots: list[Path], cache: Path) -> None:
        self.roots = [p for p in roots if p.is_dir()]
        self.cache = cache
        self._levels: dict[str, LevelMap | None] = {}
        self._png: dict[str, bytes | None] = {}
        self._textures: dict[str, Path] | None = None

    def describe(self, level: str | None) -> dict | None:
        found = self.level(level) if level else None
        if not found:
            return None
        ready = self._png.get(found.level) or (self.cache / "png" / f"{found.level}.png").is_file()
        image = f"/api/map/{found.level}.png" if ready or self._find_texture(found.texture) else None
        return found.as_dict(image)

    def level(self, level_id: str) -> LevelMap | None:
        if not _LEVEL_ID.match(level_id):
            return None
        if level_id not in self._levels:
            self._levels[level_id] = self._load_level(level_id)
        return self._levels[level_id]

    def png(self, level_id: str) -> bytes | None:
        if level_id in self._png:
            return self._png[level_id]
        info = self.level(level_id)
        if not info:
            self._png[level_id] = None
            return None
        cached = self.cache / "png" / f"{level_id}.png"
        if cached.is_file():
            self._png[level_id] = cached.read_bytes()
            return self._png[level_id]
        path = self._find_texture(info.texture)
        if path is None:
            log.info("текстура карты не найдена: %s (%s)", info.texture, level_id)
            self._png[level_id] = None
            return None
        try:
            png = dds_to_png(path.read_bytes())
        except OSError as exc:
            log.warning("не прочитан %s: %s", path, exc)
            png = None
        if png is None:
            log.warning("DDS карты не разобран: %s", path)
        else:
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_bytes(png)
            log.info("карта %s: %s (%d КБ)", level_id, path, len(png) // 1024)
        self._png[level_id] = png
        return png

    def _load_level(self, level_id: str) -> LevelMap | None:
        text = self._level_ltx(level_id)
        if text is None:
            return None
        parsed = parse_level_map(text)
        if not parsed:
            log.info("в level.ltx нет [level_map] для %s", level_id)
            return None
        x1, z1, x2, z2, texture = parsed
        return LevelMap(level_id, x1, z1, x2, z2, texture)

    def _level_ltx(self, level_id: str) -> str | None:
        cached = self.cache / "ltx" / level_id / "level.ltx"
        if cached.is_file():
            return cached.read_text(encoding="cp1251", errors="replace")
        anomaly = self._anomaly_root()
        db = anomaly / "db" / "levels" / f"level_{level_id}.db0" if anomaly else None
        converter = anomaly / "tools" / "converter.exe" if anomaly else None
        if not db or not db.is_file() or not converter or not converter.is_file():
            return None
        dest = self.cache / "ltx" / level_id
        dest.mkdir(parents=True, exist_ok=True)
        try:
            flags = {"creationflags": _CREATE_NO_WINDOW} if sys.platform == "win32" else {}
            subprocess.run(
                [str(converter), "-unpack", "-xdb", str(db), "-dir", str(dest), "-flt", "level.ltx"],
                check=False,
                capture_output=True,
                timeout=120,
                **flags,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            log.warning("converter не достал level.ltx для %s: %s", level_id, exc)
            return None
        found = next(dest.rglob("level.ltx"), None)
        if found is None:
            return None
        if found.resolve() != cached.resolve():
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_bytes(found.read_bytes())
        return cached.read_text(encoding="cp1251", errors="replace")

    def _anomaly_root(self) -> Path | None:
        for root in self.roots:
            if (root / "tools" / "converter.exe").is_file() and (root / "db" / "levels").is_dir():
                return root
        return None

    def _find_texture(self, texture: str) -> Path | None:
        name = texture.replace("/", "\\").split("\\")[-1]
        if not name or not _LEVEL_ID.match(name):
            return None
        file_name = name + ".dds"
        if self._textures is None:
            self._textures = self._index_textures()
        return self._textures.get(file_name.lower())

    def _index_textures(self) -> dict[str, Path]:
        """Later MO2 mods overwrite earlier ones. Loose files beat the archives."""
        found: dict[str, Path] = {}
        for folder in self._texture_folders():
            if not folder.is_dir():
                continue
            for path in folder.glob("*.dds"):
                found[path.name.lower()] = path
        return found

    def _texture_folders(self) -> list[Path]:
        folders: list[Path] = []
        gamma = next((root for root in self.roots if (root / "mods").is_dir() and root.name.lower() == "gamma"), None)
        anomaly = self._anomaly_root()
        if anomaly:
            folders.append(anomaly / "gamedata" / "textures" / "map")
            folders.append(anomaly / "gamedata" / "textures" / "ui")
        if gamma:
            profiles = gamma / "profiles"
            modlists = sorted(profiles.glob("*/modlist.txt")) if profiles.is_dir() else []
            # The profile that was written last is the one MO2 is using.
            modlists.sort(key=lambda path: path.stat().st_mtime)
            if modlists:
                enabled = [
                    line[1:].strip()
                    for line in modlists[-1].read_text(encoding="utf-8", errors="replace").splitlines()
                    if line.startswith("+") and line[1:].strip()
                ]
                for name in enabled:
                    mod = gamma / "mods" / name / "gamedata" / "textures"
                    folders.append(mod / "map")
                    folders.append(mod / "ui")
                profile = modlists[-1].parent
                folders.append(profile / "overwrite" / "gamedata" / "textures" / "map")
                folders.append(profile / "overwrite" / "gamedata" / "textures" / "ui")
        return folders
