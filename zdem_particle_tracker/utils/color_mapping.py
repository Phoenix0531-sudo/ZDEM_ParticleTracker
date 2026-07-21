"""Color mapping — DAT color numbers (vectorized) and group colors."""
from __future__ import annotations

from typing import Any

import numpy as np
from PySide6.QtGui import QColor


# Predefined distinguishable colours (RGB as packed int 0xRRGGBB)
_DISTINCT_COLORS = [
    0xE6194B,  # red
    0x3CB44B,  # green
    0x4363D8,  # blue
    0xF58231,  # orange
    0x911EB4,  # purple
    0x46F0F0,  # cyan
    0xF032E6,  # magenta
    0xBCF60C,  # lime
    0xFABEBE,  # pink
    0x008080,  # teal
    0xE6BEFF,  # lavender
    0x9A6324,  # brown
    0xFFE119,  # yellow
    0x800000,  # maroon
    0xAFFCF5,  # mint
    0x000075,  # navy
    0xA9A9A9,  # grey
    0xFFD8B1,  # apricot
    0x000000,  # black
]


def color_numbers_to_rgba(colors: np.ndarray, alpha: float = 1.0) -> np.ndarray:
    """Vectorized DAT color-number → RGBA float32 (N, 4).

    Formula matches MainViewer historical mapping:
        r = (c * 37 + 30) % 256
        g = (c * 71 + 40) % 256
        b = (c * 113 + 150) % 256
    """
    c = np.asarray(colors, dtype=np.int64).ravel()
    n = c.size
    if n == 0:
        return np.zeros((0, 4), dtype=np.float32)
    r = (c * 37 + 30) % 256
    g = (c * 71 + 40) % 256
    b = (c * 113 + 150) % 256
    out = np.empty((n, 4), dtype=np.float32)
    out[:, 0] = r.astype(np.float32) / 255.0
    out[:, 1] = g.astype(np.float32) / 255.0
    out[:, 2] = b.astype(np.float32) / 255.0
    out[:, 3] = float(alpha)
    return out


def color_number_to_qcolor(c: int) -> QColor:
    """Single color-number → QColor (UI widgets only)."""
    c = int(c)
    return QColor((c * 37 + 30) % 256, (c * 71 + 40) % 256, (c * 113 + 150) % 256)


class ColorMapping:
    """Stable mapping from group names to colours."""

    _PREDEFINED: dict[str, int] = {
        "base": 0x4363D8,
        "salt": 0xE6194B,
        "sedup": 0x3CB44B,
        "f": 0xF58231,
        "sand": 0xD4A574,
        "***": 0x999999,
    }

    def __init__(self) -> None:
        self._mapping: dict[str, int] = dict(self._PREDEFINED)
        self._next_color_index: int = 0

    def get_color(self, group: str) -> int:
        if not group:
            return 0x999999
        if group not in self._mapping:
            self._assign_new_color(group)
        return self._mapping[group]

    def get_qcolor(self, group: str) -> QColor:
        packed = self.get_color(group)
        return QColor((packed >> 16) & 0xFF, (packed >> 8) & 0xFF, packed & 0xFF)

    def set_color(self, group: str, color: int) -> None:
        self._mapping[group] = color & 0xFFFFFF

    def has_group(self, group: str) -> bool:
        return group in self._mapping

    @property
    def groups(self) -> list[str]:
        return list(self._mapping.keys())

    @property
    def mapping(self) -> dict[str, int]:
        return dict(self._mapping)

    def to_dict(self) -> dict[str, int]:
        return dict(self._mapping)

    def from_dict(self, data: dict[str, Any]) -> None:
        self._mapping.clear()
        self._mapping.update(self._PREDEFINED)
        for k, v in (data or {}).items():
            try:
                self._mapping[str(k)] = int(v) & 0xFFFFFF
            except Exception:
                continue
        self._reset_color_index()

    def _assign_new_color(self, group: str) -> None:
        color = _DISTINCT_COLORS[self._next_color_index % len(_DISTINCT_COLORS)]
        self._next_color_index += 1
        self._mapping[group] = color

    def _reset_color_index(self) -> None:
        self._next_color_index = len(self._mapping)

    def __repr__(self) -> str:
        return (
            f"ColorMapping(groups={len(self._mapping)}, "
            f"predefined={list(self._PREDEFINED.keys())})"
        )


_DEFAULT_MAPPER = ColorMapping()


def group_to_color(group: str, color_number: int = 0) -> QColor:
    """Return a QColor for *group* using the global ColorMapping singleton."""
    del color_number
    packed = _DEFAULT_MAPPER.get_color(str(group))
    r = (packed >> 16) & 0xFF
    g = (packed >> 8) & 0xFF
    b = packed & 0xFF
    return QColor(r, g, b)
