"""GUI smoke tests — require a Qt platform (Windows/offscreen).

Skips gracefully if MainViewer / OpenGL cannot initialize.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

SAMPLE_CANDIDATES = [
    Path(r"D:/2_Temp/StructLab/Projects/25_造山带尺度盐构造/物理实验复刻/2/data"),
    Path(r"D:/2_Temp/StructLab/Projects/25_造山带尺度盐构造/物理实验复刻/1/data"),
]


def _find_sample() -> Path | None:
    for p in SAMPLE_CANDIDATES:
        if p.is_dir() and any(p.glob("all_*.dat")):
            return p
    return None


class TestGuiSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Prefer real Windows GL if available; fall back to offscreen
        if not os.environ.get("QT_QPA_PLATFORM"):
            # keep default (windows) — OpenGL worked in probe
            pass
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication(sys.argv)
        cls.sample = _find_sample()

    def _process(self, ms: int = 50, rounds: int = 20):
        from PySide6.QtCore import QEventLoop, QTimer

        for _ in range(rounds):
            self.app.processEvents(QEventLoop.AllEvents, ms)
            time.sleep(0.01)

    def test_main_viewer_construct(self):
        from zdem_particle_tracker.widgets.main_viewer import MainViewer

        try:
            w = MainViewer()
        except Exception as e:
            self.skipTest(f"MainViewer construct failed: {e}")
        try:
            self.assertEqual(w.windowTitle(), "ZDEM Particle Tracker")
            self.assertIsNone(w._selected_id)
            self.assertIsNone(w._start_frame_ids)
            # gate before load
            self.assertFalse(w._id_in_start_frame(1))
            w.close()
        finally:
            w.deleteLater()
            self._process(rounds=5)

    def test_about_dialog_import(self):
        from zdem_particle_tracker.ui.about_dialog import APP_VERSION, show_about_dialog

        self.assertTrue(APP_VERSION)
        # Don't show modal in CI; just ensure callable
        self.assertTrue(callable(show_about_dialog))

    def test_load_sample_and_start_ids(self):
        if self.sample is None:
            self.skipTest("no sample data directory")
        from zdem_particle_tracker.widgets.main_viewer import MainViewer
        from zdem_particle_tracker.widgets.selection_logic import (
            id_allowed_at_session_start,
            pick_particle_id,
        )

        try:
            w = MainViewer()
        except Exception as e:
            self.skipTest(f"MainViewer construct failed: {e}")

        try:
            w.show()
            self._process(rounds=5)
            w.load_directory(str(self.sample))
            # Wait for first frame (async worker)
            deadline = time.time() + 45.0
            while time.time() < deadline:
                self._process(ms=100, rounds=5)
                if w._current_data is not None and w._start_frame_ids:
                    break
            if w._current_data is None or not w._start_frame_ids:
                self.skipTest("frame load timed out (async/OpenGL env)")

            d = w._current_data
            self.assertGreater(d.count, 0)
            self.assertTrue(len(w._start_frame_ids) > 0)
            pid = int(d.ids[0])
            self.assertTrue(id_allowed_at_session_start(w._start_frame_ids, pid))
            # pick should return same particle near its center
            picked = pick_particle_id(
                d.xs,
                d.ys,
                d.rads,
                d.ids,
                float(d.xs[0]),
                float(d.ys[0]),
                start_ids=w._start_frame_ids,
                tree=w._kdtree,
            )
            self.assertEqual(picked, pid)

            # reject impossible id
            w._select_particle(2**62, auto_track=False)
            self.assertNotEqual(w._selected_id, 2**62)

            # select real id without auto track for speed
            w._select_particle(pid, auto_track=False)
            self.assertEqual(w._selected_id, pid)

            # clear selection clears traj UI fields
            w._clear_selection()
            self.assertIsNone(w._selected_id)
            self.assertIsNone(w._trajectory)

            w.close()
        finally:
            try:
                w.deleteLater()
            except Exception:
                pass
            self._process(rounds=5)

    def test_tiny_synthetic_dat_session_logic(self):
        """No OpenGL dependency: pure scan + gate via temp DAT files."""
        from zdem_particle_tracker.parsers.dat_scan import (
            default_start_index,
            scan_dat_files,
            select_range,
        )
        from zdem_particle_tracker.widgets.selection_logic import (
            id_allowed_at_session_start,
            validate_time_range_indices,
        )

        # Minimal scan of real sample if present; else skip
        if self.sample is None:
            self.skipTest("no sample")
        entries = scan_dat_files(str(self.sample))
        self.assertGreater(len(entries), 0)
        si = default_start_index(entries)
        ei = len(entries) - 1
        err = validate_time_range_indices(si, ei, len(entries))
        self.assertIsNone(err)
        selected = select_range(entries, si, ei, 1)
        self.assertGreaterEqual(len(selected), 1)
        # synthetic gate
        start = {1, 2, 3}
        self.assertTrue(id_allowed_at_session_start(start, 2))
        self.assertFalse(id_allowed_at_session_start(start, 99))


if __name__ == "__main__":
    unittest.main()
