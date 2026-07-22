"""Unit tests for viewer_logic pure helpers (no display)."""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from zdem_particle_tracker.widgets.viewer_logic import (
    TABLE_HEADERS,
    color_mode_from_config,
    color_mode_from_radio,
    displacement_labels_from_point,
    last_present_point,
    parse_permanent_id_text,
    particle_info_labels,
    series_from_trajectory,
    table_rows_from_trajectory,
    traj_done_status_message,
    trajectory_status_counts,
    validate_region_bounds,
)


def _pt(step, x, y, status="present", **kw):
    base = dict(
        time_step=step,
        x_km=x,
        y_km=y,
        status=status,
        displacement_x_km=kw.get("dx", 0.0),
        displacement_y_km=kw.get("dy", 0.0),
        displacement_total_km=kw.get("dt", 0.0),
        path_length_km=kw.get("pl", 0.0),
        velocity_x=kw.get("vx", 0.0),
        velocity_y=kw.get("vy", 0.0),
        velocity_total=kw.get("v", 0.0),
        delta_step=kw.get("dstep", 0.0),
    )
    return SimpleNamespace(**base)


class TestViewerLogic(unittest.TestCase):
    def test_color_mode_mapping(self):
        self.assertEqual(
            color_mode_from_radio(group_checked=True, solid_checked=False), "group"
        )
        self.assertEqual(
            color_mode_from_radio(group_checked=False, solid_checked=True), "solid"
        )
        self.assertEqual(
            color_mode_from_radio(group_checked=False, solid_checked=False),
            "color_number",
        )
        self.assertEqual(color_mode_from_config("by_group"), "group")
        self.assertEqual(color_mode_from_config("single"), "solid")
        self.assertEqual(color_mode_from_config(None), "color_number")

    def test_region_bounds(self):
        self.assertIsNone(validate_region_bounds(0, 10, 0, 5))
        self.assertIsNotNone(validate_region_bounds(10, 0, 0, 5))
        self.assertIsNotNone(validate_region_bounds(0, 1, 5, 5))
        self.assertIsNotNone(validate_region_bounds(float("nan"), 1, 0, 1))

    def test_parse_id(self):
        pid, err = parse_permanent_id_text("42")
        self.assertEqual(pid, 42)
        self.assertIsNone(err)
        pid, err = parse_permanent_id_text("  ")
        self.assertIsNone(pid)
        self.assertIsNotNone(err)
        pid, err = parse_permanent_id_text("abc")
        self.assertIsNone(pid)
        self.assertIn("整数", err)

    def test_series_and_table(self):
        traj = [
            _pt(100, 0, 0, dx=0, pl=0),
            _pt(200, 10, 0, dx=10, pl=10, dstep=100, v=0.1, vx=0.1),
            _pt(300, float("nan"), 0, status="eroded"),
        ]
        s = series_from_trajectory(traj)
        self.assertEqual(s["steps"], [100, 200])
        self.assertEqual(s["dx"], [0.0, 10.0])
        rows = table_rows_from_trajectory(traj)
        self.assertEqual(len(rows), 3)
        self.assertEqual(len(TABLE_HEADERS), len(rows[0]))
        counts = trajectory_status_counts(traj)
        self.assertEqual(counts["ok"], 2)
        self.assertEqual(counts["eroded"], 1)
        msg = traj_done_status_message(counts)
        self.assertIn("有效 2", msg)
        self.assertIn("剥蚀 1", msg)
        last = last_present_point(traj)
        self.assertEqual(last.time_step, 200)
        labels = displacement_labels_from_point(last)
        self.assertIn("ΔX:", labels)
        empty = displacement_labels_from_point(None)
        self.assertEqual(empty["ΔX:"], "—")

    def test_particle_info_labels(self):
        blank = particle_info_labels(pid=None)
        self.assertEqual(blank["ID:"], "—")
        lab = particle_info_labels(
            pid=7, file_index=3, group="***", x=1.5, y=2.5, rad=60, status="正常"
        )
        self.assertEqual(lab["ID:"], "7")
        self.assertIn("未指定", lab["Group:"])
        lab2 = particle_info_labels(pid=1, group="salt", x=0, y=0, rad=80)
        self.assertEqual(lab2["Group:"], "salt")


if __name__ == "__main__":
    unittest.main()
