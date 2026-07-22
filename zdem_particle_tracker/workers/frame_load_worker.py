"""Worker thread for loading a single ZDEM DAT frame."""
from __future__ import annotations

import time

from PySide6.QtCore import QThread, Signal

from ..parsers.dat_parser import ParseMode, parse_dat_file
from ..utils.logging_utils import get_logger

log = get_logger("workers.frame_load")


class FrameLoadWorker(QThread):
    """Load one ZDEM DAT file in a background thread.

    Emits:
        finished: (request_id, ParticleData)
        error: (request_id, error message string)
    """

    finished = Signal(int, object)
    error = Signal(int, str)

    def __init__(
        self,
        file_path: str,
        request_id: int = 0,
        mode: ParseMode = ParseMode.FULL_PARTICLE_PROPERTIES,
        parent=None,
    ):
        super().__init__(parent)
        self._file_path = file_path
        self._request_id = int(request_id)
        self._mode = mode

    def run(self):
        t0 = time.perf_counter()
        log.debug(
            "FrameLoadWorker start req=%s mode=%s path=%s",
            self._request_id,
            getattr(self._mode, "name", self._mode),
            self._file_path,
        )
        try:
            frame_data = parse_dat_file(self._file_path, mode=self._mode)
            if frame_data is None:
                msg = f"解析失败: {self._file_path}"
                log.error("FrameLoadWorker %s", msg)
                self.error.emit(self._request_id, msg)
                return
            n = int(getattr(frame_data, "count", 0) or 0)
            log.info(
                "FrameLoadWorker ok req=%s balls=%s step=%s t=%.3fs path=%s",
                self._request_id,
                n,
                getattr(frame_data, "current_step", None),
                time.perf_counter() - t0,
                self._file_path,
            )
            self.finished.emit(self._request_id, frame_data)
        except Exception as e:
            log.exception(
                "FrameLoadWorker fail req=%s path=%s", self._request_id, self._file_path
            )
            self.error.emit(self._request_id, str(e))
