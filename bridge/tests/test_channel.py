import json
import os
import tempfile
import unittest
from pathlib import Path

from pda_bridge.channel import FILE_NAMES, STALE_AFTER_S, RejectedSnapshot, SnapshotChannel, parse_snapshot
from pda_bridge.fake_game import DemoGame, encode

SCHEMA = json.loads((Path(__file__).resolve().parents[2] / "protocol" / "snapshot-v1.schema.json").read_text("utf-8"))


class FakeClock:
    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t


def write(path: Path, data: bytes, bump_ns: int) -> None:
    path.write_bytes(data)
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + bump_ns))


class ParseSnapshotTest(unittest.TestCase):
    def test_accepts_matching_seq(self) -> None:
        snap = parse_snapshot(encode("fast", 7, "s1", {"health": 0.5}), "fast")
        self.assertEqual(snap["seq"], 7)

    def test_rejects_torn_json(self) -> None:
        data = encode("fast", 7, "s1", {"health": 0.5})
        with self.assertRaisesRegex(RejectedSnapshot, "оборванный"):
            parse_snapshot(data[: len(data) // 2], "fast")

    def test_rejects_seq_mismatch(self) -> None:
        doc = json.loads(encode("fast", 7, "s1", {}))
        doc["seq_end"] = 6
        with self.assertRaisesRegex(RejectedSnapshot, "seq_end"):
            parse_snapshot(json.dumps(doc).encode(), "fast")

    def test_rejects_wrong_kind_and_protocol(self) -> None:
        with self.assertRaisesRegex(RejectedSnapshot, "kind"):
            parse_snapshot(encode("slow", 1, "s1", {}), "fast")
        doc = json.loads(encode("fast", 1, "s1", {}))
        doc["protocol"] = 2
        with self.assertRaisesRegex(RejectedSnapshot, "протокол"):
            parse_snapshot(json.dumps(doc).encode(), "fast")

    def test_rejects_bool_seq(self) -> None:
        doc = json.loads(encode("fast", 1, "s1", {}))
        doc["seq"] = doc["seq_end"] = True
        with self.assertRaises(RejectedSnapshot):
            parse_snapshot(json.dumps(doc).encode(), "fast")


class ChannelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.clock = FakeClock()
        self.accepted: list[tuple[str, int]] = []
        self.channel = SnapshotChannel(self.dir, clock=self.clock, on_accept=lambda k, s: self.accepted.append((k, s["seq"])))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def put(self, kind: str, seq: int, session: str = "s1", body: dict | None = None, bump: int = 0) -> None:
        write(self.dir / FILE_NAMES[kind], encode(kind, seq, session, body or {}), bump)

    def test_no_files_means_no_data(self) -> None:
        self.channel.poll_once()
        _, view = self.channel.view()
        self.assertEqual(view["link"]["status"], "no_data")
        self.assertIsNone(view["fast"])

    def test_torn_file_keeps_previous_snapshot_and_recovers(self) -> None:
        self.put("fast", 1, body={"health": 0.9})
        self.channel.poll_once()
        good = encode("fast", 2, "s1", {"health": 0.4})
        write(self.dir / FILE_NAMES["fast"], good[:20], 1000)
        self.channel.poll_once()
        _, view = self.channel.view()
        self.assertEqual(view["fast"]["health"], 0.9)
        self.assertEqual(view["link"]["rejected"]["fast"], 1)
        self.assertIn("оборванный", view["link"]["last_reject"]["fast"])

        write(self.dir / FILE_NAMES["fast"], good, 2000)
        self.channel.poll_once()
        _, view = self.channel.view()
        self.assertEqual(view["fast"]["health"], 0.4)
        self.assertEqual(self.accepted, [("fast", 1), ("fast", 2)])

    def test_broken_file_is_not_reread_every_poll(self) -> None:
        write(self.dir / FILE_NAMES["fast"], b"{", 0)
        self.channel.poll_once()
        v1, _ = self.channel.view()
        self.channel.poll_once()
        v2, view = self.channel.view()
        self.assertEqual(v1, v2)
        self.assertEqual(view["link"]["rejected"]["fast"], 1)

    def test_goes_stale_when_game_stops_writing(self) -> None:
        self.put("fast", 1)
        self.channel.poll_once()
        self.assertEqual(self.channel.view()[1]["link"]["status"], "ok")
        self.clock.t += STALE_AFTER_S + 0.1
        self.channel.poll_once()
        _, view = self.channel.view()
        self.assertEqual(view["link"]["status"], "stale")
        self.assertGreater(view["link"]["fast_age_ms"], STALE_AFTER_S * 1000)

        self.put("fast", 2, bump=1000)
        self.channel.poll_once()
        self.assertEqual(self.channel.view()[1]["link"]["status"], "ok")

    def test_new_session_with_lower_seq_is_accepted(self) -> None:
        self.put("fast", 500, session="old")
        self.channel.poll_once()
        self.put("fast", 1, session="new", bump=1000)
        self.channel.poll_once()
        _, view = self.channel.view()
        self.assertEqual(view["fast"]["session"], "new")
        self.assertEqual(view["fast"]["seq"], 1)

    def test_version_bumps_only_on_change(self) -> None:
        self.put("slow", 1)
        self.channel.poll_once()
        v1, _ = self.channel.view()
        self.channel.poll_once()
        v2, _ = self.channel.view()
        self.assertEqual(v1, v2)


class DemoMatchesSchemaTest(unittest.TestCase):
    """Cheap guard that the demo never emits fields the schema forbids."""

    def check(self, kind: str, doc: dict) -> None:
        allowed = set(SCHEMA["$defs"][kind]["properties"])
        self.assertLessEqual(set(doc), allowed, f"{kind}: лишние поля {set(doc) - allowed}")
        for key in SCHEMA["$defs"]["envelope"]["required"]:
            self.assertIn(key, doc)

    def test_demo_snapshots_fit_schema_fields(self) -> None:
        game = DemoGame()
        for _ in range(2000):
            game.step(0.5)
            self.check("fast", json.loads(encode("fast", 1, game.session, game.fast())))
            self.check("slow", json.loads(encode("slow", 1, game.session, game.slow())))
            fast = game.fast()
            self.assertIn(fast["game_state"], ("in_game", "loading", "dead"))
            if "health" in fast:
                self.assertTrue(0 <= fast["health"] <= 1)
                self.assertTrue(0 <= fast["heading_deg"] < 360)


if __name__ == "__main__":
    unittest.main()
