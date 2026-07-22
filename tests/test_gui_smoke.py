"""GUI smoke — safe MainViewer construct is in test_render_pixels.

Heavy real-sample path remains opt-in via ZDEM_GUI_SAMPLE=1
(see tests.test_render_pixels.TestMainViewerConstruct.test_load_sample_select_clear).
"""
from __future__ import annotations

import os
import sys
import unittest


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
        from zdem_particle_tracker.widgets.main_viewer import MainViewer

        self.assertTrue(hasattr(MainViewer, "_select_particle"))
        self.assertTrue(hasattr(MainViewer, "_start_trajectory"))
        self.assertTrue(hasattr(MainViewer, "_setup_shortcuts"))

    def test_qapplication_platform(self):
        # Avoid creating QApplication in the parent pytest process on Linux CI
        # (same-process QWidget later can abort after OpenGL imports).
        from tests.qt_subprocess import assert_qt_script_ok

        code = """
            import sys
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance() or QApplication(sys.argv)
            name = app.platformName()
            assert isinstance(name, str) and name, name
            print("SUBPROC_OK")
        """
        assert_qt_script_ok(self, code)

    def test_backend_env_helpers(self):
        from zdem_particle_tracker.rendering.backend import (
            gl_available_for_tests,
            prefer_vispy,
        )

        self.assertIsInstance(prefer_vispy(), bool)
        self.assertIsInstance(gl_available_for_tests(), bool)

    def test_mainviewer_pyqtgraph_subprocess(self):
        """Isolated process: force PyQtGraph + offscreen — must construct without hang."""
        from tests.qt_subprocess import assert_qt_script_ok

        code = """
            import sys
            from PySide6.QtWidgets import QApplication
            app = QApplication(sys.argv)
            import zdem_particle_tracker.widgets.main_viewer as mv
            assert mv.HAVE_VISPY is False, mv.HAVE_VISPY
            w = mv.MainViewer()
            assert w.windowTitle() == "ZDEM Particle Tracker"
            w.close()
            print("SUBPROC_OK")
        """
        assert_qt_script_ok(self, code, timeout=90.0)


if __name__ == "__main__":
    unittest.main()
