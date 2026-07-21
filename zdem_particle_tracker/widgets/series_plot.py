"""Matplotlib series plot widget for in-app scientific curves.

Uses scienceplots when available for a cleaner journal-like look.
"""

from __future__ import annotations

from typing import Iterable, Optional, Sequence

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.ticker import AutoMinorLocator, MaxNLocator
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

# Apply scienceplots style once (safe if missing)
try:
    import scienceplots  # noqa: F401
    import matplotlib.pyplot as plt

    plt.style.use(["science", "no-latex", "notebook"])
except Exception:
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#222222",
            "axes.linewidth": 0.9,
            "axes.labelsize": 10,
            "axes.titlesize": 11,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "xtick.direction": "in",
            "ytick.direction": "in",
            "xtick.top": True,
            "ytick.right": True,
            "legend.fontsize": 9,
            "font.size": 10,
            "lines.linewidth": 1.4,
            "lines.markersize": 3.5,
            "savefig.dpi": 300,
            "axes.grid": False,
        }
    )


# Colorblind-friendly sequential palette for multi-series UI
_PALETTE = {
    "default": "#1f4e79",
    "speed": "#8B1A1A",
    "vx": "#1a5f2a",
    "vy": "#5b3a8c",
    "dx": "#0B3D91",
    "dy": "#B35C00",
    "dt": "#1f4e79",
    "pl": "#2F4F4F",
}


class SeriesPlotWidget(QWidget):
    """One-axis time-series plot embedded in Qt."""

    def __init__(
        self,
        ylabel: str,
        xlabel: str = "Time step",
        color_key: str = "default",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._ylabel = ylabel
        self._xlabel = xlabel
        self._color = _PALETTE.get(color_key, _PALETTE["default"])

        self._fig = Figure(figsize=(5.2, 3.4), dpi=120, tight_layout=True)
        self._ax = self._fig.add_subplot(111)
        self._canvas = FigureCanvas(self._fig)
        self._canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._canvas)

        self._line = None
        self._scatter = None
        self._setup_axes()
        self.clear()

    def _setup_axes(self) -> None:
        ax = self._ax
        ax.set_xlabel(self._xlabel)
        ax.set_ylabel(self._ylabel)
        ax.tick_params(axis="both", which="both", direction="in", top=True, right=True)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=6, integer=False))
        ax.yaxis.set_major_locator(MaxNLocator(nbins=6))
        ax.xaxis.set_minor_locator(AutoMinorLocator(2))
        ax.yaxis.set_minor_locator(AutoMinorLocator(2))
        for spine in ax.spines.values():
            spine.set_linewidth(0.9)
            spine.set_color("#222222")
        self._fig.subplots_adjust(left=0.14, right=0.97, bottom=0.15, top=0.95)

    def clear(self) -> None:
        self._ax.cla()
        self._setup_axes()
        self._line = None
        self._scatter = None
        self._ax.text(
            0.5,
            0.5,
            "No trajectory",
            transform=self._ax.transAxes,
            ha="center",
            va="center",
            color="#999999",
            fontsize=10,
        )
        self._canvas.draw_idle()

    def set_series(
        self,
        x: Sequence[float],
        y: Sequence[float],
        color: Optional[str] = None,
        marker: bool = True,
    ) -> None:
        """Replace the series data and redraw."""
        xs = np.asarray(x, dtype=float)
        ys = np.asarray(y, dtype=float)
        if xs.size == 0 or ys.size == 0 or xs.size != ys.size:
            self.clear()
            return

        # Drop non-finite pairs
        m = np.isfinite(xs) & np.isfinite(ys)
        xs, ys = xs[m], ys[m]
        if xs.size == 0:
            self.clear()
            return

        c = color or self._color
        self._ax.cla()
        self._setup_axes()

        if marker and xs.size <= 200:
            self._line = self._ax.plot(
                xs,
                ys,
                color=c,
                lw=1.5,
                marker="o",
                ms=3.2,
                mfc="white",
                mec=c,
                mew=0.9,
                solid_capstyle="round",
            )[0]
        else:
            # Many points: line only to keep UI snappy
            self._line = self._ax.plot(xs, ys, color=c, lw=1.5, solid_capstyle="round")[0]

        # Light padding
        xpad = max((xs.max() - xs.min()) * 0.03, 1.0) if xs.size > 1 else 1.0
        yspan = ys.max() - ys.min()
        ypad = max(yspan * 0.08, 1e-12)
        self._ax.set_xlim(xs.min() - xpad, xs.max() + xpad)
        self._ax.set_ylim(ys.min() - ypad, ys.max() + ypad)

        # Zero reference line for velocity/displacement style plots
        if ys.min() < 0 < ys.max() or (abs(ys.min()) < 1e-15 and ys.max() >= 0):
            self._ax.axhline(0.0, color="#bbbbbb", lw=0.7, zorder=0)

        self._canvas.draw_idle()


def make_series_tabs() -> dict:
    """Factory used by MainViewer: name -> SeriesPlotWidget."""
    return {
        "dx": SeriesPlotWidget("X displacement (km)", color_key="dx"),
        "dy": SeriesPlotWidget("Y displacement (km)", color_key="dy"),
        "dt": SeriesPlotWidget("Total displacement (km)", color_key="dt"),
        "pl": SeriesPlotWidget("Path length (km)", color_key="pl"),
        "v": SeriesPlotWidget(r"Speed $|v|$ (km/step)", color_key="speed"),
        "vx": SeriesPlotWidget(r"$V_x$ (km/step)", color_key="vx"),
        "vy": SeriesPlotWidget(r"$V_y$ (km/step)", color_key="vy"),
    }
