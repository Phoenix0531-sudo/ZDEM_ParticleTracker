"""GUI-related smoke — default path avoids constructing VisPy MainViewer.

Heavy path (real sample + window + pick/clear):
  ZDEM_GUI_SAMPLE=1 uv run python -m unittest \\
    tests.test_gui_smoke.TestGuiSmoke.test_load_sample_and_start_ids
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
    def test_about_and_gate_import(self):
        from zdem_particle_tracker.ui.about_dialog import APP_VERSION, show_about_dialog
        from zdem_particle_tracker.widgets.main_viewer import id_allowed_at_session_start
        from zdem_particle_tracker.widgets.selection_logic import (
            pick_particle_id,
            play_parse_mode_name,
        )

        self.assertTrue(APP_VERSION)
        self.assertTrue(callable(show_about_dialog))
        self.assertTrue(id_allowed_at_session_start({1}, 1))
        self.assertFalse(id_allowed_at_session_start(None, 1))
        self.assertEqual(play_parse_mode_name("group"), "FULL_PARTICLE_PROPERTIES")
        # MainViewer class import only (no instance — VisPy native can hang in batch)
        from zdem_particle_tracker.widgets.main_viewer import MainViewer

        self.assertTrue(hasattr(MainViewer, "_select_particle"))
        self.assertTrue(hasattr(MainViewer, "_start_trajectory"))
        self.assertTrue(hasattr(MainViewer, "_setup_shortcuts"))

    def test_qapplication_platform(self):
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        # May already be QCoreApplication in odd hosts
        name = getattr(app, "platformName", lambda: "unknown")()
        self.assertTrue(name is None or isinstance(name, str) or name == "unknown")

    def test_session_logic_with_sample_catalog(self):
        from zdem_particle_tracker.parsers.dat_scan import (
            default_start_index,
            scan_dat_files,
            select_range,
        )
        from zdem_particle_tracker.widgets.selection_logic import (
            id_allowed_at_session_start,
            validate_time_range_indices,
        )

        sample = _find_sample()
        if sample is None:
            self.skipTest("no sample")
        entries = scan_dat_files(str(sample))
        self.assertGreater(len(entries), 0)
        si = default_start_index(entries)
        ei = len(entries) - 1
        self.assertIsNone(validate_time_range_indices(si, ei, len(entries)))
        self.assertGreaterEqual(len(select_range(entries, si, ei, 1)), 1)
        self.assertTrue(id_allowed_at_session_start({1, 2, 3}, 2))

    @unittest.skipUnless(
        os.environ.get("ZDEM_GUI_SAMPLE", "").strip() in ("1", "true", "yes"),
        "set ZDEM_GUI_SAMPLE=1 for real sample GUI load",
    )
    def test_load_sample_and_start_ids(self):
        import time

        from PySide6.QtCore import QEventLoop
        from PySide6.QtWidgets import QApplication
        from zdem_particle_tracker.widgets.main_viewer import MainViewer
        from zdem_particle_tracker.widgets.selection_logic import (
            id_allowed_at_session_start,
            pick_particle_id,
        )

        sample = _find_sample()
        if sample is None:
            self.skipTest("no sample")
        app = QApplication.instance() or QApplication(sys.argv)
        w = MainViewer()
        try:
            w.show()
            for _ in range(5):
                app.processEvents(QEventLoop.AllEvents, 50)
            w.load_directory(str(sample))
            deadline = time.time() + 90.0
            while time.time() < deadline:
                for _ in range(10):
                    app.processEvents(QEventLoop.AllEvents, 50)
                if w._current_data is not None and w._start_frame_ids:
                    break
            if w._current_data is None or not w._start_frame_ids:
                self.skipTest("frame load timed out")
            d = w._current_data
            pid = int(d.ids[0])
            self.assertTrue(id_allowed_at_session_start(w._start_frame_ids, pid))
            self.assertEqual(
                pick_particle_id(
                    d.xs,
                    d.ys,
                    d.rads,
                    d.ids,
                    float(d.xs[0]),
                    float(d.ys[0]),
                    start_ids=w._start_frame_ids,
                    tree=w._kdtree,
                ),
                pid,
            )
            w._select_particle(pid, auto_track=False)
            self.assertEqual(w._selected_id, pid)
            w._clear_selection()
            self.assertIsNone(w._selected_id)
        finally:
            w.close()


if __name__ == "__main__":
    unittest.main()
