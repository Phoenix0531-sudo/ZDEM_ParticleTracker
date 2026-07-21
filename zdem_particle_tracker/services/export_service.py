"""ExportService — export trajectory data as CSV and PNG plots."""

from __future__ import annotations

import csv
import os
from typing import List, Optional

import numpy as np
from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from . import Trajectory, TrajectoryPoint

# ── CSV field definitions ────────────────────────────────────────────────────

CSV_FIELDS = [
    "particle_id",
    "file_index",
    "time_step",
    "x_km",
    "y_km",
    "radius_km",
    "group",
    "original_color",
    "displacement_x_km",
    "displacement_y_km",
    "displacement_total_km",
    "increment_x_km",
    "increment_y_km",
    "increment_total_km",
    "velocity_x",
    "velocity_y",
    "velocity_total",
    "delta_step",
    "path_length_km",
    "status",
    "source_file",
]

_CSV_FLOAT_FMT = "{:.6f}"


def _point_row(pt: TrajectoryPoint) -> dict:
    def f(v: float) -> str:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return ""
        return _CSV_FLOAT_FMT.format(v)

    return {
        "particle_id": pt.particle_id,
        "file_index": pt.file_index,
        "time_step": pt.time_step,
        "x_km": f(pt.x_km),
        "y_km": f(pt.y_km),
        "radius_km": f(pt.radius_km),
        "group": pt.group,
        "original_color": pt.original_color,
        "displacement_x_km": f(pt.displacement_x_km),
        "displacement_y_km": f(pt.displacement_y_km),
        "displacement_total_km": f(pt.displacement_total_km),
        "increment_x_km": f(pt.increment_x_km),
        "increment_y_km": f(pt.increment_y_km),
        "increment_total_km": f(pt.increment_total_km),
        "velocity_x": f(pt.velocity_x),
        "velocity_y": f(pt.velocity_y),
        "velocity_total": f(pt.velocity_total),
        "delta_step": f(pt.delta_step),
        "path_length_km": f(pt.path_length_km),
        "status": pt.status,
        "source_file": pt.source_file,
    }


class ExportService:
    """Export trajectory data as CSV files and PNG plots.

    Uses ``QFileDialog`` for save-path selection and warns before
    overwriting existing files.
    """

    def __init__(self, parent_widget: QWidget | None = None) -> None:
        self._parent = parent_widget

    # -----------------------------------------------------------------
    #  CSV export
    # -----------------------------------------------------------------
    def export_csv(
        self,
        trajectory: Trajectory,
        default_name: str = "trajectory.csv",
    ) -> str | None:
        """Open a *Save As* dialog and write trajectory data to CSV.

        Returns the saved path or *None* if the user cancelled.
        """
        path, _ = QFileDialog.getSaveFileName(
            self._parent,
            "导出轨迹 CSV",
            default_name,
            "CSV Files (*.csv);;All Files (*)",
        )
        if not path:
            return None

        if not self._confirm_overwrite(path):
            return None

        self._write_csv(trajectory, path)
        return path

    # -----------------------------------------------------------------
    def export_csv_to(
        self,
        trajectory: Trajectory,
        path: str,
        overwrite: bool = False,
    ) -> bool:
        """Write trajectory to *path* without a dialog.

        Returns ``True`` on success.
        """
        if os.path.exists(path) and not overwrite:
            return False
        self._write_csv(trajectory, path)
        return True

    # -----------------------------------------------------------------
    #  PNG export
    # -----------------------------------------------------------------
    def export_png(
        self,
        plot_widget,
        default_name: str = "trajectory.png",
    ) -> str | None:
        """Export the contents of a pyqtgraph PlotWidget to a PNG file.

        *plot_widget* must have a ``grab()`` or ``exportImage()`` method.
        Returns the saved path or *None* if cancelled.
        """
        path, _ = QFileDialog.getSaveFileName(
            self._parent,
            "导出图表 PNG",
            default_name,
            "PNG Images (*.png);;All Files (*)",
        )
        if not path:
            return None

        if not self._confirm_overwrite(path):
            return None

        pixmap = plot_widget.grab()
        pixmap.save(path, "PNG")
        return path

    # -----------------------------------------------------------------
    #  Internals
    # -----------------------------------------------------------------
    @staticmethod
    def _write_csv(trajectory: Trajectory, path: str) -> None:
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for pt in trajectory:
                writer.writerow(_point_row(pt))

    # -----------------------------------------------------------------
    def _confirm_overwrite(self, path: str) -> bool:
        if not os.path.exists(path):
            return True
        btn = QMessageBox.question(
            self._parent,
            "文件已存在",
            f"文件已存在:\n{os.path.basename(path)}\n\n是否覆盖？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return btn == QMessageBox.Yes
