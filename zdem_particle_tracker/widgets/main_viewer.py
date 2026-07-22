"""Main viewer — VisPy particles, trajectory, matplotlib series, Chinese UI."""
from __future__ import annotations

import os
import time
from collections import Counter

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor, QKeySequence, QShortcut
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
    QSpinBox,
    QFrame,
)

from scipy.spatial import cKDTree

from ..config import DEFAULT_DIR
from ..parsers.dat_parser import ParseMode, parse_dat_file
from ..parsers.dat_scan import (
    DatFileEntry,
    default_end_index,
    default_start_index,
    leading_ini_end_index,
    scan_dat_files,
    select_range,
)
from ..services.trajectory_service import TrajectoryService, FileInfo
from ..services.region_detector import RegionDetector
from ..services.quality_report import check_file_list, check_frame
from ..services.project_config import (
    ProjectConfig,
    load_project_config,
    save_project_config,
)
from ..utils.color_mapping import (
    ColorMapping,
    color_numbers_to_rgba,
    group_to_color,
    groups_to_rgba,
    solid_rgba,
)
from ..utils.frame_cache import LRUCache
from ..workers.frame_load_worker import FrameLoadWorker
from ..ui.group_legend_panel import GroupLegendPanel
from ..ui.about_dialog import show_about_dialog, APP_VERSION
from ..utils.logging_utils import get_logger
from .selection_logic import (
    filter_trajectory_path_xy,
    id_allowed_at_session_start,
    next_play_index,
    pick_particle_id,
    play_parse_mode_name,
    validate_time_range_indices,
)

log = get_logger("main_viewer")

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
        self.resize(1480, 920)
        # Full catalog + active session slice
        self._all_entries: list[DatFileEntry] = []
        self._frame_entries: list[DatFileEntry] = []
        self._frame_files: list[tuple[int, str]] = []  # (step, path) for active range
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
        self._color_mode = "color_number"  # color_number | group | solid
        self._region_initialized = False
        self._experiment_region = None  # (xmin, xmax, ymin, ymax, source)
        self._region_detector = RegionDetector()
        self._region_user_locked = False
        self._traj_service = TrajectoryService()
        self._current_worker = None
        self._last_quality_lines: list[str] = []
        self._project_path: str | None = None
        self._pending_project: ProjectConfig | None = None
        self._prefetch_worker: FrameLoadWorker | None = None
        self._play_buttons: list[QPushButton] = []
        self._frame_load_busy = False
        self._play_waiting = False
        self._path_to_current = True  # trajectory path clipped to current step
        # Permanent IDs present in the session *start* frame (selection gate)
        self._start_frame_ids: set[int] | None = None
        self._auto_track_on_select = True

        self._setup_ui()
        self._setup_menu()
        self._setup_shortcuts()
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

        # Display scale
        gb_disp = QGroupBox("显示比例")
        dv = QHBoxLayout(gb_disp)
        self._rb_group_scale = QButtonGroup(self)
        self._rb_real = QRadioButton("真实比例")
        self._rb_real.setChecked(True)
        self._rb_enh = QRadioButton("增强可见性")
        self._rb_group_scale.addButton(self._rb_real)
        self._rb_group_scale.addButton(self._rb_enh)
        self._rb_enh.toggled.connect(lambda: self._render())
        self._rb_real.toggled.connect(lambda: self._render())
        dv.addWidget(self._rb_real)
        dv.addWidget(self._rb_enh)
        ll.addWidget(gb_disp)

        # Color mode
        gb_cm = QGroupBox("着色模式")
        cm_lay = QVBoxLayout(gb_cm)
        self._color_mode_group = QButtonGroup(self)
        self._rb_cm_color = QRadioButton("按 color#")
        self._rb_cm_group = QRadioButton("按 Group")
        self._rb_cm_solid = QRadioButton("单色")
        self._rb_cm_color.setChecked(True)
        for rb in (self._rb_cm_color, self._rb_cm_group, self._rb_cm_solid):
            self._color_mode_group.addButton(rb)
            cm_lay.addWidget(rb)
            rb.toggled.connect(self._on_color_mode_changed)
        ll.addWidget(gb_cm)

        # Experiment directory
        gb_dir = QGroupBox("实验目录")
        dir_l = QVBoxLayout(gb_dir)
        self._dir_input = QLineEdit(DEFAULT_DIR)
        self._dir_input.setReadOnly(True)
        dir_l.addWidget(self._dir_input)
        btn_row = QHBoxLayout()
        btn = QPushButton("浏览")
        btn.clicked.connect(self._browse)
        btn_row.addWidget(btn)
        scan_btn = QPushButton("重新扫描")
        scan_btn.setObjectName("secondary")
        scan_btn.clicked.connect(self._scan_dir)
        btn_row.addWidget(scan_btn)
        dir_l.addLayout(btn_row)
        self._file_info = QLabel("尚未打开实验")
        self._file_info.setObjectName("secondary")
        self._file_info.setWordWrap(True)
        dir_l.addWidget(self._file_info)
        ll.addWidget(gb_dir)

        # Time range — default start = last leading _ini
        gb_range = QGroupBox("时间范围")
        fl_r = QFormLayout(gb_range)
        fl_r.setContentsMargins(8, 12, 8, 8)
        fl_r.setSpacing(6)
        self._cmb_start = QComboBox()
        self._cmb_start.setMinimumWidth(140)
        self._cmb_end = QComboBox()
        self._cmb_end.setMinimumWidth(140)
        self._sp_stride = QSpinBox()
        self._sp_stride.setRange(1, 999)
        self._sp_stride.setValue(1)
        self._sp_stride.setToolTip("每 N 个文件取 1 帧（1=全部）")
        fl_r.addRow("起始", self._cmb_start)
        fl_r.addRow("结束", self._cmb_end)
        fl_r.addRow("间隔 N", self._sp_stride)
        self._lbl_ini_hint = QLabel("默认起点：最后一个前导 _ini（沉积结束）")
        self._lbl_ini_hint.setObjectName("secondary")
        self._lbl_ini_hint.setWordWrap(True)
        fl_r.addRow(self._lbl_ini_hint)
        btn_apply_range = QPushButton("应用范围")
        btn_apply_range.clicked.connect(self._apply_time_range)
        fl_r.addRow(btn_apply_range)
        ll.addWidget(gb_range)

        # Group legend
        self._legend = GroupLegendPanel()
        self._legend.visibility_changed.connect(self._on_group_visibility)
        self._legend.isolate_group.connect(self._on_isolate_group)
        self._legend.show_all_groups.connect(self._on_show_all_groups)
        self._legend.show_selected_group.connect(self._on_show_selected_group)
        self._legend.color_changed.connect(self._on_group_color_changed)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._legend)
        scroll.setMinimumHeight(120)
        scroll.setMaximumHeight(220)
        scroll.setFrameShape(QFrame.NoFrame)
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
        fl.addRow("X 最小", self._sp_xmin)
        fl.addRow("X 最大", self._sp_xmax)
        fl.addRow("Y 最小", self._sp_ymin)
        fl.addRow("Y 最大", self._sp_ymax)
        self._lbl_region_src = QLabel("来源：—")
        self._lbl_region_src.setObjectName("secondary")
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

        fit_row = QHBoxLayout()
        btn2 = QPushButton("适配区域")
        btn2.setObjectName("secondary")
        btn2.clicked.connect(self._fit_region)
        fit_row.addWidget(btn2)
        btn3 = QPushButton("适配颗粒")
        btn3.setObjectName("secondary")
        btn3.clicked.connect(self._fit_particles)
        fit_row.addWidget(btn3)
        ll.addLayout(fit_row)
        btn_q = QPushButton("数据质量报告")
        btn_q.setObjectName("secondary")
        btn_q.clicked.connect(self._show_quality_report)
        ll.addWidget(btn_q)
        ll.addStretch()
        left.setMinimumWidth(260)
        left.setMaximumWidth(340)
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
        self._btn_track.setToolTip("对选中永久 ID 重新提取轨迹（点击选择后会自动追踪）")
        self._btn_track.clicked.connect(self._on_track)
        g1l.addWidget(self._btn_track)
        hint_sel = QLabel("仅可选择会话起始帧中存在的颗粒；选中后自动追踪")
        hint_sel.setObjectName("secondary")
        hint_sel.setWordWrap(True)
        hint_sel.setStyleSheet("color:#86868b;font-size:11px;")
        g1l.addWidget(hint_sel)
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
        self._cb_path_to_current = QCheckBox("路径截止当前帧")
        self._cb_path_to_current.setChecked(True)
        self._cb_path_to_current.setToolTip("勾选：只画到当前时间步；取消：画完整选定范围")
        self._cb_path_to_current.toggled.connect(self._on_path_range_toggled)
        g1l.addWidget(self._cb_path_to_current)
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
        act_open.setShortcut(QKeySequence.Open)
        act_open.triggered.connect(self._browse)
        m_file.addAction(act_open)
        act_save = QAction("保存项目配置…", self)
        act_save.setShortcut(QKeySequence.Save)
        act_save.triggered.connect(self._save_project)
        m_file.addAction(act_save)
        act_load = QAction("打开项目配置…", self)
        act_load.triggered.connect(self._open_project)
        m_file.addAction(act_load)
        m_file.addSeparator()
        act_quit = QAction("退出", self)
        act_quit.setShortcut(QKeySequence.Quit)
        act_quit.triggered.connect(self.close)
        m_file.addAction(act_quit)

        m_data = mb.addMenu("数据")
        act_q = QAction("数据质量报告", self)
        act_q.triggered.connect(self._show_quality_report)
        m_data.addAction(act_q)

        m_help = mb.addMenu("帮助")
        act_about = QAction("关于与快捷键", self)
        act_about.setShortcut(QKeySequence.HelpContents)
        act_about.triggered.connect(self._show_about)
        m_help.addAction(act_about)

    def _setup_shortcuts(self):
        def sc(key, slot):
            s = QShortcut(QKeySequence(key), self)
            s.setContext(Qt.WindowShortcut)
            s.activated.connect(slot)
            return s

        sc(Qt.Key_Space, self._play)
        sc(Qt.Key_Left, self._prev)
        sc(Qt.Key_Right, self._next)
        sc(Qt.Key_Home, self._first)
        sc(Qt.Key_End, self._last)
        sc("F", self._fit_region)
        sc("G", self._fit_particles)
        sc("L", self._locate_selected)
        sc(Qt.Key_Escape, self._clear_selection)

    def _show_about(self):
        show_about_dialog(self)

    # ── File IO ─────────────────────────────────────────────────────
    def load_directory(self, path: str, pending: ProjectConfig | None = None):
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
        self._pending_project = pending
        self._play_waiting = False
        self._frame_load_busy = False

        entries = scan_dat_files(path)
        if not entries:
            log.warning("load_directory: no DAT in %s", path)
            self._all_entries = []
            self._frame_entries = []
            self._frame_files = []
            self._sb.showMessage(f"未找到 DAT 文件: {path}")
            self._sb_label.setText("无数据")
            self._set_controls_enabled(False)
            self._populate_range_combos([])
            return

        self._all_entries = entries
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
        self._start_frame_ids = None
        self._reset_trajectory_ui()
        if HAVE_VISPY:
            try:
                self._plot.clear_origin_marker()
            except Exception:
                pass
        if hasattr(self, "_btn_traj_path"):
            self._btn_traj_path.blockSignals(True)
            self._btn_traj_path.setChecked(False)
            self._btn_traj_path.setText("显示路径")
            self._btn_traj_path.blockSignals(False)
        for k in self._lbls:
            self._lbls[k].setText("—")
        for k in self._dlbls:
            self._dlbls[k].setText("—")

        self._dir_input.setText(path)
        n_ini = sum(1 for e in entries if e.is_ini)
        lead = leading_ini_end_index(entries)
        ini_msg = (
            f"前导沉积 _ini 共 {lead + 1} 个，默认起点步 {entries[lead].step}"
            if lead >= 0
            else "未检测到前导 _ini，默认从第一帧开始"
        )
        self._lbl_ini_hint.setText(ini_msg)
        self._populate_range_combos(entries, pending=pending)

        # Defaults: last leading ini → last file, stride 1 (or from project)
        si = default_start_index(entries)
        ei = default_end_index(entries)
        stride = 1
        if pending is not None:
            if pending.start_step is not None:
                for i, e in enumerate(entries):
                    if e.step == int(pending.start_step):
                        si = i
                        break
            if pending.end_step is not None:
                for i, e in enumerate(entries):
                    if e.step == int(pending.end_step):
                        ei = i
            stride = max(1, int(pending.file_stride or 1))
            self._sp_stride.blockSignals(True)
            self._sp_stride.setValue(stride)
            self._sp_stride.blockSignals(False)
            self._cmb_start.blockSignals(True)
            self._cmb_end.blockSignals(True)
            self._cmb_start.setCurrentIndex(si)
            self._cmb_end.setCurrentIndex(ei)
            self._cmb_start.blockSignals(False)
            self._cmb_end.blockSignals(False)

        self._apply_session_range(si, ei, stride, load=True)
        list_rep = check_file_list(self._frame_files)
        self._last_quality_lines = list_rep.summary_lines()
        self._sb.showMessage(
            f"找到 {len(entries)} 个 DAT（含 {n_ini} 个 _ini），"
            f"活动范围 {len(self._frame_files)} 帧 · {ini_msg}"
        )
        self._sb_label.setText("扫描完成")
        log.info(
            "打开目录 %s: total=%d active=%d start=%s end=%s stride=%d",
            path,
            len(entries),
            len(self._frame_files),
            self._frame_files[0][0] if self._frame_files else None,
            self._frame_files[-1][0] if self._frame_files else None,
            stride,
        )

    def _populate_range_combos(
        self, entries: list[DatFileEntry], pending: ProjectConfig | None = None
    ):
        self._cmb_start.blockSignals(True)
        self._cmb_end.blockSignals(True)
        self._cmb_start.clear()
        self._cmb_end.clear()
        for e in entries:
            self._cmb_start.addItem(e.label, e)
            self._cmb_end.addItem(e.label, e)
        if entries:
            si = default_start_index(entries)
            ei = default_end_index(entries)
            self._cmb_start.setCurrentIndex(si)
            self._cmb_end.setCurrentIndex(ei)
        self._cmb_start.blockSignals(False)
        self._cmb_end.blockSignals(False)

    def _apply_time_range(self):
        si = self._cmb_start.currentIndex()
        ei = self._cmb_end.currentIndex()
        stride = self._sp_stride.value()
        log.info("apply_time_range si=%s ei=%s stride=%s n_all=%s", si, ei, stride, len(self._all_entries))
        err = validate_time_range_indices(si, ei, len(self._all_entries))
        if err:
            if "结束" in err:
                QMessageBox.warning(self, "范围无效", err)
            else:
                QMessageBox.information(self, "提示", err)
            return
        # Changing range invalidates trajectory zero point
        self._selected_id = None
        self._start_frame_ids = None
        self._reset_trajectory_ui()
        if HAVE_VISPY:
            try:
                self._plot.clear_selection()
                self._plot.clear_origin_marker()
                self._plot.render()
            except Exception:
                pass
        self._apply_session_range(si, ei, stride, load=True)
        self._sb.showMessage(
            f"已应用时间范围：{self._frame_files[0][0]} → {self._frame_files[-1][0]}，"
            f"共 {len(self._frame_files)} 帧（间隔 {stride}）。"
            f"位移零点已重置，请重新选择颗粒并追踪。"
        )
        QMessageBox.information(
            self,
            "时间范围已更新",
            "会话时间范围已变更，位移零点以新起始帧为准。\n"
            "之前的轨迹已清除，请重新选择颗粒（须存在于新的起始帧）。",
        )

    def _apply_session_range(self, start_i: int, end_i: int, stride: int, load: bool = True):
        selected = select_range(self._all_entries, start_i, end_i, stride)
        self._frame_entries = selected
        self._frame_files = [(e.step, e.path) for e in selected]
        self._frame_cache.clear()
        self._current_idx = 0
        self._current_data = None
        self._kdtree = None
        self._start_frame_ids = None
        if not selected:
            self._set_controls_enabled(False)
            return
        self._file_info.setText(
            f"活动 {len(selected)} 帧 | 步 {selected[0].step} → {selected[-1].step}"
            + (f" · 间隔 {stride}" if stride > 1 else "")
            + (f" · 起点 {'ini' if selected[0].is_ini else '正式'}")
        )
        self._slider.blockSignals(True)
        self._slider.setRange(0, max(0, len(selected) - 1))
        self._slider.setValue(0)
        self._slider.blockSignals(False)
        self._set_controls_enabled(True)
        if load:
            # First frame needs groups → FULL; later play uses BASIC
            self._load_frame(0, force=True, mode=ParseMode.FULL_PARTICLE_PROPERTIES)

    def _set_controls_enabled(self, enabled: bool):
        """Enable/disable playback & tracking controls based on experiment state."""
        for b in getattr(self, "_play_buttons", []) or []:
            b.setEnabled(enabled)
        if hasattr(self, "_slider"):
            self._slider.setEnabled(enabled)
        if hasattr(self, "_btn_track"):
            self._btn_track.setEnabled(enabled and not self._traj_service.is_running)
        if hasattr(self, "_id_input"):
            self._id_input.setEnabled(enabled)
        has_sel = enabled and self._selected_id is not None
        if hasattr(self, "_btn_locate"):
            self._btn_locate.setEnabled(has_sel)
        if hasattr(self, "_btn_clear_sel"):
            self._btn_clear_sel.setEnabled(has_sel)
        if hasattr(self, "_btn_traj_path"):
            self._btn_traj_path.setEnabled(enabled and self._trajectory is not None)
        if hasattr(self, "_cmb_start"):
            self._cmb_start.setEnabled(bool(self._all_entries))
            self._cmb_end.setEnabled(bool(self._all_entries))
            self._sp_stride.setEnabled(bool(self._all_entries))

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "选择实验目录")
        if d:
            self.load_directory(d)

    def _scan_dir(self):
        self.load_directory(self._dir_input.text())

    def _on_color_mode_changed(self, *_args):
        if self._rb_cm_group.isChecked():
            self._color_mode = "group"
        elif self._rb_cm_solid.isChecked():
            self._color_mode = "solid"
        else:
            self._color_mode = "color_number"
        self._render()

    def _on_path_range_toggled(self, checked: bool):
        self._path_to_current = bool(checked)
        if self._btn_traj_path.isChecked() and self._trajectory:
            self._draw_traj_path(self._trajectory)

    # ── Frame load (async + LRU + debounce + prefetch) ──────────────
    def _on_slider_changed(self, idx: int):
        self._pending_slider_idx = int(idx)
        self._slider_debounce.start()

    def _apply_slider_frame(self):
        self._load_frame(self._pending_slider_idx)

    def _load_frame(self, idx: int, force: bool = False, mode: ParseMode | None = None):
        if not self._frame_files or idx < 0 or idx >= len(self._frame_files):
            log.debug("load_frame skip bad idx=%s", idx)
            return
        if not force and idx == self._current_idx and self._current_data is not None:
            return
        step, path = self._frame_files[idx]
        log.debug("load_frame idx=%s step=%s force=%s mode=%s", idx, step, force, getattr(mode, "name", mode))
        self._current_idx = idx
        self._step_label.setText(f"{idx + 1}/{len(self._frame_files)}")
        self._slider.blockSignals(True)
        self._slider.setValue(idx)
        self._slider.blockSignals(False)

        # Prefer FULL if we need groups and cache has full; else BASIC for play
        use_mode = mode or ParseMode.BASIC_FRAME
        # First frame of session or legend empty → FULL
        if self._current_data is None or not self._legend.get_all_groups():
            use_mode = ParseMode.FULL_PARTICLE_PROPERTIES

        cached = self._frame_cache.get(path)
        if cached is not None:
            need_full_reload = False
            if use_mode is ParseMode.FULL_PARTICLE_PROPERTIES and self._color_mode == "group":
                gs = getattr(cached, "groups", None)
                if gs is None or len(gs) == 0:
                    need_full_reload = True
                elif cached.count > 0 and len(set(map(str, gs))) == 1 and str(gs[0]) == "***":
                    need_full_reload = True
            if not need_full_reload:
                log.debug("load_frame cache-hit idx=%s", idx)
                self._apply_frame_data(idx, cached)
                self._prefetch_neighbors(idx)
                return

        if self._load_worker is not None and self._load_worker.isRunning():
            try:
                self._load_worker.finished.disconnect()
                self._load_worker.error.disconnect()
            except Exception:
                pass

        self._load_req_id += 1
        req = self._load_req_id
        self._frame_load_busy = True
        self._sb.showMessage(
            f"正在读取起始帧…" if idx == 0 else f"加载第 {idx + 1}/{len(self._frame_files)} 帧…"
        )
        self._sb_label.setText("加载中…")
        worker = FrameLoadWorker(path, request_id=req, mode=use_mode)
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
        req = -(nxt + 1)
        mode = getattr(ParseMode, play_parse_mode_name(self._color_mode))
        worker = FrameLoadWorker(path, request_id=req, mode=mode)
        worker.finished.connect(self._on_prefetch_loaded)
        worker.error.connect(lambda *_: None)
        self._prefetch_worker = worker
        worker.start()

    def _on_prefetch_loaded(self, request_id: int, data):
        if not self._frame_files:
            return
        if request_id >= 0:
            return
        idx = -request_id - 1
        if 0 <= idx < len(self._frame_files):
            self._frame_cache.put(self._frame_files[idx][1], data)

    def _on_frame_loaded(self, request_id: int, data):
        if request_id != self._load_req_id:
            log.debug("frame_loaded stale req=%s current=%s", request_id, self._load_req_id)
            return  # stale
        self._frame_load_busy = False
        idx = self._current_idx
        log.debug("frame_loaded req=%s idx=%s balls=%s", request_id, idx, getattr(data, "count", "?"))
        if not self._frame_files or idx >= len(self._frame_files):
            return
        path = self._frame_files[idx][1]
        self._frame_cache.put(path, data)
        self._apply_frame_data(idx, data)
        self._prefetch_neighbors(idx)
        # Resume autoplay if we were waiting for this frame
        if self._play_waiting and self._play_timer.isActive():
            self._play_waiting = False

    def _on_frame_error(self, request_id: int, msg: str):
        if request_id != self._load_req_id:
            return
        self._frame_load_busy = False
        self._play_waiting = False
        log.error("frame_error req=%s msg=%s", request_id, msg)
        self._sb.showMessage(f"加载失败: {msg}")
        self._sb_label.setText("错误")
        if self._play_timer.isActive():
            self._play_timer.stop()
            if hasattr(self, "_btn_play"):
                self._btn_play.setText("▶/⏸")

    def _apply_frame_data(self, idx: int, data):
        self._current_data = data
        self._frame_load_busy = False
        # Session start frame defines the selectable permanent-ID set
        if idx == 0 and data is not None and data.count > 0:
            self._start_frame_ids = set(int(i) for i in data.ids.tolist())
            log.info("start_frame_ids set count=%d step=%s", len(self._start_frame_ids), getattr(data, "current_step", None))
        step_name = self._frame_files[idx][0] if self._frame_files else 0
        is_ini = False
        if 0 <= idx < len(self._frame_entries):
            is_ini = self._frame_entries[idx].is_ini
        tag = " · ini" if is_ini else ""
        self._file_info.setText(
            f"时间步 {data.current_step}{tag} | 颗粒 {data.count} | "
            f"{idx + 1}/{len(self._frame_files)} · 文件步 {step_name}"
        )
        if self._experiment_region is None or not self._region_user_locked:
            self._detect_and_fill_region(data)
        self._build_kdtree()
        self._refresh_legend(data)
        self._render()
        if self._btn_traj_path.isChecked() and self._trajectory:
            self._draw_traj_path(self._trajectory)
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
        # Apply deferred project settings once first frame is ready
        self._apply_pending_project_if_any()

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

    def _on_group_color_changed(self, group_name: str, color: QColor):
        """Persist legend color pick into ColorMapping (project config)."""
        packed = (color.red() << 16) | (color.green() << 8) | color.blue()
        self._color_map.set_color(str(group_name), packed)
        self._render()
        self._sb.showMessage(f"已更新 Group「{group_name}」颜色（保存项目配置后可持久化）")

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
            g_arr = np.asarray([str(g) for g in d.groups], dtype=object)
            hidden = list(self._hidden_groups)
            mask = ~np.isin(g_arr, hidden)
        return mask

    def _particle_rgba(self, d, mask) -> np.ndarray:
        n_vis = int(mask.sum()) if mask is not None else d.count
        if self._color_mode == "group" and len(d.groups) == d.count:
            return groups_to_rgba(d.groups[mask], self._color_map)
        if self._color_mode == "solid":
            return solid_rgba(n_vis)
        cols = d.colors[mask] if len(d.colors) == d.count else np.zeros(n_vis, dtype=np.int32)
        return color_numbers_to_rgba(cols)

    def _render(self):
        d = self._current_data
        if d is None or d.count == 0:
            return

        mask = self._particle_mask(d)
        xs = d.xs[mask]
        ys = d.ys[mask]
        rads = d.rads[mask]
        rgba = self._particle_rgba(d, mask)

        if HAVE_VISPY:
            if not self._region_initialized:
                xmin, xmax, ymin, ymax = self._default_view_bounds(d)
                self._plot.set_region(xmin, xmax, ymin, ymax)
                self._region_initialized = True

            enhanced_flag = self._rb_enh.isChecked()
            draw_rads = rads
            if enhanced_flag and len(rads):
                rect = None
                if hasattr(self._plot, "get_view_rect"):
                    rect = self._plot.get_view_rect()
                if rect is not None:
                    span = max(rect[1] - rect[0], rect[3] - rect[2], 1.0)
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
                    self._plot.set_selection(
                        float(d.xs[i]),
                        float(d.ys[i]),
                        float(d.rads[i]),
                        particle_id=self._selected_id,
                    )
                else:
                    self._plot.clear_selection()
            else:
                self._plot.clear_selection()

            # Origin marker from trajectory zero point
            if self._trajectory:
                for p in self._trajectory:
                    if p.status in ("normal", "present") and not (
                        isinstance(p.x_km, float) and np.isnan(p.x_km)
                    ):
                        self._plot.set_origin_marker(p.x_km, p.y_km, p.radius_km or 60.0)
                        break
            else:
                try:
                    self._plot.clear_origin_marker()
                except Exception:
                    pass
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
    def _id_in_start_frame(self, pid: int) -> bool:
        return id_allowed_at_session_start(self._start_frame_ids, pid)

    def _reset_trajectory_ui(self):
        """Clear trajectory data + path + curves + table (not the selected id)."""
        try:
            if self._traj_service.is_running:
                self._traj_service.cancel()
        except Exception:
            pass
        self._trajectory = None
        self._clear_traj_path()
        if hasattr(self, "_btn_traj_path"):
            self._btn_traj_path.blockSignals(True)
            self._btn_traj_path.setChecked(False)
            self._btn_traj_path.setText("显示路径")
            self._btn_traj_path.blockSignals(False)
        self._clear_plots_and_table()
        for k in self._dlbls:
            self._dlbls[k].setText("—")
        if HAVE_VISPY:
            try:
                self._plot.clear_origin_marker()
            except Exception:
                pass

    def _clear_plots_and_table(self):
        for key in ("dx", "dy", "dt", "pl", "v", "vx", "vy"):
            w = getattr(self, f"_plot_{key}", None)
            if w is not None and hasattr(w, "clear"):
                try:
                    w.clear()
                except Exception:
                    pass
        if hasattr(self, "_tbl"):
            self._tbl.setRowCount(0)

    def _pick_particle_at(self, x: float, y: float) -> int | None:
        """Return permanent id near (x,y), preferring hits inside particle radius.

        Only IDs present in the *session start* frame are selectable.
        """
        if self._current_data is None:
            return None
        d = self._current_data
        return pick_particle_id(
            d.xs,
            d.ys,
            d.rads,
            d.ids,
            float(x),
            float(y),
            start_ids=self._start_frame_ids,
            tree=self._kdtree,
        )

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
        else:
            self._sb.showMessage("未选中：请点击起始帧中存在的颗粒（空白处不取消选择）")

    def _on_vispy_click(self, x, y):
        pid = self._pick_particle_at(float(x), float(y))
        if pid is not None:
            self._select_particle(pid)
        else:
            self._sb.showMessage("未选中：仅可选择会话起始帧中存在的永久 ID")

    def _select_particle(self, pid: int, auto_track: bool | None = None):
        pid = int(pid)
        if self._start_frame_ids is None:
            QMessageBox.information(self, "请稍候", "起始帧尚未就绪，请等待加载完成后再选择。")
            return
        if not self._id_in_start_frame(pid):
            log.info("select rejected id=%s n_start=%s", pid, len(self._start_frame_ids or ()))
            QMessageBox.warning(
                self,
                "不可选择",
                f"永久 ID {pid} 不在会话起始帧中。\n"
                "位移零点为起始帧，只能追踪起始帧存在的颗粒。",
            )
            self._sb.showMessage(f"ID {pid} 不在起始帧，已拒绝选择")
            return
        prev = self._selected_id
        self._selected_id = pid
        self._id_input.setText(str(pid))
        self._refresh_selected_info()
        self._render()
        self._set_controls_enabled(bool(self._frame_files))
        log.info("selected particle id=%s auto_track=%s", pid, self._auto_track_on_select if auto_track is None else auto_track)
        self._sb.showMessage(f"已选中永久 ID {pid}")
        do_auto = self._auto_track_on_select if auto_track is None else bool(auto_track)
        # Auto-track on new selection (or re-select after clear)
        if do_auto and (prev != pid or self._trajectory is None):
            self._start_trajectory(pid)

    def _clear_selection(self):
        log.info("clear_selection previous_id=%s", self._selected_id)
        self._selected_id = None
        self._reset_trajectory_ui()
        for k in self._lbls:
            self._lbls[k].setText("—")
        if HAVE_VISPY:
            self._plot.clear_selection()
            try:
                self._plot.clear_origin_marker()
            except Exception:
                pass
            self._plot.render()
        self._set_controls_enabled(bool(self._frame_files))
        self._sb.showMessage("已清除选择与轨迹")

    def _locate_selected(self):
        d = self._current_data
        if d is None or self._selected_id is None:
            self._sb.showMessage("请先选择颗粒")
            return
        mask = d.ids == self._selected_id
        if not mask.any():
            self._sb.showMessage("当前帧不存在该颗粒（可能已剥蚀）")
            return
        i = int(mask.argmax())
        x, y, r = float(d.xs[i]), float(d.ys[i]), float(d.rads[i])
        half = max(r * 40.0, 500.0)
        xmin, xmax = x - half, x + half
        ymin, ymax = y - half, y + half
        if HAVE_VISPY:
            self._plot.set_region(xmin, xmax, ymin, ymax)
            self._plot.set_selection(x, y, r, particle_id=self._selected_id)
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
        if self._start_frame_ids is None:
            QMessageBox.information(self, "请稍候", "起始帧尚未就绪")
            return
        if not self._id_in_start_frame(pid):
            QMessageBox.warning(
                self,
                "不可追踪",
                f"永久 ID {pid} 不在会话起始帧中，无法作为位移零点。",
            )
            return
        # Select without nested auto-track, then start extraction
        self._select_particle(pid, auto_track=False)
        self._start_trajectory(pid)

    def _start_trajectory(self, pid: int):
        if not self._frame_files:
            return
        if self._traj_service.is_running:
            self._traj_service.cancel()
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
        log.info("start_trajectory id=%s frames=%d", pid, len(finfos))
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
        log.error("traj_error: %s", msg)
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
        log.info("traj_done %s", msg)
        self._sb.showMessage(msg)
        self._sb_label.setText("轨迹完成")
        self._update_plots(traj)
        self._update_table(traj)
        last = None
        for p in reversed(traj or []):
            if p.status in ("normal", "present"):
                last = p
                break
        if last is not None:
            self._dlbls["ΔX:"].setText(f"{last.displacement_x_km:.2f}")
            self._dlbls["ΔY:"].setText(f"{last.displacement_y_km:.2f}")
            self._dlbls["总位移:"].setText(f"{last.displacement_total_km:.2f}")
            self._dlbls["路径长:"].setText(f"{last.path_length_km:.2f}")
            self._dlbls["Vx:"].setText(f"{last.velocity_x:.6g} /step")
            self._dlbls["Vy:"].setText(f"{last.velocity_y:.6g} /step")
            self._dlbls["|v|:"].setText(f"{last.velocity_total:.6g} /step")
            self._dlbls["Δstep:"].setText(f"{last.delta_step:.0f}")
        # Auto-show path when trajectory ready
        if n_ok and hasattr(self, "_btn_traj_path"):
            self._btn_traj_path.blockSignals(True)
            self._btn_traj_path.setChecked(True)
            self._btn_traj_path.setText("隐藏路径")
            self._btn_traj_path.blockSignals(False)
            self._draw_traj_path(traj)
        elif self._btn_traj_path.isChecked():
            self._draw_traj_path(traj)
        self._render()
        self._set_controls_enabled(bool(self._frame_files))
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
        cur_step = None
        if self._current_data is not None:
            cur_step = int(self._current_data.current_step)
        xs, ys = filter_trajectory_path_xy(
            traj or [],
            path_to_current=self._path_to_current,
            current_step=cur_step,
        )
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
        if self._frame_load_busy:
            # Wait until current frame finishes; don't pile up loads
            self._play_waiting = True
            return
        nxt = next_play_index(self._current_idx, len(self._frame_files))
        if nxt is None:
            self._play_timer.stop()
            if hasattr(self, "_btn_play"):
                self._btn_play.setText("▶/⏸")
            self._sb.showMessage("已播放到最后一帧")
            return
        self._play_waiting = True
        mode_name = play_parse_mode_name(self._color_mode)
        play_mode = getattr(ParseMode, mode_name)
        self._load_frame(nxt, mode=play_mode)

    def _play(self):
        if not self._frame_files:
            return
        if self._play_timer.isActive():
            self._play_timer.stop()
            self._play_waiting = False
            if hasattr(self, "_btn_play"):
                self._btn_play.setText("▶/⏸")
            self._sb.showMessage("已暂停")
        else:
            if self._current_idx >= len(self._frame_files) - 1:
                self._load_frame(0, force=True)
            self._play_waiting = False
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
            file_stride=int(self._sp_stride.value()) if hasattr(self, "_sp_stride") else 1,
            region=region,
            region_source=src,
            region_user_locked=self._region_user_locked,
            group_colors=self._color_map.to_dict(),
            display_mode="enhanced" if self._rb_enh.isChecked() else "real",
            show_walls=self._wall_cb.isChecked(),
            color_mode=self._color_mode,
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
        # Defer region/selection until first frame loads
        self.load_directory(cfg.experiment_dir, pending=cfg)
        self._sb.showMessage(f"已打开项目配置: {path}（等待首帧…）")

    def _apply_pending_project_if_any(self):
        cfg = self._pending_project
        if cfg is None:
            return
        # Only apply once first data is ready
        if self._current_data is None:
            return
        self._pending_project = None
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
        mode = (cfg.color_mode or "color_number").lower()
        if mode in ("group", "by_group"):
            self._rb_cm_group.setChecked(True)
            self._color_mode = "group"
        elif mode in ("solid", "single"):
            self._rb_cm_solid.setChecked(True)
            self._color_mode = "solid"
        else:
            self._rb_cm_color.setChecked(True)
            self._color_mode = "color_number"
        if cfg.group_colors:
            self._color_map.from_dict(cfg.group_colors)
            for g, packed in self._color_map.to_dict().items():
                c = QColor((packed >> 16) & 0xFF, (packed >> 8) & 0xFF, packed & 0xFF)
                if hasattr(self._legend, "set_group_color"):
                    self._legend.set_group_color(g, c)
        if cfg.selected_particle_id is not None:
            pid = int(cfg.selected_particle_id)
            if self._id_in_start_frame(pid):
                self._select_particle(pid, auto_track=True)
            else:
                self._sb.showMessage(f"配置中的颗粒 ID {pid} 在起始帧不存在")
        self._render()
        self._sb.showMessage(f"已恢复项目配置: {self._project_path or ''}")
