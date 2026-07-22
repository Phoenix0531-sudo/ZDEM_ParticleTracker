"""Application entry point."""
from __future__ import annotations

import sys
import time

from PySide6.QtWidgets import QApplication, QStyleFactory

from .config import APP_STYLESHEET
from .utils.logging_utils import get_logger, install_excepthook, setup_logging
from .widgets.main_viewer import MainViewer


def main(argv: list[str] | None = None) -> int:
    """Create and run the ZDEM Particle Tracker application."""
    argv = argv or sys.argv
    log = setup_logging()
    install_excepthook(log)
    log.info("========== ZDEM Particle Tracker 启动 ==========")
    log.info("Python %s", sys.version.replace("\n", " "))
    log.info("argv=%s", argv)
    t0 = time.perf_counter()

    app = QApplication(argv)
    app.setApplicationName("ZDEM Particle Tracker")
    app.setOrganizationName("ECUT")
    style = QStyleFactory.create("Fusion")
    if style is not None:
        app.setStyle(style)
    app.setStyleSheet(APP_STYLESHEET)
    log.info("QApplication platform=%s style=%s", app.platformName(), app.style().objectName() if app.style() else None)

    try:
        win = MainViewer()
        win.show()
        log.info("主窗口已显示 (%.2fs)", time.perf_counter() - t0)
    except Exception:
        log.exception("主窗口创建失败")
        raise

    code = app.exec()
    log.info("退出 code=%s 总运行=%.1fs", code, time.perf_counter() - t0)
    return int(code)


if __name__ == "__main__":
    sys.exit(main())
