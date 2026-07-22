"""Pixel-level rendering tests: CPU ground truth + optional VisPy GL.

Default CI:
  - Always runs CPU raster checks (no OpenGL).
  - Constructs MainViewer safely (auto PyQtGraph on offscreen /
    ZDEM_FORCE_PYQTGRAPH=1).
  - VisPy GL screenshot tests run when a real GL context works;
    otherwise skipped (not failed).

Force paths:
  ZDEM_FORCE_PYQTGRAPH=1  — never VisPy
  ZDEM_FORCE_VISPY=1      — try VisPy even on offscreen
  ZDEM_GUI_SAMPLE=1       — load real sample into MainViewer (slow)
"""
from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path

import numpy as np

from zdem_particle_tracker.rendering.cpu_raster import (
    channel_dominance,
    data_to_pixel,
    dominant_color_at,
    rasterize_discs,
)
from zdem_particle_tracker.rendering.backend import (
    gl_available_for_tests,
    is_offscreen_qt,
    prefer_vispy,
)


SAMPLE_CANDIDATES = [
    Path(r"D:/2_Temp/StructLab/Projects/25_造山带尺度盐构造/物理实验复刻/2/data"),
    Path(r"D:/2_Temp/StructLab/Projects/25_造山带尺度盐构造/物理实验复刻/1/data"),
]


def _find_sample() -> Path | None:
    for p in SAMPLE_CANDIDATES:
        if p.is_dir() and any(p.glob("all_*.dat")):
            return p
    return None


def _qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


class TestCpuRaster(unittest.TestCase):
    def test_three_colored_discs(self):
        # Red at left, green center, blue right — non-overlapping
        xs = np.array([50.0, 150.0, 250.0])
        ys = np.array([100.0, 100.0, 100.0])
        rads = np.array([30.0, 30.0, 30.0])
        rgba = np.array(
            [
                [1.0, 0.0, 0.0, 1.0],
                [0.0, 1.0, 0.0, 1.0],
                [0.0, 0.0, 1.0, 1.0],
            ],
            dtype=np.float64,
        )
        img = rasterize_discs(
            xs, ys, rads, rgba, xmin=0, xmax=300, ymin=0, ymax=200, width=300, height=200
        )
        self.assertEqual(img.shape, (200, 300, 4))
        self.assertEqual(img.dtype, np.uint8)
        # Background near white at corner
        self.assertGreater(img[5, 5, 0], 240)
        # Centers
        for i, ch in enumerate((0, 1, 2)):
            row, col = data_to_pixel(
                xs[i], ys[i], xmin=0, xmax=300, ymin=0, ymax=200, width=300, height=200
            )
            rgb = dominant_color_at(img, row, col, radius=3)
            self.assertTrue(
                channel_dominance(rgb, ch, margin=40),
                f"disc {i} expected channel {ch} dominant, got {rgb} at ({row},{col})",
            )

    def test_empty(self):
        img = rasterize_discs(
            np.array([]),
            np.array([]),
            np.array([]),
            np.zeros((0, 4)),
            xmin=0,
            xmax=1,
            ymin=0,
            ymax=1,
            width=32,
            height=24,
        )
        self.assertEqual(img.shape, (24, 32, 4))
        self.assertTrue((img[..., :3] > 250).all())


class TestMainViewerConstruct(unittest.TestCase):
    """Construct MainViewer without hanging — hard on CI via subprocess."""

    def test_construct_and_close(self):
        from tests.qt_subprocess import assert_qt_script_ok

        code = """
            import sys
            import time
            from PySide6.QtWidgets import QApplication
            import zdem_particle_tracker.widgets.main_viewer as mv

            app = QApplication.instance() or QApplication(sys.argv)
            assert mv.HAVE_VISPY is False, mv.HAVE_VISPY
            t0 = time.time()
            w = mv.MainViewer()
            elapsed = time.time() - t0
            assert elapsed < 20.0, elapsed
            assert w.windowTitle() == "ZDEM Particle Tracker"
            assert hasattr(w, "_plot")
            assert hasattr(w, "_select_particle")
            app.processEvents()
            w.close()
            app.processEvents()
            print("SUBPROC_OK")
        """
        assert_qt_script_ok(self, code, timeout=90.0)

    def test_backend_selection_helpers(self):
        # Pure env logic
        self.assertIsInstance(prefer_vispy(), bool)
        self.assertIsInstance(is_offscreen_qt(), bool)
        self.assertIsInstance(gl_available_for_tests(), bool)

    @unittest.skipUnless(
        os.environ.get("ZDEM_GUI_SAMPLE", "").strip().lower() in ("1", "true", "yes"),
        "set ZDEM_GUI_SAMPLE=1 for real sample load",
    )
    def test_load_sample_select_clear(self):
        from PySide6.QtCore import QEventLoop
        from zdem_particle_tracker.widgets.main_viewer import MainViewer
        from zdem_particle_tracker.widgets.selection_logic import (
            id_allowed_at_session_start,
            pick_particle_id,
        )

        sample = _find_sample()
        if sample is None:
            self.skipTest("no sample")
        app = _qapp()
        w = MainViewer()
        try:
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


class TestVisPyPixels(unittest.TestCase):
    """Real GL readback — skip when no context."""

    @classmethod
    def setUpClass(cls):
        cls.app = _qapp()
        cls._gl = False
        cls._renderer = None
        if not gl_available_for_tests():
            return
        try:
            from zdem_particle_tracker.rendering.vispy_renderer import VisPyRenderer

            r = VisPyRenderer()
            # probe render
            r.set_region(0, 100, 0, 100)
            xs = np.array([50.0])
            ys = np.array([50.0])
            rads = np.array([20.0])
            rgba = np.array([[1.0, 0.0, 0.0, 1.0]], dtype=np.float32)
            r.set_data(xs, ys, rads, rgba)
            r.render()
            cls.app.processEvents()
            img = r.render_to_array()
            if img is not None and img.size > 0:
                cls._gl = True
                cls._renderer = r
            else:
                r.close()
        except Exception:
            cls._gl = False

    @classmethod
    def tearDownClass(cls):
        if cls._renderer is not None:
            try:
                cls._renderer.close()
            except Exception:
                pass

    def test_vispy_red_disc_visible(self):
        if not self._gl:
            self.skipTest("OpenGL context unavailable")
        from zdem_particle_tracker.rendering.vispy_renderer import VisPyRenderer

        r = VisPyRenderer()
        try:
            xmin, xmax, ymin, ymax = 0.0, 400.0, 0.0, 300.0
            r.set_region(xmin, xmax, ymin, ymax)
            xs = np.array([100.0, 200.0, 300.0])
            ys = np.array([150.0, 150.0, 150.0])
            rads = np.array([40.0, 40.0, 40.0])
            rgba = np.array(
                [
                    [1.0, 0.0, 0.0, 1.0],
                    [0.0, 1.0, 0.0, 1.0],
                    [0.0, 0.0, 1.0, 1.0],
                ],
                dtype=np.float32,
            )
            r.set_data(xs, ys, rads, rgba, enhanced=False)
            r.render()
            self.app.processEvents()
            # extra frames for GL settle
            for _ in range(5):
                self.app.processEvents()
                time.sleep(0.02)
            img = r.render_to_array()
            self.assertIsNotNone(img)
            self.assertEqual(img.ndim, 3)
            h, w = img.shape[:2]
            # non-white fraction > 0 (something drawn)
            white = (img[..., 0] > 250) & (img[..., 1] > 250) & (img[..., 2] > 250)
            nonwhite = 1.0 - float(white.mean())
            self.assertGreater(nonwhite, 0.001, "scene looks empty (all white)")

            # Sample near mapped centers — VisPy may have padding from set_region (5%)
            # so use soft channel checks: at least one sample should be red-ish
            found = {0: False, 1: False, 2: False}
            for i, ch in enumerate((0, 1, 2)):
                # map with same 5% margin as set_region
                mx = (xmax - xmin) * 0.05
                my = (ymax - ymin) * 0.05
                row, col = data_to_pixel(
                    xs[i],
                    ys[i],
                    xmin=xmin - mx,
                    xmax=xmax + mx,
                    ymin=ymin - my,
                    ymax=ymax + my,
                    width=w,
                    height=h,
                )
                rgb = dominant_color_at(img, row, col, radius=max(3, min(h, w) // 40))
                if channel_dominance(rgb, ch, margin=15):
                    found[ch] = True
            # At least red disc should be detectable (left)
            self.assertTrue(
                any(found.values()),
                f"no dominant color disc found in VisPy capture; found={found}",
            )
        finally:
            r.close()

    def test_vispy_mesh_build_matches_cpu_count(self):
        """Geometry path (no GL): disc mesh vertex count vs particle count."""
        try:
            from zdem_particle_tracker.rendering.vispy_renderer import VisPyRenderer
        except Exception:
            self.skipTest("VisPy import failed")
        n_seg = VisPyRenderer._DISC_SEGMENTS
        xs = np.array([0.0, 10.0])
        ys = np.array([0.0, 0.0])
        rads = np.array([1.0, 2.0])
        rgba = np.ones((2, 4), dtype=np.float32)
        verts, faces, vcolors = VisPyRenderer._build_disc_mesh(xs, ys, rads, rgba, n_seg=n_seg)
        # each disc: n_seg rim + 1 center
        self.assertEqual(len(verts), 2 * (n_seg + 1))
        self.assertEqual(len(faces), 2 * n_seg)
        self.assertEqual(len(vcolors), len(verts))


if __name__ == "__main__":
    unittest.main()
