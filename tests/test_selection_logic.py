"""Unit tests for selection_logic pure helpers."""
from __future__ import annotations

import unittest
from types import SimpleNamespace

import numpy as np

from zdem_particle_tracker.widgets.selection_logic import (
    filter_trajectory_path_xy,
    first_id_not_in_start,
    id_allowed_at_session_start,
    next_play_index,
    pick_particle_id,
    play_parse_mode_name,
    validate_time_range_indices,
)


class TestGate(unittest.TestCase):
    def test_allowed(self):
        self.assertTrue(id_allowed_at_session_start({1, 2}, 2))

    def test_reject_none(self):
        self.assertFalse(id_allowed_at_session_start(None, 1))


class TestPick(unittest.TestCase):
    def setUp(self):
        self.xs = np.array([0.0, 100.0, 200.0])
        self.ys = np.array([0.0, 0.0, 0.0])
        self.rads = np.array([10.0, 10.0, 10.0])
        self.ids = np.array([10, 20, 30], dtype=np.int64)
        self.start = {10, 20}  # 30 not allowed

    def test_pick_inside_disc(self):
        pid = pick_particle_id(
            self.xs, self.ys, self.rads, self.ids, 2.0, 0.0, start_ids=self.start
        )
        self.assertEqual(pid, 10)

    def test_gate_skips_disallowed(self):
        # click near id 30 which is not in start
        pid = pick_particle_id(
            self.xs, self.ys, self.rads, self.ids, 200.0, 0.0, start_ids=self.start
        )
        self.assertIsNone(pid)

    def test_empty(self):
        pid = pick_particle_id(
            np.array([]),
            np.array([]),
            np.array([]),
            np.array([], dtype=np.int64),
            0,
            0,
            start_ids={1},
        )
        self.assertIsNone(pid)


class TestPathFilter(unittest.TestCase):
    def test_clip_to_current(self):
        pts = [
            SimpleNamespace(status="present", x_km=0.0, y_km=0.0, time_step=1),
            SimpleNamespace(status="present", x_km=1.0, y_km=0.0, time_step=2),
            SimpleNamespace(status="present", x_km=2.0, y_km=0.0, time_step=3),
            SimpleNamespace(status="eroded", x_km=float("nan"), y_km=float("nan"), time_step=4),
        ]
        xs, ys = filter_trajectory_path_xy(pts, path_to_current=True, current_step=2)
        self.assertEqual(xs, [0.0, 1.0])
        self.assertEqual(ys, [0.0, 0.0])

    def test_full_range(self):
        pts = [
            SimpleNamespace(status="present", x_km=0.0, y_km=0.0, time_step=1),
            SimpleNamespace(status="present", x_km=1.0, y_km=1.0, time_step=2),
        ]
        xs, ys = filter_trajectory_path_xy(pts, path_to_current=False, current_step=1)
        self.assertEqual(len(xs), 2)


class TestPlayHelpers(unittest.TestCase):
    def test_mode_group(self):
        self.assertEqual(play_parse_mode_name("group"), "FULL_PARTICLE_PROPERTIES")
        self.assertEqual(play_parse_mode_name("color_number"), "BASIC_FRAME")

    def test_next_idx(self):
        self.assertEqual(next_play_index(0, 3), 1)
        self.assertIsNone(next_play_index(2, 3))
        self.assertIsNone(next_play_index(0, 0))

    def test_range_validate(self):
        self.assertIsNone(validate_time_range_indices(0, 2, 5))
        self.assertIsNotNone(validate_time_range_indices(3, 1, 5))
        self.assertIsNotNone(validate_time_range_indices(0, 0, 0))

    def test_first_not_in_start(self):
        self.assertEqual(first_id_not_in_start([1, 9, 2], {1, 2}), 9)
        self.assertIsNone(first_id_not_in_start([1, 2], {1, 2}))


if __name__ == "__main__":
    unittest.main()
