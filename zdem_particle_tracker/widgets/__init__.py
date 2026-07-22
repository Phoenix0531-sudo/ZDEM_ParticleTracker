# Lazy-heavy GUI imports stay out of package import so pure helpers/tests can load
# without PySide6/pyqtgraph. Import MainViewer from widgets.main_viewer directly.

from .selection_logic import (
    filter_trajectory_path_xy,
    id_allowed_at_session_start,
    pick_particle_id,
    play_parse_mode_name,
)

def __getattr__(name: str):
    if name == "MainViewer":
        from .main_viewer import MainViewer

        return MainViewer
    raise AttributeError(name)
