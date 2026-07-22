"""Application entry point."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QStyleFactory

from .config import APP_STYLESHEET
from .utils.logging_utils import install_excepthook, setup_logging
from .widgets.main_viewer import MainViewer


def main(argv: list[str] | None = None) -> int:
    """Create and run the ZDEM Particle Tracker application."""
    argv = argv or sys.argv
    log = setup_logging()
    install_excepthook(log)
    log.info("ZDEM Particle Tracker 启动")

    app = QApplication(argv)
    app.setApplicationName("ZDEM Particle Tracker")
    app.setOrganizationName("ECUT")
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setStyleSheet(APP_STYLESHEET)

    win = MainViewer()
    win.show()
    code = app.exec()
    log.info("退出 code=%s", code)
    return code


if __name__ == "__main__":
    sys.exit(main())
