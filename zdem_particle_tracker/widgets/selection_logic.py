"""Pure selection / session-start gate helpers (no Qt).

Keeps MainViewer thinner and unit-testable without a display.
"""
from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np


def id_allowed_at_session_start(start_ids: set[int] | None, pid: int) -> bool:
    """True if permanent id exists in the session start frame set."""
    if start_ids is None:
        return False
    return int(pid) in start_ids


def pick_particle_id(
    xs: np.ndarray,
    ys: np.ndarray,
    rads: np.ndarray,
    ids: np.ndarray,
    x: float,
    y: float,
    *,
    start_ids: set[int] | None,
    k: int = 8,
    tree=None,
) -> int | None:
    """Pick permanent id near (x, y), only among session-start IDs.

    Prefer discs that cover the click; else nearest within soft radius.
    ``tree`` may be a scipy.cKDTree over (xs, ys); if None, builds one.
    """
    n = int(len(ids))
    if n == 0:
        return None
    pts = np.column_stack([np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)])
    if tree is None:
        from scipy.spatial import cKDTree

        tree = cKDTree(pts)
    kk = min(max(1, int(k)), n)
    dists, idxs = tree.query(np.array([[float(x), float(y)]]), k=kk)
    dists = np.atleast_1d(np.asarray(dists).ravel())
    idxs = np.atleast_1d(np.asarray(idxs).ravel())

    best_i = None
    best_dist = None
    for dist, i in zip(dists, idxs):
        i = int(i)
        if i < 0 or i >= n:
            continue
        pid = int(ids[i])
        if not id_allowed_at_session_start(start_ids, pid):
            continue
        rad = float(rads[i])
        if float(dist) <= max(rad, 1e-9):
            if best_dist is None or float(dist) < best_dist:
                best_i, best_dist = i, float(dist)
    if best_i is None:
        soft = float(np.median(rads)) * 3.0 if n else 100.0
        for dist, i in zip(dists, idxs):
            i = int(i)
            if i < 0 or i >= n:
                continue
            pid = int(ids[i])
            if not id_allowed_at_session_start(start_ids, pid):
                continue
            if float(dist) <= soft:
                best_i = i
                break
    if best_i is None:
        return None
    return int(ids[best_i])


def filter_trajectory_path_xy(
    points: Sequence,
    *,
    path_to_current: bool,
    current_step: int | None,
) -> tuple[list[float], list[float]]:
    """Extract polyline (xs, ys) from trajectory points for path overlay.

    Stops at eroded / NaN; if path_to_current, stops past current_step.
    Points need attributes: status, x_km, y_km, time_step.
    """
    xs: list[float] = []
    ys: list[float] = []
    for p in points:
        status = getattr(p, "status", "")
        if status not in ("normal", "present"):
            continue
        x = getattr(p, "x_km", None)
        y = getattr(p, "y_km", None)
        if x is None or y is None:
            continue
        if isinstance(x, float) and np.isnan(x):
            continue
        step = int(getattr(p, "time_step", 0))
        if path_to_current and current_step is not None and step > int(current_step):
            break
        xs.append(float(x))
        ys.append(float(y))
    return xs, ys


def play_parse_mode_name(color_mode: str) -> str:
    """Return ParseMode name for playback/prefetch given color mode."""
    if (color_mode or "").lower() in ("group", "by_group"):
        return "FULL_PARTICLE_PROPERTIES"
    return "BASIC_FRAME"


def next_play_index(current_idx: int, n_frames: int) -> int | None:
    """Next frame index for play, or None if at end / empty."""
    if n_frames <= 0:
        return None
    if current_idx >= n_frames - 1:
        return None
    return current_idx + 1


def validate_time_range_indices(start_i: int, end_i: int, n_entries: int) -> str | None:
    """Return error message or None if OK."""
    if n_entries <= 0:
        return "请先打开实验目录"
    if start_i < 0 or end_i < 0 or start_i >= n_entries or end_i >= n_entries:
        return "时间步索引无效"
    if end_i < start_i:
        return "结束时间步不能早于起始时间步"
    return None


def first_id_not_in_start(
    current_ids: Iterable[int], start_ids: set[int] | None
) -> int | None:
    """Find an id present now but not at session start (for gate tests)."""
    if start_ids is None:
        return None
    for i in current_ids:
        ii = int(i)
        if ii not in start_ids:
            return ii
    return None
