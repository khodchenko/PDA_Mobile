"""HTTP side of the bridge: pairing, state, live stream, and the web PDA."""

from __future__ import annotations

import hmac
import ipaddress
import json
import logging
import mimetypes
import secrets
import socket
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from . import PROTOCOL, VERSION
from .channel import SnapshotChannel

log = logging.getLogger("pda.http")

# Windows takes MIME types from the registry, where .js is often text/plain,
# and browsers then refuse to run the module scripts.
for _ext, _type in {
    ".js": "application/javascript",
    ".mjs": "application/javascript",
    ".css": "text/css",
    ".svg": "image/svg+xml",
    ".json": "application/json",
    ".webmanifest": "application/manifest+json",
    ".png": "image/png",
}.items():
    mimetypes.add_type(_type, _ext)

STREAM_MIN_INTERVAL_S = 0.1
STREAM_KEEPALIVE_S = 5.0


def load_token(data_dir: Path, reset: bool = False) -> str:
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "token"
    if not reset and path.exists():
        token = path.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = secrets.token_urlsafe(18)
    path.write_text(token + "\n", encoding="utf-8")
    log.info("новый токен сопряжения записан в %s; старые телефоны нужно привязать заново", path)
    return token


def lan_addresses() -> list[str]:
    found: list[str] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # No packet is sent; this only asks the OS which interface routes out.
            s.connect(("192.0.2.1", 9))
            found.append(s.getsockname()[0])
    except OSError:
        pass
    try:
        for addr in socket.gethostbyname_ex(socket.gethostname())[2]:
            if addr not in found:
                found.append(addr)
    except OSError:
        pass
    return [a for a in found if not ipaddress.ip_address(a).is_loopback]


class BridgeServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        channel: SnapshotChannel,
        token: str,
        web_dist: Path | None,
        source: str,
        maps: Any = None,
    ) -> None:
        super().__init__(address, BridgeHandler)
        self.channel = channel
        self.token = token
        self.web_dist = web_dist.resolve() if web_dist else None
        self.source = source
        self.maps = maps
        self.started = time.monotonic()

    def bridge_info(self) -> dict[str, Any]:
        return {
            "version": VERSION,
            "protocol": PROTOCOL,
            "source": self.source,
            "snapshot_dir": str(self.channel.snapshot_dir),
            "uptime_s": int(time.monotonic() - self.started),
        }

    def state_body(self) -> tuple[int, dict[str, Any]]:
        version, body = self.channel.view()
        level = ((body.get("fast") or {}) or {}).get("level") or {}
        level_id = level.get("id") if isinstance(level, dict) else None
        if self.maps is not None and isinstance(level_id, str):
            try:
                described = self.maps.describe(level_id)
            except Exception:
                log.exception("карта локации %s не прочитана", level_id)
                described = None
            if described:
                body["map"] = described
        return version, {"protocol": PROTOCOL, "bridge": self.bridge_info(), **body}

    def pairing_urls(self) -> list[str]:
        port = self.server_address[1]
        return [f"http://{ip}:{port}/?token={self.token}" for ip in lan_addresses()]


class BridgeHandler(BaseHTTPRequestHandler):
    server: BridgeServer
    protocol_version = "HTTP/1.1"
    server_version = f"StalkerPdaBridge/{VERSION}"

    def log_message(self, format: str, *args: Any) -> None:
        log.debug("%s %s", self.client_address[0], format % args)

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        route = url.path
        query = parse_qs(url.query)
        if route == "/api/health":
            self._json({"ok": True, "protocol": PROTOCOL, "version": VERSION})
        elif route == "/api/pairing":
            self._pairing()
        elif route == "/api/state":
            if self._authorized(query):
                self._json(self.server.state_body()[1])
        elif route == "/api/stream":
            if self._authorized(query):
                self._stream()
        elif route.startswith("/api/map/"):
            if self._authorized(query):
                self._map(route[len("/api/map/") :])
        elif route.startswith("/api/"):
            self._error(HTTPStatus.NOT_FOUND, "нет такого адреса")
        else:
            self._static(route)

    def _is_loopback(self) -> bool:
        try:
            return ipaddress.ip_address(self.client_address[0]).is_loopback
        except ValueError:
            return False

    def _authorized(self, query: dict[str, list[str]]) -> bool:
        supplied = ""
        header = self.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            supplied = header[7:].strip()
        elif query.get("token"):
            supplied = query["token"][0]
        if supplied and hmac.compare_digest(supplied.encode(), self.server.token.encode()):
            return True
        log.info("отказ без верного токена: %s %s", self.client_address[0], urlsplit(self.path).path)
        self._error(HTTPStatus.UNAUTHORIZED, "телефон не привязан к этому мосту")
        return False

    def _pairing(self) -> None:
        # The token is only handed out to the PC itself; the phone gets it
        # from the QR code shown there.
        if not self._is_loopback():
            self._error(HTTPStatus.FORBIDDEN, "сопряжение открывается только на самом ПК")
            return
        self._json({"token": self.server.token, "urls": self.server.pairing_urls()})

    def _map(self, name: str) -> None:
        level = name[:-4] if name.endswith(".png") else ""
        png = self.server.maps.png(level) if self.server.maps is not None and level else None
        if not png:
            self._error(HTTPStatus.NOT_FOUND, "для этой локации нет картинки карты")
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/png")
        self.send_header("Cache-Control", "private, max-age=86400")
        self.send_header("Content-Length", str(len(png)))
        self.end_headers()
        self.wfile.write(png)

    def _json(self, body: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _error(self, status: HTTPStatus, message: str) -> None:
        self._json({"error": message, "status": status.value}, status)

    def _stream(self) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        client = self.client_address[0]
        log.info("поток открыт: %s", client)
        channel = self.server.channel
        sent_version = -1
        last_write = 0.0
        try:
            while True:
                with channel.changed:
                    channel.changed.wait_for(
                        lambda: channel.state.version != sent_version, timeout=STREAM_KEEPALIVE_S
                    )
                wait = STREAM_MIN_INTERVAL_S - (time.monotonic() - last_write)
                if wait > 0:
                    time.sleep(wait)
                # Sent even when nothing changed: the phone treats a silent
                # stream as dead, and snapshot ages need refreshing anyway.
                version, body = self.server.state_body()
                payload = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
                self.wfile.write(f"event: state\ndata: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
                sent_version = version
                last_write = time.monotonic()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, TimeoutError):
            pass
        finally:
            log.info("поток закрыт: %s", client)
            self.close_connection = True

    def _static(self, route: str) -> None:
        dist = self.server.web_dist
        if dist is None or not (dist / "index.html").exists():
            text = (
                "Веб-экран ПДА не собран. Выполните `npm run build` в папке web "
                "или запустите `npm run dev` и откройте его адрес."
            )
            data = text.encode("utf-8")
            self.send_response(HTTPStatus.SERVICE_UNAVAILABLE)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        target = (dist / route.lstrip("/")).resolve()
        if not target.is_relative_to(dist) or not target.is_file():
            target = dist / "index.html"
        data = target.read_bytes()
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        hashed = target.parent == dist / "assets"
        self.send_header("Cache-Control", "public, max-age=31536000, immutable" if hashed else "no-cache")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
