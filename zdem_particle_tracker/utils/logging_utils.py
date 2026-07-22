"""Application logging — never write into experiment data directories."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path


_CONFIGURED = False


def log_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    d = base / "ZDEM_ParticleTracker" / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    global _CONFIGURED
    logger = logging.getLogger("zdem_particle_tracker")
    if _CONFIGURED:
        return logger
    logger.setLevel(level)
    logger.propagate = False
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh = logging.FileHandler(log_dir() / "app.log", encoding="utf-8")
    fh.setFormatter(fmt)
    fh.setLevel(level)
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    sh.setLevel(logging.WARNING)
    logger.addHandler(fh)
    logger.addHandler(sh)
    _CONFIGURED = True
    return logger


def install_excepthook(logger: logging.Logger | None = None) -> None:
    log = logger or setup_logging()

    def _hook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        log.exception("未捕获异常", exc_info=(exc_type, exc, tb))
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            app = QApplication.instance()
            if app is not None:
                QMessageBox.critical(
                    None,
                    "程序错误",
                    f"{exc_type.__name__}: {exc}\n\n详情已写入日志：\n{log_dir() / 'app.log'}",
                )
        except Exception:
            pass

    sys.excepthook = _hook
