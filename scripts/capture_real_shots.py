"""Capture real MainViewer screenshots from existing ZDEM test samples.

Does NOT invent particle layouts. Uses SAMPLE_CANDIDATES from
tests/test_render_pixels.py, plus ZDEM_Area_Conservation/data as fallback.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

# Same candidates as tests/test_render_pixels.py + monorepo Area data
SAMPLE_CANDIDATES = [
    Path(r"D:/2_Temp/StructLab/Projects/25_造山带尺度盐构造/物理实验复刻/2/data"),
    Path(r"D:/2_Temp/StructLab/Projects/25_造山带尺度盐构造/物理实验复刻/1/data"),
    ROOT.parent / "ZDEM_Area_Conservation" / "data",
]


def find_sample() -> Path:
    for p in SAMPLE_CANDIDATES:
        if p.is_dir() and any(p.glob("all_*.dat")):
            return p
    raise SystemExit(
        "No real ZDEM sample found. Expected one of:\n  "
        + "\n  ".join(str(p) for p in SAMPLE_CANDIDATES)
    )


def wait_loaded(app, win, timeout: float = 180.0) -> bool:
    from PySide6.QtCore import QEventLoop

    deadline = time.time() + timeout
    while time.time() < deadline:
        for _ in range(20):
            app.processEvents(QEventLoop.AllEvents, 50)
        data = getattr(win, "_current_data", None)
        if data is not None and getattr(data, "count", 0) > 0:
            return True
    return False


def settle(app, n: int = 30, sleep_s: float = 0.4) -> None:
    from PySide6.QtCore import QEventLoop

    for _ in range(n):
        app.processEvents(QEventLoop.AllEvents, 50)
    time.sleep(sleep_s)
    for _ in range(n):
        app.processEvents(QEventLoop.AllEvents, 50)


def zoom_to_particles(win) -> None:
    """Tight camera on real particle bbox (screenshot-only; unlock aspect)."""
    import numpy as np

    d = win._current_data
    if d is None or d.count == 0:
        return
    pad_x = max(float(np.max(d.rads)) * 6, (float(d.xs.max()) - float(d.xs.min())) * 0.02)
    pad_y = max(float(np.max(d.rads)) * 8, (float(d.ys.max()) - float(d.ys.min())) * 0.08)
    xmin = float(d.xs.min()) - pad_x
    xmax = float(d.xs.max()) + pad_x
    ymin = float(d.ys.min()) - pad_y
    ymax = float(d.ys.max()) + pad_y
    # DEM sections are wide — unlock aspect so the band fills the canvas
    try:
        vb = win._plot.getViewBox()
        vb.setAspectLocked(False)
        vb.setRange(xRange=(xmin, xmax), yRange=(ymin, ymax), padding=0.0)
    except Exception:
        win._fit_particles()


def main() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "windows")
    os.environ["ZDEM_FORCE_PYQTGRAPH"] = "1"

    sample = find_sample()
    print("sample", sample)

    from PySide6.QtCore import QEventLoop
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QApplication
    from zdem_particle_tracker.widgets.main_viewer import MainViewer

    app = QApplication.instance() or QApplication(sys.argv)
    win = MainViewer()
    win.resize(1600, 900)
    win.setWindowTitle("ZDEM Particle Tracker")
    win.show()
    app.processEvents()

    win.load_directory(str(sample))
    if not wait_loaded(app, win, timeout=180.0):
        raise SystemExit("frame load timed out")

    # Prefer a mid/late frame (more structure) if series is long
    nframes = len(getattr(win, "_frame_files", []) or [])
    if nframes > 3:
        mid = min(nframes - 1, max(1, nframes // 3))
        try:
            win._load_frame(mid, force=True)
            if not wait_loaded(app, win, timeout=120.0):
                print("mid frame load failed, keeping first")
            else:
                print(f"jumped to frame index {mid}/{nframes}")
        except Exception as exc:
            print("frame jump", exc)

    settle(app)
    data = win._current_data
    print(f"loaded particles={data.count} step={data.current_step}")

    zoom_to_particles(win)
    settle(app, n=40, sleep_s=0.6)

    def grab(name: str) -> Path:
        app.processEvents(QEventLoop.AllEvents, 50)
        pix: QPixmap = win.grab()
        path = OUT / name
        if not pix.save(str(path), "PNG"):
            raise RuntimeError(f"save failed {path}")
        print(f"OK {path.name} {path.stat().st_size} bytes")
        return path

    grab("gui_main.png")
    grab("gui_with_data.png")
    grab("gui_fitted.png")

    # Hero = full window grab (real UI + real particles)
    hero = OUT / "gui_hero.png"
    (OUT / "gui_fitted.png").replace(hero) if False else None
    from shutil import copyfile

    copyfile(OUT / "gui_fitted.png", hero)
    print(f"hero {hero} n={data.count}")

    (OUT / "capture_source.txt").write_text(
        f"sample_dir={sample}\n"
        f"particles={data.count}\n"
        f"step={data.current_step}\n"
        f"nframes={nframes}\n"
        f"source=real ZDEM DAT from test sample path (tests/test_render_pixels SAMPLE_CANDIDATES)\n"
        f"note=not synthetic random particles; camera zoomed to particle bbox for readability\n",
        encoding="utf-8",
    )
    print((OUT / "capture_source.txt").read_text(encoding="utf-8"))

    win.close()
    app.quit()
    print("done")


if __name__ == "__main__":
    main()
