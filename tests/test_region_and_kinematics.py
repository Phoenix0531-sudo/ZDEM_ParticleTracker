"""Business tests: RegionDetector + kinematics definition."""
from __future__ import annotations

import math
import unittest

import numpy as np

from zdem_particle_tracker.services.region_detector import RegionDetector
from zdem_particle_tracker.services.trajectory_service import _compute_kinematics


class TestRegionDetector(unittest.TestCase):
    def test_walls_bbox(self):
        walls = np.array(
            [
                [0.0, 0.0, 10.0, 0.0],
                [10.0, 0.0, 10.0, 5.0],
                [10.0, 5.0, 0.0, 5.0],
                [0.0, 5.0, 0.0, 0.0],
            ]
        )
        reg = RegionDetector().detect_from_walls(walls)
        self.assertEqual(reg.source, "walls")
        self.assertAlmostEqual(reg.x_min, 0.0)
        self.assertAlmostEqual(reg.x_max, 10.0)
        self.assertAlmostEqual(reg.y_min, 0.0)
        self.assertAlmostEqual(reg.y_max, 5.0)

    def test_empty_walls_use_metadata(self):
        meta = {"left": 1.0, "right": 9.0, "bottom": 2.0, "height": 4.0}
        reg = RegionDetector().detect_from_walls(np.zeros((0, 4)), metadata=meta)
        self.assertTrue("metadata" in reg.source or reg.source in ("fallback", "default"))
        self.assertLess(reg.x_min, reg.x_max)
        self.assertAlmostEqual(reg.x_min, 1.0)
        self.assertAlmostEqual(reg.x_max, 9.0)

    def test_collinear_walls_fallback(self):
        walls = np.array([[0.0, 0.0, 5.0, 0.0], [5.0, 0.0, 10.0, 0.0]])
        reg = RegionDetector().detect_from_walls(
            walls, metadata={"left": 0, "right": 10, "bottom": 0, "height": 3}
        )
        # collinear → not a full rectangle from walls alone
        self.assertNotEqual(reg.source, "walls")


class TestKinematics(unittest.TestCase):
    def test_velocity_is_delta_over_step(self):
        # first sample velocity 0
        fx, fy, px, py, ps, pl, f0 = _compute_kinematics(
            0.0, 0.0, 0, None, None, None, None, None, 0.0
        )
        self.assertEqual(f0["velocity_total"], 0.0)
        # move +3 in x over 2 steps → vx = 1.5
        *rest, f1 = _compute_kinematics(3.0, 0.0, 2, fx, fy, px, py, ps, pl)
        self.assertAlmostEqual(f1["velocity_x"], 1.5)
        self.assertAlmostEqual(f1["velocity_total"], 1.5)
        self.assertAlmostEqual(f1["displacement_total_km"], 3.0)
        self.assertAlmostEqual(f1["path_length_km"], 3.0)

    def test_path_length_accumulates(self):
        fx = fy = px = py = ps = None
        pl = 0.0
        fields = {}
        for x, y, step in [(0.0, 0.0, 0), (0.0, 1.0, 1), (0.0, 2.0, 2)]:
            fx, fy, px, py, ps, pl, fields = _compute_kinematics(
                x, y, step, fx, fy, px, py, ps, pl
            )
        self.assertAlmostEqual(pl, 2.0)
        self.assertAlmostEqual(fields["path_length_km"], 2.0)


if __name__ == "__main__":
    unittest.main()
