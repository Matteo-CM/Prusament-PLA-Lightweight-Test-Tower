"""Tests for the pure parts of tools/check_gcode.py (python3 -I tests/gcode_test.py). No slicer needed."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import check_gcode as cg

SAMPLE = """M104 S230 ; start
M142 S36 ; set heatbreak target temp
M572 S0.036
G1 E-2 F2400 ; retraction in the start G-code must not count
;LAYER_CHANGE
;Z:0.2
M106 S76
G1 E-.7 F2700
G1 X10 Y10 F21000
G1 E.7 F1500
;TYPE:External perimeter
G1 F3000
G1 X20 Y10 E.5
G1 X30 Y10 E.5
;TYPE:Internal infill
G1 F3600
G1 X40 Y10 E.5
M106 S255
G1 E-0.7 F2700
G1 X50 Y10 F21000
M221 S100
M104 S235
M572 S0 ; reset PA
; estimated printing time (normal mode) = 25m 54s
; total filament used [g] = 2.79
"""

class Analyse(unittest.TestCase):
    def setUp(self):
        self.r = cg.analyse(SAMPLE)

    def test_retractions_in_both_number_formats_and_start_gcode_ignored(self):
        self.assertEqual(self.r["retractions"], 2)               # "E-.7" and "E-0.7"; the start-G-code one is excluded
        self.assertEqual(self.r["retraction_mm"], [0.7])

    def test_temperatures_fan_flow_pressure_advance_heatbreak(self):
        self.assertEqual(self.r["temperatures"], [230, 235])
        self.assertEqual(dict(self.r["fan_values"]), {76: 1, 255: 1})
        self.assertEqual(self.r["flow"], [100])
        self.assertEqual(self.r["pressure_advance"], [0.036])    # the "S0" reset is not a value
        self.assertEqual(self.r["heatbreak"], ["M142 S36 ; set heatbreak target temp"])

    def test_speed_is_taken_from_the_separate_F_line(self):
        self.assertEqual(self.r["speeds"]["External perimeter"], (50, 50, 50))
        self.assertEqual(self.r["speeds"]["Internal infill"], (60, 60, 60))

    def test_time_and_filament(self):
        self.assertEqual(self.r["time"], "25m 54s")
        self.assertEqual(self.r["filament_g"], "2.79")

    def test_no_retraction_gcode(self):
        self.assertEqual(cg.analyse(";LAYER_CHANGE\nG1 X1 Y1 E.1 F3000\n")["retractions"], 0)

class Model(unittest.TestCase):
    def test_test_model_is_two_separate_cubes(self):
        stl = cg.two_cubes_stl()
        self.assertEqual(stl.count("facet normal"), 24)           # 2 cubes x 12 triangles
        self.assertTrue(stl.startswith("solid") and stl.rstrip().endswith("endsolid cubes"))

if __name__ == "__main__":
    unittest.main(verbosity=2)
