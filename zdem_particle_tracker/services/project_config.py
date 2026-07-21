"""Project configuration (.zdemtrack.json)."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional, Tuple


@dataclass
class ProjectConfig:
    """Serializable project state (no particle arrays)."""

    experiment_dir: str = ""
    start_step: Optional[int] = None
    end_step: Optional[int] = None
    file_stride: int = 1
    region: Optional[Tuple[float, float, float, float]] = None  # xmin,xmax,ymin,ymax
    region_source: str = "unknown"
    region_user_locked: bool = False
    group_colors: Dict[str, int] = field(default_factory=dict)
    display_mode: str = "real"  # real | enhanced
    show_walls: bool = True
    color_mode: str = "color_number"
    selected_particle_id: Optional[int] = None
    last_export_dir: str = ""
    version: int = 1

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.region is not None:
            d["region"] = list(self.region)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectConfig":
        d = dict(data or {})
        reg = d.get("region")
        if isinstance(reg, (list, tuple)) and len(reg) >= 4:
            d["region"] = (float(reg[0]), float(reg[1]), float(reg[2]), float(reg[3]))
        else:
            d["region"] = None
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in d.items() if k in known}
        return cls(**filtered)


def save_project_config(path: str, cfg: ProjectConfig) -> None:
    path = os.path.abspath(path)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg.to_dict(), f, indent=2, ensure_ascii=False)


def load_project_config(path: str) -> ProjectConfig:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("配置文件格式无效")
    return ProjectConfig.from_dict(data)
