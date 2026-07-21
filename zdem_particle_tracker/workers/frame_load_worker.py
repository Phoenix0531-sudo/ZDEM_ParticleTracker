"""Worker thread for loading a single ZDEM DAT frame."""

from PySide6.QtCore import QThread, Signal

from ..parsers.dat_parser import ParseMode, parse_dat_file


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
        try:
            frame_data = parse_dat_file(self._file_path, mode=self._mode)
            if frame_data is None:
                self.error.emit(self._request_id, f"解析失败: {self._file_path}")
                return
            self.finished.emit(self._request_id, frame_data)
        except Exception as e:
            self.error.emit(self._request_id, str(e))
