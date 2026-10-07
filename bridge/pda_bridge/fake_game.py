"""Stand-in for the game addon: writes pda_fast.json / pda_slow.json.

Writes in place with no rename, exactly like the Lua side has to, so the
bridge's torn-read handling is exercised by the demo too. Demo data is
invented and marked reader="demo"; it says nothing about real level bounds.
"""

from __future__ import annotations

import json
import logging
import math
import random
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import PROTOCOL
from .channel import FILE_NAMES

log = logging.getLogger("pda.demo")


@dataclass(frozen=True)
class DemoLevel:
    id: str
    name: str
    route: tuple[tuple[float, float], ...]
    radiation_spot: tuple[float, float]


DEMO_LEVELS = (
    DemoLevel(
        "l01_escape",
        "Кордон",
        ((-220, -340), (-120, -260), (-40, -120), (60, -60), (140, 40), (60, 160), (-80, 120), (-180, -40)),
        (60, -60),
    ),
    DemoLevel(
        "l02_garbage",
        "Свалка",
        ((-60, -200), (40, -120), (120, -20), (60, 90), (-60, 140), (-140, 20)),
        (120, -20),
    ),
    DemoLevel(
        "l05_bar",
        "Бар «100 рентген»",
        ((-40, -60), (20, -30), (50, 30), (0, 70), (-50, 20)),
        (50, 30),
    ),
)

WALK_SPEED = 4.5
LEVEL_SECONDS = 75.0
LOADING_SECONDS = 4.0
GAME_TIME_FACTOR = 10.0


class DemoGame:
    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.session = uuid.uuid4().hex[:12]
        self.level_index = 0
        self.leg = 0
        self.x, self.z = DEMO_LEVELS[0].route[0]
        self.y = 12.0
        self.heading = 0.0
        self.health = 0.86
        self.radiation = 0.0
        self.money = 18_450
        self.game_minutes = 8 * 60.0
        self.level_elapsed = 0.0
        self.loading_left = 0.0
        self.dead_left = 0.0

    @property
    def level(self) -> DemoLevel:
        return DEMO_LEVELS[self.level_index]

    def step(self, dt: float) -> None:
        self.game_minutes += dt * GAME_TIME_FACTOR / 60.0
        if self.loading_left > 0:
            self.loading_left -= dt
            return
        if self.dead_left > 0:
            self.dead_left -= dt
            if self.dead_left <= 0:
                self.health = 0.5
                self.radiation = 0.0
                self.session = uuid.uuid4().hex[:12]
            return

        self.level_elapsed += dt
        if self.level_elapsed >= LEVEL_SECONDS:
            self.level_index = (self.level_index + 1) % len(DEMO_LEVELS)
            self.leg = 0
            self.x, self.z = self.level.route[0]
            self.level_elapsed = 0.0
            self.loading_left = LOADING_SECONDS
            log.info("демо: переход на %s", self.level.id)
            return

        route = self.level.route
        tx, tz = route[(self.leg + 1) % len(route)]
        dx, dz = tx - self.x, tz - self.z
        dist = math.hypot(dx, dz)
        if dist < 1.0:
            self.leg = (self.leg + 1) % len(route)
        else:
            move = min(dist, WALK_SPEED * dt)
            self.x += dx / dist * move
            self.z += dz / dist * move
            target = math.degrees(math.atan2(dx, dz)) % 360
            turn = (target - self.heading + 540) % 360 - 180
            self.heading = (self.heading + max(-90 * dt, min(90 * dt, turn))) % 360
        self.y = 12.0 + 1.5 * math.sin(self.x / 40.0) + math.cos(self.z / 55.0)

        rx, rz = self.level.radiation_spot
        if math.hypot(self.x - rx, self.z - rz) < 35:
            self.radiation = min(1.0, self.radiation + 0.04 * dt)
        else:
            self.radiation = max(0.0, self.radiation - 0.01 * dt)
        self.health += (0.004 - 0.03 * self.radiation) * dt
        if self.rng.random() < 0.02 * dt:
            self.health -= self.rng.uniform(0.05, 0.15)
        self.health = max(0.0, min(1.0, self.health))
        if self.health <= 0.0:
            self.dead_left = 6.0
            log.info("демо: персонаж погиб")
        if self.rng.random() < 0.05 * dt:
            self.money += self.rng.choice((-1, 1)) * self.rng.randrange(100, 2500, 50)
            self.money = max(0, self.money)

    def game_state(self) -> str:
        if self.loading_left > 0:
            return "loading"
        if self.dead_left > 0:
            return "dead"
        return "in_game"

    def fast(self) -> dict[str, Any]:
        total = int(self.game_minutes)
        body: dict[str, Any] = {
            "game_state": self.game_state(),
            "level": {"id": self.level.id, "name": self.level.name},
            "game_time": {"day": total // 1440 + 1, "hour": total // 60 % 24, "minute": total % 60},
        }
        if self.loading_left <= 0:
            body.update(
                position={"x": round(self.x, 2), "y": round(self.y, 2), "z": round(self.z, 2)},
                heading_deg=round(self.heading, 1) % 360,
                health=round(self.health, 3),
                radiation=round(self.radiation, 3),
            )
        return body

    def slow(self) -> dict[str, Any]:
        return {
            "reader": "demo",
            "game": {"build": "демо без игры"},
            "capabilities": {
                "player": True,
                "pose": True,
                "map_texture": False,
                "tasks": False,
                "inventory": False,
                "contacts": False,
                "messages": False,
            },
            "player": {"name": "Лис (демо)", "id": 0, "money": self.money},
        }


def encode(kind: str, seq: int, session: str, body: dict[str, Any]) -> bytes:
    doc = {"protocol": PROTOCOL, "kind": kind, "seq": seq, "session": session, **body, "seq_end": seq}
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def write_in_place(path: Path, data: bytes, torn: bool = False) -> None:
    if torn:
        with path.open("wb") as fh:
            fh.write(data[: max(1, len(data) // 2)])
            fh.flush()
            time.sleep(0.06)
            fh.write(data[max(1, len(data) // 2) :])
        return
    path.write_bytes(data)


class DemoWriter:
    def __init__(
        self,
        snapshot_dir: Path,
        fast_hz: float = 10.0,
        slow_hz: float = 1.0,
        torn_rate: float = 0.01,
        game: DemoGame | None = None,
    ) -> None:
        self.snapshot_dir = snapshot_dir
        self.fast_period = 1.0 / fast_hz
        self.slow_period = 1.0 / slow_hz
        self.torn_rate = torn_rate
        self.game = game or DemoGame()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.seq = {"fast": 0, "slow": 0}

    def start(self) -> None:
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        log.info("демо-игра пишет в %s", self.snapshot_dir)
        self._thread = threading.Thread(target=self._run, name="pda-demo", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def write(self, kind: str) -> None:
        self.seq[kind] += 1
        body = self.game.fast() if kind == "fast" else self.game.slow()
        data = encode(kind, self.seq[kind], self.game.session, body)
        torn = self.game.rng.random() < self.torn_rate
        write_in_place(self.snapshot_dir / FILE_NAMES[kind], data, torn=torn)

    def _run(self) -> None:
        last = time.monotonic()
        next_slow = last
        while not self._stop.is_set():
            now = time.monotonic()
            self.game.step(now - last)
            last = now
            self.write("fast")
            if now >= next_slow:
                self.write("slow")
                next_slow = now + self.slow_period
            self._stop.wait(self.fast_period)


class ReplayWriter:
    """Plays back a file recorded with --record, looping forever."""

    def __init__(self, record_path: Path, snapshot_dir: Path) -> None:
        self.record_path = record_path
        self.snapshot_dir = snapshot_dir
        self.lines = [json.loads(l) for l in record_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        if not self.lines:
            raise ValueError(f"в записи {record_path} нет снимков")
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        log.info("проигрываю %s (%d снимков) в %s", self.record_path, len(self.lines), self.snapshot_dir)
        self._thread = threading.Thread(target=self._run, name="pda-replay", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self) -> None:
        loop = 0
        while not self._stop.is_set():
            started = time.monotonic()
            for rec in self.lines:
                wait = rec["t_ms"] / 1000.0 - (time.monotonic() - started)
                if wait > 0 and self._stop.wait(wait):
                    return
                snap = dict(rec["data"])
                # Each loop is a new session so the bridge treats replays as
                # fresh loads instead of stale duplicates.
                snap["session"] = f"{snap['session']}-r{loop}"
                path = self.snapshot_dir / FILE_NAMES[rec["kind"]]
                path.write_bytes(json.dumps(snap, ensure_ascii=False).encode("utf-8"))
            loop += 1
