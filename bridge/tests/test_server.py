import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from pda_bridge.channel import FILE_NAMES, SnapshotChannel
from pda_bridge.fake_game import encode
from pda_bridge.server import BridgeServer, load_token


class ServerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.snap_dir = root / "snap"
        self.snap_dir.mkdir()
        dist = root / "dist"
        (dist / "assets").mkdir(parents=True)
        (dist / "index.html").write_text("<!doctype html><title>ПДА</title>", "utf-8")
        (dist / "assets" / "app.js").write_text("console.log(1)", "utf-8")
        (self.snap_dir / FILE_NAMES["fast"]).write_bytes(encode("fast", 3, "s1", {"health": 0.7}))
        self.channel = SnapshotChannel(self.snap_dir, poll_interval=0.02)
        self.channel.poll_once()
        self.token = load_token(root / "data")
        self.server = BridgeServer(("127.0.0.1", 0), self.channel, self.token, dist, "file")
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.channel.stop()
        self.tmp.cleanup()

    def get(self, path: str, headers: dict | None = None) -> tuple[int, dict[str, str], bytes]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", path, headers=headers or {})
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp.status, dict(resp.getheaders()), body

    def test_health_is_open(self) -> None:
        status, _, body = self.get("/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["ok"])

    def test_state_requires_token(self) -> None:
        self.assertEqual(self.get("/api/state")[0], 401)
        self.assertEqual(self.get("/api/state?token=wrong")[0], 401)
        status, _, body = self.get("/api/state", {"Authorization": f"Bearer {self.token}"})
        self.assertEqual(status, 200)
        state = json.loads(body)
        self.assertEqual(state["fast"]["health"], 0.7)
        self.assertEqual(state["link"]["status"], "ok")
        self.assertEqual(state["bridge"]["source"], "file")

    def test_pairing_is_served_to_loopback(self) -> None:
        status, _, body = self.get("/api/pairing")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["token"], self.token)
        for url in data["urls"]:
            self.assertIn(f"token={self.token}", url)

    def test_static_files_and_spa_fallback(self) -> None:
        status, headers, body = self.get("/assets/app.js")
        self.assertEqual(status, 200)
        self.assertTrue(headers["Content-Type"].startswith("application/javascript"))
        self.assertIn("immutable", headers["Cache-Control"])
        status, headers, body = self.get("/status")
        self.assertEqual(status, 200)
        self.assertIn("ПДА", body.decode("utf-8"))
        self.assertEqual(headers["Cache-Control"], "no-cache")

    def test_static_path_traversal_falls_back_to_index(self) -> None:
        status, _, body = self.get("/../snap/pda_fast.json")
        self.assertEqual(status, 200)
        self.assertIn("ПДА", body.decode("utf-8"))

    def test_stream_sends_state_then_updates(self) -> None:
        self.channel.start()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", f"/api/stream?token={self.token}")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        self.assertTrue(resp.getheader("Content-Type").startswith("text/event-stream"))

        def next_event() -> dict:
            lines = []
            while True:
                line = resp.fp.readline().decode("utf-8").rstrip("\n")
                if line == "" and lines:
                    break
                if line.startswith("data: "):
                    lines.append(line[6:])
            return json.loads("".join(lines))

        first = next_event()
        self.assertEqual(first["fast"]["seq"], 3)
        (self.snap_dir / FILE_NAMES["fast"]).write_bytes(encode("fast", 4, "s1", {"health": 0.2, "radiation": 0.1}))
        second = next_event()
        self.assertEqual(second["fast"]["seq"], 4)
        conn.close()


if __name__ == "__main__":
    unittest.main()
