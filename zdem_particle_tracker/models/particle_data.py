"""Simple 2D particle frame model."""
import numpy as np
from dataclasses import dataclass, field

@dataclass
class ParticleData:
    """Frame data for all particles at one time step (2D only)."""
    current_step: int = 0
    ball_num: int = 0
    left: float = 0.0
    right: float = 0.0
    bottom: float = 0.0
    height: float = 0.0
    wall_count: int = 0
    wall_data: np.ndarray = field(default_factory=lambda: np.empty((0, 4)))
    ids: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.int64))
    indices: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.int64))
    xs: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float64))
    ys: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float64))
    rads: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float64))
    colors: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.int32))
    groups: np.ndarray = field(default_factory=lambda: np.array([], dtype=object))
    
    @property
    def count(self) -> int:
        return len(self.ids)
