"""ZDEM Particle Tracker — services package."""

from __future__ import annotations
from collections import namedtuple
from dataclasses import dataclass
from typing import List, Optional

# ── Data structures ──────────────────────────────────────────────────────────

FileInfo = namedtuple("FileInfo", [
    "file_order",
    "filename_step",
    "current_step",
    "dat_path",
    "file_size",
    "status",
])
FileInfo.__new__.__defaults__ = (None, None, None, None, 0, "pending")


Region = namedtuple("Region", [
    "x_min", "x_max", "y_min", "y_max", "source",
])
Region.__new__.__defaults__ = (0.0, 0.0, 0.0, 0.0, "unknown")


@dataclass
class TrajectoryPoint:
    """A single observation of a tracked particle in one frame."""

    particle_id: int
    file_index: int
    time_step: int
    x_km: float
    y_km: float
    radius_km: float
    group: str = ""
    original_color: int = 0

    displacement_x_km: float = 0.0
    displacement_y_km: float = 0.0
    displacement_total_km: float = 0.0

    increment_x_km: float = 0.0
    increment_y_km: float = 0.0
    increment_total_km: float = 0.0

    velocity_x: float = 0.0
    velocity_y: float = 0.0
    velocity_total: float = 0.0
    delta_step: float = 0.0

    path_length_km: float = 0.0
    status: str = "normal"
    source_file: str = ""


Trajectory = List[TrajectoryPoint]


from .region_detector import RegionDetector
from .trajectory_service import TrajectoryService
from .export_service import ExportService
from .quality_report import QualityReport, check_frame, check_file_list
from .project_config import ProjectConfig, load_project_config, save_project_config

__all__ = [
    "FileInfo",
    "Region",
    "TrajectoryPoint",
    "Trajectory",
    "RegionDetector",
    "TrajectoryService",
    "ExportService",
    "QualityReport",
    "check_frame",
    "check_file_list",
    "ProjectConfig",
    "load_project_config",
    "save_project_config",
]
