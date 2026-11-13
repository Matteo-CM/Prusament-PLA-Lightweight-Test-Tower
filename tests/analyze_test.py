"""Tests for tools/analyze_results.py and tools/lwcurve.py (python3 -I tests/analyze_test.py)."""
import contextlib, io, os, re, sys, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import analyze_results as ar
import lwcurve as lw
import make_profile as mp


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = ar.main(argv)
    return code, out.getvalue(), err.getvalue()


class Constants(unittest.TestCase):
    def test_fallbacks_equal_the_plugin_source(self):
        """lwcurve has hard-coded fallbacks; they must equal what the plugin says."""
        src = open(os.path.join(HERE, "..", "com.community.pla-lw-temp-test", "pla_lw_temp_test.lua"), encoding="utf-8").read()
        grab = lambda name: int(re.search(r"local %s = (\d+)" % name, src).group(1))
        self.assertEqual((lw.MIN_TEMP, lw.MAX_SAFE_TEMP, lw.TEMP_OK_MIN, lw.TEMP_OK_MAX, lw.WIDE_MIN, lw.WIDE_MAX),
                         (grab("MIN_TEMP"), grab("MAX_SAFE_TEMP"), grab("TEMP_OK_MIN"), grab("TEMP_OK_MAX"), grab("WIDE_MIN"), grab("WIDE_MAX")))
        self.assertEqual((lw.MIN_TEMP, lw.TEMP_OK_MIN, lw.TEMP_OK_MAX, lw.MAX_SAFE_TEMP), (190, 210, 240, 250))
        self.assertEqual(lw.CURVE, [(215, 1.0), (230, 0.45), (235, 0.38)])

    def test_curve_and_zones(self):
        self.assertAlmostEqual(lw.em_at(215), 1.0)
        self.assertAlmostEqual(lw.em_at(230), 0.45)
        self.assertAlmostEqual(lw.em_at(235), 0.38)
        self.assertAlmostEqual(lw.em_at(250), 0.35)
        self.assertAlmostEqual(lw.em_at(205), 1.0)
        self.assertEqual([lw.zone_of(t) for t in (209, 210, 240, 241)], ["cold", "ok", "ok", "hot"])


class Analyse(unittest.TestCase):
    def test_formula_matches_the_readme_example(self):
        # README: the 215 C band (EM 1.00) measures 0.55 mm -> 1.00 * 0.48 / 0.55 = 0.87
        row = ar.analyse({215: 0.55})[0]
        self.assertAlmostEqual(row["em_used"], 1.0)
        self.assertAlmostEqual(row["em_needed"], 0.8727, places=3)

    def test_two_perimeters_use_the_larger_target(self):
        row = ar.analyse({230: 0.90}, perimeters=2)[0]
        self.assertAlmostEqual(row["em_needed"], 0.45, places=3)
        self.assertTrue(row["on_target"])

    def test_wall_on_target_leaves_the_multiplier_unchanged(self):
        row = ar.analyse({230: 0.48})[0]
        self.assertAlmostEqual(row["em_needed"], row["em_used"], places=3)
        self.assertTrue(row["on_target"])

    def test_zone_flags(self):
        rows = {r["temp"]: r for r in ar.analyse({205: 0.5, 230: 0.5, 245: 0.5})}
        self.assertTrue(any("too cold" in n for n in rows[205]["notes"]))
        self.assertEqual(rows[230]["notes"], [])
        self.assertTrue(any("too hot" in n for n in rows[245]["notes"]))

    def test_measurement_sanity_and_monotonic_warnings(self):
        self.assertTrue(any("measurement error" in n for n in ar.analyse({230: 3.0})[0]["notes"]))
        rows = ar.analyse({220: 0.60, 230: 0.30})          # hotter band suddenly needs far more flow
        self.assertTrue(any("MORE flow" in n or "measurement error" in n for r in rows for n in r["notes"]))
        rows = ar.analyse({220: 0.60, 230: 0.25})          # 230 would need MORE flow than 220: inconsistent
        self.assertTrue(any("MORE flow" in n for n in rows[1]["notes"]))
        rows = ar.analyse({220: 0.55, 230: 0.50})          # consistent
        self.assertFalse(any("MORE flow" in n for r in rows for n in r["notes"]))


class Cli(unittest.TestCase):
    def test_table_and_pick_prompt(self):
        code, out, _ = run(["215=0.55", "225=0.50", "235=0.46", "--pick", "225"])
        self.assertEqual(code, 0)
        self.assertIn("225 C", out)
        self.assertRegex(out, r"Make me a Lightweight PLA filament profile for PrusaSlicer 3 with the 225 degrees / 0\.\d\d combo")
        self.assertIn("--temp 225 --em", out)

    def test_above_250_is_refused(self):
        code, _, err = run(["260=0.5"])
        self.assertEqual(code, 2)
        self.assertIn("toxic fumes", err)

    def test_picking_an_unusable_band_is_refused(self):
        code, _, err = run(["205=0.5", "230=0.5", "--pick", "205"])
        self.assertEqual(code, 2)
        self.assertIn("outside the usable range", err)
        code, _, err = run(["230=0.5", "--pick", "999"])
        self.assertEqual(code, 2)

    def test_bad_input_is_rejected(self):
        for bad in (["abc"], ["230=-1"], ["230=x"]):
            with self.assertRaises(SystemExit):
                with contextlib.redirect_stderr(io.StringIO()):
                    ar.main(bad)


class GeneratorRange(unittest.TestCase):
    def test_out_of_range_temperatures_warn_but_still_work(self):
        for temp, word in ((205, "too cold"), (245, "too hot")):
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                code = mp.main(["--temp", str(temp), "--em", "0.4", "--print"])
            self.assertEqual(code, 0)
            self.assertIn(word, err.getvalue())
            self.assertIn("WARNING", err.getvalue())

    def test_in_range_is_silent_and_250_plus_is_refused(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(mp.main(["--temp", "230", "--em", "0.45", "--print"]), 0)
        self.assertNotIn("WARNING", err.getvalue())
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(mp.main(["--temp", "251", "--em", "0.35", "--print"]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
