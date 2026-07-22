"""Deep unit tests for erosion, region, kinematics, LRU, quality, scan.

All tests are self-contained (no sample file dependency) unless explicitly
marked with @skipUnless.
"""
from __future__ import annotations

import math
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

from zdem_particle_tracker.models import ParticleData
from zdem_particle_tracker.parsers import (
    ParseMode,
    find_dat_files,
    find_particle_in_file,
    parse_dat_file,
)
from zdem_particle_tracker.services.region_detector import RegionDetector
from zdem_particle_tracker.services.trajectory_service import (
    _compute_kinematics,
    _hit_to_present_fields,
    TrajectoryService,
    FileInfo,
)
from zdem_particle_tracker.services.quality_report import (
    check_file_list,
    check_frame,
    QualityReport,
)
from zdem_particle_tracker.utils.frame_cache import LRUCache
from zdem_particle_tracker.utils.color_mapping import (
    ColorMapping,
    color_numbers_to_rgba,
    group_to_color,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_dat(path: str, lines: list[str]) -> str:
    """Write lines to a file and return the path."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines), encoding="utf-8")
    return path


def _minimal_frame(
    ids: list[int],
    xs: list[float],
    ys: list[float],
    rads: list[float] | None = None,
    groups: list[str] | None = None,
    step: int = 100,
) -> ParticleData:
    d = ParticleData()
    d.current_step = step
    d.ids = np.array(ids, dtype=np.int64)
    d.xs = np.array(xs, dtype=np.float64)
    d.ys = np.array(ys, dtype=np.float64)
    d.rads = np.array(rads or [10.0] * len(ids), dtype=np.float64)
    d.colors = np.zeros(len(ids), dtype=np.int32)
    d.indices = np.arange(1, len(ids) + 1, dtype=np.int64)
    d.groups = np.array(groups or ["base"] * len(ids), dtype=object)
    return d


# ── Erosion & Trajectory ─────────────────────────────────────────────────────


class TestErosionDetection(unittest.TestCase):
    """Validate erosion vs file_error distinction using real parser + worker."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self._dir = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def _write_frame(self, step: int, keep_1001: bool = True):
        name = f"all_{step:06d}.dat"
        if keep_1001:
            lines = [
                f"current_step: {step}",
                "ball_num: 2",
                "left: 0   right: 800",
                "bottom: 0  height: 500",
                "",
                "Ball Data",
                "  index        id            x            y         rad      color",
                "  1         1001          10          20          60         1",
                "  2         1002          30          40          80         2",
            ]
        else:
            lines = [
                f"current_step: {step}",
                "ball_num: 1",
                "left: 0   right: 800",
                "bottom: 0  height: 500",
                "",
                "Ball Data",
                "  index        id            x            y         rad      color",
                "  1         1002          30          40          80         2",
            ]
        return _make_dat(str(self._dir / name), lines)

    def _run_worker(self, particle_id: int, finfos):
        """Run TrajectoryService worker to completion with a QCoreApplication."""
        from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
        from zdem_particle_tracker.services.trajectory_service import _TrajectoryWorker

        app = QCoreApplication.instance()
        if app is None:
            app = QCoreApplication([])

        worker = _TrajectoryWorker(particle_id, finfos, max_workers=2)
        traj_box = []
        err_box = []

        def _done(t):
            traj_box.append(t)
            loop.quit()

        def _err(m):
            err_box.append(m)
            loop.quit()

        worker.finished.connect(_done)
        worker.error.connect(_err)
        loop = QEventLoop()
        worker.start()
        # Safety timeout
        QTimer.singleShot(15000, loop.quit)
        loop.exec()
        worker.wait(3000)
        if err_box:
            self.fail(f"worker error: {err_box[0]}")
        self.assertEqual(len(traj_box), 1, "worker did not emit finished")
        return traj_box[0]

    def test_particle_in_first_two_then_eroded(self):
        """Particle present in frames 0/1, missing in frame 2 => status eroded."""
        self._write_frame(100, keep_1001=True)
        self._write_frame(200, keep_1001=True)
        self._write_frame(300, keep_1001=False)

        files = find_dat_files(str(self._dir))
        self.assertEqual(len(files), 3)

        # Also verify find_particle_in_file distinguishes found vs not-found
        hit0 = find_particle_in_file(files[0][1], 1001)
        hit2 = find_particle_in_file(files[2][1], 1001)
        self.assertTrue(hit0.file_ok and hit0.found)
        self.assertTrue(hit2.file_ok and not hit2.found)

        finfos = [
            FileInfo(file_order=i, filename_step=str(s), current_step=s, dat_path=p, file_size=0)
            for i, (s, p) in enumerate(files)
        ]
        traj = self._run_worker(1001, finfos)
        self.assertGreaterEqual(len(traj), 3)
        statuses = [p.status for p in traj]
        self.assertEqual(statuses[0], "normal")
        self.assertEqual(statuses[1], "normal")
        self.assertEqual(statuses[2], "eroded")
        self.assertAlmostEqual(traj[0].x_km, 10.0)
        self.assertTrue(math.isnan(traj[2].x_km))

    def test_file_error_is_not_erosion(self):
        """A missing/corrupt file should be file_error, not eroded."""
        finfos = [
            FileInfo(0, "all_01.dat", 100, "/nonexistent/all_00000100.dat", 0),
            FileInfo(1, "all_02.dat", 200, "/nonexistent/all_00000200.dat", 0),
        ]
        # Direct unit check of find_particle_in_file
        hit = find_particle_in_file(finfos[0].dat_path, 42)
        self.assertFalse(hit.file_ok)
        self.assertFalse(hit.found)

        traj = self._run_worker(42, finfos)
        self.assertEqual(len(traj), 2)
        for p in traj:
            self.assertEqual(p.status, "file_error")


# ── Kinematics ────────────────────────────────────────────────────────────────


class TestKinematicsDeep(unittest.TestCase):
    def test_path_length_accumulates(self):
        """Path length should monotonically accumulate regardless of direction."""
        fx = fy = px = py = ps = None
        pl = 0.0
        # step 0: origin
        fx, fy, px, py, ps, pl, k0 = _compute_kinematics(0, 0, 0, fx, fy, px, py, ps, pl)
        self.assertAlmostEqual(pl, 0.0)
        self.assertAlmostEqual(k0["displacement_x_km"], 0.0)
        # step 1000: move right 10
        fx, fy, px, py, ps, pl, k1 = _compute_kinematics(10, 0, 1000, fx, fy, px, py, ps, pl)
        self.assertAlmostEqual(pl, 10.0)
        self.assertAlmostEqual(k1["increment_total_km"], 10.0)
        self.assertAlmostEqual(k1["velocity_x"], 0.01)
        # step 2000: move back left 10
        fx, fy, px, py, ps, pl, k2 = _compute_kinematics(0, 0, 2000, fx, fy, px, py, ps, pl)
        self.assertAlmostEqual(pl, 20.0)
        self.assertAlmostEqual(k2["displacement_total_km"], 0.0)
        self.assertAlmostEqual(k2["increment_total_km"], 10.0)
        # velocity negative on return
        self.assertAlmostEqual(k2["velocity_x"], -0.01)

    def test_diagonal(self):
        fx = fy = px = py = ps = None
        pl = 0.0
        # First sample is the zero point
        fx, fy, px, py, ps, pl, k0 = _compute_kinematics(0, 0, 0, fx, fy, px, py, ps, pl)
        self.assertAlmostEqual(k0["displacement_total_km"], 0.0)
        # Move to (3,4)
        fx, fy, px, py, ps, pl, k = _compute_kinematics(3, 4, 500, fx, fy, px, py, ps, pl)
        self.assertAlmostEqual(k["displacement_total_km"], 5.0)
        self.assertAlmostEqual(k["velocity_total"], 5.0 / 500)

    def test_same_position_zero_velocity(self):
        fx = fy = px = py = ps = None
        pl = 0.0
        fx, fy, px, py, ps, pl, _k = _compute_kinematics(10, 20, 0, fx, fy, px, py, ps, pl)
        fx, fy, px, py, ps, pl, k = _compute_kinematics(10, 20, 1000, fx, fy, px, py, ps, pl)
        self.assertAlmostEqual(k["increment_total_km"], 0.0)
        self.assertAlmostEqual(k["velocity_total"], 0.0)

    def test_velocity_formula(self):
        """Vx = Δx / Δstep, Vy = Δy / Δstep."""
        fx = fy = px = py = ps = None
        pl = 0.0
        fx, fy, px, py, ps, pl, _k = _compute_kinematics(0, 0, 100, fx, fy, px, py, ps, pl)
        fx, fy, px, py, ps, pl, k = _compute_kinematics(50, 100, 200, fx, fy, px, py, ps, pl)
        self.assertAlmostEqual(k["velocity_x"], 0.5)
        self.assertAlmostEqual(k["velocity_y"], 1.0)
        self.assertAlmostEqual(k["velocity_total"], math.hypot(0.5, 1.0))

    def test_delta_step_zero_protection(self):
        """Same step as previous should not produce infinite velocity."""
        fx = fy = px = py = ps = None
        pl = 0.0
        fx, fy, px, py, ps, pl, _k = _compute_kinematics(0, 0, 100, fx, fy, px, py, ps, pl)
        fx, fy, px, py, ps, pl, k = _compute_kinematics(50, 0, 100, fx, fy, px, py, ps, pl)
        self.assertAlmostEqual(k["delta_step"], 0.0)
        self.assertAlmostEqual(k["velocity_x"], 0.0)


# ── Region Detector ──────────────────────────────────────────────────────────


class TestRegionDetector(unittest.TestCase):
    def setUp(self):
        self.det = RegionDetector()

    def test_walls_rect(self):
        walls = np.array([
            [0.0, 0.0, 80000.0, 0.0],
            [0.0, 50000.0, 80000.0, 50000.0],
            [0.0, 0.0, 0.0, 50000.0],
            [80000.0, 0.0, 80000.0, 50000.0],
        ], dtype=np.float64)
        reg = self.det.detect_from_walls(walls)
        self.assertEqual(reg.source, "walls")
        self.assertAlmostEqual(reg.x_min, 0.0)
        self.assertAlmostEqual(reg.x_max, 80000.0)
        self.assertAlmostEqual(reg.y_min, 0.0)
        self.assertAlmostEqual(reg.y_max, 50000.0)

    def test_walls_empty_fallback(self):
        reg = self.det.detect_from_walls(
            np.empty((0, 4)),
            metadata={"left": 0, "right": 100, "bottom": 0, "height": 50},
        )
        self.assertIn("metadata", reg.source)
        self.assertAlmostEqual(reg.x_min, 0.0)
        self.assertAlmostEqual(reg.x_max, 100.0)
        self.assertAlmostEqual(reg.y_min, 0.0)
        self.assertAlmostEqual(reg.y_max, 50.0)

    def test_walls_collinear_fallback(self):
        walls = np.array([[0.0, 0.0, 1.0, 0.0]], dtype=np.float64)
        reg = self.det.detect_from_walls(walls, metadata={"left": 0, "right": 200, "bottom": 0, "height": 100})
        self.assertIn("metadata", reg.source)
        self.assertAlmostEqual(reg.x_max, 200.0)

    def test_metadata_direct(self):
        reg = self.det.detect_from_metadata({"left": 12, "right": 99, "bottom": -5, "height": 70})
        self.assertEqual(reg.source, "metadata")
        self.assertAlmostEqual(reg.x_min, 12.0)
        self.assertAlmostEqual(reg.x_max, 99.0)
        self.assertAlmostEqual(reg.y_min, -5.0)
        self.assertAlmostEqual(reg.y_max, 65.0)  # bottom + height

    def test_metadata_absolute_top_when_bottom_zero(self):
        # ZDEM-style: bottom=0, height field is absolute top Y, comparable to X span
        reg = self.det.detect_from_metadata({"left": 0, "right": 50000, "bottom": 0, "height": 50160})
        self.assertEqual(reg.source, "metadata")
        self.assertAlmostEqual(reg.y_min, 0.0)
        self.assertAlmostEqual(reg.y_max, 50160.0)

    def test_no_metadata_fallback_unit(self):
        reg = self.det._fallback_region(None, "no-data")
        self.assertEqual(reg.source, "no-data")
        self.assertAlmostEqual(reg.x_max, 1.0)


# ── LRU Cache ────────────────────────────────────────────────────────────────


class TestLRUCacheDeep(unittest.TestCase):
    def test_eviction_order(self):
        c = LRUCache(3)
        for k in range(5):
            c.put(k, k * 10)
        self.assertNotIn(0, c)
        self.assertNotIn(1, c)
        self.assertIn(2, c)
        self.assertIn(3, c)
        self.assertIn(4, c)
        self.assertEqual(c.get(2), 20)
        # Access 2 moves it to end; next put evicts 3 (oldest)
        c.put(5, 50)
        self.assertNotIn(3, c)
        self.assertIn(2, c)

    def test_update_refreshes(self):
        c = LRUCache(2)
        c.put("a", 1)
        c.put("b", 2)
        c.put("a", 99)  # update — should not evict a
        self.assertIn("a", c)
        self.assertIn("b", c)
        c.put("c", 3)
        self.assertNotIn("a", c) if False else None  # b is now oldest
        # Actually after put("a",99), order is b→a, so c evicts b
        self.assertIn("a", c)
        self.assertNotIn("b", c)

    def test_contains(self):
        c = LRUCache(2)
        c.put("x", 1)
        self.assertIn("x", c)
        self.assertNotIn("y", c)

    def test_get_default(self):
        c = LRUCache(2)
        self.assertIsNone(c.get("missing"))
        self.assertEqual(c.get("missing", 42), 42)

    def test_clear(self):
        c = LRUCache(2)
        c.put("a", 1)
        c.put("b", 2)
        c.clear()
        self.assertEqual(len(c), 0)

    def test_zero_capacity_raises(self):
        with self.assertRaises(ValueError):
            LRUCache(0)


# ── Color Mapping ────────────────────────────────────────────────────────────


class TestColorMappingDeep(unittest.TestCase):
    def test_vector_shape(self):
        colors = np.array([0, 1, 15, 127, 255], dtype=np.int32)
        rgba = color_numbers_to_rgba(colors)
        self.assertEqual(rgba.shape, (5, 4))
        self.assertTrue(np.allclose(rgba[:, 3], 1.0))

    def test_zero_inputs(self):
        rgba = color_numbers_to_rgba(np.array([], dtype=np.int32))
        self.assertEqual(rgba.shape, (0, 4))

    def test_group_colors_stable(self):
        """Same group name should always get same color."""
        gm = ColorMapping()
        c1 = gm.get_color("salt")
        c2 = gm.get_color("salt")
        self.assertEqual(c1, c2)

    def test_different_groups_different(self):
        gm = ColorMapping()
        c1 = gm.get_color("base")
        c2 = gm.get_color("salt")
        c3 = gm.get_color("sedup")
        # at least two should differ
        self.assertFalse(c1 == c2 == c3)

    def test_unknown_group_not_white(self):
        gm = ColorMapping()
        c = gm.get_color(str(99999))
        self.assertNotEqual(c, (1.0, 1.0, 1.0))

    def test_roundtrip_dict(self):
        gm = ColorMapping()
        gm.get_color("test_grp")
        d = gm.to_dict()
        gm2 = ColorMapping()
        gm2.from_dict(d)
        self.assertEqual(gm2.get_color("test_grp"), gm.get_color("test_grp"))

    def test_color_number_known_groups(self):
        """Check the provided sample groups get deterministic colors."""
        gm = ColorMapping()
        for g in ("base", "salt", "sedup", "f"):
            c = gm.get_color(g)
            self.assertIsInstance(c, int)
            self.assertGreaterEqual(c, 0)
            self.assertLessEqual(c, 0xFFFFFF)


# ── Quality Report ───────────────────────────────────────────────────────────


class TestQualityReportDeep(unittest.TestCase):
    def test_empty_frame_errors(self):
        d = _minimal_frame([], [], [])
        rep = check_frame(d)
        codes = [i.code for i in rep.issues]
        self.assertIn("empty_frame", codes)

    def test_step_mismatch(self):
        d = _minimal_frame([1], [0.0], [0.0], step=100)
        rep = check_frame(d, filename_step=99)
        codes = [i.code for i in rep.issues]
        self.assertIn("step_mismatch", codes)

    def test_dup_id_error(self):
        d = ParticleData()
        d.ids = np.array([5, 5], dtype=np.int64)
        d.xs = np.array([0.0, 10.0])
        d.ys = np.array([0.0, 10.0])
        d.rads = np.array([1.0, 1.0])
        d.colors = np.zeros(2, dtype=np.int32)
        d.indices = np.array([1, 2], dtype=np.int64)
        d.groups = np.array(["base", "salt"], dtype=object)
        rep = check_frame(d)
        codes = [i.code for i in rep.issues]
        self.assertIn("dup_id", codes)

    def test_nan_coord_error(self):
        d = _minimal_frame([1], [float("nan")], [0.0])
        rep = check_frame(d)
        codes = [i.code for i in rep.issues]
        self.assertIn("nan_coord", codes)

    def test_bad_radius(self):
        d = _minimal_frame([1], [0.0], [0.0], rads=[-1.0])
        rep = check_frame(d)
        codes = [i.code for i in rep.issues]
        self.assertIn("bad_radius", codes)

    def test_out_of_region(self):
        d = _minimal_frame([1], [999999.0], [0.0])
        rep = check_frame(d, wall_region=(0, 1000, 0, 1000))
        codes = [i.code for i in rep.issues]
        self.assertIn("out_of_region", codes)

    def test_groups_report(self):
        d = _minimal_frame([1, 2], [0, 10], [0, 10], groups=["base", "***"])
        rep = check_frame(d)
        msgs = "\n".join(rep.summary_lines())
        self.assertIn("***", msgs)

    def test_file_list_empty(self):
        rep = check_file_list([])
        self.assertEqual(rep.errors[0].code, "no_files")

    def test_file_list_dup_step(self):
        rep = check_file_list([(100, "a"), (100, "b")])
        codes = [i.code for i in rep.issues]
        self.assertIn("dup_step", codes)

    def test_file_list_non_increasing(self):
        rep = check_file_list([(300, "a"), (200, "b"), (100, "c")])
        codes = [i.code for i in rep.issues]
        self.assertIn("not_increasing", codes)

    def test_region_conflict(self):
        d = _minimal_frame([1], [50], [25], step=100)
        rep = check_frame(
            d,
            wall_region=(0, 80000, 0, 50000),
            meta_region=(0, 80160, 0, 50160),
        )
        codes = [i.code for i in rep.issues]
        self.assertIn("region_conflict", codes)


# ── Find DAT files ───────────────────────────────────────────────────────────


class TestFindDatFilesDeep(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self._dir = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def _touch(self, name: str):
        (self._dir / name).write_text("", encoding="utf-8")

    def test_only_all_prefix(self):
        self._touch("all_0000010000.dat")
        self._touch("all_0000020000.dat")
        self._touch("vtk_inters_10000.vtk")
        self._touch("0000020000.sav")
        self._touch("readme.txt")
        # Non-recursive: files under a subdir must be ignored
        sub = self._dir / "subdir"
        sub.mkdir(exist_ok=True)
        (sub / "all_0000000003.dat").write_text("", encoding="utf-8")

        files = find_dat_files(str(self._dir))
        self.assertEqual(len(files), 2)
        basenames = [os.path.basename(p) for _, p in files]
        self.assertTrue(all(n.startswith("all_") for n in basenames))
        self.assertNotIn("all_0000000003.dat", basenames)

    def test_sorted_order(self):
        self._touch("all_100.dat")
        self._touch("all_20.dat")
        self._touch("all_3.dat")
        files = find_dat_files(str(self._dir))
        steps = [s for s, _ in files]
        self.assertEqual(steps, [3, 20, 100])

    def test_empty_dir(self):
        files = find_dat_files(str(self._dir))
        self.assertEqual(len(files), 0)

    def test_non_existent_dir(self):
        files = find_dat_files("/nonexistent/path/xyz")
        self.assertEqual(len(files), 0)


# ── ParticleData ─────────────────────────────────────────────────────────────


class TestParticleData(unittest.TestCase):
    def test_count_property(self):
        d = _minimal_frame([1, 2, 3], [0, 1, 2], [0, 1, 2])
        self.assertEqual(d.count, 3)

    def test_empty_count(self):
        d = ParticleData()
        self.assertEqual(d.count, 0)

    def test_wall_data_default_shape(self):
        d = ParticleData()
        self.assertEqual(d.wall_data.shape, (0, 4))


# ── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    unittest.main()
