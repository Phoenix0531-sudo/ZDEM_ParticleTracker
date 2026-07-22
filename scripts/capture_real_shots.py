"""Capture real Qt screenshots with a valid synthetic ZDEM DAT frame."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)


def write_zdem_dat(path: Path, step: int, seed: int = 0) -> None:
    rng = np.random.default_rng(seed + step)
    n = 120
    xs = rng.uniform(8, 92, n)
    ys = rng.uniform(8, 52, n)
    rs = rng.uniform(1.0, 2.4, n)
    ids = np.arange(1000, 1000 + n)
    colors = rng.integers(0, 5, n)
    lines = [
        "Parameter Data",
        f"current_step: {step}",
        f"ball_num: {n}",
        "left: 0.0",
        "right: 100.0",
        "bottom: 0.0",
        "height: 60.0",
        "",
        "Wall Data",
        "  wall num 4",
        "  P1[0]    P1[1]    P2[0]    P2[1]",
        "  0.0      0.0      100.0    0.0",
        "  100.0    0.0      100.0    60.0",
        "  100.0    60.0     0.0      60.0",
        "  0.0      60.0     0.0      0.0",
        "",
        "Ball Data",
        "  index        id            x            y         rad      color",
    ]
    for i in range(n):
        lines.append(
            f" {i+1}  {ids[i]}  {xs[i]:.4f}  {ys[i]:.4f}  {rs[i]:.4f}  {int(colors[i])}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "windows")
    # Prefer CPU/pyqtgraph path for reliable grab of particle layer
    os.environ["ZDEM_FORCE_PYQTGRAPH"] = "1"

    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)

    from zdem_particle_tracker.widgets.main_viewer import MainViewer

    tmp = Path(tempfile.mkdtemp(prefix="zdem_ss_"))
    write_zdem_dat(tmp / "all_0.dat", 0, seed=1)
    write_zdem_dat(tmp / "all_1.dat", 1, seed=2)
    write_zdem_dat(tmp / "all_2.dat", 2, seed=3)
    print("sample dir", tmp)

    win = MainViewer()
    win.resize(1440, 920)
    win.setWindowTitle("ZDEM Particle Tracker")
    win.show()
    app.processEvents()

    # Load directory
    loaded = False
    for meth in ("load_directory", "open_directory", "set_directory"):
        if hasattr(win, meth):
            try:
                getattr(win, meth)(str(tmp))
                loaded = True
                print("loaded via", meth)
                break
            except Exception as exc:
                print(meth, exc)

    # Allow workers / UI refresh
    for _ in range(30):
        app.processEvents()
        QTimer.singleShot(0, lambda: None)
        app.processEvents()

    import time

    time.sleep(0.8)
    for _ in range(50):
        app.processEvents()

    def grab(name: str) -> Path:
        app.processEvents()
        pix: QPixmap = win.grab()
        path = OUT / name
        if not pix.save(str(path), "PNG"):
            raise RuntimeError(f"save failed {path}")
        print(f"OK {path} {path.stat().st_size} bytes")
        return path

    grab("gui_main.png")
    grab("gui_with_data.png")

    # Try fit particles if available
    for meth in ("fit_particles", "on_fit_particles", "_fit_particles"):
        if hasattr(win, meth):
            try:
                getattr(win, meth)()
                time.sleep(0.3)
                for _ in range(20):
                    app.processEvents()
                grab("gui_fitted.png")
            except Exception as exc:
                print("fit", exc)
            break

    win.close()
    app.quit()
    print("done loaded=", loaded)


if __name__ == "__main__":
    main()
