"""Pack the game addon into a zip that Mod Organizer 2 installs as is.

    python3 tools/pack_addon.py   ->  dist/stalker-pda-addon-<version>.zip
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "addon" / "stalker_pda"
DIST = ROOT / "dist"


def addon_version() -> str:
    src = (ADDON / "gamedata" / "scripts" / "xpda_export.script").read_text("utf-8")
    match = re.search(r'^VERSION = "([^"]+)"', src, re.M)
    if not match:
        raise SystemExit("VERSION не найден в xpda_export.script")
    return match.group(1)


def main() -> int:
    DIST.mkdir(exist_ok=True)
    target = DIST / f"stalker-pda-addon-{addon_version()}.zip"
    files = sorted(p for p in ADDON.rglob("*") if p.is_file())
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, path.relative_to(ADDON).as_posix())
    print(target)
    for path in files:
        print("  " + path.relative_to(ADDON).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())
