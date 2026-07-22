# Lazy-heavy GUI imports stay out of package import so pure helpers/tests can load
# without PySide6/pyqtgraph. Import MainViewer from widgets.main_viewer directly.

from .selection_logic import (
    filter_trajectory_path_xy,
    id_allowed_at_session_start,
    pick_particle_id,
    play_parse_mode_name,
)
from .viewer_logic import (
    color_mode_from_radio,
    parse_permanent_id_text,
    series_from_trajectory,
    validate_region_bounds,
)

__all__ = [
    "filter_trajectory_path_xy",
    "id_allowed_at_session_start",
    "pick_particle_id",
    "play_parse_mode_name",
    "color_mode_from_radio",
    "parse_permanent_id_text",
    "series_from_trajectory",
    "validate_region_bounds",
    "MainViewer",
]


def __getattr__(name: str):
    if name == "MainViewer":
        from .main_viewer import MainViewer

        return MainViewer
    raise AttributeError(name)
