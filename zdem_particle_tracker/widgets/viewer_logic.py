"""Pure helpers for MainViewer — no Qt / no display.

Covers trajectory table/plot series extraction, color mode mapping,
project-config field resolution, and time-range UI index helpers.
"""
from __future__ import annotations

from typing import Any, Iterable, Sequence

import numpy as np


def color_mode_from_radio(
    *, group_checked: bool, solid_checked: bool, color_checked: bool = False
) -> str:
    """Map color-mode radio state to internal mode string."""
    if group_checked:
        return "group"
    if solid_checked:
        return "solid"
    return "color_number"


def color_mode_from_config(mode: str | None) -> str:
    """Normalize project config color_mode → internal string."""
    m = (mode or "color_number").lower()
    if m in ("group", "by_group"):
        return "group"
    if m in ("solid", "single"):
        return "solid"
    return "color_number"


def display_mode_from_enhanced(enhanced: bool) -> str:
    return "enhanced" if enhanced else "real"


def region_tuple_from_config(
    region: Sequence[float] | None, source: str | None
) -> tuple[float, float, float, float, str] | None:
    """Return (xmin, xmax, ymin, ymax, source) or None."""
    if region is None or len(region) < 4:
        return None
    return (
        float(region[0]),
        float(region[1]),
        float(region[2]),
        float(region[3]),
        str(source or "user"),
    )


def validate_region_bounds(
    xmin: float, xmax: float, ymin: float, ymax: float
) -> str | None:
    """Return error message if region is invalid, else None."""
    if not all(np.isfinite([xmin, xmax, ymin, ymax])):
        return "区域坐标必须为有限数字"
    if xmax <= xmin:
        return "X 最大值必须大于 X 最小值"
    if ymax <= ymin:
        return "Y 最大值必须大于 Y 最小值"
    return None


def present_trajectory_points(traj: Sequence | None) -> list:
    """Filter trajectory points usable for curves (present + finite xy)."""
    if not traj:
        return []
    out = []
    for p in traj:
        status = getattr(p, "status", "")
        if status not in ("normal", "present"):
            continue
        x = getattr(p, "x_km", None)
        if isinstance(x, float) and np.isnan(x):
            continue
        out.append(p)
    return out


def trajectory_status_counts(traj: Sequence | None) -> dict[str, int]:
    """Count status categories for status bar messages."""
    n_ok = n_er = n_fe = 0
    for p in traj or []:
        st = getattr(p, "status", "")
        if st in ("normal", "present"):
            n_ok += 1
        elif st == "eroded":
            n_er += 1
        elif st == "file_error":
            n_fe += 1
    return {"ok": n_ok, "eroded": n_er, "file_error": n_fe, "total": len(traj or [])}


def last_present_point(traj: Sequence | None):
    """Last present trajectory point (scan reverse), or None."""
    for p in reversed(list(traj or [])):
        if getattr(p, "status", "") in ("normal", "present"):
            return p
    return None


def series_from_trajectory(traj: Sequence | None) -> dict[str, list]:
    """Build plot series dict from trajectory present points."""
    pts = present_trajectory_points(traj)
    if not pts:
        return {
            "steps": [],
            "dx": [],
            "dy": [],
            "dt": [],
            "pl": [],
            "v": [],
            "vx": [],
            "vy": [],
        }
    return {
        "steps": [int(p.time_step) for p in pts],
        "dx": [float(p.displacement_x_km) for p in pts],
        "dy": [float(p.displacement_y_km) for p in pts],
        "dt": [float(p.displacement_total_km) for p in pts],
        "pl": [float(p.path_length_km) for p in pts],
        "v": [float(p.velocity_total) for p in pts],
        "vx": [float(p.velocity_x) for p in pts],
        "vy": [float(p.velocity_y) for p in pts],
    }


def displacement_labels_from_point(p) -> dict[str, str]:
    """Label texts for right panel displacement group."""
    if p is None:
        keys = ["ΔX:", "ΔY:", "总位移:", "路径长:", "Vx:", "Vy:", "|v|:", "Δstep:"]
        return {k: "—" for k in keys}
    return {
        "ΔX:": f"{p.displacement_x_km:.2f}",
        "ΔY:": f"{p.displacement_y_km:.2f}",
        "总位移:": f"{p.displacement_total_km:.2f}",
        "路径长:": f"{p.path_length_km:.2f}",
        "Vx:": f"{p.velocity_x:.6g} /step",
        "Vy:": f"{p.velocity_y:.6g} /step",
        "|v|:": f"{p.velocity_total:.6g} /step",
        "Δstep:": f"{p.delta_step:.0f}",
    }


def format_traj_cell(v: Any, nd: int | None = 2) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if nd is None:
        return f"{v:.6g}"
    return f"{v:.{nd}f}"


def table_rows_from_trajectory(traj: Sequence | None) -> list[list[str]]:
    """Full table body as string cells (no Qt)."""
    if not traj:
        return []
    rows: list[list[str]] = []
    for p in traj:
        rows.append(
            [
                str(getattr(p, "time_step", "")),
                format_traj_cell(getattr(p, "x_km", None), 1),
                format_traj_cell(getattr(p, "y_km", None), 1),
                format_traj_cell(getattr(p, "displacement_x_km", None), 2),
                format_traj_cell(getattr(p, "displacement_y_km", None), 2),
                format_traj_cell(getattr(p, "displacement_total_km", None), 2),
                format_traj_cell(getattr(p, "velocity_x", None), None),
                format_traj_cell(getattr(p, "velocity_y", None), None),
                format_traj_cell(getattr(p, "velocity_total", None), None),
                (
                    f"{getattr(p, 'delta_step', 0):.0f}"
                    if getattr(p, "delta_step", None)
                    else "0"
                ),
                format_traj_cell(getattr(p, "path_length_km", None), 2),
                str(getattr(p, "status", "")),
            ]
        )
    return rows


TABLE_HEADERS = [
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


def traj_done_status_message(counts: dict[str, int]) -> str:
    msg = f"轨迹提取完成: {counts['total']} 帧（有效 {counts['ok']}"
    if counts.get("eroded"):
        msg += f"，剥蚀 {counts['eroded']}"
    if counts.get("file_error"):
        msg += f"，文件错误 {counts['file_error']}"
    msg += "）"
    return msg


def parse_permanent_id_text(text: str) -> tuple[int | None, str | None]:
    """Parse ID input. Returns (pid, error_message)."""
    s = (text or "").strip()
    if not s:
        return None, "请输入永久颗粒 ID"
    try:
        return int(s), None
    except ValueError:
        return None, "永久颗粒 ID 必须是整数（不是文件 index）"


def combo_index_for_step(steps: Sequence[int], step: int | None) -> int:
    """Find combo index for time step; 0 if missing."""
    if step is None or not steps:
        return 0
    try:
        return list(steps).index(int(step))
    except ValueError:
        return 0


def particle_info_labels(
    *,
    pid: int | None,
    file_index: Any = None,
    group: Any = None,
    x: Any = None,
    y: Any = None,
    rad: Any = None,
    status: str = "—",
) -> dict[str, str]:
    """Right-panel basic info labels."""
    if pid is None:
        return {
            "ID:": "—",
            "序号:": "—",
            "Group:": "—",
            "X:": "—",
            "Y:": "—",
            "半径:": "—",
            "状态:": "—",
        }
    g = group
    if g == "***":
        g_disp = "未指定（***）"
    else:
        g_disp = str(g) if g is not None else "—"
    return {
        "ID:": str(pid),
        "序号:": "—" if file_index is None else str(file_index),
        "Group:": g_disp,
        "X:": "—" if x is None else f"{float(x):.2f}",
        "Y:": "—" if y is None else f"{float(y):.2f}",
        "半径:": "—" if rad is None else f"{float(rad):.2f}",
        "状态:": status or "—",
    }


def should_auto_show_path(n_ok: int, path_button_checked: bool) -> bool:
    """Whether to draw path after traj done."""
    return bool(n_ok) or bool(path_button_checked)
