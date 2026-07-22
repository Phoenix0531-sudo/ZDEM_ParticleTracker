"""TrajectoryService — extract particle trajectory across frame files."""

from __future__ import annotations

import math
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from PySide6.QtCore import QThread, Signal

from ..parsers.dat_parser import find_particle_in_file
from . import FileInfo, Trajectory, TrajectoryPoint


def _compute_kinematics(
    x: float,
    y: float,
    step: int,
    first_x: Optional[float],
    first_y: Optional[float],
    prev_x: Optional[float],
    prev_y: Optional[float],
    prev_step: Optional[int],
    path_length: float,
) -> tuple:
    """Return (first_x, first_y, prev_x, prev_y, prev_step, path_length, fields_dict)."""
    if first_x is None:
        first_x, first_y = x, y
    if prev_x is None:
        prev_x, prev_y = x, y
    if prev_step is None:
        prev_step = step

    dx = x - first_x
    dy = y - first_y
    dt = math.hypot(dx, dy)

    ix = x - prev_x
    iy = y - prev_y
    it = math.hypot(ix, iy)
    path_length = path_length + it

    # Velocity: step difference (km / step). First valid sample → 0.
    dstep = float(step - prev_step)
    if dstep > 0:
        vx = ix / dstep
        vy = iy / dstep
        vtot = math.hypot(vx, vy)
    else:
        vx = 0.0
        vy = 0.0
        vtot = 0.0
        dstep = 0.0

    fields = dict(
        displacement_x_km=dx,
        displacement_y_km=dy,
        displacement_total_km=dt,
        increment_x_km=ix,
        increment_y_km=iy,
        increment_total_km=it,
        velocity_x=vx,
        velocity_y=vy,
        velocity_total=vtot,
        delta_step=dstep,
        path_length_km=path_length,
    )
    return first_x, first_y, x, y, step, path_length, fields


def _hit_to_present_fields(hit) -> dict:
    return dict(
        x_km=float(hit.x),
        y_km=float(hit.y),
        radius_km=float(hit.rad),
        group=str(hit.group or "***"),
        original_color=int(hit.color),
    )


class _TrajectoryWorker(QThread):
    """Worker that streams each DAT for one permanent particle id."""

    progress = Signal(int, int)  # current, total
    finished = Signal(object)  # Trajectory
    error = Signal(str)

    def __init__(
        self,
        particle_id: int,
        files: List[FileInfo],
        max_workers: int = 4,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._particle_id = int(particle_id)
        self._files = list(files)
        self._cancelled = False
        self._max_workers = max(1, int(max_workers))

    def cancel(self) -> None:
        self._cancelled = True

    def _scan_one(self, idx: int, finfo: FileInfo):
        if self._cancelled:
            return idx, "cancelled", None
        hit = find_particle_in_file(finfo.dat_path, self._particle_id)
        return idx, "ok", hit

    def run(self) -> None:
        total = len(self._files)
        if total == 0:
            self.finished.emit([])
            return

        # Parallel parse (I/O bound). Preserve order, stop after first eroded.
        # Progress uses contiguous time-order prefix so the bar never jumps backward
        # when futures complete out of order.
        results: dict[int, object] = {}
        try:
            with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
                futures = {
                    pool.submit(self._scan_one, idx, finfo): idx
                    for idx, finfo in enumerate(self._files)
                }
                done_flags = [False] * total
                contiguous = 0
                for fut in as_completed(futures):
                    if self._cancelled:
                        for f in futures:
                            f.cancel()
                        return
                    idx, status, hit = fut.result()
                    results[idx] = (status, hit)
                    if 0 <= idx < total:
                        done_flags[idx] = True
                    while contiguous < total and done_flags[contiguous]:
                        contiguous += 1
                    # Contiguous prefix = "frames 0..k-1 ready" (time order)
                    self.progress.emit(contiguous, total)

            trajectory: Trajectory = []
            first_x: Optional[float] = None
            first_y: Optional[float] = None
            prev_x: Optional[float] = None
            prev_y: Optional[float] = None
            prev_step: Optional[int] = None
            path_length = 0.0
            eroded = False

            for idx, finfo in enumerate(self._files):
                if self._cancelled:
                    return
                if eroded:
                    trajectory.append(
                        TrajectoryPoint(
                            particle_id=self._particle_id,
                            file_index=idx,
                            time_step=int(getattr(finfo, "current_step", 0) or 0),
                            x_km=math.nan,
                            y_km=math.nan,
                            radius_km=0.0,
                            status="eroded",
                            source_file=os.path.basename(finfo.dat_path),
                            path_length_km=path_length,
                        )
                    )
                    self.progress.emit(idx + 1, total)
                    continue

                status, hit = results.get(idx, ("missing", None))
                if status != "ok" or hit is None:
                    trajectory.append(
                        TrajectoryPoint(
                            particle_id=self._particle_id,
                            file_index=idx,
                            time_step=int(getattr(finfo, "current_step", 0) or 0),
                            x_km=math.nan,
                            y_km=math.nan,
                            radius_km=0.0,
                            status="file_error",
                            source_file=os.path.basename(finfo.dat_path),
                            path_length_km=path_length,
                        )
                    )
                    self.progress.emit(idx + 1, total)
                    continue

                if not hit.file_ok:
                    trajectory.append(
                        TrajectoryPoint(
                            particle_id=self._particle_id,
                            file_index=idx,
                            time_step=int(hit.current_step or getattr(finfo, "current_step", 0) or 0),
                            x_km=math.nan,
                            y_km=math.nan,
                            radius_km=0.0,
                            status="file_error",
                            source_file=os.path.basename(finfo.dat_path),
                            path_length_km=path_length,
                        )
                    )
                    self.progress.emit(idx + 1, total)
                    continue

                step = int(hit.current_step or getattr(finfo, "current_step", 0) or 0)

                if hit.found:
                    fields = _hit_to_present_fields(hit)
                    first_x, first_y, prev_x, prev_y, prev_step, path_length, kin = (
                        _compute_kinematics(
                            fields["x_km"],
                            fields["y_km"],
                            step,
                            first_x,
                            first_y,
                            prev_x,
                            prev_y,
                            prev_step,
                            path_length,
                        )
                    )
                    trajectory.append(
                        TrajectoryPoint(
                            particle_id=self._particle_id,
                            file_index=idx,
                            time_step=step,
                            status="normal",
                            source_file=os.path.basename(finfo.dat_path),
                            **fields,
                            **kin,
                        )
                    )
                else:
                    # Valid file, id missing → permanent erosion
                    eroded = True
                    trajectory.append(
                        TrajectoryPoint(
                            particle_id=self._particle_id,
                            file_index=idx,
                            time_step=step,
                            x_km=math.nan,
                            y_km=math.nan,
                            radius_km=0.0,
                            status="eroded",
                            source_file=os.path.basename(finfo.dat_path),
                            path_length_km=path_length,
                        )
                    )
                self.progress.emit(idx + 1, total)

            self.finished.emit(trajectory)
        except Exception as exc:
            self.error.emit(str(exc))


class TrajectoryService:
    """High-level trajectory extraction manager."""

    def __init__(self) -> None:
        self._worker: Optional[_TrajectoryWorker] = None

    def start(
        self,
        particle_id: int,
        files: List[FileInfo],
        max_workers: int = 4,
    ) -> _TrajectoryWorker:
        self.cancel()
        worker = _TrajectoryWorker(particle_id, files, max_workers=max_workers)
        self._worker = worker
        worker.start()
        return worker

    def cancel(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        self._worker = None

    @property
    def is_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()
