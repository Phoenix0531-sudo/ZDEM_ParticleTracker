"""Application entry point."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QStyleFactory

from .config import APP_STYLESHEET
from .widgets.main_viewer import MainViewer


def main(argv: list[str] | None = None) -> int:
    """Create and run the ZDEM Particle Tracker application."""
    argv = argv or sys.argv
    app = QApplication(argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    qss = APP_STYLESHEET
    app.setStyleSheet(qss)

    win = MainViewer()
    win.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
