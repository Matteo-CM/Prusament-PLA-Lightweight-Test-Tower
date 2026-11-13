"""Tests for tools/official_lw.py using a small SYNTHETIC bundle (python3 -I tests/official_test.py). No network."""
import contextlib, io, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import official_lw as ol

INI = """# synthetic bundle shaped like Prusa's, with made-up numbers
[filament:*common*]
temperature = 200
min_fan_speed = 100
cooling = 1
extrusion_multiplier = 1

[filament:*LW*]
inherits = *common*
extrusion_multiplier = 0.5
cooling = 0
filament_max_volumetric_speed = 4

[filament:*FASTFAN*]
min_fan_speed = 85

[filament:Prusament PLA Lightweight @TESTPRINTER]
inherits = *LW*; *FASTFAN*
min_fan_speed = 30
temperature = 230
filament_retract_lift = 0
start_filament_gcode = "M572 S0 ; Pressure advance\\n\\nM142 S36"

[filament:Prusament PLA Lightweight @OTHER]
inherits = *LW*
"""

class Resolve(unittest.TestCase):
    def setUp(self):
        self.secs = ol.parse_ini(INI)

    def test_inheritance_order_later_parents_and_own_keys_win(self):
        v = ol.resolve(self.secs, "Prusament PLA Lightweight @TESTPRINTER")
        self.assertEqual(v["extrusion_multiplier"], "0.5")      # from *LW*, overriding *common*
        self.assertEqual(v["cooling"], "0")
        self.assertEqual(v["temperature"], "230")               # own key beats parent (200)
        self.assertEqual(v["min_fan_speed"], "30")              # own key beats *FASTFAN* (85) and *common* (100)
        self.assertNotIn("inherits", v)

    def test_later_parent_overrides_earlier_one(self):
        secs = ol.parse_ini("[filament:a]\nx = 1\n[filament:b]\nx = 2\n[filament:c]\ninherits = a; b\n")
        self.assertEqual(ol.resolve(secs, "c")["x"], "2")

    def test_cycle_and_missing_parent_are_reported(self):
        with self.assertRaises(RuntimeError):
            ol.resolve(ol.parse_ini("[filament:a]\ninherits = b\n[filament:b]\ninherits = a\n"), "a")
        with self.assertRaises(KeyError):
            ol.resolve(ol.parse_ini("[filament:a]\ninherits = missing\n"), "a")

    def test_variants_and_pressure_advance(self):
        self.assertEqual(ol.variants(self.secs), ["@OTHER".lstrip("@"), "TESTPRINTER"])
        v = ol.resolve(self.secs, "Prusament PLA Lightweight @TESTPRINTER")
        self.assertEqual(ol.pressure_advance_of(v), "0")

    def test_latest_version_is_numeric_not_alphabetic(self):
        self.assertEqual(ol.latest_version("2.5.9 a\n2.5.16 b\n2.5.10 c\n# x\n"), "2.5.16")
        with self.assertRaises(ValueError):
            ol.latest_version("nothing here")

class Compare(unittest.TestCase):
    def test_compare_flags_differences_and_unset_values(self):
        secs = ol.parse_ini(INI)
        off = ol.resolve(secs, "Prusament PLA Lightweight @TESTPRINTER")
        ours = {"temperature": "230", "min_fan_speed": "45", "cooling": "0", "retract_lift": "0", "pressure_advance_value": "0",
                "retract_length": "0"}
        rows = {r[0]: r for r in ol.compare(off, ours)}
        self.assertEqual(rows["temperature"][3], "same")
        self.assertEqual(rows["min_fan_speed"][3], "differs")
        self.assertEqual(rows["cooling"][3], "same")
        self.assertEqual(rows["retract_lift"][3], "same")             # maps to filament_retract_lift
        self.assertEqual(rows["pressure advance (M572 S)"][3], "same")
        self.assertEqual(rows["extrusion_multiplier"][3], "not set by us")
        self.assertEqual(rows["retract_length"][3], "differs")        # official does not override it

    def test_reads_values_from_a_generated_preset(self):
        yaml_text = "kind: filament\nvariants:\n  - condition: x\n    values:\n      temperature: 230\n      cooling: 0\n      retract_before_wipe: '0%'\n    features:\n      a: b\n"
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as fh:
            fh.write(yaml_text)
        try:
            self.assertEqual(ol.read_yaml_values(fh.name), {"temperature": "230", "cooling": "0", "retract_before_wipe": "0%"})
        finally:
            os.unlink(fh.name)

class Cli(unittest.TestCase):
    def run_cli(self, argv):
        with tempfile.NamedTemporaryFile("w", suffix=".ini", delete=False) as fh:
            fh.write(INI)
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                code = ol.main(["--file", fh.name] + argv)
        finally:
            os.unlink(fh.name)
        return code, out.getvalue()

    def test_list_and_variant(self):
        code, out = self.run_cli(["--list"])
        self.assertEqual(code, 0)
        self.assertIn("TESTPRINTER", out)
        code, out = self.run_cli(["--variant", "testprinter"])
        self.assertEqual(code, 0)
        self.assertIn("M572 S0", out)
        self.assertEqual(self.run_cli(["--variant", "nope"])[0], 2)

if __name__ == "__main__":
    unittest.main(verbosity=2)
