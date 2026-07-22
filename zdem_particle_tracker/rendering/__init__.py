"""Rendering package — VisPy GPU path with CPU raster + backend selection."""

from .backend import gl_available_for_tests, prefer_vispy, try_import_vispy_renderer
from .cpu_raster import channel_dominance, data_to_pixel, dominant_color_at, rasterize_discs

__all__ = [
    "prefer_vispy",
    "try_import_vispy_renderer",
    "gl_available_for_tests",
    "rasterize_discs",
    "data_to_pixel",
    "dominant_color_at",
    "channel_dominance",
    "VisPyRenderer",
]


def __getattr__(name: str):
    if name == "VisPyRenderer":
        cls = try_import_vispy_renderer()
        if cls is None:
            raise AttributeError("VisPyRenderer unavailable")
        return cls
    raise AttributeError(name)
