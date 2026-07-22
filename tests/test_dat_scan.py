"""Tests for DAT directory scanning and session range defaults.

Key rule: leading consecutive ``all_*_ini.dat`` files are the deposition
phase; default analysis start is the *last* of that prefix.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from zdem_particle_tracker.parsers.dat_scan import (
    DatFileEntry,
    default_end_index,
    default_start_index,
    leading_ini_end_index,
    scan_dat_files,
    select_range,
)
from zdem_particle_tracker.parsers.dat_parser import find_dat_files


def _touch(dirpath: Path, name: str) -> Path:
    p = dirpath / name
    p.write_text("current_step: 0\nball_num: 0\n", encoding="utf-8")
    return p


class TestDatScan(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_sample_style_leading_ini(self):
        """Mirrors 物理实验复刻/2/data layout."""
        for name in [
            "all_0000000000_ini.dat",
            "all_0000003000_ini.dat",
            "all_0000006000_ini.dat",
            "all_0000026000.dat",
            "all_0000046000.dat",
            "0000026000.sav",
            "vtk_inters_0000026000.vtk",
            "all_0000026000.jpg",
        ]:
            _touch(self.root, name)

        entries = scan_dat_files(str(self.root))
        self.assertEqual(len(entries), 5)
        self.assertTrue(all(isinstance(e, DatFileEntry) for e in entries))
        self.assertTrue(entries[0].is_ini)
        self.assertTrue(entries[2].is_ini)
        self.assertFalse(entries[3].is_ini)
        self.assertEqual(leading_ini_end_index(entries), 2)
        self.assertEqual(default_start_index(entries), 2)
        self.assertEqual(entries[default_start_index(entries)].step, 6000)
        self.assertEqual(default_end_index(entries), 4)

        selected = select_range(
            entries, default_start_index(entries), default_end_index(entries), 1
        )
        self.assertEqual([e.step for e in selected], [6000, 26000, 46000])
        self.assertTrue(selected[0].is_ini)

    def test_no_ini_defaults_to_first(self):
        _touch(self.root, "all_0000100000.dat")
        _touch(self.root, "all_0000200000.dat")
        entries = scan_dat_files(str(self.root))
        self.assertEqual(leading_ini_end_index(entries), -1)
        self.assertEqual(default_start_index(entries), 0)

    def test_mid_run_ini_not_leading(self):
        """Restart dumps later in the run must not move default start."""
        for name in [
            "all_0000000000_ini.dat",
            "all_0000010000.dat",
            "all_0000020000.dat",
            "all_0000110000_ini.dat",  # mid-run restart
            "all_0000120000.dat",
        ]:
            _touch(self.root, name)
        entries = scan_dat_files(str(self.root))
        # Only first file is leading ini
        self.assertEqual(leading_ini_end_index(entries), 0)
        self.assertEqual(default_start_index(entries), 0)
        self.assertEqual(entries[0].step, 0)

    def test_stride_keeps_end(self):
        for i in range(10):
            _touch(self.root, f"all_{i * 1000:010d}.dat")
        entries = scan_dat_files(str(self.root))
        selected = select_range(entries, 0, 9, stride=3)
        steps = [e.step for e in selected]
        self.assertEqual(steps[0], 0)
        self.assertEqual(steps[-1], 9000)
        self.assertLessEqual(len(selected), 5)

    def test_non_recursive(self):
        sub = self.root / "sub"
        sub.mkdir()
        _touch(self.root, "all_0000001000.dat")
        _touch(sub, "all_0000002000.dat")
        entries = scan_dat_files(str(self.root))
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].step, 1000)

    def test_find_dat_files_compat(self):
        _touch(self.root, "all_0000006000_ini.dat")
        _touch(self.root, "all_0000026000.dat")
        pairs = find_dat_files(str(self.root))
        self.assertEqual(len(pairs), 2)
        self.assertEqual(pairs[0][0], 6000)


if __name__ == "__main__":
    unittest.main()
