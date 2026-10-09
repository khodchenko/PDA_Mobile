"""Runs the Lua exporter under LuaJIT with engine stubs and checks its output
against the protocol schema and the bridge parser.

    python3 addon/tests/test_exporter.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ADDON = ROOT / "addon" / "stalker_pda" / "gamedata"
SCRIPTS = ADDON / "scripts"
CONFIGS = ADDON / "configs"
HARNESS = Path(__file__).resolve().parent / "harness.lua"
SCHEMA = json.loads((ROOT / "protocol" / "snapshot-v1.schema.json").read_text("utf-8"))

sys.path.insert(0, str(ROOT / "bridge"))
from pda_bridge.channel import SnapshotChannel, parse_snapshot  # noqa: E402

LUAJIT = shutil.which("luajit")


def schema_errors(value: Any, schema: dict, at: str = "$") -> list[str]:
    """The subset of JSON Schema 2020-12 used by snapshot-v1."""
    if schema is True:
        return []
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        return schema_errors(value, SCHEMA["$defs"][name], at)
    errors: list[str] = []
    if "oneOf" in schema:
        matches = sum(1 for s in schema["oneOf"] if not schema_errors(value, s, at))
        if matches != 1:
            errors.append(f"{at}: подходит {matches} вариантов oneOf")
        return errors
    for sub in schema.get("allOf", []):
        errors += schema_errors(value, sub, at)
    if "const" in schema and value != schema["const"]:
        errors.append(f"{at}: ожидалось {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{at}: {value!r} не из {schema['enum']}")
    kind = schema.get("type")
    if kind == "object":
        if not isinstance(value, dict):
            return errors + [f"{at}: не объект"]
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{at}: нет {key}")
        props = schema.get("properties", {})
        for key, item in value.items():
            if key in props:
                errors += schema_errors(item, props[key], f"{at}.{key}")
            elif schema.get("additionalProperties") is False:
                errors.append(f"{at}: лишнее поле {key}")
    elif kind == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
        errors.append(f"{at}: не целое")
    elif kind == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
        errors.append(f"{at}: не число")
    elif kind == "string":
        if not isinstance(value, str):
            errors.append(f"{at}: не строка")
        elif len(value) < schema.get("minLength", 0):
            errors.append(f"{at}: короче {schema['minLength']}")
    elif kind == "boolean" and not isinstance(value, bool):
        errors.append(f"{at}: не bool")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{at}: меньше {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{at}: больше {schema['maximum']}")
        if "exclusiveMaximum" in schema and value >= schema["exclusiveMaximum"]:
            errors.append(f"{at}: не меньше {schema['exclusiveMaximum']}")
    return errors


class Run:
    def __init__(self, out: Path) -> None:
        self.out = out
        self.fast_raw = [l for l in (out / "fast.jsonl").read_bytes().splitlines() if l]
        self.slow_raw = [l for l in (out / "slow.jsonl").read_bytes().splitlines() if l]
        self.fast = [parse_snapshot(raw, "fast") for raw in self.fast_raw]
        self.slow = [parse_snapshot(raw, "slow") for raw in self.slow_raw]
        self.log = (out / "xray.log").read_bytes().decode("cp1251")


@unittest.skipUnless(LUAJIT, "luajit не установлен")
class ExporterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)
        (self.out / "appdata").mkdir()
        (self.out / "saves").mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_scenario(self, scenario: str, configs: Path = CONFIGS) -> Run:
        proc = subprocess.run(
            [LUAJIT, str(HARNESS), str(SCRIPTS), str(configs), str(self.out), scenario],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        run = Run(self.out)
        for doc in run.fast + run.slow:
            self.assertEqual(schema_errors(doc, SCHEMA), [], doc)
        return run

    def test_normal_session(self) -> None:
        run = self.run_scenario("normal")
        self.assertGreater(len(run.slow), 3)
        self.assertEqual(len({d["session"] for d in run.fast + run.slow}), 1)
        self.assertEqual([d["seq"] for d in run.fast], list(range(1, len(run.fast) + 1)))
        for raw in run.fast_raw + run.slow_raw:
            self.assertTrue(raw.rstrip().endswith(b"}"), raw)
            self.assertLess(raw.index(b'"seq"'), raw.index(b'"seq_end"'))

        first = run.fast[0]
        self.assertEqual(first["game_state"], "in_game")
        self.assertEqual(first["level"], {"id": "l01_escape", "name": "Кордон"})
        self.assertEqual(first["game_time"], {"day": 3, "hour": 21, "minute": 47})
        self.assertAlmostEqual(first["heading_deg"], 36.9, places=1)
        self.assertEqual(first["position"], {"x": -118.4, "y": 11.9, "z": -257.1})

        garbage = [d for d in run.fast if d.get("level", {}).get("id") == "l02_garbage"]
        self.assertTrue(garbage)
        self.assertNotIn("name", garbage[0]["level"])
        self.assertIn("нет перевода для l02_garbage", run.log)

        self.assertIn("dead", [d["game_state"] for d in run.fast])
        self.assertEqual(run.fast[-1], {**run.fast[-1], "game_state": "loading"})
        self.assertEqual(set(run.fast[-1]), {"protocol", "kind", "seq", "session", "game_state", "seq_end"})

        slow = run.slow[0]
        self.assertEqual(slow["reader"], "anomaly")
        self.assertEqual(slow["player"], {"name": "Меченый", "id": 0, "money": 12500})
        self.assertTrue(slow["capabilities"]["player"])
        self.assertTrue(slow["capabilities"]["pose"])
        self.assertFalse(slow["capabilities"]["tasks"])

    def test_fast_rate_holds_ten_hertz_on_frame_updates(self) -> None:
        run = self.run_scenario("normal")
        in_game = [d for d in run.fast if d["game_state"] != "loading"]
        self.assertGreaterEqual(len(in_game), 44)
        self.assertLessEqual(len(in_game), 47)
        self.assertIn("быстрых 46", run.log)

    def test_report_explains_path_and_fields(self) -> None:
        self.run_scenario("normal")
        report = (self.out / "appdata" / "pda_report.txt").read_text("utf-8")
        self.assertIn(f'--snapshot-dir "{self.out}/appdata/"', report)
        self.assertIn("$app_data_root$", report)
        self.assertIn("player.money   ok", report)
        self.assertIn("os.rename", report)

    def test_log_is_cp1251(self) -> None:
        run = self.run_scenario("normal")
        self.assertIn("[xpda] экспорт 0.1.1 запущен", run.log)
        self.assertIn("состояние игры: dead", run.log)

    def test_missing_engine_functions_drop_fields_instead_of_zeroing(self) -> None:
        run = self.run_scenario("broken_api")
        for d in run.fast:
            self.assertNotIn("heading_deg", d)
            self.assertNotIn("radiation", d)
        slow = run.slow[0]
        self.assertEqual(slow["player"], {"id": 0})
        self.assertFalse(slow["capabilities"]["player"])
        self.assertEqual(run.log.count("поле player.money не читается"), 1)
        self.assertIn("money is not exported in this build", run.log)
        self.assertEqual(run.log.count("поле heading_deg не читается"), 1)

    def test_falls_back_to_saves_when_appdata_is_not_writable(self) -> None:
        run = self.run_scenario("appdata_readonly")
        self.assertTrue(run.fast)
        self.assertTrue((self.out / "saves" / "pda_fast.json").exists())
        self.assertRegex(run.log, r"missing/appdata/ \(\$app_data_root\$\): ошибка")

    def test_snapshot_dir_from_config(self) -> None:
        (self.out / "custom").mkdir()
        configs = self.out / "configs"
        configs.mkdir()
        (configs / "xpda.ltx").write_text(f"[xpda]\nsnapshot_dir = {self.out}/custom/\nfast_period_ms = 200\n", "utf-8")
        run = self.run_scenario("config_dir", configs)
        self.assertTrue((self.out / "custom" / "pda_fast.json").exists())
        self.assertFalse((self.out / "appdata" / "pda_fast.json").exists())
        self.assertLessEqual(len(run.fast), 25)

    def test_utf8_strings_pass_through(self) -> None:
        run = self.run_scenario("utf8_names")
        self.assertEqual(run.fast[0]["level"]["name"], "Кордон")
        self.assertEqual(run.slow[0]["player"]["name"], "Стрелок")

    def test_out_of_range_time_is_dropped_with_reason(self) -> None:
        run = self.run_scenario("bad_time")
        self.assertNotIn("game_time", run.fast[0])
        self.assertIn("значения вне диапазона: день 0", run.log)

    def test_mcm_page_shows_bridge_status_and_stores_nothing(self) -> None:
        self.run_scenario("normal")
        before = (self.out / "mcm_before.txt").read_text("utf-8")
        live = (self.out / "mcm_bridge.txt").read_text("utf-8")
        quiet = (self.out / "mcm_quiet.txt").read_text("utf-8")
        self.assertIn("игра его видит", before)
        self.assertIn("Экспорт: идёт", before)
        self.assertIn("Мост: не запущен", before)
        self.assertIn("Мост: читает снимки, seq 7, порт 47615", live)
        self.assertIn("Мост: молчит уже", quiet)
        tree = (self.out / "mcm_tree.txt").read_text("utf-8").splitlines()
        self.assertEqual(tree[0], "xpda")
        self.assertEqual(tree[1], "title,desc")
        shown = (self.out / "mcm_shown.txt").read_bytes().decode("cp1251")
        self.assertIn("Мост: молчит уже", shown)

    def test_bridge_accepts_exporter_files(self) -> None:
        self.run_scenario("normal")
        channel = SnapshotChannel(self.out / "appdata")
        channel.poll_once()
        _, view = channel.view()
        self.assertEqual(view["link"]["rejected"], {"fast": 0, "slow": 0})
        self.assertEqual(view["fast"]["game_state"], "loading")
        self.assertEqual(view["slow"]["reader"], "anomaly")


@unittest.skipUnless(LUAJIT, "luajit не установлен")
class TextTest(unittest.TestCase):
    def lua(self, code: str) -> bytes:
        prelude = f"xpda_text = setmetatable({{}}, {{__index = _G}}); setfenv(assert(loadfile([[{SCRIPTS / 'xpda_text.script'}]])), xpda_text)(); "
        proc = subprocess.run([LUAJIT, "-e", prelude + code], capture_output=True, timeout=10)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def test_cp1251_table_matches_python_codec(self) -> None:
        out = self.lua("local t = {} for b = 128, 255 do if b ~= 152 then t[#t+1] = string.char(b) end end io.write(xpda_text.from_cp1251(table.concat(t)))")
        expected = bytes(b for b in range(128, 256) if b != 152).decode("cp1251")
        self.assertEqual(out.decode("utf-8"), expected)

    def test_to_cp1251_round_trip_keeps_ansi_bytes(self) -> None:
        sample = "Папка «C:\\Игры» — ок №1"
        path_bytes = "C:\\Пользователи\\".encode("cp1251")
        out = self.lua(f"io.write(xpda_text.to_cp1251([[{sample}]] .. string.char({','.join(str(b) for b in path_bytes)})))")
        self.assertEqual(out, sample.encode("cp1251") + path_bytes)

    def test_auto_keeps_utf8_and_converts_cp1251(self) -> None:
        out = self.lua("io.write(xpda_text.to_utf8('Бар', 'auto'), '|', xpda_text.to_utf8(string.char(193, 224, 240), 'auto'))")
        self.assertEqual(out.decode("utf-8"), "Бар|Бар")


if __name__ == "__main__":
    unittest.main()
