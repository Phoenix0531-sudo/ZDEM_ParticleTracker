"""Main viewer — VisPy particles, trajectory, matplotlib series, Chinese UI."""
from __future__ import annotations

import os
from collections import Counter

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QComboBox,
    QGroupBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QFileDialog,
    QSlider,
    QCheckBox,
    QRadioButton,
    QButtonGroup,
    QMessageBox,
    QDoubleSpinBox,
    QFormLayout,
    QProgressBar,
    QTextEdit,
    QDialog,
    QDialogButtonBox,
    QScrollArea,
)

from scipy.spatial import cKDTree

from ..config import DEFAULT_DIR
from ..parsers.dat_parser import ParseMode, find_dat_files, parse_dat_file
from ..services.trajectory_service import TrajectoryService, FileInfo
from ..services.region_detector import RegionDetector
from ..services.quality_report import check_file_list, check_frame
from ..services.project_config import (
    ProjectConfig,
    load_project_config,
    save_project_config,
)
from ..utils.color_mapping import ColorMapping, color_numbers_to_rgba, group_to_color
from ..utils.frame_cache import LRUCache
from ..workers.frame_load_worker import FrameLoadWorker
from ..ui.group_legend_panel import GroupLegendPanel

# VisPy GPU renderer (auto-detect — may fail in headless mode)
HAVE_VISPY = False
try:
    from ..rendering.vispy_renderer import VisPyRenderer

    HAVE_VISPY = True
except Exception:
    pass


class MainViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ZDEM Particle Tracker")
        self.resize(1400, 900)
        self._frame_files: list[tuple[int, str]] = []
        self._current_idx = 0
        self._current_data = None
        self._selected_id = None
        self._trajectory = None
        self._kdtree = None
        self._traj_path_item = None
        self._selection_items = []
        self._frame_cache: LRUCache = LRUCache(5)
        self._load_req_id = 0
        self._load_worker: FrameLoadWorker | None = None
        self._slider_debounce = QTimer(self)
        self._slider_debounce.setSingleShot(True)
        self._slider_debounce.setInterval(80)
        self._slider_debounce.timeout.connect(self._apply_slider_frame)
        self._pending_slider_idx = 0
        self._hidden_groups: set[str] = set()
        self._color_map = ColorMapping()
        self._region_initialized = False
        self._experiment_region = None  # (xmin, xmax, ymin, ymax, source)
        self._region_detector = RegionDetector()
        self._region_user_locked = False
        self._traj_service = TrajectoryService()
        self._current_worker = None
        self._last_quality_lines: list[str] = []
        self._project_path: str | None = None
        self._prefetch_worker: FrameLoadWorker | None = None
        self._play_buttons: list[QPushButton] = []

        self._setup_ui()
        self._setup_menu()
        self._play_timer = QTimer()
        self._play_timer.timeout.connect(self._on_play_tick)
        self._set_controls_enabled(False)

    # ── UI ──────────────────────────────────────────────────────────
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        ml = QHBoxLayout(central)
        ml.setContentsMargins(0, 0, 0, 0)
        sp = QSplitter(Qt.Horizontal)
        ml.addWidget(sp)

        # Left
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(8, 8, 8, 8)
        ll.setSpacing(8)

        self._wall_cb = QCheckBox("显示墙体")
        self._wall_cb.setChecked(True)
        self._wall_cb.toggled.connect(self._render)
        ll.addWidget(self._wall_cb)

        dv = QHBoxLayout()
        self._rb_group = QButtonGroup(self)
        self._rb_real = QRadioButton("真实比例")
        self._rb_real.setChecked(True)
        self._rb_enh = QRadioButton("增强可见性")
        self._rb_group.addButton(self._rb_real)
        self._rb_group.addButton(self._rb_enh)
        self._rb_enh.toggled.connect(lambda: self._render())
        self._rb_real.toggled.connect(lambda: self._render())
        dv.addWidget(self._rb_real)
        dv.addWidget(self._rb_enh)
        ll.addLayout(dv)

        ll.addWidget(QLabel("实验目录:"))
        self._dir_input = QLineEdit(DEFAULT_DIR)
        self._dir_input.setReadOnly(True)
        ll.addWidget(self._dir_input)
        btn_row = QHBoxLayout()
        btn = QPushButton("浏览")
        btn.clicked.connect(self._browse)
        btn_row.addWidget(btn)
        scan_btn = QPushButton("扫描")
        scan_btn.clicked.connect(self._scan_dir)
        btn_row.addWidget(scan_btn)
        ll.addLayout(btn_row)
        self._file_info = QLabel("")
        ll.addWidget(self._file_info)

        # Group legend
        self._legend = GroupLegendPanel()
        self._legend.visibility_changed.connect(self._on_group_visibility)
        self._legend.isolate_group.connect(self._on_isolate_group)
        self._legend.show_all_groups.connect(self._on_show_all_groups)
        self._legend.show_selected_group.connect(self._on_show_selected_group)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._legend)
        scroll.setMinimumHeight(120)
        scroll.setMaximumHeight(220)
        ll.addWidget(scroll)

        # Region
        gb_reg = QGroupBox("实验区域")
        fl = QFormLayout(gb_reg)
        fl.setContentsMargins(8, 12, 8, 8)
        fl.setSpacing(6)
        self._sp_xmin = QDoubleSpinBox()
        self._sp_xmax = QDoubleSpinBox()
        self._sp_ymin = QDoubleSpinBox()
        self._sp_ymax = QDoubleSpinBox()
        for spb in (self._sp_xmin, self._sp_xmax, self._sp_ymin, self._sp_ymax):
            spb.setDecimals(1)
            spb.setRange(-1e9, 1e9)
            spb.setSingleStep(100.0)
            spb.setKeyboardTracking(False)
        fl.addRow("X 最小 (Xmin)", self._sp_xmin)
        fl.addRow("X 最大 (Xmax)", self._sp_xmax)
        fl.addRow("Y 最小 (Ymin)", self._sp_ymin)
        fl.addRow("Y 最大 (Ymax)", self._sp_ymax)
        self._lbl_region_src = QLabel("来源：—")
        self._lbl_region_src.setStyleSheet("color:#666;font-size:11px")
        fl.addRow(self._lbl_region_src)
        reg_btns = QHBoxLayout()
        btn_apply = QPushButton("应用区域")
        btn_apply.clicked.connect(self._apply_user_region)
        btn_redetect = QPushButton("重新检测")
        btn_redetect.setObjectName("secondary")
        btn_redetect.clicked.connect(self._redetect_region)
        reg_btns.addWidget(btn_apply)
        reg_btns.addWidget(btn_redetect)
        fl.addRow(reg_btns)
        ll.addWidget(gb_reg)

        btn2 = QPushButton("适配区域")
        btn2.clicked.connect(self._fit_region)
        ll.addWidget(btn2)
        btn3 = QPushButton("适配颗粒")
        btn3.clicked.connect(self._fit_particles)
        ll.addWidget(btn3)
        btn_q = QPushButton("数据质量报告")
        btn_q.setObjectName("secondary")
        btn_q.clicked.connect(self._show_quality_report)
        ll.addWidget(btn_q)
        ll.addStretch()
        left.setMinimumWidth(240)
        left.setMaximumWidth(320)
        sp.addWidget(left)

        # Center
        center = QWidget()
        cl = QVBoxLayout(center)
        cl.setContentsMargins(4, 4, 4, 4)
        self._tabs = QTabWidget()
        if HAVE_VISPY:
            self._plot = VisPyRenderer()
            self._scatter = None
            self._plot.clicked.connect(self._on_vispy_click)
        else:
            self._plot = pg.PlotWidget()
            self._plot.setBackground("#ffffff")
            vb = self._plot.getViewBox()
            vb.setAspectLocked(True)
            vb.invertY(False)
            vb.setMouseMode(pg.ViewBox.PanMode)
            self._plot.scene().sigMouseClicked.connect(self._on_click)
            self._scatter = pg.ScatterPlotItem(pxMode=False, symbol="o")
            self._plot.addItem(self._scatter)
        self._tabs.addTab(self._plot, "颗粒视图")

        from .series_plot import make_series_tabs

        self._series = make_series_tabs()
        self._plot_dx = self._series["dx"]
        self._plot_dy = self._series["dy"]
        self._plot_dt = self._series["dt"]
        self._plot_pl = self._series["pl"]
        self._plot_v = self._series["v"]
        self._plot_vx = self._series["vx"]
        self._plot_vy = self._series["vy"]
        self._tabs.addTab(self._plot_dx, "X 位移")
        self._tabs.addTab(self._plot_dy, "Y 位移")
        self._tabs.addTab(self._plot_dt, "总位移")
        self._tabs.addTab(self._plot_pl, "路径长度")
        self._tabs.addTab(self._plot_v, "速度")
        self._tabs.addTab(self._plot_vx, "Vx")
        self._tabs.addTab(self._plot_vy, "Vy")

        self._tbl = QTableWidget()
        self._tbl.setAlternatingRowColors(False)
        self._tbl.horizontalHeader().setStretchLastSection(True)
        self._tabs.addTab(self._tbl, "轨迹数据表")
        cl.addWidget(self._tabs)

        pb = QHBoxLayout()
        self._play_buttons = []
        for txt, slot, tip in [
            ("⏮", self._first, "第一帧"),
            ("◀", self._prev, "上一帧"),
            ("▶/⏸", self._play, "播放 / 暂停"),
            ("▶", self._next, "下一帧"),
            ("⏭", self._last, "最后一帧"),
        ]:
            b = QPushButton(txt)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            pb.addWidget(b)
            self._play_buttons.append(b)
        self._btn_play = self._play_buttons[2]
        self._slider = QSlider(Qt.Horizontal)
        self._slider.valueChanged.connect(self._on_slider_changed)
        pb.addWidget(self._slider)
        self._step_label = QLabel("0/0")
        pb.addWidget(self._step_label)
        pb.addWidget(QLabel("播放间隔(ms):"))
        self._spd = QComboBox()
        self._spd.addItems(["100", "200", "500", "1000"])
        self._spd.setCurrentIndex(1)
        self._spd.setToolTip("自动播放时每帧间隔")
        pb.addWidget(self._spd)
        cl.addLayout(pb)

        # Trajectory progress
        prog_row = QHBoxLayout()
        self._traj_progress = QProgressBar()
        self._traj_progress.setVisible(False)
        self._traj_progress.setRange(0, 100)
        self._btn_cancel_traj = QPushButton("取消追踪")
        self._btn_cancel_traj.setObjectName("danger")
        self._btn_cancel_traj.setVisible(False)
        self._btn_cancel_traj.clicked.connect(self._cancel_trajectory)
        prog_row.addWidget(self._traj_progress, 1)
        prog_row.addWidget(self._btn_cancel_traj)
        cl.addLayout(prog_row)

        sp.addWidget(center)
        sp.setStretchFactor(1, 1)

        # Right
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(8, 8, 8, 8)
        rl.setSpacing(8)
        gb1 = QGroupBox("颗粒追踪")
        g1l = QVBoxLayout(gb1)
        hl = QHBoxLayout()
        hl.addWidget(QLabel("永久 ID:"))
        self._id_input = QLineEdit()
        self._id_input.setPlaceholderText("输入永久颗粒 ID…")
        self._id_input.setToolTip("追踪唯一依据：永久 id，不是文件 index")
        self._id_input.returnPressed.connect(self._on_track)
        hl.addWidget(self._id_input)
        g1l.addLayout(hl)
        self._btn_track = QPushButton("追踪")
        self._btn_track.clicked.connect(self._on_track)
        g1l.addWidget(self._btn_track)
        row_sel = QHBoxLayout()
        self._btn_locate = QPushButton("定位")
        self._btn_locate.setObjectName("secondary")
        self._btn_locate.setToolTip("把视图中心移到当前选中颗粒")
        self._btn_locate.clicked.connect(self._locate_selected)
        self._btn_clear_sel = QPushButton("清除选择")
        self._btn_clear_sel.setObjectName("secondary")
        self._btn_clear_sel.clicked.connect(self._clear_selection)
        row_sel.addWidget(self._btn_locate)
        row_sel.addWidget(self._btn_clear_sel)
        g1l.addLayout(row_sel)
        self._btn_traj_path = QPushButton("显示路径")
        self._btn_traj_path.setCheckable(True)
        self._btn_traj_path.setToolTip("在颗粒视图中叠加已提取轨迹")
        self._btn_traj_path.toggled.connect(self._toggle_traj_path)
        g1l.addWidget(self._btn_traj_path)
        rl.addWidget(gb1)

        gb2 = QGroupBox("颗粒信息")
        self._info = QVBoxLayout(gb2)
        self._info.setSpacing(4)
        self._lbls = {}
        for k in ["ID:", "序号:", "Group:", "X:", "Y:", "半径:", "状态:"]:
            h = QHBoxLayout()
            h.addWidget(QLabel(k, styleSheet="color:#666;min-width:50px"))
            lbl = QLabel("—")
            h.addWidget(lbl)
            h.addStretch()
            self._info.addLayout(h)
            self._lbls[k] = lbl
        rl.addWidget(gb2)

        gb3 = QGroupBox("位移 / 速度")
        dl = QVBoxLayout(gb3)
        dl.setSpacing(4)
        self._dlbls = {}
        for k in ["ΔX:", "ΔY:", "总位移:", "路径长:", "Vx:", "Vy:", "|v|:", "Δstep:"]:
            h = QHBoxLayout()
            h.addWidget(QLabel(k, styleSheet="color:#666;min-width:50px"))
            lbl = QLabel("—")
            h.addWidget(lbl)
            h.addStretch()
            dl.addLayout(h)
            self._dlbls[k] = lbl
        rl.addWidget(gb3)
        rl.addStretch()
        right.setMinimumWidth(220)
        right.setMaximumWidth(320)
        sp.addWidget(right)
        sp.setSizes([280, 700, 250])

        self._sb = self.statusBar()
        self._sb_label = QLabel("就绪")
        self._sb.addPermanentWidget(self._sb_label)

    def _setup_menu(self):
        mb = self.menuBar()
        m_file = mb.addMenu("文件")
        act_open = QAction("打开实验目录…", self)
        act_open.triggered.connect(self._browse)
        m_file.addAction(act_open)
        act_save = QAction("保存项目配置…", self)
        act_save.triggered.connect(self._save_project)
        m_file.addAction(act_save)
        act_load = QAction("打开项目配置…", self)
        act_load.triggered.connect(self._open_project)
        m_file.addAction(act_load)
        m_file.addSeparator()
        act_quit = QAction("退出", self)
        act_quit.triggered.connect(self.close)
        m_file.addAction(act_quit)

        m_data = mb.addMenu("数据")
        act_q = QAction("数据质量报告", self)
        act_q.triggered.connect(self._show_quality_report)
        m_data.addAction(act_q)

    # ── File IO ─────────────────────────────────────────────────────
    def load_directory(self, path: str):
        # Stop any in-flight activity so directory switch stays predictable
        try:
            if self._play_timer.isActive():
                self._play_timer.stop()
            if hasattr(self, "_btn_play"):
                self._btn_play.setText("▶/⏸")
            self._traj_service.cancel()
        except Exception:
            pass
        self._traj_progress.setVisible(False)
        self._btn_cancel_traj.setVisible(False)

        files = find_dat_files(path)
        if not files:
            self._sb.showMessage(f"未找到 DAT 文件: {path}")
            self._sb_label.setText("无数据")
            self._set_controls_enabled(False)
            return
        self._frame_files = files
        self._frame_cache.clear()
        self._region_initialized = False
        self._selected_id = None
        self._experiment_region = None
        self._region_user_locked = False
        self._trajectory = None
        self._kdtree = None
        self._current_data = None
        self._current_idx = 0
        self._hidden_groups.clear()
        self._legend.clear()
        self._clear_traj_path()
        if hasattr(self, "_btn_traj_path"):
            self._btn_traj_path.blockSignals(True)
            self._btn_traj_path.setChecked(False)
            self._btn_traj_path.setText("显示路径")
            self._btn_traj_path.blockSignals(False)
        for k in self._lbls:
            self._lbls[k].setText("—")
        for k in self._dlbls:
            self._dlbls[k].setText("—")
        list_rep = check_file_list(files)
        self._last_quality_lines = list_rep.summary_lines()
        self._dir_input.setText(path)
        self._sb.showMessage(f"找到 {len(files)} 个 DAT 文件，正在读取起始帧…")
        self._sb_label.setText("扫描完成")
        self._file_info.setText(
            f"{len(files)} 文件 | 步 {files[0][0]} → {files[-1][0]}"
        )
        self._slider.blockSignals(True)
        self._slider.setRange(0, max(0, len(files) - 1))
        self._slider.setValue(0)
        self._slider.blockSignals(False)
        self._set_controls_enabled(True)
        self._load_frame(0, force=True)

    def _set_controls_enabled(self, enabled: bool):
        """Enable/disable playback & tracking controls based on experiment state."""
        for b in getattr(self, "_play_buttons", []) or []:
            b.setEnabled(enabled)
        if hasattr(self, "_slider"):
            self._slider.setEnabled(enabled)
        if hasattr(self, "_btn_track"):
            self._btn_track.setEnabled(enabled)
        if hasattr(self, "_id_input"):
            self._id_input.setEnabled(enabled)
        has_sel = enabled and self._selected_id is not None
        if hasattr(self, "_btn_locate"):
            self._btn_locate.setEnabled(has_sel)
        if hasattr(self, "_btn_clear_sel"):
            self._btn_clear_sel.setEnabled(has_sel)
        if hasattr(self, "_btn_traj_path"):
            self._btn_traj_path.setEnabled(enabled and self._trajectory is not None)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "选择实验目录")
        if d:
            self.load_directory(d)

    def _scan_dir(self):
        self.load_directory(self._dir_input.text())

    # ── Frame load (async + LRU + debounce + prefetch) ──────────────
    def _on_slider_changed(self, idx: int):
        self._pending_slider_idx = int(idx)
        self._slider_debounce.start()

    def _apply_slider_frame(self):
        self._load_frame(self._pending_slider_idx)

    def _load_frame(self, idx: int, force: bool = False):
        if not self._frame_files or idx < 0 or idx >= len(self._frame_files):
            return
        if not force and idx == self._current_idx and self._current_data is not None:
            return
        step, path = self._frame_files[idx]
        self._current_idx = idx
        self._step_label.setText(f"{idx + 1}/{len(self._frame_files)}")
        self._slider.blockSignals(True)
        self._slider.setValue(idx)
        self._slider.blockSignals(False)

        cached = self._frame_cache.get(path)
        if cached is not None:
            self._apply_frame_data(idx, cached)
            self._prefetch_neighbors(idx)
            return

        # Drop signal handlers of previous worker; request id filters stale results
        if self._load_worker is not None and self._load_worker.isRunning():
            try:
                self._load_worker.finished.disconnect()
                self._load_worker.error.disconnect()
            except Exception:
                pass

        self._load_req_id += 1
        req = self._load_req_id
        self._sb.showMessage(f"正在读取起始帧…" if idx == 0 else f"加载第 {idx + 1}/{len(self._frame_files)} 帧…")
        self._sb_label.setText("加载中…")
        worker = FrameLoadWorker(
            path, request_id=req, mode=ParseMode.FULL_PARTICLE_PROPERTIES
        )
        worker.finished.connect(self._on_frame_loaded)
        worker.error.connect(self._on_frame_error)
        self._load_worker = worker
        worker.start()

    def _prefetch_neighbors(self, idx: int):
        """Warm LRU with next frame while UI stays responsive."""
        nxt = idx + 1
        if nxt >= len(self._frame_files):
            return
        path = self._frame_files[nxt][1]
        if path in self._frame_cache:
            return
        if self._prefetch_worker is not None and self._prefetch_worker.isRunning():
            return
        # Use negative request ids so they never collide with UI loads
        self._load_req_id  # keep attribute warm
        req = -(nxt + 1)
        worker = FrameLoadWorker(
            path, request_id=req, mode=ParseMode.FULL_PARTICLE_PROPERTIES
        )
        worker.finished.connect(self._on_prefetch_loaded)
        worker.error.connect(lambda *_: None)
        self._prefetch_worker = worker
        worker.start()

    def _on_prefetch_loaded(self, request_id: int, data):
        # Prefetch only: put into cache, never change current view
        if not self._frame_files:
            return
        # request_id = -(idx+1)
        if request_id >= 0:
            return
        idx = -request_id - 1
        if 0 <= idx < len(self._frame_files):
            self._frame_cache.put(self._frame_files[idx][1], data)

    def _on_frame_loaded(self, request_id: int, data):
        if request_id != self._load_req_id:
            return  # stale
        idx = self._current_idx
        if not self._frame_files or idx >= len(self._frame_files):
            return
        path = self._frame_files[idx][1]
        self._frame_cache.put(path, data)
        self._apply_frame_data(idx, data)
        self._prefetch_neighbors(idx)

    def _on_frame_error(self, request_id: int, msg: str):
        if request_id != self._load_req_id:
            return
        self._sb.showMessage(f"加载失败: {msg}")
        self._sb_label.setText("错误")
        # stop autoplay on hard failure
        if self._play_timer.isActive():
            self._play_timer.stop()
            if hasattr(self, "_btn_play"):
                self._btn_play.setText("▶/⏸")

    def _apply_frame_data(self, idx: int, data):
        self._current_data = data
        step_name = self._frame_files[idx][0] if self._frame_files else 0
        self._file_info.setText(
            f"时间步 {data.current_step} | 颗粒 {data.count} | 文件步 {step_name}"
        )
        if self._experiment_region is None or not self._region_user_locked:
            self._detect_and_fill_region(data)
        self._build_kdtree()
        self._refresh_legend(data)
        self._render()
        wall_reg = None
        meta_reg = None
        if self._experiment_region:
            wall_reg = self._experiment_region[:4]
        meta_reg = (
            float(data.left),
            float(data.right),
            float(data.bottom),
            float(data.bottom + data.height)
            if data.height > data.bottom
            else float(data.height),
        )
        rep = check_frame(
            data,
            filename_step=self._frame_files[idx][0],
            wall_region=wall_reg if self._experiment_region and self._experiment_region[4] == "walls" else None,
            meta_region=meta_reg,
        )
        base = [ln for ln in self._last_quality_lines if ln.startswith("[信息]") or "文件" in ln]
        if not base:
            base = check_file_list(self._frame_files).summary_lines()
        self._last_quality_lines = base + rep.summary_lines()
        self._sb.showMessage(f"就绪 — 步 {data.current_step}, {data.count} 颗粒")
        self._sb_label.setText("就绪")
        if self._selected_id is not None:
            self._refresh_selected_info()
        self._set_controls_enabled(True)

    # ── Region ──────────────────────────────────────────────────────
    def _detect_and_fill_region(self, d, force=False):
        if d is None:
            return
        if self._region_user_locked and not force:
            return
        meta = {
            "left": float(d.left),
            "right": float(d.right),
            "bottom": float(d.bottom),
            "height": float(d.height),
        }
        walls = getattr(d, "wall_data", None)
        region = None
        if walls is not None and len(walls) > 0:
            region = self._region_detector.detect_from_walls(np.asarray(walls), meta)
        if region is None or str(region.source).startswith("metadata-after") or region.source == "walls-empty":
            region = self._region_detector.detect_from_metadata(meta)
        self._set_experiment_region(
            region.x_min,
            region.x_max,
            region.y_min,
            region.y_max,
            source=region.source,
            user_locked=False,
            apply_view=False,
        )

    def _set_experiment_region(
        self, xmin, xmax, ymin, ymax, source="user", user_locked=False, apply_view=True
    ):
        xmin, xmax = float(xmin), float(xmax)
        ymin, ymax = float(ymin), float(ymax)
        if xmax <= xmin or ymax <= ymin:
            QMessageBox.warning(self, "区域无效", "要求 Xmax > Xmin 且 Ymax > Ymin")
            return False
        self._experiment_region = (xmin, xmax, ymin, ymax, str(source))
        self._region_user_locked = bool(user_locked)
        for spb, val in (
            (self._sp_xmin, xmin),
            (self._sp_xmax, xmax),
            (self._sp_ymin, ymin),
            (self._sp_ymax, ymax),
        ):
            spb.blockSignals(True)
            spb.setValue(float(val))
            spb.blockSignals(False)
        src_map = {"walls": "外部墙体", "metadata": "参数区域", "user": "用户输入"}
        src_txt = src_map.get(source, source)
        if str(source).startswith("metadata-after"):
            src_txt = "参数区域（墙体不可用）"
        self._lbl_region_src.setText(
            f"来源：{src_txt}  |  X[{xmin:.0f},{xmax:.0f}] Y[{ymin:.0f},{ymax:.0f}]"
        )
        if apply_view:
            self._apply_region_to_view()
        return True

    def _apply_user_region(self):
        ok = self._set_experiment_region(
            self._sp_xmin.value(),
            self._sp_xmax.value(),
            self._sp_ymin.value(),
            self._sp_ymax.value(),
            source="user",
            user_locked=True,
            apply_view=True,
        )
        if ok:
            self._sb.showMessage("已应用实验区域（用户锁定）")

    def _redetect_region(self):
        d = self._current_data
        if d is None:
            self._sb.showMessage("请先加载实验数据")
            return
        self._region_user_locked = False
        self._detect_and_fill_region(d, force=True)
        self._apply_region_to_view()
        if self._experiment_region:
            xmin, xmax, ymin, ymax, src = self._experiment_region
            self._sb.showMessage(
                f"已重新检测区域（{src}）：X[{xmin:.1f},{xmax:.1f}] Y[{ymin:.1f},{ymax:.1f}]"
            )

    def _apply_region_to_view(self):
        if self._experiment_region is None:
            return
        xmin, xmax, ymin, ymax, _src = self._experiment_region
        self._region_initialized = True
        if HAVE_VISPY:
            self._plot.set_region(xmin, xmax, ymin, ymax)
            self._plot.render()
        else:
            mx = (xmax - xmin) * 0.05
            my = (ymax - ymin) * 0.05
            self._plot.getViewBox().setRange(
                xRange=(xmin - mx, xmax + mx), yRange=(ymin - my, ymax + my)
            )

    def _build_kdtree(self):
        d = self._current_data
        if d is None or d.count == 0:
            self._kdtree = None
            return
        self._kdtree = cKDTree(np.column_stack([d.xs, d.ys]))

    # ── Group legend ────────────────────────────────────────────────
    def _refresh_legend(self, d):
        if d is None or d.count == 0 or len(d.groups) == 0:
            return
        counts = Counter(str(g) for g in d.groups)
        existing = set(self._legend.get_all_groups())
        for g, n in counts.items():
            label = "未指定（***）" if g == "***" else g
            col = self._color_map.get_qcolor(g) if hasattr(self._color_map, "get_qcolor") else group_to_color(g)
            if g in existing:
                self._legend.set_group_count(g, n)
            else:
                # store by raw group name
                self._legend.add_group(g, col, n, visible=g not in self._hidden_groups)
                # fix display name for ***
                item = self._legend.get_group_item(g)
                if item is not None and g == "***":
                    item._name_label.setText(label)

    def _on_group_visibility(self, group_name: str, visible: bool):
        if visible:
            self._hidden_groups.discard(group_name)
        else:
            self._hidden_groups.add(group_name)
        self._render()

    def _on_isolate_group(self, group_name: str):
        all_g = self._legend.get_all_groups()
        self._hidden_groups = set(all_g) - {group_name}
        for g in all_g:
            self._legend.set_group_visible(g, g == group_name)
        self._render()

    def _on_show_all_groups(self):
        self._hidden_groups.clear()
        for g in self._legend.get_all_groups():
            self._legend.set_group_visible(g, True)
        self._render()

    def _on_show_selected_group(self):
        d = self._current_data
        if d is None or self._selected_id is None:
            self._sb.showMessage("请先选择颗粒")
            return
        mask = d.ids == self._selected_id
        if not mask.any():
            return
        g = str(d.groups[int(mask.argmax())])
        self._on_isolate_group(g)

    # ── Rendering ───────────────────────────────────────────────────
    def _particle_mask(self, d) -> np.ndarray:
        n = d.count
        mask = np.ones(n, dtype=bool)
        if self._hidden_groups and len(d.groups) == n:
            for i, g in enumerate(d.groups):
                if str(g) in self._hidden_groups:
                    mask[i] = False
        return mask

    def _render(self):
        d = self._current_data
        if d is None or d.count == 0:
            return

        mask = self._particle_mask(d)
        xs = d.xs[mask]
        ys = d.ys[mask]
        rads = d.rads[mask]
        cols = d.colors[mask] if len(d.colors) == d.count else np.zeros(len(xs), dtype=np.int32)
        rgba = color_numbers_to_rgba(cols)

        if HAVE_VISPY:
            if not self._region_initialized:
                xmin, xmax, ymin, ymax = self._default_view_bounds(d)
                self._plot.set_region(xmin, xmax, ymin, ymax)
                self._region_initialized = True

            enhanced_flag = self._rb_enh.isChecked()
            # Soft min size for enhanced: scale rads in display only
            draw_rads = rads
            if enhanced_flag and len(rads):
                # approximate min radius in data units from current view span
                rect = None
                if hasattr(self._plot, "get_view_rect"):
                    rect = self._plot.get_view_rect()
                if rect is not None:
                    span = max(rect[1] - rect[0], rect[3] - rect[2], 1.0)
                    # ~2px on a 1000px canvas → span * 0.002
                    min_r = span * 0.001
                    draw_rads = np.maximum(rads, min_r)

            self._plot.set_data(xs, ys, draw_rads, rgba, enhanced=enhanced_flag)

            if self._wall_cb.isChecked() and getattr(d, "wall_data", None) is not None and len(d.wall_data):
                self._plot.set_walls(d.wall_data)
            else:
                self._plot.clear_walls()

            if self._selected_id is not None:
                sm = d.ids == self._selected_id
                if sm.any():
                    i = int(sm.argmax())
                    self._plot.set_selection(float(d.xs[i]), float(d.ys[i]), float(d.rads[i]))
                else:
                    self._plot.clear_selection()
            else:
                self._plot.clear_selection()
            self._plot.render()
        else:
            if not self._region_initialized:
                xmin, xmax, ymin, ymax = self._default_view_bounds(d)
                mx = (xmax - xmin) * 0.05
                my = (ymax - ymin) * 0.05
                self._plot.getViewBox().setRange(
                    xRange=(xmin - mx, xmax + mx), yRange=(ymin - my, ymax + my)
                )
                self._region_initialized = True
            sizes = rads * 2
            if self._rb_enh.isChecked():
                vr = self._plot.getViewBox().viewRange()
                xr = vr[0][1] - vr[0][0]
                if xr > 0:
                    vw = self._plot.viewport().width() if self._plot.viewport() else 100
                    ppu = vw / xr if xr else 0
                    if ppu > 0:
                        min_data = 2.0 / ppu
                        bmin = float(sizes.min()) if len(sizes) else 0
                        if bmin > 0 and bmin < min_data:
                            sizes = sizes * (min_data / bmin)
            brushes = [QColor(int(r * 255), int(g * 255), int(b * 255)) for r, g, b, _a in rgba]
            self._scatter.setData(
                x=xs, y=ys, size=sizes, pen=None, brush=brushes, pxMode=False
            )

    # ── Selection ───────────────────────────────────────────────────
    def _pick_particle_at(self, x: float, y: float) -> int | None:
        """Return permanent id near (x,y), preferring hits inside particle radius."""
        if self._kdtree is None or self._current_data is None:
            return None
        d = self._current_data
        # Query a few nearest candidates
        k = min(8, d.count)
        dists, idxs = self._kdtree.query(np.array([[x, y]]), k=k)
        dists = np.atleast_1d(np.asarray(dists).ravel())
        idxs = np.atleast_1d(np.asarray(idxs).ravel())
        best_i = None
        best_dist = None
        for dist, i in zip(dists, idxs):
            i = int(i)
            if i < 0 or i >= d.count:
                continue
            rad = float(d.rads[i])
            # Prefer particles whose disc covers the click
            if dist <= max(rad, 1e-9):
                if best_dist is None or dist < best_dist:
                    best_i, best_dist = i, float(dist)
        if best_i is None:
            # Fall back to nearest if within a soft max pick radius
            i0 = int(idxs[0])
            soft = float(np.median(d.rads)) * 3.0 if d.count else 100.0
            if float(dists[0]) <= soft and 0 <= i0 < d.count:
                best_i = i0
        if best_i is None:
            return None
        return int(d.ids[best_i])

    def _on_click(self, event):
        if self._kdtree is None or self._current_data is None:
            return
        if HAVE_VISPY:
            return
        sp = event.scenePos()
        vb = self._plot.getViewBox()
        dp = vb.mapSceneToView(sp)
        pid = self._pick_particle_at(float(dp.x()), float(dp.y()))
        if pid is not None:
            self._select_particle(pid)

    def _on_vispy_click(self, x, y):
        pid = self._pick_particle_at(float(x), float(y))
        if pid is not None:
            self._select_particle(pid)

    def _select_particle(self, pid: int):
        self._selected_id = int(pid)
        self._id_input.setText(str(pid))
        self._refresh_selected_info()
        self._render()
        self._set_controls_enabled(bool(self._frame_files))
        self._sb.showMessage(f"已选中永久 ID {pid}")

    def _clear_selection(self):
        self._selected_id = None
        # Keep id text so user can re-track, but clear visual selection
        for k in self._lbls:
            self._lbls[k].setText("—")
        for k in self._dlbls:
            self._dlbls[k].setText("—")
        if HAVE_VISPY:
            self._plot.clear_selection()
            self._plot.render()
        self._set_controls_enabled(bool(self._frame_files))
        self._sb.showMessage("已清除选择")

    def _locate_selected(self):
        d = self._current_data
        if d is None or self._selected_id is None:
            self._sb.showMessage("请先选择颗粒")
            return
        mask = d.ids == self._selected_id
        if not mask.any():
            self._sb.showMessage("当前帧不存在该颗粒")
            return
        i = int(mask.argmax())
        x, y, r = float(d.xs[i]), float(d.ys[i]), float(d.rads[i])
        half = max(r * 40.0, 500.0)
        xmin, xmax = x - half, x + half
        ymin, ymax = y - half, y + half
        if HAVE_VISPY:
            self._plot.set_region(xmin, xmax, ymin, ymax)
            self._plot.set_selection(x, y, r)
            self._plot.render()
        else:
            self._plot.getViewBox().setRange(xRange=(xmin, xmax), yRange=(ymin, ymax))
        self._sb.showMessage(f"已定位 ID {self._selected_id}")

    def _refresh_selected_info(self):
        d = self._current_data
        pid = self._selected_id
        if d is None or pid is None:
            return
        mask = d.ids == pid
        if not mask.any():
            self._lbls["状态:"].setText("本帧不存在")
            return
        i = int(mask.argmax())
        self._lbls["ID:"].setText(str(pid))
        self._lbls["序号:"].setText(str(int(d.indices[i])))
        g = str(d.groups[i]) if len(d.groups) > i else "***"
        self._lbls["Group:"].setText("未指定（***）" if g == "***" else g)
        self._lbls["X:"].setText(f"{d.xs[i]:.2f}")
        self._lbls["Y:"].setText(f"{d.ys[i]:.2f}")
        self._lbls["半径:"].setText(f"{d.rads[i]:.1f}")
        self._lbls["状态:"].setText("正常")
        # If trajectory exists, refresh displacement panel for current step
        if self._trajectory:
            for p in self._trajectory:
                if int(p.time_step) == int(d.current_step) and p.status in (
                    "normal",
                    "present",
                ):
                    self._dlbls["ΔX:"].setText(f"{p.displacement_x_km:.2f}")
                    self._dlbls["ΔY:"].setText(f"{p.displacement_y_km:.2f}")
                    self._dlbls["总位移:"].setText(f"{p.displacement_total_km:.2f}")
                    self._dlbls["路径长:"].setText(f"{p.path_length_km:.2f}")
                    self._dlbls["Vx:"].setText(f"{p.velocity_x:.6g} /step")
                    self._dlbls["Vy:"].setText(f"{p.velocity_y:.6g} /step")
                    self._dlbls["|v|:"].setText(f"{p.velocity_total:.6g} /step")
                    self._dlbls["Δstep:"].setText(f"{p.delta_step:.0f}")
                    break

    # ── Trajectory ──────────────────────────────────────────────────
    def _on_track(self):
        if not self._frame_files:
            QMessageBox.warning(self, "提示", "请先打开实验目录")
            return
        if self._traj_service.is_running:
            QMessageBox.information(self, "提示", "轨迹正在提取，请先取消或等待完成")
            return
        txt = self._id_input.text().strip()
        if not txt:
            QMessageBox.warning(self, "提示", "请输入永久颗粒 ID")
            return
        try:
            pid = int(txt)
        except ValueError:
            QMessageBox.warning(self, "提示", "请输入整数永久 ID（不是 index）")
            return
        d = self._current_data
        if d is None or not np.any(d.ids == pid):
            QMessageBox.warning(self, "提示", f"当前帧中未找到永久 ID {pid}")
            return
        self._select_particle(pid)
        finfos = [
            FileInfo(
                file_order=i,
                filename_step=os.path.basename(p),
                current_step=s,
                dat_path=p,
                file_size=os.path.getsize(p) if os.path.exists(p) else 0,
                status="pending",
            )
            for i, (s, p) in enumerate(self._frame_files)
        ]
        self._btn_track.setEnabled(False)
        self._traj_progress.setVisible(True)
        self._traj_progress.setValue(0)
        self._btn_cancel_traj.setVisible(True)
        self._sb.showMessage(f"正在提取轨迹：0 / {len(finfos)}")
        self._sb_label.setText("提取轨迹…")
        worker = self._traj_service.start(pid, finfos, max_workers=4)
        self._current_worker = worker
        worker.progress.connect(self._on_traj_progress)
        worker.finished.connect(self._on_traj_done)
        worker.error.connect(self._on_traj_error)

    def _on_traj_progress(self, cur: int, total: int):
        total = max(total, 1)
        self._traj_progress.setValue(int(100 * cur / total))
        self._sb.showMessage(f"正在提取轨迹：{cur} / {total}")

    def _cancel_trajectory(self):
        self._traj_service.cancel()
        self._traj_progress.setVisible(False)
        self._btn_cancel_traj.setVisible(False)
        self._btn_track.setEnabled(True)
        self._sb.showMessage("操作已取消")
        self._sb_label.setText("已取消")
        self._set_controls_enabled(bool(self._frame_files))

    def _on_traj_error(self, msg: str):
        self._traj_progress.setVisible(False)
        self._btn_cancel_traj.setVisible(False)
        self._btn_track.setEnabled(True)
        self._sb.showMessage(f"追踪失败: {msg}")
        self._sb_label.setText("错误")
        self._set_controls_enabled(bool(self._frame_files))

    def _on_traj_done(self, traj):
        self._trajectory = traj
        self._traj_progress.setVisible(False)
        self._btn_cancel_traj.setVisible(False)
        self._btn_track.setEnabled(True)
        self._current_worker = None
        n_ok = sum(1 for p in (traj or []) if p.status in ("normal", "present"))
        n_er = sum(1 for p in (traj or []) if p.status == "eroded")
        n_fe = sum(1 for p in (traj or []) if p.status == "file_error")
        msg = f"轨迹提取完成: {len(traj)} 帧（有效 {n_ok}"
        if n_er:
            msg += f"，剥蚀 {n_er}"
        if n_fe:
            msg += f"，文件错误 {n_fe}"
        msg += "）"
        self._sb.showMessage(msg)
        self._sb_label.setText("轨迹完成")
        self._update_plots(traj)
        self._update_table(traj)
        last = None
        for p in reversed(traj or []):
            if p.status in ("normal", "present") and not (
                isinstance(p.x_km, float) and np.isnan(p.x_km)
            ):
                last = p
                break
        if last is None and traj:
            last = traj[-1]
        if last is not None:
            self._dlbls["ΔX:"].setText(f"{last.displacement_x_km:.2f}")
            self._dlbls["ΔY:"].setText(f"{last.displacement_y_km:.2f}")
            self._dlbls["总位移:"].setText(f"{last.displacement_total_km:.2f}")
            self._dlbls["路径长:"].setText(f"{last.path_length_km:.2f}")
            self._dlbls["Vx:"].setText(f"{last.velocity_x:.6g} /step")
            self._dlbls["Vy:"].setText(f"{last.velocity_y:.6g} /step")
            self._dlbls["|v|:"].setText(f"{last.velocity_total:.6g} /step")
            self._dlbls["Δstep:"].setText(f"{last.delta_step:.0f}")
        if self._btn_traj_path.isChecked():
            self._draw_traj_path(traj)
        self._set_controls_enabled(bool(self._frame_files))
        # Jump to trajectory tab for immediate feedback
        if n_ok:
            self._tabs.setCurrentWidget(self._plot_dt)

    def _style_curve(self, pw, x, y, color="#1f4e79"):
        if hasattr(pw, "set_series"):
            pw.set_series(x, y, color=color)
            return
        pen = pg.mkPen(color=color, width=1.8)
        pw.plot(x, y, pen=pen)

    def _update_plots(self, traj):
        plots = [
            self._plot_dx,
            self._plot_dy,
            self._plot_dt,
            self._plot_pl,
            self._plot_v,
            self._plot_vx,
            self._plot_vy,
        ]
        for pw in plots:
            if hasattr(pw, "clear"):
                pw.clear()
        if not traj:
            return
        pts = [
            p
            for p in traj
            if p.status in ("normal", "present")
            and not (isinstance(p.x_km, float) and np.isnan(p.x_km))
        ]
        if not pts:
            return
        steps = [p.time_step for p in pts]
        self._style_curve(self._plot_dx, steps, [p.displacement_x_km for p in pts])
        self._style_curve(self._plot_dy, steps, [p.displacement_y_km for p in pts])
        self._style_curve(self._plot_dt, steps, [p.displacement_total_km for p in pts])
        self._style_curve(self._plot_pl, steps, [p.path_length_km for p in pts])
        self._style_curve(
            self._plot_v, steps, [p.velocity_total for p in pts], color="#8B1A1A"
        )
        self._style_curve(
            self._plot_vx, steps, [p.velocity_x for p in pts], color="#1a5f2a"
        )
        self._style_curve(
            self._plot_vy, steps, [p.velocity_y for p in pts], color="#5b3a8c"
        )

    def _update_table(self, traj):
        if not traj:
            return
        headers = [
            "时间步",
            "X",
            "Y",
            "ΔX",
            "ΔY",
            "总位移",
            "Vx",
            "Vy",
            "|v|",
            "Δstep",
            "路径长度",
            "状态",
        ]
        self._tbl.setColumnCount(len(headers))
        self._tbl.setHorizontalHeaderLabels(headers)
        self._tbl.setRowCount(len(traj))
        for r, p in enumerate(traj):
            def fmt(v, nd=2):
                if v is None or (isinstance(v, float) and np.isnan(v)):
                    return "—"
                return f"{v:.{nd}f}" if nd is not None else f"{v:.6g}"

            vals = [
                p.time_step,
                fmt(p.x_km, 1),
                fmt(p.y_km, 1),
                fmt(p.displacement_x_km, 2),
                fmt(p.displacement_y_km, 2),
                fmt(p.displacement_total_km, 2),
                fmt(p.velocity_x, None),
                fmt(p.velocity_y, None),
                fmt(p.velocity_total, None),
                f"{p.delta_step:.0f}" if p.delta_step else "0",
                fmt(p.path_length_km, 2),
                p.status,
            ]
            for c, v in enumerate(vals):
                self._tbl.setItem(r, c, QTableWidgetItem(str(v)))
        self._tbl.resizeColumnsToContents()

    def _toggle_traj_path(self, checked):
        self._btn_traj_path.setText("隐藏路径" if checked else "显示路径")
        if checked and self._trajectory:
            self._draw_traj_path(self._trajectory)
        else:
            self._clear_traj_path()

    def _draw_traj_path(self, traj):
        self._clear_traj_path()
        xs = [
            p.x_km
            for p in traj
            if p.status in ("normal", "present")
            and not (isinstance(p.x_km, float) and np.isnan(p.x_km))
        ]
        ys = [
            p.y_km
            for p in traj
            if p.status in ("normal", "present")
            and not (isinstance(p.y_km, float) and np.isnan(p.y_km))
        ]
        if len(xs) < 2:
            return
        if HAVE_VISPY:
            self._plot.set_trajectory_path(xs, ys)
        else:
            self._traj_path_item = pg.PlotDataItem(
                xs,
                ys,
                pen=pg.mkPen(color=(160, 160, 160), width=2, style=Qt.DashLine),
            )
            self._plot.addItem(self._traj_path_item)

    def _clear_traj_path(self):
        if HAVE_VISPY:
            self._plot.clear_trajectory_path()
        elif self._traj_path_item is not None:
            self._plot.removeItem(self._traj_path_item)
            self._traj_path_item = None

    # ── View ────────────────────────────────────────────────────────
    def _default_view_bounds(self, d):
        if self._experiment_region is not None:
            xmin, xmax, ymin, ymax, _src = self._experiment_region
            return float(xmin), float(xmax), float(ymin), float(ymax)
        meta = {
            "left": float(d.left),
            "right": float(d.right),
            "bottom": float(d.bottom),
            "height": float(d.height),
        }
        walls = getattr(d, "wall_data", None)
        if walls is not None and len(walls) > 0:
            reg = self._region_detector.detect_from_walls(np.asarray(walls), meta)
            if reg.source == "walls":
                return float(reg.x_min), float(reg.x_max), float(reg.y_min), float(reg.y_max)
        reg = self._region_detector.detect_from_metadata(meta)
        return float(reg.x_min), float(reg.x_max), float(reg.y_min), float(reg.y_max)

    def _fit_region(self):
        d = self._current_data
        if d is None:
            return
        if self._experiment_region is None:
            self._detect_and_fill_region(d, force=True)
        self._apply_region_to_view()
        if self._experiment_region:
            xmin, xmax, ymin, ymax, src = self._experiment_region
            self._sb.showMessage(
                f"已适配实验区域（{src}）：X[{xmin:.1f},{xmax:.1f}] Y[{ymin:.1f},{ymax:.1f}]"
            )

    def _fit_particles(self):
        d = self._current_data
        if d is None or d.count == 0:
            return
        pad = max(float(np.max(d.rads)) * 4, (d.xs.max() - d.xs.min()) * 0.02)
        xmin, xmax = float(d.xs.min()) - pad, float(d.xs.max()) + pad
        ymin, ymax = float(d.ys.min()) - pad, float(d.ys.max()) + pad
        if HAVE_VISPY:
            self._plot.set_region(xmin, xmax, ymin, ymax)
            self._plot.render()
        else:
            self._plot.getViewBox().setRange(xRange=(xmin, xmax), yRange=(ymin, ymax))
        self._sb.showMessage(
            f"已适配颗粒：X[{xmin:.1f},{xmax:.1f}] Y[{ymin:.1f},{ymax:.1f}]（未改实验区域）"
        )

    # ── Playback ────────────────────────────────────────────────────
    def _first(self):
        if not self._frame_files:
            return
        self._load_frame(0, force=True)

    def _prev(self):
        if not self._frame_files:
            return
        self._load_frame(max(0, self._current_idx - 1))

    def _next(self):
        if not self._frame_files:
            return
        self._load_frame(min(len(self._frame_files) - 1, self._current_idx + 1))

    def _last(self):
        if not self._frame_files:
            return
        self._load_frame(len(self._frame_files) - 1, force=True)

    def _on_play_tick(self):
        if not self._frame_files:
            self._play_timer.stop()
            return
        if self._current_idx >= len(self._frame_files) - 1:
            self._play_timer.stop()
            if hasattr(self, "_btn_play"):
                self._btn_play.setText("▶/⏸")
            self._sb.showMessage("已播放到最后一帧")
            return
        self._load_frame(self._current_idx + 1)

    def _play(self):
        if not self._frame_files:
            return
        if self._play_timer.isActive():
            self._play_timer.stop()
            if hasattr(self, "_btn_play"):
                self._btn_play.setText("▶/⏸")
            self._sb.showMessage("已暂停")
        else:
            # If at end, restart from first
            if self._current_idx >= len(self._frame_files) - 1:
                self._load_frame(0, force=True)
            self._play_timer.start(int(self._spd.currentText()))
            if hasattr(self, "_btn_play"):
                self._btn_play.setText("⏸")
            self._sb.showMessage("播放中…")

    def closeEvent(self, event):
        try:
            self._play_timer.stop()
            self._traj_service.cancel()
        except Exception:
            pass
        super().closeEvent(event)

    # ── Quality / project ───────────────────────────────────────────
    def _show_quality_report(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("数据质量报告")
        dlg.resize(560, 420)
        lay = QVBoxLayout(dlg)
        te = QTextEdit()
        te.setReadOnly(True)
        lines = self._last_quality_lines or ["尚无检查结果，请先打开实验目录。"]
        te.setPlainText("\n".join(lines))
        lay.addWidget(te)
        bb = QDialogButtonBox(QDialogButtonBox.Ok)
        bb.accepted.connect(dlg.accept)
        lay.addWidget(bb)
        dlg.exec()

    def _build_project_config(self) -> ProjectConfig:
        region = None
        src = "unknown"
        if self._experiment_region:
            region = self._experiment_region[:4]
            src = self._experiment_region[4]
        start = self._frame_files[0][0] if self._frame_files else None
        end = self._frame_files[-1][0] if self._frame_files else None
        return ProjectConfig(
            experiment_dir=self._dir_input.text(),
            start_step=start,
            end_step=end,
            file_stride=1,
            region=region,
            region_source=src,
            region_user_locked=self._region_user_locked,
            group_colors=self._color_map.to_dict(),
            display_mode="enhanced" if self._rb_enh.isChecked() else "real",
            show_walls=self._wall_cb.isChecked(),
            color_mode="color_number",
            selected_particle_id=self._selected_id,
        )

    def _save_project(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存项目配置",
            self._project_path or "project.zdemtrack.json",
            "ZDEM Track (*.zdemtrack.json);;JSON (*.json)",
        )
        if not path:
            return
        if not path.endswith(".json"):
            path += ".zdemtrack.json"
        try:
            save_project_config(path, self._build_project_config())
            self._project_path = path
            self._sb.showMessage(f"已保存项目配置: {path}")
        except Exception as e:
            QMessageBox.warning(self, "保存失败", str(e))

    def _open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "打开项目配置",
            "",
            "ZDEM Track (*.zdemtrack.json);;JSON (*.json);;All (*.*)",
        )
        if not path:
            return
        try:
            cfg = load_project_config(path)
        except Exception as e:
            QMessageBox.warning(self, "打开失败", str(e))
            return
        self._project_path = path
        if not cfg.experiment_dir or not os.path.isdir(cfg.experiment_dir):
            QMessageBox.warning(
                self,
                "目录缺失",
                f"配置中的实验目录不存在:\n{cfg.experiment_dir}\n请重新选择。",
            )
            return
        self.load_directory(cfg.experiment_dir)
        if cfg.region is not None:
            self._set_experiment_region(
                *cfg.region,
                source=cfg.region_source or "user",
                user_locked=bool(cfg.region_user_locked),
                apply_view=True,
            )
        self._wall_cb.setChecked(bool(cfg.show_walls))
        if cfg.display_mode == "enhanced":
            self._rb_enh.setChecked(True)
        else:
            self._rb_real.setChecked(True)
        if cfg.group_colors:
            self._color_map.from_dict(cfg.group_colors)
        if cfg.selected_particle_id is not None and self._current_data is not None:
            if np.any(self._current_data.ids == int(cfg.selected_particle_id)):
                self._select_particle(int(cfg.selected_particle_id))
        self._sb.showMessage(f"已打开项目配置: {path}")
