"""Find where the game addon actually wrote its snapshots.

Under Mod Organizer 2 files the game creates inside the virtual game folder
land in the profile's overwrite folder, not where the game thinks they are.

A GAMMA install is two different folders at the root of the same drive, never
one inside the other. The install guide uses C:\\Anomaly and C:\\GAMMA.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

MARKERS = ("pda_fast.json", "pda_slow.json", "pda_report.txt")
SKIP_DIRS = {"gamedata", "db", "bin", "shaders_cache", "node_modules", ".git", "downloads"}
MAX_DEPTH = 6
# Official layout: two sibling folders at a drive root (C:\Anomaly, C:\GAMMA).
INSTALL_DIR_NAMES = ("Anomaly", "GAMMA")
_DRIVE = re.compile(r"^[A-Za-z]:")


@dataclass
class Found:
    directory: Path
    fast_mtime: float | None
    has_report: bool

    def describe(self, now: float | None = None) -> str:
        now = time.time() if now is None else now
        if self.fast_mtime is None:
            age = "pda_fast.json нет, только отчёт"
        else:
            age = f"pda_fast.json обновлён {max(0, now - self.fast_mtime):.0f} с назад"
        return f"{self.directory}  ({age})"


def windows_drive(path: Path) -> str | None:
    text = str(path.expanduser()).replace("/", "\\")
    if _DRIVE.match(text):
        return text[:2].upper()
    return None


def _is_drive_root(path: Path) -> bool:
    text = str(path).replace("/", "\\").rstrip("\\")
    return bool(re.fullmatch(r"[A-Za-z]:", text))


def standard_install_dirs(path: Path) -> list[Path]:
    """Anomaly and GAMMA at the root of the same Windows drive as path."""
    drive = windows_drive(path)
    if drive is None:
        return []
    return [Path(f"{drive}\\{name}") for name in INSTALL_DIR_NAMES]


def as_windows_path(path: Path) -> Path:
    """C:/GAMMA and C:\\GAMMA become the same path. Other paths stay as they are."""
    drive = windows_drive(path)
    if drive is None:
        return path.expanduser()
    rest = str(path.expanduser()).replace("/", "\\")[2:].lstrip("\\")
    if not rest:
        return Path(drive + "\\")
    return Path(drive + "\\" + rest)


def search_roots(given: list[Path], exists=None) -> list[Path]:
    """Folders to scan: what the user named, plus the sibling install on that drive.

    C:\\GAMMA also searches C:\\Anomaly, and the other way around. A bare drive
    such as C:\\ is not walked; only the two install folders are.
    """
    is_dir = exists or (lambda p: p.expanduser().is_dir())
    ordered: list[Path] = []
    seen: set[str] = set()
    candidates: list[Path] = []
    for path in given:
        expanded = as_windows_path(path)
        candidates.append(expanded)
        candidates.extend(standard_install_dirs(expanded))
    for path in candidates:
        if _is_drive_root(path) or not is_dir(path):
            continue
        key = str(path).replace("/", "\\").rstrip("\\").lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(path)
    return ordered


def find_snapshot_dirs(roots: list[Path], max_depth: int = MAX_DEPTH) -> list[Found]:
    found: dict[Path, Found] = {}
    for root in roots:
        root = root.expanduser()
        if not root.is_dir():
            continue
        base_depth = len(root.resolve().parts)
        for current, dirs, files in os.walk(root):
            here = Path(current)
            depth = len(here.resolve().parts) - base_depth
            dirs[:] = [] if depth >= max_depth else [d for d in dirs if d.lower() not in SKIP_DIRS]
            names = set(files)
            if not names.intersection(MARKERS):
                continue
            fast = here / "pda_fast.json"
            found[here.resolve()] = Found(
                directory=here.resolve(),
                fast_mtime=fast.stat().st_mtime if fast.exists() else None,
                has_report="pda_report.txt" in names,
            )
    return sorted(found.values(), key=lambda f: f.fast_mtime or 0, reverse=True)
