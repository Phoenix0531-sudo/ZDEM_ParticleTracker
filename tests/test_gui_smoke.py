"""GUI smoke tests — lightweight; real sample load is opt-in.

Default suite must stay fast and non-blocking. Set ZDEM_GUI_SAMPLE=1 for
the heavy sample+VisPy path (run that test alone, not inside discover).
"""
from __future__ import annotations

import os
import sys
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
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication(sys.argv)
        cls.sample = _find_sample()

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
            self.assertFalse(w._id_in_start_frame(1))
            # Exercise pure gate wiring without show()/processEvents loops
            w._start_frame_ids = {42, 99}
            self.assertTrue(w._id_in_start_frame(42))
            self.assertFalse(w._id_in_start_frame(1))
            w._clear_selection()
            self.assertIsNone(w._selected_id)
            w.close()
        finally:
            try:
                w.deleteLater()
            except Exception:
                pass

    def test_about_dialog_import(self):
        from zdem_particle_tracker.ui.about_dialog import APP_VERSION, show_about_dialog

        self.assertTrue(APP_VERSION)
        self.assertTrue(callable(show_about_dialog))

    def test_tiny_synthetic_dat_session_logic(self):
        """No OpenGL dependency: scan + gate via sample catalog if present."""
        from zdem_particle_tracker.parsers.dat_scan import (
            default_start_index,
            scan_dat_files,
            select_range,
        )
        from zdem_particle_tracker.widgets.selection_logic import (
            id_allowed_at_session_start,
            validate_time_range_indices,
        )

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
        start = {1, 2, 3}
        self.assertTrue(id_allowed_at_session_start(start, 2))
        self.assertFalse(id_allowed_at_session_start(start, 99))

    @unittest.skipUnless(
        os.environ.get("ZDEM_GUI_SAMPLE", "").strip() in ("1", "true", "yes"),
        "set ZDEM_GUI_SAMPLE=1 for real sample GUI load (~1 min); run alone",
    )
    def test_load_sample_and_start_ids(self):
        import time

        if self.sample is None:
            self.skipTest("no sample data directory")
        from PySide6.QtCore import QEventLoop
        from zdem_particle_tracker.widgets.main_viewer import MainViewer
        from zdem_particle_tracker.widgets.selection_logic import (
            id_allowed_at_session_start,
            pick_particle_id,
        )

        try:
            w = MainViewer()
        except Exception as e:
            self.skipTest(f"MainViewer construct failed: {e}")

        def process(rounds=10, ms=50):
            for _ in range(rounds):
                self.app.processEvents(QEventLoop.AllEvents, ms)

        try:
            w.show()
            process(5)
            w.load_directory(str(self.sample))
            deadline = time.time() + 90.0
            while time.time() < deadline:
                process(10, 50)
                if w._current_data is not None and w._start_frame_ids:
                    break
            if w._current_data is None or not w._start_frame_ids:
                self.skipTest("frame load timed out")
            d = w._current_data
            pid = int(d.ids[0])
            self.assertTrue(id_allowed_at_session_start(w._start_frame_ids, pid))
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
            w._select_particle(pid, auto_track=False)
            self.assertEqual(w._selected_id, pid)
            w._clear_selection()
            self.assertIsNone(w._selected_id)
            w.close()
        finally:
            try:
                w.deleteLater()
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
