"""RegionDetector — determine view bounds from wall data or metadata."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np

from ..utils.logging_utils import get_logger
from . import Region

log = get_logger("services.region")


class RegionDetector:
    """Detect the rectangular region of interest for particle visualisation.

    Two detection strategies are available:

    * ``detect_from_walls`` — compute a bounding box from wall endpoint
      coordinates.
    * ``detect_from_metadata`` — use the ``left``, ``right``, ``bottom``,
      ``height`` values stored in a frame's metadata section.

    If walls do not form a clear rectangle the detector falls back to
    metadata when available.
    """

    # Tolerance for considering wall segments co-linear / axis‑aligned
    _COLINEAR_TOL = 1e-3

    # -----------------------------------------------------------------
    def detect_from_walls(
        self,
        walls: np.ndarray,
        metadata: Dict[str, float] | None = None,
    ) -> Region:
        """Compute bounding rectangle from wall endpoint data.

        Parameters
        ----------
        walls:
            Array of shape ``(N, 4)`` where columns are
            ``[x1, y1, x2, y2]`` — the two endpoints of each wall segment.
        metadata:
            Optional frame metadata dict with keys ``left``, ``right``,
            ``bottom``, ``height``.  Used as a fallback when walls do not
            produce a valid rectangle.

        Returns
        -------
        Region namedtuple.
        """
        if walls.ndim != 2 or walls.shape[1] < 4 or walls.shape[0] == 0:
            return self._fallback_region(metadata, "walls-empty")

        # Collect all unique endpoints
        pts = np.unique(
            np.column_stack([
                walls[:, 0], walls[:, 1],
                walls[:, 2], walls[:, 3],
            ]).reshape(-1, 2),
            axis=0,
        )
        if pts.shape[0] < 2:
            return self._fallback_region(metadata, "walls-no-endpoints")

        x_min, y_min = pts.min(axis=0)
        x_max, y_max = pts.max(axis=0)

        if x_max - x_min < self._COLINEAR_TOL or y_max - y_min < self._COLINEAR_TOL:
            return self._fallback_region(metadata, "walls-collinear")

        reg = Region(
            x_min=float(x_min),
            x_max=float(x_max),
            y_min=float(y_min),
            y_max=float(y_max),
            source="walls",
        )
        log.debug(
            "detect_from_walls n=%s -> X[%.1f,%.1f] Y[%.1f,%.1f]",
            walls.shape[0],
            reg.x_min,
            reg.x_max,
            reg.y_min,
            reg.y_max,
        )
        return reg

    # -----------------------------------------------------------------
    def detect_from_metadata(self, metadata: Dict[str, Any]) -> Region:
        """Construct a region from frame metadata.

        Expects keys ``left``, ``right``, ``bottom``, ``height`` (or ``top``).

        Semantics for ``height`` (ZDEM samples vary):
        - If ``height > bottom`` **and** treating height as *delta* would make
          ``y_max = bottom + height`` larger than a reasonable absolute top
          when bottom is near 0 and height itself looks like a top coordinate
          (common: bottom=0, height=50160 meaning top), use absolute top.
        - Heuristic: when ``bottom ≈ 0`` and ``height`` is much larger than a
          tiny epsilon, prefer **absolute top** only if ``height`` is also
          comparable to the X span (order-of-magnitude box). Otherwise treat
          as delta so unit tests / short boxes stay correct.
        - Default / safe: **delta** → ``y_max = bottom + height``.
        """
        left = float(metadata.get("left", 0.0))
        right = float(metadata.get("right", 0.0))
        bottom = float(metadata.get("bottom", 0.0))
        height_raw = float(metadata.get("height", metadata.get("top", 0.0)))

        if right - left < self._COLINEAR_TOL:
            right = left + 1.0

        x_span = max(right - left, self._COLINEAR_TOL)
        # Absolute top: bottom near 0, height_raw looks like a top coordinate
        # of similar magnitude to x_span (full experimental domain).
        use_absolute = (
            height_raw > bottom
            and abs(bottom) <= self._COLINEAR_TOL * 10
            and height_raw >= x_span * 0.2
            and height_raw <= x_span * 5.0
        )
        if height_raw <= self._COLINEAR_TOL:
            y_max = bottom + 1.0
            mode = "delta-fallback"
        elif use_absolute:
            y_max = height_raw
            mode = "absolute-top"
        else:
            y_max = bottom + height_raw
            mode = "delta"

        if y_max - bottom < self._COLINEAR_TOL:
            y_max = bottom + 1.0
            mode = "delta-min"

        reg = Region(
            x_min=left,
            x_max=right,
            y_min=bottom,
            y_max=y_max,
            source="metadata",
        )
        log.debug(
            "detect_from_metadata mode=%s height_raw=%s -> X[%.1f,%.1f] Y[%.1f,%.1f]",
            mode,
            height_raw,
            reg.x_min,
            reg.x_max,
            reg.y_min,
            reg.y_max,
        )
        return reg

    # -----------------------------------------------------------------
    @staticmethod
    def _fallback_region(
        metadata: Dict[str, Any] | None,
        reason: str,
    ) -> Region:
        """Return a metadata‑derived region, or a unit square as last resort."""
        if metadata is not None:
            left = float(metadata.get("left", 0.0))
            right = float(metadata.get("right", 1.0))
            bottom = float(metadata.get("bottom", 0.0))
            height = float(metadata.get("height", metadata.get("top", 1.0)))
            return Region(
                x_min=left,
                x_max=right if right > left else left + 1.0,
                y_min=bottom,
                y_max=bottom + (height if height > 0 else 1.0),
                source=f"metadata-after-{reason}",
            )
        return Region(x_min=0.0, x_max=1.0, y_min=0.0, y_max=1.0, source=reason)
