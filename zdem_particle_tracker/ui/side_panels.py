"""Composable side / center chrome for MainViewer (no business logic).

Keeps MainViewer._setup_ui thin: build widgets here, connect slots in MainViewer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QComboBox,
    QGroupBox,
    QSlider,
    QCheckBox,
    QRadioButton,
    QButtonGroup,
    QDoubleSpinBox,
    QFormLayout,
    QProgressBar,
    QScrollArea,
    QSpinBox,
    QFrame,
)

from .group_legend_panel import GroupLegendPanel


@dataclass
class LeftPanel:
    widget: QWidget
    wall_cb: QCheckBox
    rb_real: QRadioButton
    rb_enh: QRadioButton
    rb_cm_color: QRadioButton
    rb_cm_group: QRadioButton
    rb_cm_solid: QRadioButton
    dir_input: QLineEdit
    file_info: QLabel
    cmb_start: QComboBox
    cmb_end: QComboBox
    sp_stride: QSpinBox
    lbl_ini_hint: QLabel
    legend: GroupLegendPanel
    sp_xmin: QDoubleSpinBox
    sp_xmax: QDoubleSpinBox
    sp_ymin: QDoubleSpinBox
    sp_ymax: QDoubleSpinBox
    lbl_region_src: QLabel


@dataclass
class RightPanel:
    widget: QWidget
    id_input: QLineEdit
    btn_track: QPushButton
    btn_locate: QPushButton
    btn_clear_sel: QPushButton
    btn_traj_path: QPushButton
    cb_path_to_current: QCheckBox
    lbls: dict  # basic info
    dlbls: dict  # displacement


@dataclass
class PlaybackBar:
    widget: QWidget  # actually a layout host
    layout: QHBoxLayout
    play_buttons: list
    btn_play: QPushButton
    slider: QSlider
    step_label: QLabel
    spd: QComboBox
    traj_progress: QProgressBar
    btn_cancel_traj: QPushButton
    prog_layout: QHBoxLayout


def _spin_region() -> QDoubleSpinBox:
    spb = QDoubleSpinBox()
    spb.setDecimals(1)
    spb.setRange(-1e9, 1e9)
    spb.setSingleStep(100.0)
    spb.setKeyboardTracking(False)
    return spb


def build_left_panel(
    parent: QWidget,
    *,
    default_dir: str,
    on_browse: Callable,
    on_scan: Callable,
    on_apply_range: Callable,
    on_color_mode: Callable,
    on_scale: Callable,
    on_render: Callable,
    on_apply_region: Callable,
    on_redetect: Callable,
    on_fit_region: Callable,
    on_fit_particles: Callable,
    on_quality: Callable,
    on_group_visibility: Callable,
    on_isolate_group: Callable,
    on_show_all_groups: Callable,
    on_show_selected_group: Callable,
    on_group_color: Callable,
) -> LeftPanel:
    left = QWidget(parent)
    ll = QVBoxLayout(left)
    ll.setContentsMargins(8, 8, 8, 8)
    ll.setSpacing(8)

    wall_cb = QCheckBox("显示墙体")
    wall_cb.setChecked(True)
    wall_cb.toggled.connect(on_render)
    ll.addWidget(wall_cb)

    gb_disp = QGroupBox("显示比例")
    dv = QHBoxLayout(gb_disp)
    rb_group_scale = QButtonGroup(left)
    rb_real = QRadioButton("真实比例")
    rb_real.setChecked(True)
    rb_enh = QRadioButton("增强可见性")
    rb_group_scale.addButton(rb_real)
    rb_group_scale.addButton(rb_enh)
    rb_enh.toggled.connect(on_scale)
    rb_real.toggled.connect(on_scale)
    dv.addWidget(rb_real)
    dv.addWidget(rb_enh)
    ll.addWidget(gb_disp)

    gb_cm = QGroupBox("着色模式")
    cm_lay = QVBoxLayout(gb_cm)
    color_mode_group = QButtonGroup(left)
    rb_cm_color = QRadioButton("按 color#")
    rb_cm_group = QRadioButton("按 Group")
    rb_cm_solid = QRadioButton("单色")
    rb_cm_color.setChecked(True)
    for rb in (rb_cm_color, rb_cm_group, rb_cm_solid):
        color_mode_group.addButton(rb)
        cm_lay.addWidget(rb)
        rb.toggled.connect(on_color_mode)
    ll.addWidget(gb_cm)

    gb_dir = QGroupBox("实验目录")
    dir_l = QVBoxLayout(gb_dir)
    dir_input = QLineEdit(default_dir)
    dir_input.setReadOnly(True)
    dir_l.addWidget(dir_input)
    btn_row = QHBoxLayout()
    btn = QPushButton("浏览")
    btn.clicked.connect(on_browse)
    btn_row.addWidget(btn)
    scan_btn = QPushButton("重新扫描")
    scan_btn.setObjectName("secondary")
    scan_btn.clicked.connect(on_scan)
    btn_row.addWidget(scan_btn)
    dir_l.addLayout(btn_row)
    file_info = QLabel("尚未打开实验")
    file_info.setObjectName("secondary")
    file_info.setWordWrap(True)
    dir_l.addWidget(file_info)
    ll.addWidget(gb_dir)

    gb_range = QGroupBox("时间范围")
    fl_r = QFormLayout(gb_range)
    fl_r.setContentsMargins(8, 12, 8, 8)
    fl_r.setSpacing(6)
    cmb_start = QComboBox()
    cmb_start.setMinimumWidth(140)
    cmb_end = QComboBox()
    cmb_end.setMinimumWidth(140)
    sp_stride = QSpinBox()
    sp_stride.setRange(1, 999)
    sp_stride.setValue(1)
    sp_stride.setToolTip("每 N 个文件取 1 帧（1=全部）")
    fl_r.addRow("起始", cmb_start)
    fl_r.addRow("结束", cmb_end)
    fl_r.addRow("间隔 N", sp_stride)
    lbl_ini_hint = QLabel("默认起点：最后一个前导 _ini（沉积结束）")
    lbl_ini_hint.setObjectName("secondary")
    lbl_ini_hint.setWordWrap(True)
    fl_r.addRow(lbl_ini_hint)
    btn_apply_range = QPushButton("应用范围")
    btn_apply_range.clicked.connect(on_apply_range)
    fl_r.addRow(btn_apply_range)
    ll.addWidget(gb_range)

    legend = GroupLegendPanel()
    legend.visibility_changed.connect(on_group_visibility)
    legend.isolate_group.connect(on_isolate_group)
    legend.show_all_groups.connect(on_show_all_groups)
    legend.show_selected_group.connect(on_show_selected_group)
    legend.color_changed.connect(on_group_color)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(legend)
    scroll.setMinimumHeight(120)
    scroll.setMaximumHeight(220)
    scroll.setFrameShape(QFrame.NoFrame)
    ll.addWidget(scroll)

    gb_reg = QGroupBox("实验区域")
    fl = QFormLayout(gb_reg)
    fl.setContentsMargins(8, 12, 8, 8)
    fl.setSpacing(6)
    sp_xmin, sp_xmax = _spin_region(), _spin_region()
    sp_ymin, sp_ymax = _spin_region(), _spin_region()
    fl.addRow("X 最小", sp_xmin)
    fl.addRow("X 最大", sp_xmax)
    fl.addRow("Y 最小", sp_ymin)
    fl.addRow("Y 最大", sp_ymax)
    lbl_region_src = QLabel("来源：—")
    lbl_region_src.setObjectName("secondary")
    fl.addRow(lbl_region_src)
    reg_btns = QHBoxLayout()
    btn_apply = QPushButton("应用区域")
    btn_apply.clicked.connect(on_apply_region)
    btn_redetect = QPushButton("重新检测")
    btn_redetect.setObjectName("secondary")
    btn_redetect.clicked.connect(on_redetect)
    reg_btns.addWidget(btn_apply)
    reg_btns.addWidget(btn_redetect)
    fl.addRow(reg_btns)
    ll.addWidget(gb_reg)

    fit_row = QHBoxLayout()
    btn2 = QPushButton("适配区域")
    btn2.setObjectName("secondary")
    btn2.clicked.connect(on_fit_region)
    fit_row.addWidget(btn2)
    btn3 = QPushButton("适配颗粒")
    btn3.setObjectName("secondary")
    btn3.clicked.connect(on_fit_particles)
    fit_row.addWidget(btn3)
    ll.addLayout(fit_row)
    btn_q = QPushButton("数据质量报告")
    btn_q.setObjectName("secondary")
    btn_q.clicked.connect(on_quality)
    ll.addWidget(btn_q)
    ll.addStretch()
    left.setMinimumWidth(260)
    left.setMaximumWidth(340)

    return LeftPanel(
        widget=left,
        wall_cb=wall_cb,
        rb_real=rb_real,
        rb_enh=rb_enh,
        rb_cm_color=rb_cm_color,
        rb_cm_group=rb_cm_group,
        rb_cm_solid=rb_cm_solid,
        dir_input=dir_input,
        file_info=file_info,
        cmb_start=cmb_start,
        cmb_end=cmb_end,
        sp_stride=sp_stride,
        lbl_ini_hint=lbl_ini_hint,
        legend=legend,
        sp_xmin=sp_xmin,
        sp_xmax=sp_xmax,
        sp_ymin=sp_ymin,
        sp_ymax=sp_ymax,
        lbl_region_src=lbl_region_src,
    )


def build_right_panel(
    parent: QWidget,
    *,
    on_track: Callable,
    on_locate: Callable,
    on_clear: Callable,
    on_path_toggle: Callable,
    on_path_range: Callable,
) -> RightPanel:
    right = QWidget(parent)
    rl = QVBoxLayout(right)
    rl.setContentsMargins(8, 8, 8, 8)
    rl.setSpacing(8)

    gb1 = QGroupBox("颗粒追踪")
    g1l = QVBoxLayout(gb1)
    hl = QHBoxLayout()
    hl.addWidget(QLabel("永久 ID:"))
    id_input = QLineEdit()
    id_input.setPlaceholderText("输入永久颗粒 ID…")
    id_input.setToolTip("追踪唯一依据：永久 id，不是文件 index")
    id_input.returnPressed.connect(on_track)
    hl.addWidget(id_input)
    g1l.addLayout(hl)
    btn_track = QPushButton("追踪")
    btn_track.setToolTip("对选中永久 ID 重新提取轨迹（点击选择后会自动追踪）")
    btn_track.clicked.connect(on_track)
    g1l.addWidget(btn_track)
    hint_sel = QLabel("仅可选择会话起始帧中存在的颗粒；选中后自动追踪")
    hint_sel.setObjectName("secondary")
    hint_sel.setWordWrap(True)
    hint_sel.setStyleSheet("color:#86868b;font-size:11px;")
    g1l.addWidget(hint_sel)
    row_sel = QHBoxLayout()
    btn_locate = QPushButton("定位")
    btn_locate.setObjectName("secondary")
    btn_locate.setToolTip("把视图中心移到当前选中颗粒")
    btn_locate.clicked.connect(on_locate)
    btn_clear_sel = QPushButton("清除选择")
    btn_clear_sel.setObjectName("secondary")
    btn_clear_sel.clicked.connect(on_clear)
    row_sel.addWidget(btn_locate)
    row_sel.addWidget(btn_clear_sel)
    g1l.addLayout(row_sel)
    btn_traj_path = QPushButton("显示路径")
    btn_traj_path.setCheckable(True)
    btn_traj_path.setToolTip("在颗粒视图中叠加已提取轨迹")
    btn_traj_path.toggled.connect(on_path_toggle)
    g1l.addWidget(btn_traj_path)
    cb_path_to_current = QCheckBox("路径截止当前帧")
    cb_path_to_current.setChecked(True)
    cb_path_to_current.setToolTip("勾选：只画到当前时间步；取消：画完整选定范围")
    cb_path_to_current.toggled.connect(on_path_range)
    g1l.addWidget(cb_path_to_current)
    rl.addWidget(gb1)

    gb2 = QGroupBox("颗粒信息")
    info = QVBoxLayout(gb2)
    info.setSpacing(4)
    lbls = {}
    for k in ["ID:", "序号:", "Group:", "X:", "Y:", "半径:", "状态:"]:
        h = QHBoxLayout()
        h.addWidget(QLabel(k, styleSheet="color:#666;min-width:50px"))
        lbl = QLabel("—")
        h.addWidget(lbl)
        h.addStretch()
        info.addLayout(h)
        lbls[k] = lbl
    rl.addWidget(gb2)

    gb3 = QGroupBox("位移 / 速度")
    dl = QVBoxLayout(gb3)
    dl.setSpacing(4)
    dlbls = {}
    for k in ["ΔX:", "ΔY:", "总位移:", "路径长:", "Vx:", "Vy:", "|v|:", "Δstep:"]:
        h = QHBoxLayout()
        h.addWidget(QLabel(k, styleSheet="color:#666;min-width:50px"))
        lbl = QLabel("—")
        h.addWidget(lbl)
        h.addStretch()
        dl.addLayout(h)
        dlbls[k] = lbl
    rl.addWidget(gb3)
    rl.addStretch()
    right.setMinimumWidth(220)
    right.setMaximumWidth(320)

    return RightPanel(
        widget=right,
        id_input=id_input,
        btn_track=btn_track,
        btn_locate=btn_locate,
        btn_clear_sel=btn_clear_sel,
        btn_traj_path=btn_traj_path,
        cb_path_to_current=cb_path_to_current,
        lbls=lbls,
        dlbls=dlbls,
    )


def build_playback_bar(
    parent: QWidget,
    *,
    on_first: Callable,
    on_prev: Callable,
    on_play: Callable,
    on_next: Callable,
    on_last: Callable,
    on_slider: Callable,
    on_cancel_traj: Callable,
) -> PlaybackBar:
    host = QWidget(parent)
    pb = QHBoxLayout(host)
    pb.setContentsMargins(0, 0, 0, 0)
    play_buttons = []
    for txt, slot, tip in [
        ("⏮", on_first, "第一帧"),
        ("◀", on_prev, "上一帧"),
        ("▶/⏸", on_play, "播放 / 暂停"),
        ("▶", on_next, "下一帧"),
        ("⏭", on_last, "最后一帧"),
    ]:
        b = QPushButton(txt)
        b.setToolTip(tip)
        b.clicked.connect(slot)
        pb.addWidget(b)
        play_buttons.append(b)
    btn_play = play_buttons[2]
    slider = QSlider(Qt.Horizontal)
    slider.valueChanged.connect(on_slider)
    pb.addWidget(slider)
    step_label = QLabel("0/0")
    pb.addWidget(step_label)
    pb.addWidget(QLabel("播放间隔(ms):"))
    spd = QComboBox()
    spd.addItems(["100", "200", "500", "1000"])
    spd.setCurrentIndex(1)
    spd.setToolTip("自动播放时每帧间隔")
    pb.addWidget(spd)

    prog_host = QWidget(parent)
    prog_row = QHBoxLayout(prog_host)
    prog_row.setContentsMargins(0, 0, 0, 0)
    traj_progress = QProgressBar()
    traj_progress.setVisible(False)
    traj_progress.setRange(0, 100)
    btn_cancel_traj = QPushButton("取消追踪")
    btn_cancel_traj.setObjectName("danger")
    btn_cancel_traj.setVisible(False)
    btn_cancel_traj.clicked.connect(on_cancel_traj)
    prog_row.addWidget(traj_progress, 1)
    prog_row.addWidget(btn_cancel_traj)

    return PlaybackBar(
        widget=host,
        layout=pb,
        play_buttons=play_buttons,
        btn_play=btn_play,
        slider=slider,
        step_label=step_label,
        spd=spd,
        traj_progress=traj_progress,
        btn_cancel_traj=btn_cancel_traj,
        prog_layout=prog_row,
    )
