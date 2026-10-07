"""Find where the game addon actually wrote its snapshots.

Under Mod Organizer 2 files the game creates inside the virtual game folder
land in the profile's overwrite folder, not where the game thinks they are.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

MARKERS = ("pda_fast.json", "pda_slow.json", "pda_report.txt")
SKIP_DIRS = {"gamedata", "db", "bin", "shaders_cache", "node_modules", ".git", "downloads"}
MAX_DEPTH = 6


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
