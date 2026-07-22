"""Application logging — never write into experiment data directories.

Logs go to:
  %LOCALAPPDATA%/ZDEM_ParticleTracker/logs/app.log   (rotating)
  stderr WARNING+ by default

Environment:
  ZDEM_LOG_LEVEL=DEBUG|INFO|WARNING|ERROR
  ZDEM_LOG_CONSOLE=1  — also mirror INFO to stderr
"""
from __future__ import annotations

import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False
_ROOT_NAME = "zdem_particle_tracker"


def log_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    d = base / "ZDEM_ParticleTracker" / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _level_from_env(default: int = logging.INFO) -> int:
    raw = (os.environ.get("ZDEM_LOG_LEVEL") or "").strip().upper()
    if not raw:
        return default
    return getattr(logging, raw, default)


def get_logger(name: str | None = None) -> logging.Logger:
    """Child logger under zdem_particle_tracker.*"""
    if name is None or name == _ROOT_NAME:
        return logging.getLogger(_ROOT_NAME)
    if name.startswith(_ROOT_NAME + "."):
        return logging.getLogger(name)
    return logging.getLogger(f"{_ROOT_NAME}.{name}")


def setup_logging(level: int | None = None) -> logging.Logger:
    """Idempotent setup: rotating file + stderr WARNING (or INFO if ZDEM_LOG_CONSOLE=1)."""
    global _CONFIGURED
    logger = logging.getLogger(_ROOT_NAME)
    lvl = level if level is not None else _level_from_env(logging.INFO)
    if _CONFIGURED:
        logger.setLevel(lvl)
        return logger

    logger.setLevel(lvl)
    logger.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    log_path = log_dir() / "app.log"
    fh = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    fh.setLevel(logging.DEBUG)  # file always keeps detail; logger filters
    logger.addHandler(fh)

    console_lvl = logging.INFO if os.environ.get("ZDEM_LOG_CONSOLE", "").strip() in (
        "1",
        "true",
        "yes",
    ) else logging.WARNING
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    sh.setLevel(console_lvl)
    logger.addHandler(sh)

    _CONFIGURED = True
    logger.info("日志初始化 level=%s file=%s", logging.getLevelName(lvl), log_path)
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
            log.debug("无法弹出错误对话框", exc_info=True)

    sys.excepthook = _hook

    # Qt thread exceptions (PySide6 / Qt 5.15+)
    try:
        from PySide6.QtCore import qInstallMessageHandler, QtMsgType

        def _qt_msg(mode, context, message):
            # Map Qt message types to logging levels
            text = str(message)
            if mode == QtMsgType.QtFatalMsg:
                log.error("QtFatal: %s", text)
            elif mode == QtMsgType.QtCriticalMsg:
                log.error("QtCritical: %s", text)
            elif mode == QtMsgType.QtWarningMsg:
                log.warning("QtWarning: %s", text)
            else:
                log.debug("Qt: %s", text)

        qInstallMessageHandler(_qt_msg)
        log.debug("已安装 Qt 消息处理器")
    except Exception:
        log.debug("Qt 消息处理器不可用", exc_info=True)

    # QThread.uncaught exceptions via threading.excepthook (3.8+)
    try:
        import threading

        def _thread_hook(args):
            if args.exc_type is SystemExit:
                return
            log.error(
                "线程未捕获异常 thread=%s",
                getattr(args.thread, "name", "?"),
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )

        threading.excepthook = _thread_hook  # type: ignore[attr-defined]
    except Exception:
        pass


def log_exception(log: logging.Logger, msg: str, exc: BaseException | None = None) -> None:
    if exc is not None:
        log.error("%s: %s", msg, exc, exc_info=exc)
    else:
        log.exception(msg)


def format_tb(exc: BaseException) -> str:
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
