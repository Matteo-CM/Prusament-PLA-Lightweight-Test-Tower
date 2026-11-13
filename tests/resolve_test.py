"""Tests for the pure parts of tools/resolve_stock.py (python3 -I tests/resolve_test.py). No slicer needed."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import resolve_stock as rs

class Diff(unittest.TestCase):
    def test_diff_lists_changed_added_and_removed_keys(self):
        a = {"temperature": [230], "min_fan_speed": [85], "gone": [1]}
        b = {"temperature": [240], "min_fan_speed": [85], "new": [0]}
        self.assertEqual(rs.diff_settings(a, b), [("gone", [1], None), ("new", None, [0]), ("temperature", [230], [240])])

    def test_identical_is_empty(self):
        self.assertEqual(rs.diff_settings({"a": [1]}, {"a": [1]}), [])

class Discovery(unittest.TestCase):
    def test_explicit_datadir_must_exist(self):
        self.assertIsNone(rs.find_datadir("/definitely/not/here"))
        self.assertEqual(rs.find_datadir(os.path.dirname(__file__)), os.path.dirname(__file__))

    def test_explicit_slicer_command_is_split(self):
        self.assertEqual(rs.find_slicer("flatpak run com.prusa3d.PrusaSlicer"), ["flatpak", "run", "com.prusa3d.PrusaSlicer"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
