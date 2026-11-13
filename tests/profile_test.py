"""Tests for tools/make_profile.py (python3 -I tests/profile_test.py). PyYAML is optional."""
import os, sys, tempfile, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import make_profile as mp
try:
    import yaml
except ImportError:
    yaml = None


def gen(*argv):
    args = _parse(list(argv))
    return mp.make_preset(args)


def _parse(argv):
    import argparse
    # reuse main()'s parser by calling it with --print and capturing the namespace
    captured = {}
    orig = mp.make_preset
    def spy(a):
        captured["a"] = a
        return orig(a)
    mp.make_preset = spy
    try:
        with open(os.devnull, "w") as dn:
            old = sys.stdout; sys.stdout = dn
            try:
                mp.main(argv + ["--print"])
            finally:
                sys.stdout = old
    finally:
        mp.make_preset = orig
    return captured["a"]


@unittest.skipIf(yaml is None, "PyYAML not installed")
class ProfileYaml(unittest.TestCase):
    def setUp(self):
        self.name, self.text, self.values = gen("--temp", "240", "--em", "0.37")
        self.doc = yaml.safe_load(self.text)
        self.v = self.doc["variants"][0]

    def test_structure_matches_what_the_slicer_saves(self):
        self.assertEqual(self.doc["kind"], "filament")
        self.assertEqual(sorted(self.doc), ["id", "kind", "variants"])
        self.assertEqual(sorted(self.v), ["condition", "features", "id", "name", "unconditional_inherits", "values"])
        self.assertEqual(self.v["unconditional_inherits"], ["Prusament PLA"])
        self.assertEqual(self.v["features"]["$.type"], "PLA")

    def test_key_values(self):
        val = self.v["values"]
        self.assertEqual(val["temperature"], 240)
        self.assertEqual(val["first_layer_temperature"], 240)
        self.assertAlmostEqual(val["extrusion_multiplier"], 0.37)
        self.assertEqual((val["min_fan_speed"], val["max_fan_speed"], val["bridge_fan_speed"]), (30, 30, 100))
        self.assertEqual(val["retract_length"], 0)
        self.assertEqual(val["slowdown_below_layer_time"], 0)
        self.assertEqual(val["enable_dynamic_fan_speeds"], 0)
        self.assertEqual(val["retract_before_wipe"], "0%")
        self.assertEqual(val["bed_temperature"], 60)

    def test_name_and_condition(self):
        self.assertEqual(self.v["name"], "Prusament PLA Lightweight 240C EM0.37")
        self.assertIn("printer.base_model=~/(COREONE|", self.v["condition"])
        self.assertIn("! print.high_temp_printhead", self.v["condition"])

    def test_ids_are_stable_and_distinct(self):
        _, text2, _ = gen("--temp", "240", "--em", "0.37")
        self.assertEqual(self.text, text2)
        self.assertNotEqual(self.doc["id"], self.v["id"])
        _, text3, _ = gen("--temp", "235", "--em", "0.38")
        self.assertNotEqual(yaml.safe_load(text3)["id"], self.doc["id"])

    def test_nozzle_and_flow_condition(self):
        _, t, _ = gen("--temp", "235", "--em", "0.38", "--nozzle", "0.4", "--high-flow")
        c = yaml.safe_load(t)["variants"][0]["condition"]
        self.assertIn("tool.nozzle_diameter == 0.4", c)
        self.assertIn("tool.nozzle_high_flow", c)
        _, t, _ = gen("--temp", "235", "--em", "0.38", "--standard-flow")
        self.assertIn("not tool.nozzle_high_flow", yaml.safe_load(t)["variants"][0]["condition"])

    def test_custom_name_sanitised_and_quoted_notes(self):
        name, t, _ = gen("--temp", "230", "--em", "0.45", "--name", "My LW: PLA/test 230!")
        self.assertEqual(name, "My LW PLAtest 230")
        d = yaml.safe_load(t)["variants"][0]
        self.assertIn("230 C", d["values"]["filament_notes"])

    def test_same_keys_as_the_users_own_saved_preset(self):
        """The preset the slicer itself saved has these value keys; ours must be a superset of the
        keys a UI-saved LW preset touches (EM, first layer temperature, fans)."""
        for k in ("extrusion_multiplier", "first_layer_temperature", "max_fan_speed", "min_fan_speed"):
            self.assertIn(k, self.v["values"])


@unittest.skipIf(yaml is None, "PyYAML not installed")
class Baking(unittest.TestCase):
    """--stock-json copies the printer-specific keys a child preset would otherwise lose.
    The fixture is a real resolved config of 'Prusament PLA @COREONE HF0.4' from PrusaSlicer 3 alpha."""
    FIX = os.path.join(HERE, "fixtures", "stock_coreone_hf04_prusament_pla.json")

    def test_heatbreak_gcode_and_hf_limit_survive(self):
        _, t, _ = gen("--temp", "240", "--em", "0.37", "--stock-json", self.FIX, "--printers", "COREONE", "--nozzle", "0.4", "--high-flow")
        v = yaml.safe_load(t)["variants"][0]["values"]
        self.assertEqual(v["start_filament_gcode"], "M142 S36 ; set heatbreak target temp")
        self.assertEqual(v["filament_max_volumetric_speed"], 24)
        self.assertEqual(v["min_print_speed"], 20)
        self.assertEqual(v["filament_purge_multiplier"], "81.25%")
        self.assertEqual(v["filament_infill_max_crossing_speed"], 200)
        self.assertEqual(v["pressure_advance"], "enabled")

    def test_tower_values_are_never_overridden_by_stock(self):
        _, t, _ = gen("--temp", "240", "--em", "0.37", "--stock-json", self.FIX)
        v = yaml.safe_load(t)["variants"][0]["values"]
        self.assertEqual((v["temperature"], v["min_fan_speed"], v["max_fan_speed"]), (240, 30, 30))
        self.assertAlmostEqual(v["extrusion_multiplier"], 0.37)
        self.assertNotIn("temperature", [k for k in mp.BAKE_KEYS])

    def test_without_stock_json_nothing_is_baked(self):
        _, t, _ = gen("--temp", "240", "--em", "0.37")
        self.assertNotIn("start_filament_gcode", yaml.safe_load(t)["variants"][0]["values"])

    def test_bake_value_conversions(self):
        self.assertEqual(mp.bake_value([{"value": 81.25, "is_percent": True}]), "81.25%")
        self.assertEqual(mp.bake_value([True]), 1)
        self.assertEqual(mp.bake_value([24.0]), 24.0)
        self.assertIsNone(mp.bake_value([]))
        self.assertIsNone(mp.bake_value(None))


class Validation(unittest.TestCase):
    def test_rejects_unsafe_or_silly_values(self):
        for argv in (["--temp", "260", "--em", "0.4"], ["--temp", "240", "--em", "2"], ["--temp", "240", "--em", "0.05"],
                     ["--temp", "240", "--em", "0.4", "--fan", "150"], ["--temp", "100", "--em", "0.4"]):
            with self.assertRaises(ValueError, msg=argv):
                gen(*argv)

    def test_cli_exit_codes_and_files(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(mp.main(["--temp", "240", "--em", "0.37", "--out", d]), 0)
            self.assertTrue(os.path.exists(os.path.join(d, "filament-Prusament PLA Lightweight 240C EM0.37.yaml")))
            self.assertEqual(mp.main(["--temp", "999", "--em", "0.37", "--out", d]), 2)
            self.assertEqual(mp.main(["--temp", "240", "--em", "0.37", "--out", d, "--install", "--datadir", d + "/nope"]), 3)

    def test_install_writes_into_user_preset_folder(self):
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "presets", "user", "prusa-research-fff", "PrusaResearch")
            os.makedirs(dest)
            self.assertEqual(mp.main(["--temp", "240", "--em", "0.37", "--out", os.path.join(d, "o"), "--install", "--datadir", d]), 0)
            self.assertEqual(len(os.listdir(dest)), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
