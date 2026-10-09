import os
import tempfile
import time
import unittest
from pathlib import Path

from pda_bridge.locate import find_snapshot_dirs, search_roots, standard_install_dirs


class LocateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def touch(self, rel: str, age_s: float = 0) -> Path:
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{}", "utf-8")
        t = time.time() - age_s
        os.utime(p, (t, t))
        return p

    def test_finds_mo2_overwrite_and_orders_by_freshness(self) -> None:
        self.touch("Anomaly/appdata/pda_fast.json", age_s=3600)
        self.touch("MO2/overwrite/appdata/pda_fast.json", age_s=1)
        self.touch("MO2/overwrite/appdata/pda_report.txt")
        found = find_snapshot_dirs([self.root / "Anomaly", self.root / "MO2"])
        self.assertEqual(len(found), 2)
        self.assertEqual(found[0].directory, (self.root / "MO2/overwrite/appdata").resolve())
        self.assertTrue(found[0].has_report)
        self.assertEqual(found[1].directory, (self.root / "Anomaly/appdata").resolve())

    def test_report_without_snapshots_is_listed_last(self) -> None:
        self.touch("a/pda_report.txt")
        self.touch("b/pda_fast.json")
        found = find_snapshot_dirs([self.root])
        self.assertEqual([f.directory.name for f in found], ["b", "a"])
        self.assertIn("только отчёт", found[1].describe())

    def test_find_in_without_snapshots_exits_with_error(self) -> None:
        from pda_bridge.__main__ import main

        self.touch("GAMMA/overwrite/appdata/pda_report.txt")
        code = main(["--find-in", str(self.root / "GAMMA"), "--data-dir", str(self.root / "data")])
        self.assertEqual(code, 2)

    def test_skips_gamedata_and_missing_roots(self) -> None:
        self.touch("Anomaly/gamedata/scripts/pda_fast.json")
        self.assertEqual(find_snapshot_dirs([self.root / "Anomaly", self.root / "nope"]), [])

    def test_standard_install_is_two_folders_at_the_drive_root(self) -> None:
        self.assertEqual(
            [str(p) for p in standard_install_dirs(Path("C:/GAMMA"))],
            [r"C:\Anomaly", r"C:\GAMMA"],
        )
        self.assertEqual(
            [str(p) for p in standard_install_dirs(Path("D:/Anomaly/appdata"))],
            [r"D:\Anomaly", r"D:\GAMMA"],
        )
        self.assertEqual(standard_install_dirs(Path("/home/stalker")), [])

    def test_search_roots_adds_the_sibling_install_and_skips_the_drive(self) -> None:
        present = {Path(r"C:\GAMMA"), Path(r"C:\Anomaly")}

        def exists(path: Path) -> bool:
            return path in present

        roots = search_roots([Path("C:/GAMMA")], exists)
        self.assertEqual(roots, [Path(r"C:\GAMMA"), Path(r"C:\Anomaly")])
        self.assertEqual(search_roots([Path("C:/")], exists), [Path(r"C:\Anomaly"), Path(r"C:\GAMMA")])
