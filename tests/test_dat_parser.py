"""Unit tests for ZDEM DAT file parser.

Tests construct temporary files in ZDEM-like format to exercise the parser
without requiring actual simulation output.
"""

import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

from zdem_particle_tracker.parsers.dat_parser import parse_dat_file, find_dat_files


class TestDatParser(unittest.TestCase):
    """Test suite for dat_parser.parse_dat_file and find_dat_files."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    # ------------------------------------------------------------------ #
    #  Helper: write a ZDEM-like DAT file
    # ------------------------------------------------------------------ #

    def _write_dat(self, name: str, lines: list) -> str:
        """Write lines to a file inside the temp directory and return the path."""
        path = self.dir / name
        path.write_text("\n".join(lines), encoding="utf-8")
        return str(path)

    # ------------------------------------------------------------------ #
    #  Tests
    # ------------------------------------------------------------------ #

    def test_parse_metadata(self):
        """Verify step and ball count are read from header metadata."""
        content = [
            "Parameter Data",
            "current_step: 42",
            "ball_num: 10",
            "left: 0.0",
            "right: 100.0",
            "bottom: 0.0",
            "height: 50.0",
            "",
            "Ball Data",
            "  index        id            x            y         rad      color",
            " 1  101  10.0  20.0  2.5  1",
            " 2  102  30.0  40.0  3.0  2",
            " 3  103  50.0  60.0  1.5  3",
            " 4  104  15.0  25.0  2.0  1",
            " 5  105  35.0  45.0  2.8  2",
            " 6  106  55.0  65.0  3.2  3",
            " 7  107  70.0  10.0  1.8  1",
            " 8  108  80.0  30.0  2.2  2",
            " 9  109  90.0  20.0  2.6  3",
            "10  110  25.0  35.0  3.0  1",
        ]
        path = self._write_dat("all_42.dat", content)
        pd = parse_dat_file(path)

        self.assertEqual(pd.current_step, 42)
        self.assertEqual(pd.ball_num, 10)
        self.assertEqual(pd.left, 0.0)
        self.assertEqual(pd.right, 100.0)
        self.assertEqual(pd.bottom, 0.0)
        self.assertEqual(pd.height, 50.0)

    def test_parse_particle_table(self):
        """Verify basic particle data is parsed correctly."""
        content = [
            "Parameter Data",
            "current_step: 10",
            "ball_num: 4",
            "left: 0",
            "right: 200",
            "bottom: 0",
            "height: 100",
            "",
            "Ball Data",
            "  index        id            x            y         rad      color",
            "  1  201  12.5  22.5  1.0  0",
            "  2  202  34.0  56.0  2.0  1",
            "  3  203  78.0  90.0  1.5  2",
            "  4  204  10.0  10.0  3.0  3",
        ]
        path = self._write_dat("all_10.dat", content)
        pd = parse_dat_file(path)

        self.assertEqual(pd.count, 4)
        self.assertEqual(list(pd.ids), [201, 202, 203, 204])
        self.assertEqual(list(pd.indices), [1, 2, 3, 4])
        np.testing.assert_array_almost_equal(pd.xs, [12.5, 34.0, 78.0, 10.0])
        np.testing.assert_array_almost_equal(pd.ys, [22.5, 56.0, 90.0, 10.0])
        np.testing.assert_array_almost_equal(pd.rads, [1.0, 2.0, 1.5, 3.0])
        self.assertEqual(list(pd.colors), [0, 1, 2, 3])

    def test_parse_walls(self):
        """Verify wall data is parsed correctly."""
        content = [
            "Parameter Data",
            "current_step: 1",
            "ball_num: 2",
            "left: 0",
            "right: 100",
            "bottom: 0",
            "height: 100",
            "",
            "Wall Data",
            "  wall num 2",
            "  P1[0]    P1[1]    P2[0]    P2[1]",
            "  0.0      0.0      100.0    0.0",
            "  0.0      100.0    100.0    100.0",
            "",
            "Ball Data",
            "  index        id            x            y         rad      color",
            "  1  301  50.0  50.0  5.0  0",
            "  2  302  30.0  30.0  4.0  1",
        ]
        path = self._write_dat("all_1.dat", content)
        pd = parse_dat_file(path)

        self.assertIsNotNone(pd.wall_data)
        self.assertEqual(pd.wall_data.shape, (2, 4))
        np.testing.assert_array_almost_equal(
            pd.wall_data,
            [[0.0, 0.0, 100.0, 0.0], [0.0, 100.0, 100.0, 100.0]],
        )

    def test_parse_error_missing_file(self):
        """Verify graceful handling of a missing file."""
        pd = parse_dat_file("/nonexistent/path/all_0.dat")
        # Should return an empty ParticleData (not crash)
        self.assertEqual(pd.count, 0)
        self.assertEqual(pd.current_step, 0)
        self.assertEqual(pd.ball_num, 0)

    def test_parse_error_corrupt_file(self):
        """Verify graceful handling of a corrupt/non-DAT file."""
        path = self._write_dat("all_0.dat", ["this is not valid zdem data", "garbage", "123"])
        pd = parse_dat_file(path)
        # Should return empty data without crashing
        self.assertEqual(pd.count, 0)

    def test_parse_mode(self):
        """Verify parsing works with [Metadata]/[Particles] section format."""
        content = [
            "[Metadata]",
            "current_step: 55",
            "ball_num: 2",
            "",
            "[Particles]",
            "  index        id            x            y         rad      color",
            "  1  401  100.0  200.0  1.5  0",
            "  2  402  150.0  250.0  2.0  1",
        ]
        path = self._write_dat("all_55.dat", content)
        pd = parse_dat_file(path)

        self.assertEqual(pd.current_step, 55)
        self.assertEqual(pd.count, 2)
        self.assertEqual(list(pd.ids), [401, 402])

    def test_find_dat_files(self):
        """Verify find_dat_files discovers and sorts DAT files."""
        # Create several DAT files
        self._write_dat("all_1.dat", ["Ball Data", "  index id x y rad color"])
        self._write_dat("all_10.dat", ["Ball Data", "  index id x y rad color"])
        self._write_dat("all_2.dat", ["Ball Data", "  index id x y rad color"])
        self._write_dat("all_100.dat", ["Ball Data", "  index id x y rad color"])
        self._write_dat("readme.txt", ["not a dat file"])

        files = find_dat_files(str(self.dir))
        # Should find 4 files, sorted by step number
        self.assertEqual(len(files), 4)
        steps = [s for s, _ in files]
        self.assertEqual(steps, [1, 2, 10, 100])

    def test_find_dat_files_empty_dir(self):
        """Verify find_dat_files on an empty directory returns empty list."""
        empty_dir = self.dir / "empty"
        empty_dir.mkdir()
        files = find_dat_files(str(empty_dir))
        self.assertEqual(files, [])

    def test_find_dat_files_nonexistent(self):
        """Verify find_dat_files on a non-existent directory returns empty list."""
        files = find_dat_files("/nonexistent/path")
        self.assertEqual(files, [])

    def test_parse_with_metadata_header(self):
        """Verify parsing works with [Metadata] header and key=value format."""
        content = [
            "[Metadata]",
            "  current_step: 99",
            "  ball_num: 3",
            "  left: 0.0    right: 50.0",
            "  bottom: 0.0  height: 25.0",
            "",
            "Ball Data",
            "  index        id            x            y         rad      color",
            "  1  501  25.0  12.5  1.0  5",
            "  2  502  30.0  15.0  1.5  6",
            "  3  503  35.0  18.0  2.0  7",
        ]
        path = self._write_dat("all_99.dat", content)
        pd = parse_dat_file(path)

        self.assertEqual(pd.current_step, 99)
        self.assertEqual(pd.count, 3)
        self.assertEqual(list(pd.colors), [5, 6, 7])

    def test_parse_empty_particle_section(self):
        """Verify parsing when ball section exists but has no particles."""
        content = [
            "current_step: 0",
            "ball_num: 0",
            "left: 0  right: 10",
            "bottom: 0  height: 10",
            "",
            "Ball Data",
        ]
        path = self._write_dat("all_0.dat", content)
        pd = parse_dat_file(path)
        self.assertEqual(pd.count, 0)
        self.assertEqual(pd.current_step, 0)


if __name__ == "__main__":
    unittest.main()
