"""Application configuration and styling."""

import json
import os
from pathlib import Path

APP_STYLESHEET = """
/* === Global === */
* {
    font-family: -apple-system, 'San Francisco', 'Helvetica Neue', sans-serif;
    font-size: 13px;
    color: #1d1d1f;
}
QWidget {
    background-color: #f5f5f7;
    border-radius: 6px;
}

/* === Cards / GroupBox === */
QGroupBox, QFrame#card {
    background-color: #ffffff;
    border: 1px solid #d2d2d7;
    border-radius: 6px;
    padding: 16px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 8px;
    color: #1d1d1f;
    font-weight: 600;
}

/* === Buttons === */
QPushButton {
    background-color: #0071e3;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    font-size: 13px;
    font-weight: 500;
    min-height: 20px;
}
QPushButton:hover {
    background-color: #0077ed;
}
QPushButton:pressed {
    background-color: #006edb;
}
QPushButton:disabled {
    background-color: #c7c7cc;
    color: #8e8e93;
}
QPushButton#danger {
    background-color: #ff3b30;
}
QPushButton#danger:hover {
    background-color: #ff453a;
}
QPushButton#danger:pressed {
    background-color: #d70015;
}
QPushButton#secondary {
    background-color: #e8e8ed;
    color: #1d1d1f;
}
QPushButton#secondary:hover {
    background-color: #dcdce0;
}
QPushButton#secondary:pressed {
    background-color: #c7c7cc;
}

/* === Labels === */
QLabel {
    color: #1d1d1f;
    background: transparent;
    border: none;
}
QLabel#secondary {
    color: #86868b;
    font-size: 12px;
}

/* === Line Edit / SpinBox / ComboBox === */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #ffffff;
    border: 1px solid #d2d2d7;
    border-radius: 6px;
    padding: 6px 10px;
    color: #1d1d1f;
    selection-background-color: #0071e3;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #0071e3;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox::down-arrow {
    image: none;
    width: 0;
}

/* === CheckBox / RadioButton === */
QCheckBox, QRadioButton {
    spacing: 8px;
    color: #1d1d1f;
    background: transparent;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #c7c7cc;
    background: #ffffff;
}
QCheckBox::indicator:checked {
    background-color: #0071e3;
    border-color: #0071e3;
}

/* === Slider === */
QSlider::groove:horizontal {
    height: 4px;
    background: #d2d2d7;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #ffffff;
    border: 1px solid #c7c7cc;
    width: 18px;
    height: 18px;
    margin: -7px 0;
    border-radius: 9px;
}
QSlider::handle:horizontal:hover {
    background: #f5f5f7;
    border-color: #0071e3;
}
QSlider::sub-page:horizontal {
    background: #0071e3;
    border-radius: 2px;
}

/* === ScrollBar === */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #c7c7cc;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #a8a8ad;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #c7c7cc;
    border-radius: 4px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background: #a8a8ad;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* === Table === */
QTableWidget, QTableView {
    background-color: #ffffff;
    border: 1px solid #d2d2d7;
    border-radius: 6px;
    gridline-color: #e8e8ed;
    selection-background-color: #e8f0fe;
    selection-color: #1d1d1f;
}
QHeaderView::section {
    background-color: #f5f5f7;
    color: #86868b;
    border: none;
    border-bottom: 1px solid #d2d2d7;
    padding: 6px 10px;
    font-weight: 600;
    font-size: 12px;
}

/* === Tree === */
QTreeWidget, QTreeView {
    background-color: #ffffff;
    border: 1px solid #d2d2d7;
    border-radius: 6px;
    show-decoration-selected: 1;
}
QTreeWidget::item, QTreeView::item {
    padding: 4px 6px;
}
QTreeWidget::item:selected, QTreeView::item:selected {
    background-color: #e8f0fe;
    color: #1d1d1f;
}

/* === Tab === */
QTabWidget::pane {
    border: 1px solid #d2d2d7;
    border-radius: 6px;
    background: #ffffff;
}
QTabBar::tab {
    background: #e8e8ed;
    color: #86868b;
    border: none;
    padding: 8px 20px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}
QTabBar::tab:selected {
    background: #ffffff;
    color: #1d1d1f;
    font-weight: 600;
}
QTabBar::tab:hover:!selected {
    background: #dcdce0;
    color: #1d1d1f;
}

/* === Splitter === */
QSplitter::handle {
    background: #d2d2d7;
    width: 1px;
    height: 1px;
}

/* === Progress Bar === */
QProgressBar {
    background: #e8e8ed;
    border: none;
    border-radius: 4px;
    height: 6px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background: #0071e3;
    border-radius: 4px;
}

/* === Tooltip === */
QToolTip {
    background: #1d1d1f;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}

/* === StatusBar === */
QStatusBar {
    background: #f5f5f7;
    border-top: 1px solid #d2d2d7;
    color: #1d1d1f;
}
QStatusBar QLabel {
    color: #86868b;
    font-size: 12px;
}

/* === Empty-state secondary labels === */
QLabel#secondary {
    color: #86868b;
    font-size: 12px;
}

/* === Dialog === */
QDialog {
    background: #f5f5f7;
}
QTextBrowser {
    background: #ffffff;
    border: 1px solid #d2d2d7;
    border-radius: 6px;
    padding: 8px;
}

/* === Menu === */
QMenuBar {
    background: transparent;
    border-bottom: 1px solid #d2d2d7;
}
QMenuBar::item:selected {
    background: #e8e8ed;
    border-radius: 4px;
}
QMenu {
    background: #ffffff;
    border: 1px solid #d2d2d7;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
}
QMenu::item:selected {
    background: #e8f0fe;
    color: #0071e3;
}

"""


class AppConfig:
    """Application configuration manager.

    Persists user preferences as JSON in the user config directory.
    """

    DEFAULT_CONFIG = {
        "window_geometry": None,
        "window_state": None,
        "recent_files": [],
        "last_opened_dir": None,
        "theme": "light",
        "frame_step": 1,
        "auto_advance": False,
        "tracking_enabled": True,
        "min_particle_radius": 0.5,
        "max_particle_displacement": 50.0,
        "color_scheme": "group",
        "show_walls": True,
        "show_labels": False,
        "render_quality": "high",
    }

    def __init__(self, config_dir: str | None = None):
        if config_dir is None:
            config_dir = str(Path.home() / ".zdem_particle_tracker")
        self._config_dir = Path(config_dir)
        self._config_file = self._config_dir / "config.json"
        self._data: dict = {}
        self.load()

    @property
    def config_dir(self) -> str:
        return str(self._config_dir)

    @property
    def config_file(self) -> str:
        return str(self._config_file)

    def load(self) -> None:
        """Load configuration from disk, falling back to defaults."""
        self._data = dict(self.DEFAULT_CONFIG)
        if self._config_file.exists():
            try:
                with open(self._config_file, "r") as f:
                    saved = json.load(f)
                self._data.update(saved)
            except (json.JSONDecodeError, OSError):
                pass

    def save(self) -> None:
        """Save configuration to disk."""
        self._config_dir.mkdir(parents=True, exist_ok=True)
        with open(self._config_file, "w") as f:
            json.dump(self._data, f, indent=2)

    def get(self, key: str, default=None):
        """Get a config value by key."""
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        """Set a config value and persist to disk."""
        self._data[key] = value
        self.save()

    def update(self, mapping: dict) -> None:
        """Update multiple config values and persist."""
        self._data.update(mapping)
        self.save()

    def reset(self) -> None:
        """Reset configuration to defaults."""
        self._data = dict(self.DEFAULT_CONFIG)
        self.save()

    def to_dict(self) -> dict:
        """Return a copy of all configuration data."""
        return dict(self._data)

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        """Create an AppConfig from a dictionary (does not persist)."""
        cfg = cls.__new__(cls)
        cfg._config_dir = Path.home() / ".zdem_particle_tracker"
        cfg._config_file = cfg._config_dir / "config.json"
        cfg._data = dict(cls.DEFAULT_CONFIG)
        cfg._data.update(data)
        return cfg


DEFAULT_DIR = r"D:\2_Temp\StructLab\Projects\25_造山带尺度盐构造\物理实验复刻\2\data"
