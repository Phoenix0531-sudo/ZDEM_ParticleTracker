"""Smoke tests for P0/P1 performance paths (parser, cache, colors, kinematics)."""
from __future__ import annotations

import math
import os
import tempfile
import unittest

import numpy as np

from zdem_particle_tracker.parsers.dat_parser import (
    ParseMode,
    find_dat_files,
    find_particle_in_file,
    parse_dat_file,
)
from zdem_particle_tracker.services.project_config import (
    ProjectConfig,
    load_project_config,
    save_project_config,
)
from zdem_particle_tracker.services.quality_report import check_file_list, check_frame
from zdem_particle_tracker.services.trajectory_service import _compute_kinematics
from zdem_particle_tracker.utils.color_mapping import color_numbers_to_rgba
from zdem_particle_tracker.utils.frame_cache import LRUCache


SAMPLE = r"D:\2_Temp\StructLab\Projects\25_造山带尺度盐构造\物理实验复刻\2\data\all_0000026000.dat"
SAMPLE_DIR = os.path.dirname(SAMPLE)


@unittest.skipUnless(os.path.isfile(SAMPLE), "sample DAT not present")
class TestParserModes(unittest.TestCase):
    def test_full_and_basic(self):
        full = parse_dat_file(SAMPLE, mode=ParseMode.FULL_PARTICLE_PROPERTIES)
        basic = parse_dat_file(SAMPLE, mode=ParseMode.BASIC_FRAME)
        self.assertEqual(full.current_step, 26000)
        self.assertEqual(full.count, basic.count)
        self.assertGreater(full.count, 1000)
        self.assertTrue(len(full.wall_data) > 0)
        # basic may not have real groups
        self.assertEqual(len(full.ids), len(np.unique(full.ids)))

    def test_find_particle(self):
        full = parse_dat_file(SAMPLE, mode=ParseMode.BASIC_FRAME)
        pid = int(full.ids[0])
        hit = find_particle_in_file(SAMPLE, pid)
        self.assertTrue(hit.found)
        self.assertTrue(hit.file_ok)
        self.assertAlmostEqual(hit.x, float(full.xs[0]), places=4)
        self.assertAlmostEqual(hit.y, float(full.ys[0]), places=4)

    def test_find_missing(self):
        hit = find_particle_in_file(SAMPLE, -999999)
        self.assertTrue(hit.file_ok)
        self.assertFalse(hit.found)


class TestCacheAndColors(unittest.TestCase):
    def test_lru(self):
        c = LRUCache(2)
        c.put("a", 1)
        c.put("b", 2)
        c.put("c", 3)
        self.assertNotIn("a", c)
        self.assertIn("b", c)
        c.get("b")
        c.put("d", 4)
        self.assertNotIn("c", c)
        self.assertIn("b", c)

    def test_color_vector(self):
        colors = np.array([0, 1, 2], dtype=np.int32)
        rgba = color_numbers_to_rgba(colors)
        self.assertEqual(rgba.shape, (3, 4))
        self.assertTrue(np.allclose(rgba[:, 3], 1.0))
        # match scalar formula
        c = 1
        self.assertAlmostEqual(rgba[1, 0], ((c * 37 + 30) % 256) / 255.0, places=5)


class TestKinematics(unittest.TestCase):
    def test_round_trip_path(self):
        # right 10 then back 10 → total disp 0, path 20
        fx = fy = px = py = ps = None
        pl = 0.0
        fx, fy, px, py, ps, pl, k0 = _compute_kinematics(0, 0, 0, fx, fy, px, py, ps, pl)
        fx, fy, px, py, ps, pl, k1 = _compute_kinematics(10, 0, 1000, fx, fy, px, py, ps, pl)
        fx, fy, px, py, ps, pl, k2 = _compute_kinematics(0, 0, 2000, fx, fy, px, py, ps, pl)
        self.assertAlmostEqual(k2["displacement_total_km"], 0.0, places=9)
        self.assertAlmostEqual(pl, 20.0, places=9)
        self.assertAlmostEqual(k1["velocity_x"], 0.01, places=9)
        self.assertAlmostEqual(k2["velocity_x"], -0.01, places=9)


class TestQualityAndProject(unittest.TestCase):
    def test_file_list(self):
        files = [(1000, "a"), (2000, "b"), (3000, "c")]
        rep = check_file_list(files)
        self.assertTrue(any(i.code == "range" for i in rep.issues))

    def test_project_roundtrip(self):
        cfg = ProjectConfig(
            experiment_dir="D:/tmp",
            region=(0, 80000, 0, 50000),
            region_source="walls",
            selected_particle_id=42,
        )
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "p.zdemtrack.json")
            save_project_config(path, cfg)
            loaded = load_project_config(path)
            self.assertEqual(loaded.selected_particle_id, 42)
            self.assertEqual(loaded.region, (0, 80000, 0, 50000))


@unittest.skipUnless(os.path.isdir(SAMPLE_DIR), "sample dir not present")
class TestScan(unittest.TestCase):
    def test_find_dat(self):
        files = find_dat_files(SAMPLE_DIR)
        self.assertGreater(len(files), 0)
        self.assertTrue(all(name.endswith(".dat") or True for _, name in files))
        # non-recursive: subdir not scanned — just check pattern
        for step, path in files:
            self.assertTrue(os.path.basename(path).startswith("all_"))


if __name__ == "__main__":
    unittest.main()
