"""CPU raster helpers for pixel-level tests without OpenGL.

Used to assert particle disc placement / colors when GL is unavailable,
and as a ground-truth reference for VisPy screenshots when GL works.
"""
from __future__ import annotations

import numpy as np


def rasterize_discs(
    xs: np.ndarray,
    ys: np.ndarray,
    rads: np.ndarray,
    rgba: np.ndarray,
    *,
    xmin: float,
    xmax: float,
    ymin: float,
    ymax: float,
    width: int = 200,
    height: int = 150,
    bg: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
) -> np.ndarray:
    """Raster filled discs in data coords → RGBA uint8 image (H, W, 4).

    y-up data coordinates (scientific): row 0 is ymax.
    Later particles overwrite earlier ones (painter's algorithm).
    """
    xs = np.asarray(xs, dtype=np.float64)
    ys = np.asarray(ys, dtype=np.float64)
    rads = np.asarray(rads, dtype=np.float64)
    rgba = np.asarray(rgba, dtype=np.float64)
    if rgba.ndim != 2 or rgba.shape[1] < 3:
        raise ValueError("rgba must be (N, 3|4)")
    if rgba.shape[1] == 3:
        a = np.ones((rgba.shape[0], 1), dtype=np.float64)
        rgba = np.hstack([rgba, a])
    n = len(xs)
    img = np.empty((height, width, 4), dtype=np.float64)
    img[:] = bg

    dx = (xmax - xmin) / max(width, 1)
    dy = (ymax - ymin) / max(height, 1)
    # pixel centers
    px = xmin + (np.arange(width) + 0.5) * dx
    py = ymax - (np.arange(height) + 0.5) * dy  # row 0 = top = ymax
    XX, YY = np.meshgrid(px, py)

    for i in range(n):
        r = float(rads[i])
        if r <= 0:
            continue
        mask = (XX - xs[i]) ** 2 + (YY - ys[i]) ** 2 <= r * r
        col = rgba[i]
        a = float(col[3]) if col.shape[0] > 3 else 1.0
        a = max(0.0, min(1.0, a))
        for c in range(3):
            img[..., c] = np.where(
                mask, col[c] * a + img[..., c] * (1.0 - a), img[..., c]
            )
        img[..., 3] = np.where(mask, np.maximum(img[..., 3], a), img[..., 3])

    out = np.clip(img * 255.0, 0, 255).astype(np.uint8)
    return out


def dominant_color_at(
    img: np.ndarray, row: int, col: int, radius: int = 2
) -> tuple[int, int, int]:
    """Mean RGB in a small window around (row, col)."""
    h, w = img.shape[:2]
    r0 = max(0, row - radius)
    r1 = min(h, row + radius + 1)
    c0 = max(0, col - radius)
    c1 = min(w, col + radius + 1)
    patch = img[r0:r1, c0:c1, :3].astype(np.float64)
    m = patch.reshape(-1, 3).mean(axis=0)
    return int(m[0]), int(m[1]), int(m[2])


def data_to_pixel(
    x: float,
    y: float,
    *,
    xmin: float,
    xmax: float,
    ymin: float,
    ymax: float,
    width: int,
    height: int,
) -> tuple[int, int]:
    """Map data (x,y) y-up → (row, col)."""
    col = int((x - xmin) / (xmax - xmin) * width)
    row = int((ymax - y) / (ymax - ymin) * height)
    col = max(0, min(width - 1, col))
    row = max(0, min(height - 1, row))
    return row, col


def channel_dominance(rgb: tuple[int, int, int], channel: int, margin: int = 30) -> bool:
    """True if channel is clearly highest among R,G,B."""
    vals = list(rgb)
    return vals[channel] >= max(vals) and vals[channel] >= min(vals) + margin
