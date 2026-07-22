"""Renderer backend selection (VisPy vs PyQtGraph fallback).

Environment:
  ZDEM_FORCE_PYQTGRAPH=1  — never use VisPy (safe for offscreen CI)
  ZDEM_FORCE_VISPY=1      — try VisPy even on offscreen (may fail)
  QT_QPA_PLATFORM=offscreen — default to PyQtGraph unless FORCE_VISPY
"""
from __future__ import annotations

import os
from typing import Optional


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def is_offscreen_qt() -> bool:
    plat = (os.environ.get("QT_QPA_PLATFORM") or "").strip().lower()
    return plat in ("offscreen", "minimal", "null")


def prefer_vispy() -> bool:
    """Whether VisPy should be attempted for MainViewer."""
    if _env_truthy("ZDEM_FORCE_PYQTGRAPH"):
        return False
    if _env_truthy("ZDEM_FORCE_VISPY"):
        return True
    if is_offscreen_qt():
        # offscreen has no OpenGL context on many hosts
        return False
    return True


def try_import_vispy_renderer():
    """Return VisPyRenderer class or None."""
    if not prefer_vispy():
        return None
    try:
        from .vispy_renderer import VisPyRenderer

        return VisPyRenderer
    except Exception:
        return None


def opengl_context_ok(canvas=None) -> bool:
    """Best-effort check: can we render a tiny frame?"""
    if canvas is None:
        return False
    try:
        img = canvas.render(alpha=True)
        return img is not None and getattr(img, "size", 0) > 0
    except Exception:
        return False


def gl_available_for_tests() -> bool:
    """True when VisPy pixel tests should run (not forced pyqtgraph / not offscreen)."""
    if _env_truthy("ZDEM_FORCE_PYQTGRAPH"):
        return False
    if is_offscreen_qt() and not _env_truthy("ZDEM_FORCE_VISPY"):
        return False
    try:
        from .vispy_renderer import VisPyRenderer  # noqa: F401

        return True
    except Exception:
        return False
