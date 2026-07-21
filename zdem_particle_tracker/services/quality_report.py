"""Data quality checks for a loaded experiment."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

import numpy as np

from ..models.particle_data import ParticleData


@dataclass
class QualityIssue:
    level: str  # info | warning | error | fatal
    code: str
    message: str


@dataclass
class QualityReport:
    issues: List[QualityIssue] = field(default_factory=list)

    def add(self, level: str, code: str, message: str) -> None:
        self.issues.append(QualityIssue(level=level, code=code, message=message))

    @property
    def warnings(self) -> List[QualityIssue]:
        return [i for i in self.issues if i.level == "warning"]

    @property
    def errors(self) -> List[QualityIssue]:
        return [i for i in self.issues if i.level in ("error", "fatal")]

    def summary_lines(self) -> List[str]:
        order = {"fatal": 0, "error": 1, "warning": 2, "info": 3}
        items = sorted(self.issues, key=lambda x: order.get(x.level, 9))
        level_zh = {
            "info": "信息",
            "warning": "警告",
            "error": "错误",
            "fatal": "致命",
        }
        return [f"[{level_zh.get(i.level, i.level)}] {i.message}" for i in items]


def check_frame(
    data: ParticleData,
    filename_step: Optional[int] = None,
    wall_region: Optional[Tuple[float, float, float, float]] = None,
    meta_region: Optional[Tuple[float, float, float, float]] = None,
) -> QualityReport:
    """Validate a single parsed frame."""
    rep = QualityReport()
    if data is None:
        rep.add("fatal", "no_data", "无帧数据")
        return rep

    if filename_step is not None and int(data.current_step) != int(filename_step):
        rep.add(
            "warning",
            "step_mismatch",
            f"文件名时间步 {filename_step} 与 current_step {data.current_step} 不一致",
        )

    if data.ball_num > 0 and data.count != data.ball_num:
        rep.add(
            "warning",
            "count_mismatch",
            f"ball num={data.ball_num}，实际读取 {data.count}",
        )

    if data.count == 0:
        rep.add("error", "empty_frame", "该帧没有颗粒")
        return rep

    if len(data.ids) != len(np.unique(data.ids)):
        rep.add("error", "dup_id", "永久 ID 存在重复")

    if not np.all(np.isfinite(data.xs)) or not np.all(np.isfinite(data.ys)):
        rep.add("error", "nan_coord", "坐标包含 NaN 或 Inf")

    if np.any(data.rads <= 0):
        rep.add("error", "bad_radius", "存在半径 ≤ 0 的颗粒")

    # Groups
    if len(data.groups):
        uniq = sorted({str(g) for g in data.groups})
        rep.add("info", "groups", f"Group 种类: {', '.join(uniq)}")
        if "***" in uniq:
            rep.add("info", "group_star", "存在未指定 Group（***）")

    # Region conflict
    if wall_region and meta_region:
        wx0, wx1, wy0, wy1 = wall_region
        mx0, mx1, my0, my1 = meta_region
        if abs(wx0 - mx0) > 1 or abs(wx1 - mx1) > 1 or abs(wy0 - my0) > 1 or abs(wy1 - my1) > 1:
            rep.add(
                "warning",
                "region_conflict",
                f"墙体区域 [{wx0:.0f},{wx1:.0f}]×[{wy0:.0f},{wy1:.0f}] "
                f"与参数区域 [{mx0:.0f},{mx1:.0f}]×[{my0:.0f},{my1:.0f}] 不一致，默认优先墙体",
            )

    # Particles outside region
    region = wall_region or meta_region
    if region is not None:
        x0, x1, y0, y1 = region
        out = (
            (data.xs < x0) | (data.xs > x1) | (data.ys < y0) | (data.ys > y1)
        )
        n_out = int(np.count_nonzero(out))
        if n_out > 0:
            rep.add(
                "warning",
                "out_of_region",
                f"{n_out} 个颗粒中心落在实验区域外",
            )

    return rep


def check_file_list(files: Sequence[Tuple[int, str]]) -> QualityReport:
    """Checks on the scanned file index (filename steps only)."""
    rep = QualityReport()
    if not files:
        rep.add("fatal", "no_files", "未找到 all_*.dat 文件")
        return rep
    steps = [s for s, _ in files]
    if len(steps) != len(set(steps)):
        rep.add("error", "dup_step", "文件名时间步存在重复")
    if any(steps[i] >= steps[i + 1] for i in range(len(steps) - 1)):
        rep.add("error", "not_increasing", "文件名时间步未严格递增")
    rep.add(
        "info",
        "range",
        f"共 {len(files)} 个文件，时间步 {steps[0]} → {steps[-1]}",
    )
    return rep
