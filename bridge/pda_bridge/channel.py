"""Read the snapshot files the game writes and track link health."""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import PROTOCOL

KINDS = ("fast", "slow")
FILE_NAMES = {"fast": "pda_fast.json", "slow": "pda_slow.json"}

# Pause menus and main menu stop the game's update callback, so a silent
# file is normal there; the phone must say so instead of freezing.
STALE_AFTER_S = 3.0

log = logging.getLogger("pda.link")


class RejectedSnapshot(ValueError):
    pass


def parse_snapshot(raw: bytes, kind: str) -> dict[str, Any]:
    """Validate one file. Raises RejectedSnapshot with a reason for the log."""
    if not raw:
        raise RejectedSnapshot("пустой файл")
    try:
        data = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise RejectedSnapshot(f"не UTF-8: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RejectedSnapshot(f"оборванный или битый JSON: {exc.msg} в позиции {exc.pos}") from exc
    if not isinstance(data, dict):
        raise RejectedSnapshot("корень не объект")
    if data.get("protocol") != PROTOCOL:
        raise RejectedSnapshot(f"протокол {data.get('protocol')!r}, мост ждёт {PROTOCOL}")
    if data.get("kind") != kind:
        raise RejectedSnapshot(f"kind {data.get('kind')!r} в файле {FILE_NAMES[kind]}")
    seq, seq_end = data.get("seq"), data.get("seq_end")
    if not isinstance(seq, int) or isinstance(seq, bool) or seq != seq_end:
        raise RejectedSnapshot(f"seq {seq!r} не совпадает с seq_end {seq_end!r}")
    if not isinstance(data.get("session"), str) or not data["session"]:
        raise RejectedSnapshot("нет session")
    return data


@dataclass
class KindState:
    snapshot: dict[str, Any] | None = None
    accepted_at: float | None = None
    accepted: int = 0
    rejected: int = 0
    last_reject: str | None = None
    last_stat: tuple[int, int] | None = None


@dataclass
class LinkState:
    kinds: dict[str, KindState] = field(default_factory=lambda: {k: KindState() for k in KINDS})
    version: int = 0
    status: str = "no_data"


class SnapshotChannel:
    """Polls the two files, keeps the last valid snapshot of each kind."""

    def __init__(
        self,
        snapshot_dir: Path,
        poll_interval: float = 0.05,
        clock: Callable[[], float] = time.monotonic,
        on_accept: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.snapshot_dir = snapshot_dir
        self.poll_interval = poll_interval
        self.clock = clock
        self.on_accept = on_accept
        self.state = LinkState()
        self.changed = threading.Condition()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._reject_logged_at: dict[str, float] = {}

    def start(self) -> None:
        log.info("читаю снимки из %s", self.snapshot_dir)
        self._thread = threading.Thread(target=self._run, name="pda-channel", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop.is_set():
            self.poll_once()
            self._stop.wait(self.poll_interval)

    def poll_once(self) -> None:
        bumped = False
        for kind in KINDS:
            bumped |= self._poll_kind(kind)
        status = self._compute_status()
        with self.changed:
            if status != self.state.status:
                log.info("связь с игрой: %s -> %s", self.state.status, status)
                self.state.status = status
                bumped = True
            if bumped:
                self.state.version += 1
                self.changed.notify_all()

    def _poll_kind(self, kind: str) -> bool:
        ks = self.state.kinds[kind]
        path = self.snapshot_dir / FILE_NAMES[kind]
        try:
            st = path.stat()
        except FileNotFoundError:
            return False
        except OSError as exc:
            self._log_reject(kind, f"stat: {exc}")
            return False
        stat_key = (st.st_mtime_ns, st.st_size)
        if stat_key == ks.last_stat:
            return False
        try:
            raw = path.read_bytes()
        except OSError as exc:
            self._log_reject(kind, f"чтение: {exc}")
            return False
        # A torn read is retried as soon as the writer finishes, because
        # finishing the write changes the file's size or mtime.
        ks.last_stat = stat_key
        try:
            snap = parse_snapshot(raw, kind)
        except RejectedSnapshot as exc:
            with self.changed:
                ks.rejected += 1
                ks.last_reject = str(exc)
            self._log_reject(kind, str(exc))
            return True
        prev = ks.snapshot
        if prev and prev["session"] == snap["session"] and prev["seq"] == snap["seq"]:
            return False
        if prev is None or prev["session"] != snap["session"]:
            log.info("%s: сессия игры %s, seq %d", kind, snap["session"], snap["seq"])
        with self.changed:
            ks.snapshot = snap
            ks.accepted_at = self.clock()
            ks.accepted += 1
        if self.on_accept:
            self.on_accept(kind, snap)
        return True

    def _log_reject(self, kind: str, reason: str) -> None:
        now = self.clock()
        if now - self._reject_logged_at.get(kind, -1e9) >= 5.0:
            self._reject_logged_at[kind] = now
            log.warning("%s: снимок отклонён (%s). Беру прошлый.", kind, reason)

    def _compute_status(self) -> str:
        fast = self.state.kinds["fast"]
        if fast.accepted_at is None:
            return "no_data"
        return "ok" if self.clock() - fast.accepted_at <= STALE_AFTER_S else "stale"

    def view(self) -> tuple[int, dict[str, Any]]:
        """Version and a JSON-ready link summary with the latest snapshots."""
        now = self.clock()
        with self.changed:
            kinds = self.state.kinds

            def age(k: str) -> int | None:
                at = kinds[k].accepted_at
                return None if at is None else int((now - at) * 1000)

            body = {
                "link": {
                    "status": self.state.status,
                    "fast_age_ms": age("fast"),
                    "slow_age_ms": age("slow"),
                    "accepted": {k: kinds[k].accepted for k in KINDS},
                    "rejected": {k: kinds[k].rejected for k in KINDS},
                    "last_reject": {k: kinds[k].last_reject for k in KINDS},
                },
                "fast": kinds["fast"].snapshot,
                "slow": kinds["slow"].snapshot,
            }
            return self.state.version, body
