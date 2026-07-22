"""Regression: trajectory cancel must emit finished (not hang UI)."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QTimer

from zdem_particle_tracker.services import FileInfo, TrajectoryService


class TestTrajectoryCancel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_cancel_emits_finished(self):
        # Use real sample if present; else tiny missing paths still exercise cancel path
        sample = Path(r"D:/2_Temp/StructLab/Projects/25_造山带尺度盐构造/物理实验复刻/2/data")
        files: list[FileInfo] = []
        if sample.is_dir():
            dats = sorted(sample.glob("all_*.dat"))[:8]
            for i, p in enumerate(dats):
                files.append(
                    FileInfo(i, p.name, i * 1000, str(p), p.stat().st_size, "pending")
                )
        if not files:
            # fallback synthetic missing files — cancel still must finish
            for i in range(6):
                files.append(
                    FileInfo(i, f"all_{i}.dat", i, f"/no/such/{i}.dat", 0, "pending")
                )

        svc = TrajectoryService()
        events: list = []

        def on_fin(tr):
            events.append(("fin", len(tr) if tr is not None else None))
            self.app.quit()

        def on_err(m):
            events.append(("err", m))
            self.app.quit()

        w = svc.start(1, files, max_workers=4)
        w.finished.connect(on_fin)
        w.error.connect(on_err)
        QTimer.singleShot(30, svc.cancel)
        QTimer.singleShot(5000, self.app.quit)
        self.app.exec()
        self.assertTrue(events, "cancel produced no finished/error signal")
        self.assertEqual(events[0][0], "fin", f"expected finished, got {events}")


if __name__ == "__main__":
    unittest.main()
