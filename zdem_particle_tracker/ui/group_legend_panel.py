"""Group legend panel — manage particle group visibility and isolation."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class ColorSwatch(QLabel):
    """A small colored square representing a group color."""

    def __init__(self, color: QColor, size: int = 16, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, size, size, 3, 3)
        painter.end()
        self.setPixmap(pixmap)


class GroupItem(QWidget):
    """A single group entry in the legend with color swatch, name, count, and visibility checkbox."""

    def __init__(self, group_name: str, color: QColor, count: int = 0, visible: bool = True, parent=None):
        super().__init__(parent)
        self._group_name = group_name
        self._color = color
        self._count = count
        self._visible = visible
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        # Color swatch
        self._swatch = ColorSwatch(self._color, 14)
        layout.addWidget(self._swatch)

        # Visibility checkbox
        self._checkbox = QCheckBox()
        self._checkbox.setChecked(self._visible)
        layout.addWidget(self._checkbox)

        # Group name
        self._name_label = QLabel(self._group_name)
        self._name_label.setStyleSheet("color: #1d1d1f; font-size: 12px; font-weight: 500;")
        self._name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self._name_label, stretch=1)

        # Particle count
        self._count_label = QLabel(str(self._count))
        self._count_label.setStyleSheet("color: #86868b; font-size: 11px;")
        self._count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self._count_label)

    @property
    def group_name(self) -> str:
        return self._group_name

    @property
    def is_visible(self) -> bool:
        return self._checkbox.isChecked()

    def set_visible(self, visible: bool):
        self._checkbox.setChecked(visible)

    def set_count(self, count: int):
        self._count = count
        self._count_label.setText(str(count))

    def set_color(self, color: QColor):
        self._color = color
        size = self._swatch.width() or 14
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, size, size, 3, 3)
        painter.end()
        self._swatch.setPixmap(pixmap)


class GroupLegendPanel(QWidget):
    """Left-side panel showing particle groups with color legend and visibility control.

    Signals:
        visibility_changed(group_name, visible): emitted when a group's visibility toggles
        isolate_group(group_name): emitted on double-click to isolate a group
        show_all_groups(): emitted when "Show All" is clicked
        show_selected_group(): emitted when "Show Selected Group" is clicked
        color_changed(group_name, QColor): user picked a new color (right-click / 改色)
    """

    visibility_changed = Signal(str, bool)
    isolate_group = Signal(str)
    show_all_groups = Signal()
    show_selected_group = Signal()
    color_changed = Signal(str, QColor)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._group_items = {}  # group_name -> GroupItem
        self._setup_ui()

    def _setup_ui(self):
        self.setMinimumWidth(180)
        self.setMaximumWidth(300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Title
        title = QLabel("图例")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #1d1d1f; padding-bottom: 4px;")
        layout.addWidget(title)

        hint = QLabel("双击仅显示该组 · 右键改颜色")
        hint.setObjectName("secondary")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #86868b; font-size: 11px;")
        layout.addWidget(hint)

        # Group list container
        self._group_container = QVBoxLayout()
        self._group_container.setSpacing(2)
        layout.addLayout(self._group_container)

        layout.addStretch()

        # Buttons
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(4)

        self._show_all_btn = QPushButton("显示全部")
        self._show_all_btn.setObjectName("secondary")
        self._show_all_btn.clicked.connect(self.show_all_groups.emit)
        btn_layout.addWidget(self._show_all_btn)

        self._show_selected_btn = QPushButton("显示所选组")
        self._show_selected_btn.setObjectName("secondary")
        self._show_selected_btn.clicked.connect(self.show_selected_group.emit)
        btn_layout.addWidget(self._show_selected_btn)

        layout.addLayout(btn_layout)

    def _on_checkbox_toggled(self, group_name: str, checked: bool):
        self.visibility_changed.emit(group_name, checked)

    def _on_item_double_clicked(self, group_name: str):
        self.isolate_group.emit(group_name)

    def _on_item_context_menu(self, group_name: str, pos):
        item = self._group_items.get(group_name)
        if item is None:
            return
        menu = QMenu(self)
        act_color = menu.addAction("修改颜色…")
        act_iso = menu.addAction("仅显示此组")
        chosen = menu.exec(item.mapToGlobal(pos))
        if chosen is act_color:
            cur = item._color if hasattr(item, "_color") else QColor(128, 128, 128)
            c = QColorDialog.getColor(cur, self, f"Group 颜色 — {group_name}")
            if c.isValid():
                item.set_color(c)
                self.color_changed.emit(group_name, c)
        elif chosen is act_iso:
            self.isolate_group.emit(group_name)

    # --- Public API ---

    def add_group(self, group_name: str, color: QColor, count: int = 0, visible: bool = True):
        """Add or update a group in the legend."""
        item = GroupItem(group_name, color, count, visible)

        # Connect signals
        item._checkbox.toggled.connect(
            lambda checked, g=group_name: self._on_checkbox_toggled(g, checked)
        )
        item.mouseDoubleClickEvent = lambda event, g=group_name: self._on_item_double_clicked(g)
        item.setContextMenuPolicy(Qt.CustomContextMenu)
        item.customContextMenuRequested.connect(
            lambda pos, g=group_name: self._on_item_context_menu(g, pos)
        )

        self._group_items[group_name] = item
        self._group_container.addWidget(item)

    def set_group_color(self, group_name: str, color: QColor):
        item = self._group_items.get(group_name)
        if item is not None:
            item.set_color(color)

    def remove_group(self, group_name: str):
        """Remove a group from the legend."""
        item = self._group_items.pop(group_name, None)
        if item is not None:
            self._group_container.removeWidget(item)
            item.deleteLater()

    def clear(self):
        """Remove all groups."""
        for name in list(self._group_items.keys()):
            self.remove_group(name)

    def set_group_visible(self, group_name: str, visible: bool):
        """Set visibility of a group."""
        item = self._group_items.get(group_name)
        if item is not None:
            item.set_visible(visible)

    def set_group_count(self, group_name: str, count: int):
        """Update particle count for a group."""
        item = self._group_items.get(group_name)
        if item is not None:
            item.set_count(count)

    def get_visible_groups(self) -> list:
        """Return list of group names that are currently visible."""
        return [name for name, item in self._group_items.items() if item.is_visible]

    def get_all_groups(self) -> list:
        """Return list of all group names."""
        return list(self._group_items.keys())

    def get_group_item(self, group_name: str):
        """Get the GroupItem widget for a group."""
        return self._group_items.get(group_name)
