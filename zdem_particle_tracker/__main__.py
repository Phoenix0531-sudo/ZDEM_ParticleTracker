"""Entry point for ZDEM Particle Tracker."""
import sys, os
os.environ.setdefault('QT_AUTO_SCREEN_SCALE_FACTOR', '1')
from PySide6.QtWidgets import QApplication, QStyleFactory
from PySide6.QtCore import QTimer
from .config import APP_STYLESHEET, DEFAULT_DIR
from .widgets.main_viewer import MainViewer

def main():
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create('Fusion'))
    app.setStyleSheet(APP_STYLESHEET)
    win = MainViewer()
    win.setWindowTitle('ZDEM 颗粒轨迹追踪器')
    if os.path.exists(DEFAULT_DIR):
        from .parsers.dat_parser import find_dat_files
        files = find_dat_files(DEFAULT_DIR)
        if files:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: win.load_directory(DEFAULT_DIR))
    win.show()
    return app.exec()

if __name__ == '__main__':
    sys.exit(main())
