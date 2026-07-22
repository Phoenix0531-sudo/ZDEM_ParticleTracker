"""UI panels used by the active MainViewer."""

from .about_dialog import APP_VERSION, show_about_dialog
from .group_legend_panel import GroupLegendPanel

__all__ = [
    "GroupLegendPanel",
    "show_about_dialog",
    "APP_VERSION",
]
