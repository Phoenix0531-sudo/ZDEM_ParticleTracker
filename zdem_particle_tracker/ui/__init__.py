"""UI panels used by the active MainViewer."""

from .about_dialog import APP_VERSION, show_about_dialog
from .group_legend_panel import GroupLegendPanel
from .side_panels import build_left_panel, build_playback_bar, build_right_panel

__all__ = [
    "GroupLegendPanel",
    "show_about_dialog",
    "APP_VERSION",
    "build_left_panel",
    "build_playback_bar",
    "build_right_panel",
]
