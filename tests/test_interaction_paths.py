"""Interactive-path automation without VisPy MainViewer construct.

Covers: project config round-trip fields, time-range validation, play index,
selection gate + pick, path filter, color/region helpers, trajectory series,
and side-panel factory (Qt widgets only — no OpenGL canvas).
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from zdem_particle_tracker.parsers.dat_scan import (
    default_start_index,
    scan_dat_files,
    select_range,
)
from zdem_particle_tracker.services.project_config import (
    ProjectConfig,
    load_project_config,
    save_project_config,
)
from zdem_particle_tracker.widgets.selection_logic import (
    filter_trajectory_path_xy,
    id_allowed_at_session_start,
    next_play_index,
    pick_particle_id,
    play_parse_mode_name,
    validate_time_range_indices,
)
from zdem_particle_tracker.widgets.viewer_logic import (
    color_mode_from_config,
    color_mode_from_radio,
    parse_permanent_id_text,
    series_from_trajectory,
    traj_done_status_message,
    trajectory_status_counts,
    validate_region_bounds,
)

SAMPLE_CANDIDATES = [
    Path(r"D:/2_Temp/StructLab/Projects/25_造山带尺度盐构造/物理实验复刻/2/data"),
    Path(r"D:/2_Temp/StructLab/Projects/25_造山带尺度盐构造/物理实验复刻/1/data"),
]


def _find_sample() -> Path | None:
    for p in SAMPLE_CANDIDATES:
        if p.is_dir() and any(p.glob("all_*.dat")):
            return p
    return None


class TestInteractionLogic(unittest.TestCase):
    """Business rules that UI buttons eventually call."""

    def test_play_index_lifecycle(self):
        self.assertIsNone(next_play_index(0, 0))
        self.assertEqual(next_play_index(0, 3), 1)
        self.assertEqual(next_play_index(1, 3), 2)
        self.assertIsNone(next_play_index(2, 3))

    def test_time_range_validation(self):
        self.assertIsNotNone(validate_time_range_indices(0, 0, 0))
        self.assertIsNone(validate_time_range_indices(0, 2, 5))
        self.assertIsNotNone(validate_time_range_indices(3, 1, 5))
        self.assertIsNotNone(validate_time_range_indices(-1, 1, 5))

    def test_selection_and_pick(self):
        xs = np.array([0.0, 10.0, 20.0])
        ys = np.array([0.0, 0.0, 0.0])
        rads = np.array([2.0, 2.0, 2.0])
        ids = np.array([1, 2, 99])
        start = {1, 2}  # 99 not selectable
        self.assertTrue(id_allowed_at_session_start(start, 1))
        self.assertFalse(id_allowed_at_session_start(start, 99))
        pid = pick_particle_id(xs, ys, rads, ids, 0.5, 0.0, start_ids=start)
        self.assertEqual(pid, 1)
        pid_bad = pick_particle_id(xs, ys, rads, ids, 20.0, 0.0, start_ids=start)
        self.assertIsNone(pid_bad)  # 99 present at click but not in start

    def test_path_clip_to_current(self):
        pts = [
            SimpleNamespace(status="present", x_km=0.0, y_km=0.0, time_step=10),
            SimpleNamespace(status="present", x_km=1.0, y_km=0.0, time_step=20),
            SimpleNamespace(status="present", x_km=2.0, y_km=0.0, time_step=30),
            SimpleNamespace(status="eroded", x_km=float("nan"), y_km=0.0, time_step=40),
        ]
        xs, ys = filter_trajectory_path_xy(
            pts, path_to_current=True, current_step=20
        )
        self.assertEqual(xs, [0.0, 1.0])
        xs2, _ = filter_trajectory_path_xy(
            pts, path_to_current=False, current_step=20
        )
        self.assertEqual(xs2, [0.0, 1.0, 2.0])

    def test_group_prefetch_mode(self):
        self.assertEqual(play_parse_mode_name("group"), "FULL_PARTICLE_PROPERTIES")
        self.assertEqual(play_parse_mode_name("color_number"), "BASIC_FRAME")

    def test_traj_cancel_empty_counts(self):
        counts = trajectory_status_counts([])
        self.assertEqual(counts["total"], 0)
        self.assertEqual(counts["ok"], 0)
        # empty list is cancel path message precursor
        self.assertIn("0", traj_done_status_message(counts))

    def test_project_config_roundtrip(self):
        cfg = ProjectConfig(
            experiment_dir=r"D:/fake/experiment",
            start_step=6000,
            end_step=36000,
            file_stride=2,
            region=(0.0, 80000.0, 0.0, 50000.0),
            region_source="walls",
            region_user_locked=True,
            group_colors={"salt": 0xFF0000},
            display_mode="enhanced",
            show_walls=True,
            color_mode="group",
            selected_particle_id=42,
        )
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "proj.zdemtrack.json")
            save_project_config(path, cfg)
            loaded = load_project_config(path)
        self.assertEqual(loaded.start_step, 6000)
        self.assertEqual(loaded.file_stride, 2)
        self.assertEqual(loaded.region, (0.0, 80000.0, 0.0, 50000.0))
        self.assertTrue(loaded.region_user_locked)
        self.assertEqual(color_mode_from_config(loaded.color_mode), "group")
        self.assertEqual(loaded.selected_particle_id, 42)

    def test_sample_session_range_defaults(self):
        sample = _find_sample()
        if sample is None:
            self.skipTest("no sample")
        entries = scan_dat_files(str(sample))
        self.assertGreater(len(entries), 2)
        si = default_start_index(entries)
        ei = len(entries) - 1
        self.assertIsNone(validate_time_range_indices(si, ei, len(entries)))
        active = select_range(entries, si, ei, 1)
        self.assertGreaterEqual(len(active), 1)
        # stride 2 shortens
        active2 = select_range(entries, si, ei, 2)
        self.assertLessEqual(len(active2), len(active))

    def test_series_from_mock_track(self):
        traj = [
            SimpleNamespace(
                status="present",
                time_step=1,
                x_km=0.0,
                y_km=0.0,
                displacement_x_km=0.0,
                displacement_y_km=0.0,
                displacement_total_km=0.0,
                path_length_km=0.0,
                velocity_x=0.0,
                velocity_y=0.0,
                velocity_total=0.0,
                delta_step=0.0,
            ),
            SimpleNamespace(
                status="present",
                time_step=2,
                x_km=10.0,
                y_km=0.0,
                displacement_x_km=10.0,
                displacement_y_km=0.0,
                displacement_total_km=10.0,
                path_length_km=10.0,
                velocity_x=10.0,
                velocity_y=0.0,
                velocity_total=10.0,
                delta_step=1.0,
            ),
        ]
        s = series_from_trajectory(traj)
        self.assertEqual(s["steps"], [1, 2])
        self.assertEqual(s["dt"][-1], 10.0)


class TestSidePanelFactory(unittest.TestCase):
    """Qt chrome builders without VisPy MainViewer.

    Skipped on GitHub Actions: QWidget under offscreen Qt on Linux runners
    has aborted the process (exit 134). Pure logic tests above still cover
    the same bindings without creating widgets.
    """

    @classmethod
    def setUpClass(cls):
        if os.environ.get("GITHUB_ACTIONS") or os.environ.get("CI") == "true":
            raise unittest.SkipTest(
                "Qt widget factory is abort-prone on headless Linux CI; run locally"
            )
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_build_left_right_playback(self):
        from PySide6.QtWidgets import QWidget

        from zdem_particle_tracker.ui.side_panels import (
            build_left_panel,
            build_playback_bar,
            build_right_panel,
        )

        parent = QWidget()
        noop = lambda *a, **k: None
        left = build_left_panel(
            parent,
            default_dir="D:/tmp",
            on_browse=noop,
            on_scan=noop,
            on_apply_range=noop,
            on_color_mode=noop,
            on_scale=noop,
            on_render=noop,
            on_apply_region=noop,
            on_redetect=noop,
            on_fit_region=noop,
            on_fit_particles=noop,
            on_quality=noop,
            on_group_visibility=noop,
            on_isolate_group=noop,
            on_show_all_groups=noop,
            on_show_selected_group=noop,
            on_group_color=noop,
        )
        self.assertTrue(left.wall_cb.isChecked())
        self.assertEqual(left.dir_input.text(), "D:/tmp")
        left.cmb_start.addItem("step 100", 100)
        left.cmb_end.addItem("step 200", 200)
        self.assertEqual(left.cmb_start.count(), 1)

        right = build_right_panel(
            parent,
            on_track=noop,
            on_locate=noop,
            on_clear=noop,
            on_path_toggle=noop,
            on_path_range=noop,
        )
        self.assertIn("ID:", right.lbls)
        self.assertIn("ΔX:", right.dlbls)
        right.id_input.setText("123")
        pid, err = parse_permanent_id_text(right.id_input.text())
        self.assertEqual(pid, 123)
        self.assertIsNone(err)

        pb = build_playback_bar(
            parent,
            on_first=noop,
            on_prev=noop,
            on_play=noop,
            on_next=noop,
            on_last=noop,
            on_slider=noop,
            on_cancel_traj=noop,
        )
        self.assertEqual(len(pb.play_buttons), 5)
        self.assertFalse(pb.traj_progress.isVisible())
        pb.slider.setRange(0, 10)
        pb.slider.setValue(3)
        self.assertEqual(pb.slider.value(), 3)

        # color radio → mode helper
        left.rb_cm_group.setChecked(True)
        mode = color_mode_from_radio(
            group_checked=left.rb_cm_group.isChecked(),
            solid_checked=left.rb_cm_solid.isChecked(),
        )
        self.assertEqual(mode, "group")

        # region spins
        left.sp_xmin.setValue(0)
        left.sp_xmax.setValue(100)
        left.sp_ymin.setValue(0)
        left.sp_ymax.setValue(50)
        self.assertIsNone(
            validate_region_bounds(
                left.sp_xmin.value(),
                left.sp_xmax.value(),
                left.sp_ymin.value(),
                left.sp_ymax.value(),
            )
        )
        left.sp_xmax.setValue(-1)
        self.assertIsNotNone(
            validate_region_bounds(
                left.sp_xmin.value(),
                left.sp_xmax.value(),
                left.sp_ymin.value(),
                left.sp_ymax.value(),
            )
        )


if __name__ == "__main__":
    unittest.main()
