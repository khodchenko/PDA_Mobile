"""Command line entry: python -m pda_bridge --demo"""

from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import sys
import tempfile
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any

from . import PROTOCOL, VERSION
from .channel import BridgePulse, SnapshotChannel
from .fake_game import DemoWriter, ReplayWriter
from .locate import MARKERS, find_snapshot_dirs, search_roots, standard_install_dirs
from .maps import MapLibrary
from .server import BridgeServer, lan_addresses, load_token

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PORT = 47615


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="pda_bridge",
        description="Мост между игрой (Anomaly / GAMMA) и веб-экраном ПДА на телефоне.",
    )
    src = p.add_mutually_exclusive_group()
    src.add_argument("--snapshot-dir", type=Path, help="папка, куда игровой аддон пишет pda_fast.json и pda_slow.json")
    src.add_argument("--demo", action="store_true", help="без игры: имитация пишет снимки во временную папку")
    src.add_argument("--replay", type=Path, metavar="FILE", help="проиграть запись, сделанную через --record")
    src.add_argument(
        "--locate",
        type=Path,
        nargs="+",
        metavar="DIR",
        help="найти, куда игра пишет снимки: укажите папку игры и папку MO2, мост не запускается",
    )
    src.add_argument(
        "--find-in",
        type=Path,
        nargs="+",
        metavar="DIR",
        help="найти самые свежие снимки в этих папках и читать их",
    )
    p.add_argument("--open", action="store_true", help="открыть ПДА в браузере после запуска")
    p.add_argument("--host", default="0.0.0.0", help="адрес прослушивания (по умолчанию все интерфейсы локальной сети)")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--web-dist", type=Path, default=ROOT / "web" / "dist", help="собранный веб-экран")
    p.add_argument("--data-dir", type=Path, default=ROOT / "bridge" / ".data", help="токен и логи моста")
    p.add_argument("--reset-token", action="store_true", help="выдать новый токен; все телефоны отвяжутся")
    p.add_argument("--record", type=Path, metavar="FILE", help="записывать принятые снимки в JSONL")
    p.add_argument("--torn-rate", type=float, default=0.01, help="доля оборванных записей в демо (проверка отбраковки)")
    p.add_argument("-v", "--verbose", action="store_true", help="подробный лог, включая каждый HTTP-запрос")
    return p.parse_args(argv)


def setup_logging(data_dir: Path, verbose: bool) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    log_path = data_dir / "bridge.log"
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s [%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    file = logging.handlers.RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    file.setFormatter(fmt)
    root.addHandler(console)
    root.addHandler(file)
    return log_path


class Recorder:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.started = time.monotonic()
        self.lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = path.open("a", encoding="utf-8")

    def __call__(self, kind: str, snap: dict[str, Any]) -> None:
        rec = {"t_ms": int((time.monotonic() - self.started) * 1000), "kind": kind, "data": snap}
        with self.lock:
            self.fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            self.fh.flush()


def locate(roots: list[Path]) -> int:
    roots = search_roots(roots)
    found = find_snapshot_dirs(roots)
    if not found:
        print("Снимков не найдено. Запустите игру с аддоном, загрузите сохранение и повторите.")
        print("Проверьте также gamedata\\configs\\xpda.ltx: snapshot_dir и лог игры (строки [xpda]).")
        return 1
    print("Найдены папки со снимками (свежие сверху):")
    for f in found:
        print("  " + f.describe())
    print(f'\nЗапуск моста: python -m pda_bridge --snapshot-dir "{found[0].directory}"')
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.locate:
        return locate(args.locate)
    log_path = setup_logging(args.data_dir, args.verbose)
    log = logging.getLogger("pda.bridge")
    log.info("мост ПДА %s, протокол %d, лог: %s", VERSION, PROTOCOL, log_path)

    writer: DemoWriter | ReplayWriter | None = None
    if args.find_in:
        roots = search_roots(args.find_in)
        found = [f for f in find_snapshot_dirs(roots) if f.fast_mtime is not None]
        if not found:
            looked = roots or list(args.find_in)
            log.error(
                "в %s снимков игры нет. По инструкции GAMMA это две папки в корне диска, "
                "например C:\\Anomaly и C:\\GAMMA; смотрел в обе, если они есть. "
                "Включите аддон в MO2, загрузите сохранение и запустите снова.",
                ", ".join(str(p) for p in looked),
            )
            return 2
        args.snapshot_dir = found[0].directory
        log.info("снимки найдены: %s", found[0].describe())
    if args.snapshot_dir:
        snapshot_dir, source = args.snapshot_dir.expanduser().resolve(), "file"
        if not snapshot_dir.is_dir():
            log.error("папки снимков нет: %s. Укажите ту, куда пишет игровой аддон.", snapshot_dir)
            return 2
        if not any((snapshot_dir / name).exists() for name in MARKERS):
            log.warning(
                "в %s пока нет снимков. Если игра идёт через MO2, они могут быть в папке overwrite. "
                "Найти: python -m pda_bridge --locate ПАПКА_ИГРЫ ПАПКА_MO2",
                snapshot_dir,
            )
    else:
        snapshot_dir = Path(tempfile.mkdtemp(prefix="stalker-pda-"))
        if args.replay:
            source = "replay"
            writer = ReplayWriter(args.replay, snapshot_dir)
        else:
            if not args.demo:
                log.info("источник не указан, запускаю демо. Для игры: --snapshot-dir ПАПКА")
            source = "demo"
            writer = DemoWriter(snapshot_dir, torn_rate=args.torn_rate)

    recorder = Recorder(args.record) if args.record else None
    if recorder:
        log.info("запись снимков в %s", args.record)
    channel = SnapshotChannel(
        snapshot_dir,
        on_accept=recorder,
        pulse=BridgePulse(snapshot_dir / "pda_bridge.txt", port=args.port, source=source),
    )
    token = load_token(args.data_dir, reset=args.reset_token)
    web_dist = args.web_dist if (args.web_dist / "index.html").exists() else None
    if web_dist is None:
        log.warning("веб-экран не найден в %s. Соберите его: cd web && npm run build", args.web_dist)

    try:
        maps = MapLibrary(standard_install_dirs(snapshot_dir), args.data_dir / "maps")
        server = BridgeServer((args.host, args.port), channel, token, web_dist, source, maps)
    except OSError as exc:
        log.error("не удалось открыть порт %s:%d: %s", args.host, args.port, exc)
        return 2

    if writer:
        writer.start()
    channel.start()
    log.info("на этом ПК: http://127.0.0.1:%d  (вкладка «Связь» покажет QR для телефона)", args.port)
    for ip in lan_addresses():
        log.info("в локальной сети: http://%s:%d", ip, args.port)
    if args.open:
        webbrowser.open(f"http://127.0.0.1:{args.port}")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        log.info("остановка")
    finally:
        server.server_close()
        channel.stop()
        if writer:
            writer.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
